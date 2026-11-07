"""
Mide lo que cuesta una pregunta normal con el modelo que esté conectado, y de ahí sugiere las
cuotas. También revisa que las respuestas sean correctas: una cuota bien puesta no sirve de nada
si los topes de fragmentos o de salida dañan la respuesta.

Los supuestos de uso están abajo: cámbienlos si conocen el tamaño real del curso.

    python calibrar.py --salida gemini [--intervalo 5] [--rpm-proveedor 15]
"""

import argparse
import asyncio
import json
import math
import os
import statistics
import time
import unicodedata
from datetime import datetime, timezone

from ataques import EDGE, abrir_sesion, asignar_ips, calentar_ips, cliente, llm, motivo_de, reiniciar

# Supuestos de uso (no salen de una medición: ajustar con datos reales del curso)
ESTUDIANTES = 40
PREGUNTAS_POR_DIA = 10
PREGUNTAS_POR_SESION = 30
ESTUDIANTES_POR_IP = 20  # una sala o el campus salen a internet por una sola IP

# (pregunta, alguna de estas palabras debe estar en una respuesta correcta)
PREGUNTAS = [
    ("¿Quién dicta Arquitectura de Software?", ["ramirez"]),
    ("¿En qué salón es Arquitectura de Software?", ["b-204"]),
    ("¿Cuánto vale el corte 2 de Arquitectura de Software?", ["35"]),
    ("¿Qué es la arquitectura hexagonal?", ["dominio", "puertos", "ports"]),
    ("¿Cuáles son los niveles del diagrama C4?", ["contenedor"]),
    ("¿Qué es un ADR?", ["decision"]),
    ("¿Cuándo se entrega el taller de diagramas C4?", ["viernes"]),
    ("¿Qué significa la triada CIA?", ["confidencialidad"]),
    ("¿Cómo se calcula el riesgo en seguridad de la información?", ["probabilidad"]),
    ("¿Qué diferencia hay entre criptografía simétrica y asimétrica?", ["clave"]),
    ("¿Cuántos pasos tiene la guía de análisis de riesgos?", ["4", "cuatro"]),
    ("¿Quién dicta Fundamentos de Seguridad de la Información?", ["torres"]),
    ("¿Qué entra en el corte 3 de Fundamentos de Seguridad de la Información?", ["owasp"]),
    ("¿Cuándo fue la batalla de Boyacá?", ["1819"]),
    ("¿Qué fue el Frente Nacional?", ["liberal", "conservador"]),
    ("¿Qué pasó en el Bogotazo?", ["gaitan"]),
    ("¿Qué reconoció la Constitución de 1991?", ["estado social", "diversidad"]),
    ("¿Cuál es el tema del ensayo del corte 1 de Historia de Colombia?", ["independencia"]),
    ("¿Cuántas fuentes pide el ensayo de Historia de Colombia?", ["3", "tres"]),
    ("¿Quién dicta Historia de Colombia?", ["herrera"]),
    ("¿Qué es la regla de la cadena?", ["g'(x)", "derivada", "compuesta"]),
    ("¿Qué mide la derivada?", ["cambio"]),
    ("¿Qué es la integral definida?", ["area"]),
    ("¿Qué temas entran en el corte 2 de Matemáticas Básicas?", ["limites", "funciones"]),
    ("¿Cuándo se entrega el taller de derivadas?", ["miercoles"]),
    ("¿Quién dicta Matemáticas Básicas?", ["gomez"]),
    ("¿En qué horario es Matemáticas Básicas?", ["8-10", "8 a 10", "8:00"]),
    ("¿Qué es MVC?", ["model", "modelo"]),
    ("¿Cuánto vale la redacción en el ensayo de Historia de Colombia?", ["30"]),
    ("¿En qué salón es Historia de Colombia?", ["d-105"]),
]


def normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def percentil(valores: list[float], p: float) -> float:
    orden = sorted(valores)
    return orden[min(len(orden) - 1, math.ceil(p * len(orden)) - 1)] if orden else 0


def arriba(valor: float, multiplo: int) -> int:
    return int(math.ceil(valor / multiplo) * multiplo)


