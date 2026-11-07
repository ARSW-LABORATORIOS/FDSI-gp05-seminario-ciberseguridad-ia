"""
Corre T01-T05 contra las dos versiones y deja los resultados en /resultados. Ataca solo
servicios de este mismo Docker Compose.

Los tokens salen de las estadísticas de mock-llm, por donde pasan las dos versiones: estimados si
simula, los que reporta el modelo si está midiendo con uno real.
Cada IP de la red pública es una dirección real asignada a este contenedor, no una cabecera
falsificada, así el límite por IP del borde se comporta como en un ataque real.

    python ataques.py [--segundos 15] [--pruebas T01,T03] [--salida simulado]
"""

import argparse
import asyncio
import json
import os
import random
import statistics
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone

import altcha
import httpx
import redis

EDGE = "http://edge:8080"
UNSECURE = "http://unsecure:8000"
MOCK = "http://mock-llm:9000"
CAPTCHA = os.getenv("CAPTCHA_ENABLED", "true").lower() in ("1", "true", "si", "sí", "yes", "on")
RED = "172.30.0"
SPIKE_MAX = int(os.getenv("SPIKE_MAX_REQUESTS", "5"))
SPIKE_VENTANA = int(os.getenv("SPIKE_WINDOW_SECONDS", "10"))
PRECIO_ENTRADA = float(os.getenv("PRECIO_ENTRADA_USD_1M", "0"))
PRECIO_SALIDA = float(os.getenv("PRECIO_SALIDA_USD_1M", "0"))

MATERIAS = ["Arquitectura de Software", "Seguridad de la Información", "Matemáticas Básicas", "Historia de Colombia"]
TEMAS = ["el corte 1", "el corte 2", "el corte 3", "el parcial", "el taller", "la guía", "los apuntes", "el docente", "el salón", "la entrega"]
ESTUDIANTE = [
    "¿Quién dicta Arquitectura de Software y en qué salón?",
    "¿Qué temas entran en el corte 2 de Matemáticas Básicas?",
    "¿Qué es la triada CIA?",
    "¿Cuándo fue la batalla de Boyacá?",
    "¿Cómo se entrega el taller de diagramas C4?",
    "¿Cuántos pasos tiene la guía de análisis de riesgos?",
    "¿Qué es la regla de la cadena?",
    "¿Qué fue el Frente Nacional?",
    "¿Qué porcentaje vale el corte 3 de Historia de Colombia?",
    "¿Qué es la arquitectura hexagonal?",
]


def motivo_de(r: httpx.Response) -> str:
    """Qué capa rechazó la petición, para comprobar que cada ataque se frena donde dice el ADR."""
    try:
        detalle = r.json().get("detail")
        return detalle["codigo"] if isinstance(detalle, dict) else f"http_{r.status_code}"
    except ValueError:
        return f"http_{r.status_code}"


class CuotaDiariaAgotada(Exception):
    """El proveedor ya no responde hoy: seguir daría números falsos."""


def pregunta_variada() -> str:
    # el número al final es a propósito: la caché exige los mismos números, así que este
    # atacante la esquiva siempre y estas pruebas miden las cuotas en su peor caso
    return f"Explícame {random.choice(TEMAS)} de {random.choice(MATERIAS)}, detalle {random.randint(1, 10**6)}"


def asignar_ips(n: int) -> list[str]:
    salida = subprocess.run(["ip", "-o", "-4", "addr"], capture_output=True, text=True, check=True).stdout
    interfaz = next(l.split()[1] for l in salida.splitlines() if f" {RED}." in l)
    ips = [f"{RED}.{100 + i}" for i in range(n)]
    for ip in ips:
        subprocess.run(["ip", "addr", "add", f"{ip}/24", "dev", interfaz], capture_output=True)
    return ips


