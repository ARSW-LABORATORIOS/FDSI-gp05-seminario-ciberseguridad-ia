"""
Gateway de políticas: hace el trabajo de ingreso de Apigee en el ADR-001. Es el único punto
por donde entra una pregunta, y corre aparte del orquestador, así que si este se satura los
controles siguen en pie.

Se escribió a mano porque no encontramos un gateway abierto que traiga todo junto sin pagar:
LiteLLM deja la autenticación JWT para su versión enterprise, y Kong su caché semántica. El
egreso a los modelos sí lo hace LiteLLM.

Orden del flujo: sesión -> ráfagas -> tamaño -> filtro -> caché -> cuota -> llamadas por minuto
-> orquestador -> ajuste de tokens reales. Cualquier rechazo antes del orquestador cuesta cero tokens.

A diferencia del ADR, la caché va ANTES de la cuota: una respuesta en caché no gasta nada, y
medimos que ponerla después le negaba a un estudiante sin cuota respuestas que costaban cero.
"""

import logging
import os
import threading
import time

import httpx
import redis
import tiktoken
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

import identidad
from cache_semantico import CacheSemantico
from cuotas import CUOTA_GLOBAL, Cuotas
from filtros import limpiar_salida, revisar_entrada

ORQUESTADOR = os.getenv("ORQUESTADOR_URL", "http://orquestador:8000/ask")
TIMEOUT = float(os.getenv("ORQUESTADOR_TIMEOUT", "150"))
MAX_TOKENS_PREGUNTA = int(os.getenv("PROMPT_TOKEN_LIMIT", "200"))
# 5 fragmentos de ~450 caracteres + el prompt de sistema + el tope de salida del orquestador
RESERVA_POR_PREGUNTA = int(os.getenv("TOKEN_RESERVE_PER_QUESTION", "1300"))
MAX_SIMULTANEAS = int(os.getenv("MAX_CONCURRENT_LLM", "4"))
ESPERA_CUPO = float(os.getenv("LLM_SLOT_WAIT_SECONDS", "8"))
FALLOS_PARA_ABRIR = int(os.getenv("CIRCUIT_FAILURES", "5"))
SEGUNDOS_ABIERTO = int(os.getenv("CIRCUIT_OPEN_SECONDS", "30"))
# precio de lista del modelo, solo para mostrar en dólares lo que se está gastando
PRECIO_ENTRADA = float(os.getenv("PRECIO_ENTRADA_USD_1M", "0"))
PRECIO_SALIDA = float(os.getenv("PRECIO_SALIDA_USD_1M", "0"))

log = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(title="Gateway de políticas FDSI-GP-05")
valkey = redis.Redis(host=os.getenv("VALKEY_HOST", "valkey"), port=6379, decode_responses=True)
cuotas = Cuotas(valkey)
cache = CacheSemantico(valkey)
contador_tokens = tiktoken.get_encoding("cl100k_base")
http = httpx.Client(timeout=TIMEOUT)
cupos_llm = threading.BoundedSemaphore(MAX_SIMULTANEAS)

PETICIONES = Counter("gateway_peticiones_total", "Preguntas por resultado", ["resultado"])
TOKENS = Counter("gateway_tokens_total", "Tokens gastados en el LLM", ["tipo"])
COSTO = Counter("gateway_costo_usd_total", "Costo estimado a precio de lista, en dólares")
GASTO_GLOBAL = Gauge("gateway_tokens_global_hoy", "Tokens gastados hoy en todo el servicio")
TOPE_GLOBAL = Gauge("gateway_tokens_global_tope", "Tope diario de tokens del servicio")
CIRCUITO = Gauge("gateway_circuito_abierto", "1 si el circuito hacia el orquestador está abierto")
SESIONES = Counter("gateway_sesiones_total", "Sesiones por resultado", ["resultado"])
LATENCIA = Histogram("gateway_latencia_segundos", "Latencia de /ask", buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120))
TOPE_GLOBAL.set(CUOTA_GLOBAL)


