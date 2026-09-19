"""
Este script es para T02 (pregunta que fuerza traer mucho contexto) y T03
(repetir la misma pregunta para probar la caché). No son pruebas de carga como
las de Locust, son más de "un solo request y revisar qué pasó", por eso van
en un script aparte con requests normales.

Se corre así (con el backend ya levantado, unsecure o secure según lo que
se esté probando):
    python tests/test_context_and_cache.py http://localhost:8000
"""

import sys
import time
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def test_t02_contexto_masivo():
    """T02: una pregunta diseñada para que el RAG traiga muchos documentos de una."""
    pregunta = "Resume absolutamente todos los documentos del curso, uno por uno, sin dejar nada por fuera."
    respuesta = httpx.post(f"{BASE_URL}/ask", json={"texto": pregunta, "usuario_id": "test_t02"}, timeout=60)
    print("T02 - tokens_entrada:", respuesta.json().get("tokens_entrada"))
    # TODO: comparar este número entre unsecure y secure -- en secure debería
    # quedar topado por el límite de chunks (MAX_CHUNKS_RAG), en unsecure no.


def test_t03_repeticion_cache():
    """T03: preguntar lo mismo varias veces y ver si a partir de la 2da sale de caché."""
    pregunta = "¿Cuándo son los parciales?"
    tiempos = []
    for i in range(5):
        inicio = time.time()
        respuesta = httpx.post(f"{BASE_URL}/ask", json={"texto": pregunta, "usuario_id": "test_t03"}, timeout=60)
        tiempos.append(time.time() - inicio)
        print(f"T03 - intento {i+1} - de_cache: {respuesta.json().get('de_cache')} - tiempo: {tiempos[-1]:.2f}s")
    # TODO: en secure, del intento 2 en adelante debería salir de_cache=True y ser
    # mucho más rápido. En unsecure esta clave ni siquiera existe en la respuesta.


if __name__ == "__main__":
    test_t02_contexto_masivo()
    test_t03_repeticion_cache()