async def calentar_ips(ips: list[str]) -> None:
    """La primera conexión desde una IP secundaria tarda hasta 20 s en este Docker. Se hace
    antes de medir: si no, esa demora se confunde con latencia del sistema."""
    async def una(ip):
        for _ in range(3):
            try:
                async with cliente(ip) as c:
                    await c.get(f"{EDGE}/healthz", timeout=40)
                    await c.get(f"{UNSECURE}/health", timeout=40)
                return True
            except httpx.HTTPError:
                continue
        return False
    listas = await asyncio.gather(*(una(ip) for ip in ips))
    print(f"IP listas: {sum(listas)}/{len(ips)}", flush=True)


def cliente(ip: str) -> httpx.AsyncClient:
    limites = httpx.Limits(max_connections=50, max_keepalive_connections=20)
    return httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(local_address=ip, limits=limites), timeout=60)


async def drenar_y_reiniciar():
    # las peticiones del ataque anterior siguen en cola en el servidor aunque el cliente ya
    # terminó: si no se esperan, sus tokens se contarían en la prueba siguiente
    anterior = -1
    for _ in range(200):  # con un modelo local la cola puede tardar minutos en vaciarse
        estado = llm()
        if estado["en_curso"] == 0 and estado["intentos"] == anterior:
            break
        anterior = estado["intentos"]
        await asyncio.sleep(3)
    if llm()["cuota_dia_agotada"]:
        raise CuotaDiariaAgotada()
    # con un proveedor real, su cupo por minuto no se reinicia con nosotros: sin esta pausa la
    # versión que corre después arranca con el cupo que dejó agotado la anterior
    await asyncio.sleep(PARAMS["pausa"])
    reiniciar()


def reiniciar():
    redis.Redis(host="valkey").flushall()
    httpx.post(f"{MOCK}/admin/reset", timeout=10)


def llm() -> dict:
    s = httpx.get(f"{MOCK}/stats", timeout=10).json()
    return {
        "llamadas_llm": s["principal"] + s["respaldo"],
        "tokens": s["tokens_entrada"] + s["tokens_salida"],
        "tokens_entrada": s["tokens_entrada"],
        "tokens_salida": s["tokens_salida"],
        "usd": round((s["tokens_entrada"] * PRECIO_ENTRADA + s["tokens_salida"] * PRECIO_SALIDA) / 1_000_000, 6),
        "intentos": s["intentos"],
        "en_curso": s["en_curso"],
        "rechazos_proveedor": s["rechazos_proveedor"],
        "errores_proveedor": s["errores_red"],
        "truncadas": s["truncadas"],
        "vacias": s["vacias"],
        "segundos_modelo": s["segundos_modelo"],
        "modelo": s["modelo"],
        "cuota_dia_agotada": s["cuota_dia_agotada"],
        "golpes_al_proveedor": s["golpes_al_proveedor"],
    }


async def abrir_sesion(c: httpx.AsyncClient) -> str | None:
    """Abre una sesión como lo haría un bot: resuelve la prueba de trabajo si está activa."""
    cuerpo = {}
    if CAPTCHA:
        r = await c.get(f"{EDGE}/altcha/challenge")
        if r.status_code != 200:
            return None
        reto = altcha.Challenge.from_dict(r.json())
        solucion = await asyncio.to_thread(altcha.solve_challenge, reto)
        cuerpo = {"altcha": altcha.Payload(challenge=reto, solution=solucion).to_base64()}
    r = await c.post(f"{EDGE}/session", json=cuerpo)
    return r.json()["token"] if r.status_code == 200 else None


class Objetivo:
    def __init__(self, nombre: str):
        self.nombre = nombre
        self.seguro = nombre == "secure"
        self.url = f"{EDGE}/ask" if self.seguro else f"{UNSECURE}/ask"


async def preguntar(objetivo: Objetivo, c: httpx.AsyncClient, texto: str, token: str | None = None) -> httpx.Response | None:
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        return await c.post(objetivo.url, json={"message": texto}, headers=cabeceras)
    except httpx.HTTPError:
        return None