class Circuito:
    """Si el orquestador falla seguido, deja de insistir un rato en vez de acumular espera."""

    def __init__(self):
        self.fallos = 0
        self.abierto_hasta = 0.0
        self.lock = threading.Lock()

    def abierto(self) -> bool:
        return time.time() < self.abierto_hasta

    def registrar(self, ok: bool) -> None:
        with self.lock:
            self.fallos = 0 if ok else self.fallos + 1
            if self.fallos >= FALLOS_PARA_ABRIR:
                self.abierto_hasta = time.time() + SEGUNDOS_ABIERTO
                self.fallos = 0
                log.warning("circuito abierto por %ss", SEGUNDOS_ABIERTO)
        CIRCUITO.set(1 if self.abierto() else 0)


circuito = Circuito()


class Pregunta(BaseModel):
    message: str | None = None
    texto: str | None = None  # el formato que usa tests/ en el laboratorio


class SolicitudSesion(BaseModel):
    altcha: str = Field(default="", max_length=4096)


def ip_cliente(request: Request) -> str:
    # solo el borde llega hasta aquí (red interna) y él reescribe esta cabecera
    return request.headers.get("x-real-ip") or request.client.host


def rechazar(status: int, motivo: str, mensaje: str, reintentar_en: int | None = None) -> HTTPException:
    PETICIONES.labels(motivo).inc()
    cabeceras = {"Retry-After": str(reintentar_en)} if reintentar_en else None
    return HTTPException(status_code=status, detail={"codigo": motivo, "mensaje": mensaje}, headers=cabeceras)


# Estas rutas son `async` a propósito: corren en el bucle principal y no en el pool de hilos
# que usa /ask. Bajo ataque ese pool se llena de peticiones esperando cupo, y antes eso dejaba
# a Prometheus sin métricas y a los estudiantes sin poder abrir sesión justo durante el ataque.
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/config")
async def config():
    return {"captcha_enabled": identidad.CAPTCHA_ENABLED}


@app.get("/altcha/challenge")
async def reto():
    if not identidad.CAPTCHA_ENABLED:
        raise HTTPException(status_code=404, detail="La verificación está desactivada")
    return identidad.crear_reto()


@app.post("/session")
async def crear_sesion(body: SolicitudSesion, request: Request):
    # abrir muchas sesiones para esquivar la cuota por sesión es el riesgo residual del ADR
    if cuotas.sesiones_excedidas(ip_cliente(request)):
        SESIONES.labels("demasiadas").inc()
        raise HTTPException(status_code=429, detail={"codigo": "demasiadas_sesiones", "mensaje": "Se abrieron demasiadas sesiones desde esta conexión."})
    if identidad.CAPTCHA_ENABLED and not identidad.verificar_reto(body.altcha, valkey):
        SESIONES.labels("reto_invalido").inc()
        raise HTTPException(status_code=403, detail={"codigo": "reto_invalido", "mensaje": "La verificación no es válida o ya se usó."})
    SESIONES.labels("ok").inc()
    return identidad.crear_sesion()


@app.post("/ask")
def preguntar(body: Pregunta, request: Request, authorization: str | None = Header(default=None)):
    inicio = time.time()
    try:
        return _atender(body, ip_cliente(request), authorization)
    finally:
        LATENCIA.observe(time.time() - inicio)


