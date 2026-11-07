"""
Proveedor de pruebas, con dos modos que comparten rutas y estadísticas para que T01-T05 corran
igual en los dos:

- Simulado (por defecto): responde rápido y reporta tokens estimados (caracteres / 4). Sirve
  para comparar unsecure contra secure sin gastar ni depender de una GPU, no como costo real.
- Medición (con DESTINO_URL): reenvía la llamada al modelo real y cuenta los tokens que ese
  modelo reporta en `usage`. Unsecure y secure pasan los dos por aquí, así se miden igual.

En medición hay dos frenos para no abusar del proveedor durante un ataque simulado:
- Si el proveedor responde 429 con un tiempo de espera, no se le vuelve a llamar hasta que pase:
  se responde el mismo 429 desde aquí. Para la aplicación es igual; para él son menos golpes.
- MEDICION_TOPE_TOKENS corta la medición, por si la llave llegara a tener facturación activa.

Tiene dos rutas (/primary y /secondary) para poder probar el failover de LiteLLM.
"""

import asyncio
import os
import re
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

CAPACIDAD = int(os.getenv("MOCK_MAX_CONCURRENCY", "8"))
LATENCIA = float(os.getenv("MOCK_LATENCY_SECONDS", "0.25"))
DESTINO_URL = os.getenv("DESTINO_URL", "").rstrip("/")
DESTINO_KEY = os.getenv("DESTINO_KEY", "")
DESTINO_MODELO = os.getenv("DESTINO_MODELO", "")
TOPE_TOKENS = int(os.getenv("MEDICION_TOPE_TOKENS", "0"))

app = FastAPI(title="mock-llm")
capacidad = asyncio.Semaphore(CAPACIDAD)
http = httpx.AsyncClient(timeout=float(os.getenv("DESTINO_TIMEOUT", "120")))
estado = {"principal_caido": False, "espera_hasta": 0.0}
stats = {
    "principal": 0, "respaldo": 0, "tokens_entrada": 0, "tokens_salida": 0, "intentos": 0, "en_curso": 0,
    "rechazos_proveedor": 0, "rechazos_minuto": 0, "rechazos_dia": 0, "rechazos_tope": 0, "errores_red": 0,
    "truncadas": 0, "vacias": 0, "segundos_modelo": 0.0,
}
# no se reinicia entre pruebas: es lo que protege el gasto de toda la medición
acumulado = {"tokens_acumulados": 0, "llamadas_acumuladas": 0, "golpes_al_proveedor": 0, "cuota_dia_agotada": False}


def tokens(texto: str) -> int:
    return max(1, len(texto) // 4)


def error(mensaje: str, status: int, espera: int | None = None) -> JSONResponse:
    return JSONResponse({"error": {"message": mensaje}}, status_code=status, headers={"Retry-After": str(espera)} if espera else None)


def registrar(ruta: str, entrada: int, salida: int, fin: str | None, texto: str | None, segundos: float) -> None:
    stats[ruta] += 1
    stats["tokens_entrada"] += entrada
    stats["tokens_salida"] += salida
    stats["segundos_modelo"] = round(stats["segundos_modelo"] + segundos, 3)
    stats["truncadas"] += fin == "length"
    stats["vacias"] += not texto
    acumulado["tokens_acumulados"] += entrada + salida
    acumulado["llamadas_acumuladas"] += 1


async def simular(body: dict, ruta: str) -> dict:
    inicio = time.time()
    texto_entrada = "\n".join(str(m.get("content", "")) for m in body.get("messages", []))
    entrada = tokens(texto_entrada)
    # sin tope de salida, una pregunta grande produce una respuesta grande
    salida = min(int(body.get("max_tokens") or 4096), max(40, entrada // 3))
    async with capacidad:
        await asyncio.sleep(LATENCIA)
    texto = f"[Respuesta simulada por mock-llm, ruta {ruta}] Revisé los documentos del curso que me pasaron."
    registrar(ruta, entrada, salida, "stop", texto, time.time() - inicio)
    return {
        "id": f"mock-{time.time_ns()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "mock"),
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": texto}}],
        "usage": {"prompt_tokens": entrada, "completion_tokens": salida, "total_tokens": entrada + salida},
    }


def segundos_de_espera(texto: str) -> int:
    hallado = re.search(r'"retryDelay":\s*"(\d+)', texto) or re.search(r"retry in (\d+)", texto)
    return int(hallado.group(1)) + 1 if hallado else 5


async def reenviar(body: dict, ruta: str):
    ahora = time.time()
    if TOPE_TOKENS and acumulado["tokens_acumulados"] >= TOPE_TOKENS:
        stats["rechazos_tope"] += 1
        return error("Se alcanzó el tope de tokens de esta medición", 429, 3600)
    if ahora < estado["espera_hasta"]:
        stats["rechazos_proveedor"] += 1
        return error("El proveedor pidió esperar (respuesta local del medidor)", 429, int(estado["espera_hasta"] - ahora) + 1)

    cabeceras = {"Authorization": f"Bearer {DESTINO_KEY}"} if DESTINO_KEY else {}
    acumulado["golpes_al_proveedor"] += 1
    try:
        r = await http.post(f"{DESTINO_URL}/chat/completions", json={**body, "model": DESTINO_MODELO}, headers=cabeceras)
    except httpx.HTTPError as e:
        stats["errores_red"] += 1
        return error(f"No se pudo llamar al proveedor: {type(e).__name__}", 502)

    if r.status_code == 429:
        espera = segundos_de_espera(r.text)
        estado["espera_hasta"] = time.time() + espera
        stats["rechazos_proveedor"] += 1
        if "PerDay" in r.text:
            stats["rechazos_dia"] += 1
            acumulado["cuota_dia_agotada"] = True
        else:
            stats["rechazos_minuto"] += 1
        return error("El proveedor limitó la llamada", 429, espera)
    if r.status_code != 200:
        stats["errores_red"] += 1
        return error(f"El proveedor respondió {r.status_code}", r.status_code)

    datos = r.json()
    uso = datos.get("usage") or {}
    opcion = (datos.get("choices") or [{}])[0]
    entrada = uso.get("prompt_tokens", 0)
    # total - entrada: si el modelo razona, esos tokens también se cobran como salida
    salida = uso.get("total_tokens", 0) - entrada
    registrar(ruta, entrada, salida, opcion.get("finish_reason"), (opcion.get("message") or {}).get("content"), time.time() - ahora)
    return datos


async def responder(request: Request, ruta: str):
    if ruta == "principal" and estado["principal_caido"]:
        return error("proveedor principal caído (simulado)", 503)
    body = await request.json()
    stats["intentos"] += 1
    stats["en_curso"] += 1
    try:
        return await (reenviar(body, ruta) if DESTINO_URL else simular(body, ruta))
    finally:
        stats["en_curso"] -= 1


@app.post("/primary/v1/chat/completions")
async def principal(request: Request):
    return await responder(request, "principal")


@app.post("/secondary/v1/chat/completions")
async def respaldo(request: Request):
    return await responder(request, "respaldo")


@app.get("/stats")
def ver_stats():
    return {**stats, **acumulado, "modo": "medicion" if DESTINO_URL else "simulado", "modelo": DESTINO_MODELO or "simulado"}


@app.post("/admin/reset")
def reset():
    for k in stats:
        if k != "en_curso":
            stats[k] = 0
    estado["principal_caido"] = False
    return stats


@app.post("/admin/principal/{accion}")
def cambiar_principal(accion: str):
    estado["principal_caido"] = accion == "caer"
    return estado