def porcentaje(parte: int, total: int) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def p95(valores: list[float]) -> float:
    if not valores:
        return 0.0
    return round(statistics.quantiles(valores, n=20, method="inclusive")[18], 3) if len(valores) >= 2 else round(valores[0], 3)


async def inundar(objetivo: Objetivo, c: httpx.AsyncClient, segundos: float, hilos: int, conteo: Counter, motivos: Counter, rotar: bool = False, sesiones: list | None = None):
    """Manda preguntas distintas sin esperar. Con `rotar`, abre otra sesión cuando la frenan."""
    token = None
    if objetivo.seguro:
        for _ in range(5):  # un atacante insiste hasta tener sesión: sin ella solo recibe 401
            token = await abrir_sesion(c)
            if token:
                break
            await asyncio.sleep(1)
        if not token:
            motivos["sin_sesion"] += 1
            return
    if sesiones is not None and token:
        sesiones.append(1)
    fin = time.time() + segundos

    async def hilo():
        nonlocal token
        while time.time() < fin:
            r = await preguntar(objetivo, c, pregunta_variada(), token)
            conteo[r.status_code if r is not None else "error"] += 1
            if r is not None and r.status_code != 200:
                motivos[motivo_de(r)] += 1
            if rotar and objetivo.seguro and r is not None and r.status_code == 429 and "limite_borde" not in r.text:
                nuevo = await abrir_sesion(c)
                if nuevo:
                    token = nuevo
                    if sesiones is not None:
                        sesiones.append(1)
                else:
                    await asyncio.sleep(1)

    await asyncio.gather(*(hilo() for _ in range(hilos)))


async def t01(objetivo: Objetivo, ips: list[str], segundos: float) -> dict:
    """Flooding de un solo usuario desde una IP."""
    await drenar_y_reiniciar()
    conteo, motivos = Counter(), Counter()
    async with cliente(ips[0]) as c:
        await inundar(objetivo, c, segundos, 20, conteo, motivos)
    total = sum(conteo.values())
    return {"peticiones": total, "ok": conteo[200], "pct_429": porcentaje(conteo[429], total), "motivos": dict(motivos), **llm()}


async def t02(objetivo: Objetivo, ips: list[str], _: float) -> dict:
    """Pregunta que fuerza contexto masivo, y otra gigante para llenar el prompt. Se repite porque
    un modelo real varía mucho: la misma pregunta dio 8 tokens de salida en una corrida y 661 en otra.
    4 repeticiones caben en el límite por IP de la capa gratuita (4 por minuto)."""
    await drenar_y_reiniciar()
    gigante = "Resume cada tema del curso con todo el detalle posible. " * 150
    entradas, salidas, fragmentos, estados = [], [], [], Counter()
    async with cliente(ips[1]) as c:
        token = await abrir_sesion(c) if objetivo.seguro else None
        for i in range(PARAMS["repeticiones"]):
            if objetivo.seguro and i:
                await asyncio.sleep(SPIKE_VENTANA / SPIKE_MAX + 0.2)
            # el número hace que cada repetición llegue al modelo y no salga de la caché
            r = await preguntar(objetivo, c, f"Resume absolutamente todos los documentos del curso, uno por uno, sin dejar nada por fuera (intento {i + 1}).", token)
            estados[r.status_code if r is not None else "error"] += 1
            if r is not None and r.status_code == 200:
                datos = r.json()
                entradas.append(datos.get("tokens_entrada", 0))
                salidas.append(datos.get("tokens_salida", 0))
                fragmentos.append(datos.get("fragmentos", 0))
        tras_masiva = llm()
        if objetivo.seguro:
            await asyncio.sleep(SPIKE_VENTANA / SPIKE_MAX + 0.2)
        r2 = await preguntar(objetivo, c, gigante, token)
    totales = [e + s for e, s in zip(entradas, salidas)]
    return {
        "repeticiones": PARAMS["repeticiones"],
        "estados_masiva": dict(estados),
        "tokens_entrada_masiva": round(statistics.mean(entradas)) if entradas else None,
        "tokens_salida_masiva": round(statistics.mean(salidas)) if salidas else None,
        "tokens_salida_min_max": [min(salidas), max(salidas)] if salidas else None,
        "fragmentos": round(statistics.mean(fragmentos)) if fragmentos else None,
        "tokens_totales_masiva": round(statistics.mean(totales)) if totales else None,
        "estado_prompt_gigante": r2.status_code if r2 is not None else "error",
        "tokens_prompt_gigante": llm()["tokens"] - tras_masiva["tokens"],
        "usd": llm()["usd"],
    }