def sugerir(entradas: list[int], totales: list[int], rpm_proveedor: int, rpd_proveedor: int) -> dict:
    salida_max = int(os.getenv("MAX_TOKENS_SALIDA", "300"))
    p50, p95 = percentil(totales, 0.5), percentil(totales, 0.95)
    reserva = arriba(max(entradas) * 1.2 + salida_max, 50)  # cota: la salida no puede pasar del tope
    sugerido = {
        "TOKEN_RESERVE_PER_QUESTION": reserva,
        "QUOTA_TOKENS_SESSION": arriba(PREGUNTAS_POR_SESION * p95, 1000),
        "QUOTA_TOKENS_IP_DAY": arriba(ESTUDIANTES_POR_IP * PREGUNTAS_POR_DIA * p50, 1000),
        "QUOTA_TOKENS_GLOBAL_DAY": arriba(ESTUDIANTES * PREGUNTAS_POR_DIA * p50 * 1.5, 10000),
        "QUOTA_TOKENS_IP_AHORRO": 3 * reserva,
    }
    if rpd_proveedor:
        # el tope no puede pasar de lo que el proveedor deja gastar al día: si no, un ataque sostenido
        # agota su cuota antes de que entre el modo de ahorro y el servicio queda muerto hasta mañana
        sugerido["QUOTA_TOKENS_GLOBAL_DAY"] = min(sugerido["QUOTA_TOKENS_GLOBAL_DAY"], int(rpd_proveedor * p50 // 10000 * 10000))
    if rpm_proveedor:
        sugerido["LLM_RPM_GLOBAL"] = math.floor(rpm_proveedor * 0.9)  # un margen para no tocar el límite
        sugerido["LLM_RPM_POR_IP"] = math.floor(rpm_proveedor * 0.9) // 3  # una IP no puede quedarse con todo
    return sugerido


async def principal():
    args = argparse.ArgumentParser()
    args.add_argument("--salida", default="simulado")
    args.add_argument("--intervalo", type=float, default=5, help="segundos entre preguntas")
    args.add_argument("--rpm-proveedor", type=int, default=0, help="límite por minuto del proveedor, si lo tiene")
    args.add_argument("--rpd-proveedor", type=int, default=0, help="límite por día del proveedor, si lo tiene")
    args.add_argument("--max-preguntas", type=int, default=len(PREGUNTAS))
    args = args.parse_args()

    ips = asignar_ips(12)
    await calentar_ips(ips)
    reiniciar()
    filas = []
    for i, (pregunta, esperadas) in enumerate(PREGUNTAS[:args.max_preguntas]):
        # cada IP y sesión hace 3 preguntas: aquí se mide el costo, no los límites
        inicio_vuelta = time.time()
        async with cliente(ips[(i // 3) % len(ips)]) as c:
            if i % 3 == 0:
                token = await abrir_sesion(c)
            inicio = time.time()
            r = await c.post(f"{EDGE}/ask", json={"message": pregunta}, headers={"Authorization": f"Bearer {token}"}, timeout=170)
            segundos = time.time() - inicio
        datos = r.json() if r.status_code == 200 else {}
        respuesta = normalizar(datos.get("answer", ""))
        filas.append({
            "pregunta": pregunta, "estado": r.status_code, "motivo": None if r.status_code == 200 else motivo_de(r),
            "segundos": round(segundos, 3), "segundos_rag": datos.get("segundos_rag", 0), "segundos_llm": datos.get("segundos_llm", 0), "tokens_entrada": datos.get("tokens_entrada", 0), "tokens_salida": datos.get("tokens_salida", 0),
            "tokens_total": datos.get("tokens_total", 0), "fragmentos": datos.get("fragmentos", 0), "fin": datos.get("fin"),
            "correcta": any(e in respuesta for e in esperadas), "respuesta": datos.get("answer", ""), "fuentes": datos.get("fuentes", []),
        })
        f = filas[-1]
        print(f"[{i + 1}/{args.max_preguntas}] {f['estado']} {f['segundos']:.1f}s {f['tokens_total']} tokens {'bien' if f['correcta'] else 'REVISAR'}: {pregunta}", flush=True)
        await asyncio.sleep(max(0, args.intervalo - (time.time() - inicio_vuelta)))

    buenas = [f for f in filas if f["estado"] == 200 and f["tokens_total"] > 0]
    totales = [f["tokens_total"] for f in buenas]
    entradas = [f["tokens_entrada"] for f in buenas]
    salidas = [f["tokens_salida"] for f in buenas]
    tiempos = [f["segundos"] for f in buenas]
    tiempos_llm = [f["segundos_llm"] for f in buenas]
    tiempos_rag = [f["segundos_rag"] for f in buenas]
    proveedor = llm()
    if not buenas:
        raise SystemExit(f"Ninguna pregunta llegó al modelo: {[f['motivo'] for f in filas][:5]}")
    resumen = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "modelo": llm().get("modelo"),
        "preguntas": len(filas),
        "respondidas": len(buenas),
        "correctas": sum(f["correcta"] for f in filas),
        "errores_proveedor": proveedor["errores_proveedor"],
        "rechazos_proveedor": proveedor["rechazos_proveedor"],
        "tokens_entrada_total": proveedor["tokens_entrada"],
        "tokens_salida_total": proveedor["tokens_salida"],
        "usd_total": proveedor["usd"],
        "truncadas": sum(f["fin"] == "length" for f in filas),
        "tokens_total": {"mediana": statistics.median(totales), "p95": percentil(totales, 0.95), "max": max(totales), "promedio": round(statistics.mean(totales), 1)},
        "tokens_entrada": {"mediana": statistics.median(entradas), "max": max(entradas)},
        "tokens_salida": {"mediana": statistics.median(salidas), "max": max(salidas)},
        "segundos": {"mediana": round(statistics.median(tiempos), 2), "p95": round(percentil(tiempos, 0.95), 2), "max": round(max(tiempos), 2)},
        "segundos_modelo": {"mediana": round(statistics.median(tiempos_llm), 2), "p95": round(percentil(tiempos_llm, 0.95), 2), "max": round(max(tiempos_llm), 2)},
        "segundos_busqueda": {"mediana": round(statistics.median(tiempos_rag), 3), "max": round(max(tiempos_rag), 3)},
        "supuestos": {"estudiantes": ESTUDIANTES, "preguntas_por_dia": PREGUNTAS_POR_DIA, "preguntas_por_sesion": PREGUNTAS_POR_SESION, "estudiantes_por_ip": ESTUDIANTES_POR_IP},
        "sugerido": sugerir(entradas, totales, args.rpm_proveedor, args.rpd_proveedor),
        "filas": filas,
    }
    os.makedirs("/resultados", exist_ok=True)
    with open(f"/resultados/calibracion-{args.salida}.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in resumen.items() if k != "filas"}, indent=2, ensure_ascii=False))
    reiniciar()


if __name__ == "__main__":
    asyncio.run(principal())