def _atender(body: Pregunta, ip: str, authorization: str | None) -> dict:
    # 1. identidad: el usuario_id del body deja de existir, la llave es el sub firmado
    sub = identidad.validar_sesion(authorization)
    if sub is None:
        raise rechazar(401, "sesion_invalida", "Tu sesión no es válida o ya venció.")

    # 2. ráfagas por sesión
    if cuotas.spike(sub):
        cuotas.marcar_sospechosa(ip)
        raise rechazar(429, "rafaga", "Vas muy rápido. Espera unos segundos.", 10)

    # 3. tamaño de la pregunta
    pregunta = (body.message or body.texto or "").strip()
    if not pregunta:
        raise rechazar(400, "pregunta_vacia", "Escribe una pregunta.")
    tokens_pregunta = len(contador_tokens.encode(pregunta, disallowed_special=()))
    if tokens_pregunta > MAX_TOKENS_PREGUNTA:
        raise rechazar(400, "pregunta_larga", f"La pregunta es muy larga (máximo {MAX_TOKENS_PREGUNTA} tokens).")

    # 4. filtro de la pregunta
    motivo = revisar_entrada(pregunta)
    if motivo:
        raise rechazar(400, "filtro", f"No puedo procesar esa pregunta: {motivo}.")

    # 5. caché semántica
    guardada, vector = cache.buscar(pregunta)
    if guardada is not None:
        PETICIONES.labels("cache").inc()
        return {**guardada, "de_cache": True, "tokens_total": 0, "tokens_entrada": 0, "tokens_salida": 0}

    # 6. cuota: reserva el estimado por sesión, IP y global
    reserva, tope = cuotas.reservar(sub, ip, tokens_pregunta + RESERVA_POR_PREGUNTA)
    if reserva is None:
        mensaje = "El servicio está en modo de ahorro y esta conexión ya usó su parte de hoy." if tope == "modo_ahorro" else "Se acabó la cuota de tokens disponible por hoy."
        raise rechazar(429, tope, mensaje, 3600)

    tokens_reales = 0
    try:
        # 7. llamadas por minuto: no mandarle al proveedor más de lo que acepta. Va después de la
        # cuota para que alguien sin cuota no le quite el cupo a quien sí la tiene
        exceso = cuotas.llamadas_excedidas(ip)
        if exceso == "rpm_ip":
            raise rechazar(429, exceso, "Esta conexión ya hizo muchas preguntas este minuto. Espera un momento.", 15)
        if exceso:
            raise rechazar(503, exceso, "El asistente está ocupado. Intenta en un momento.", 15)

        # 8-10. orquestador, con cupos y circuito para no acumular espera si se atasca
        resultado = _llamar_orquestador(pregunta)
        tokens_reales = resultado.get("tokens_total", 0)
        entrada, salida = resultado.get("tokens_entrada", 0), resultado.get("tokens_salida", 0)
        TOKENS.labels("entrada").inc(entrada)
        TOKENS.labels("salida").inc(salida)
        COSTO.inc((entrada * PRECIO_ENTRADA + salida * PRECIO_SALIDA) / 1_000_000)

        resultado["answer"] = limpiar_salida(resultado.get("answer", ""))
        # una respuesta cortada o vacía no se guarda: se le repetiría a todos durante un día
        if resultado.get("fuentes") and resultado.get("fin") == "stop":
            cache.guardar(pregunta, vector, resultado)
        PETICIONES.labels("ok").inc()
        return {**resultado, "de_cache": False}
    except HTTPException as e:
        # si se agotó el tiempo el proveedor pudo haber cobrado igual: la reserva no se devuelve
        if isinstance(e.detail, dict) and e.detail.get("codigo") == "tiempo_agotado":
            tokens_reales = reserva.tokens
        raise
    finally:
        # 11. se descuenta lo gastado de verdad; un rechazo devuelve toda la reserva
        cuotas.ajustar(reserva, tokens_reales)
        GASTO_GLOBAL.set(cuotas.gasto_global_hoy())


def _llamar_orquestador(pregunta: str) -> dict:
    if circuito.abierto():
        raise rechazar(503, "circuito_abierto", "El asistente no está disponible. Intenta en un momento.", SEGUNDOS_ABIERTO)
    if not cupos_llm.acquire(timeout=ESPERA_CUPO):
        raise rechazar(503, "sin_cupo", "El asistente está ocupado. Intenta en un momento.", 5)
    try:
        r = http.post(ORQUESTADOR, json={"message": pregunta})
    except httpx.TimeoutException:
        circuito.registrar(False)
        raise rechazar(504, "tiempo_agotado", "El asistente tardó demasiado. Intenta de nuevo.")
    except httpx.HTTPError as e:
        circuito.registrar(False)
        log.warning("orquestador inalcanzable: %s", type(e).__name__)
        raise rechazar(502, "error_interno", "No pude obtener una respuesta. Intenta de nuevo.")
    finally:
        cupos_llm.release()
    if r.status_code == 429:
        # el proveedor limita, pero el sistema está sano: abrir el circuito cortaría a todos
        raise rechazar(503, "proveedor_ocupado", "El modelo está ocupado. Intenta en unos segundos.", 15)
    if r.status_code == 504:
        circuito.registrar(False)
        raise rechazar(504, "tiempo_agotado", "El asistente tardó demasiado. Intenta de nuevo.")
    if r.status_code != 200:
        circuito.registrar(False)
        log.warning("orquestador respondió %s: %s", r.status_code, r.text[:200])
        raise rechazar(502, "error_interno", "No pude obtener una respuesta. Intenta de nuevo.")
    circuito.registrar(True)
    return r.json()


@app.get("/metrics")
async def metricas():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