async def t03(objetivo: Objetivo, ips: list[str], _: float) -> dict:
    """La misma pregunta repetida, y luego reformulada."""
    await drenar_y_reiniciar()
    base = "¿Cuándo son los parciales de Matemáticas Básicas?"
    reformuladas = [
        "¿Cuándo es el parcial de Matemáticas Básicas?",
        "¿En qué fecha son los parciales de Matemáticas Básicas?",
        "Dime cuándo son los parciales de la materia Matemáticas Básicas",
    ]
    tiempos, repetida, parecida = [], [], []
    async with cliente(ips[2]) as c:
        token = await abrir_sesion(c) if objetivo.seguro else None
        for i, texto in enumerate([base] * 5 + reformuladas):
            if objetivo.seguro:
                await asyncio.sleep(SPIKE_VENTANA / SPIKE_MAX + 0.2)  # respeta el límite de ráfagas: esto mide la caché, no el límite
            inicio = time.time()
            r = await preguntar(objetivo, c, texto, token)
            tiempos.append(time.time() - inicio)
            hit = bool(r is not None and r.status_code == 200 and r.json().get("de_cache"))
            if 1 <= i < 5:
                repetida.append(hit)
            elif i >= 5:
                parecida.append(hit)
    return {
        "aciertos_repetida": f"{sum(repetida)}/{len(repetida)}",
        "aciertos_reformulada": f"{sum(parecida)}/{len(parecida)}",
        "latencia_primera_s": round(tiempos[0], 3),
        "latencia_repetida_s": round(statistics.mean(tiempos[1:5]), 3),
        **llm(),
    }


async def t04(objetivo: Objetivo, ips: list[str], segundos: float) -> dict:
    """Ráfaga de muchas IP, que además abren otra sesión cada vez que las frenan."""
    await drenar_y_reiniciar()
    conteo, motivos, sesiones = Counter(), Counter(), []
    clientes = [cliente(ip) for ip in ips[10:40]]
    try:
        # además del ataque, un estudiante pregunta durante toda la prueba
        ataque = asyncio.gather(*(inundar(objetivo, c, segundos, 3, conteo, motivos, rotar=True, sesiones=sesiones) for c in clientes))
        durante = await estudiantes(objetivo, [ips[5]], segundos, PARAMS["intervalo"])
        await ataque
    finally:
        await asyncio.gather(*(c.aclose() for c in clientes))
    total = sum(conteo.values())
    gasto = llm()

    # el riesgo residual del ADR: si el ataque agota el tope global, ¿qué le pasa a un estudiante?
    despues = None
    if objetivo.seguro:
        async with cliente(ips[6]) as c:  # otra IP: la de `durante` ya gastó su parte
            r = await preguntar(objetivo, c, "¿Qué es la arquitectura hexagonal?", await abrir_sesion(c))
        despues = r.status_code if r is not None else "error"
    return {"ips": len(clientes), "peticiones": total, "ok": conteo[200], "pct_429": porcentaje(conteo[429], total), "sesiones_abiertas": len(sesiones), "motivos": dict(motivos), "estudiante_despues": despues, "estudiante_durante_pct_exito": durante["pct_exito"], "estudiante_durante_preguntas": durante["preguntas"], "estudiante_durante_motivos": durante["motivos"], "estudiante_durante_p95_s": durante["p95_s"], **gasto}


async def estudiante(objetivo: Objetivo, c: httpx.AsyncClient, segundos: float, intervalo: float) -> dict:
    """Un estudiante normal. Cada pregunta lleva un número distinto para que ninguna salga de la
    caché: si no, la versión segura parece más rápida solo porque repite respuestas guardadas."""
    token = await abrir_sesion(c) if objetivo.seguro else None
    latencias, estados, motivos = [], Counter(), Counter()
    desfase = random.uniform(0, intervalo)  # para que varios estudiantes no pregunten al tiempo
    await asyncio.sleep(desfase)
    fin = time.time() + segundos - desfase
    preguntas = iter(ESTUDIANTE * 50)
    de_cache = 0
    while time.time() < fin:
        inicio = time.time()
        r = await preguntar(objetivo, c, f"{next(preguntas)} (consulta {random.randint(1, 10**6)})", token)
        estados[r.status_code if r is not None else "error"] += 1
        if r is not None and r.status_code == 200:
            latencias.append(time.time() - inicio)
            de_cache += bool(r.json().get("de_cache"))
        else:
            motivos[motivo_de(r) if r is not None else "error_red"] += 1
        await asyncio.sleep(max(0, intervalo - (time.time() - inicio)))
    return {"estados": estados, "motivos": motivos, "latencias": latencias, "de_cache": de_cache}


async def estudiantes(objetivo: Objetivo, ips: list[str], segundos: float, intervalo: float) -> dict:
    clientes = [cliente(ip) for ip in ips]
    try:
        partes = await asyncio.gather(*(estudiante(objetivo, c, segundos, intervalo) for c in clientes))
    finally:
        await asyncio.gather(*(c.aclose() for c in clientes))
    latencias = [v for p in partes for v in p["latencias"]]
    total = sum(sum(p["estados"].values()) for p in partes)
    motivos = sum((p["motivos"] for p in partes), Counter())
    return {
        "preguntas": total,
        "respondidas": len(latencias),
        "de_cache": sum(p["de_cache"] for p in partes),
        "pct_exito": porcentaje(len(latencias), total),
        "p95_s": p95(latencias),
        "mediana_s": round(statistics.median(latencias), 3) if latencias else 0.0,
        "max_s": round(max(latencias), 3) if latencias else 0.0,
        "motivos": dict(motivos),
    }


async def t05(objetivo: Objetivo, ips: list[str], segundos: float) -> dict:
    """Estudiantes solos, y luego los mismos mientras otra IP hace flooding."""
    legitimos = [ips[3]] + ips[40:40 + PARAMS["estudiantes"] - 1]
    await drenar_y_reiniciar()
    sin_ataque = await estudiantes(objetivo, legitimos, segundos, PARAMS["intervalo"])
    await drenar_y_reiniciar()
    conteo, motivos = Counter(), Counter()
    async with cliente(ips[4]) as atacante:
        tarea = asyncio.create_task(inundar(objetivo, atacante, segundos, 20, conteo, motivos))
        await asyncio.sleep(1)  # el ataque ya está en marcha cuando llegan los estudiantes
        con_ataque = await estudiantes(objetivo, legitimos, segundos - 1, PARAMS["intervalo"])
        await tarea
    base = sin_ataque["p95_s"] or 0.001
    return {
        "estudiantes": len(legitimos),
        "muestras_sin_ataque": sin_ataque["respondidas"],
        "muestras_con_ataque": con_ataque["respondidas"],
        "preguntas_con_ataque": con_ataque["preguntas"],
        "de_cache_con_ataque": con_ataque["de_cache"],
        "sin_ataque_mediana_s": sin_ataque["mediana_s"],
        "con_ataque_mediana_s": con_ataque["mediana_s"],
        "sin_ataque_p95_s": sin_ataque["p95_s"],
        "con_ataque_p95_s": con_ataque["p95_s"],
        "con_ataque_max_s": con_ataque["max_s"],
        "veces_mas_lento_p95": round(con_ataque["p95_s"] / base, 1),
        "sin_ataque_pct_exito": sin_ataque["pct_exito"],
        "motivos_sin_ataque": sin_ataque["motivos"],
        "con_ataque_pct_exito": con_ataque["pct_exito"],
        "motivos_estudiante": con_ataque["motivos"],
        "peticiones_atacante": sum(conteo.values()),
        "motivos_atacante": dict(motivos),
        **llm(),
    }


PRUEBAS = {"T01": t01, "T02": t02, "T03": t03, "T04": t04, "T05": t05}
PARAMS = {"estudiantes": 1, "intervalo": 3.0, "pausa": 0.0, "repeticiones": 4}


async def principal():
    args = argparse.ArgumentParser()
    args.add_argument("--segundos", type=float, default=15)
    args.add_argument("--segundos-t05", type=float, default=60, help="con menos, el p95 es casi el máximo de pocas muestras")
    args.add_argument("--segundos-t04", type=float, default=120, help="tiene que alcanzar para que el tope global entre en juego")
    args.add_argument("--pruebas", default="T01,T02,T03,T04,T05")
    args.add_argument("--versiones", default="unsecure,secure")
    args.add_argument("--estudiantes", type=int, default=1, help="estudiantes simultáneos en T05")
    args.add_argument("--intervalo-estudiante", type=float, default=3, help="segundos entre preguntas en T05")
    args.add_argument("--pausa", type=float, default=0, help="segundos entre pruebas para que se libere el cupo del proveedor")
    args.add_argument("--salida", default="simulado", help="nombre del archivo de resultados")
    args = args.parse_args()
    PARAMS.update(estudiantes=args.estudiantes, intervalo=args.intervalo_estudiante, pausa=args.pausa)

    ips = asignar_ips(40 + args.estudiantes)
    await calentar_ips(ips)
    resultados = {
        "fecha": datetime.now(timezone.utc).isoformat(), "modelo": llm()["modelo"], "captcha": CAPTCHA, "segundos": args.segundos,
        "segundos_t04": args.segundos_t04, "segundos_t05": args.segundos_t05, "estudiantes": args.estudiantes,
        "intervalo_estudiante": args.intervalo_estudiante, "spike": f"{SPIKE_MAX}/{SPIKE_VENTANA}s", "completa": False,
    }
    # una corrida parcial no pisa la completa
    completa = set(args.pruebas.split(",")) == set(PRUEBAS) and set(args.versiones.split(",")) == {"unsecure", "secure"}
    nombre = f"{args.salida}.json" if completa else f"{args.salida}-parcial.json"
    try:
        for prueba in args.pruebas.split(","):
            resultados[prueba] = {}
            for version in args.versiones.split(","):
                print(f"-> {prueba} contra {version}", flush=True)
                segundos = {"T04": args.segundos_t04, "T05": args.segundos_t05}.get(prueba, args.segundos)
                resultados[prueba][version] = await PRUEBAS[prueba](Objetivo(version), ips, segundos)
                print(json.dumps(resultados[prueba][version], ensure_ascii=False), flush=True)
        resultados["completa"] = completa
    except CuotaDiariaAgotada:
        print("El proveedor agotó la cuota del día: la corrida se detiene aquí.", flush=True)
        resultados["detenida_por"] = "cuota_dia_agotada"
    resultados["total_golpes_al_proveedor"] = llm()["golpes_al_proveedor"]
    reiniciar()

    os.makedirs("/resultados", exist_ok=True)
    with open(f"/resultados/{nombre}", "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"Guardado en infra/pruebas/resultados/{nombre}")


if __name__ == "__main__":
    asyncio.run(principal())
