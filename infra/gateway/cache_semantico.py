"""
Equivalente abierto de SemanticCacheLookup / SemanticCachePopulate. Guarda en Valkey, así
sobrevive a un reinicio del gateway (el TODO de secure/semantic_cache.py).

El modelo es multilingüe porque las preguntas son en español: all-MiniLM-L6-v2, el del
laboratorio, está pensado para inglés.

Riesgo del ADR: una respuesta en caché la puede recibir otro usuario. Por eso los filtros
corren antes (una pregunta con datos personales nunca llega aquí) y solo se guardan
respuestas que salieron de documentos del curso.

Otro riesgo, medido con este modelo: "¿cuánto vale el corte 3?" y "¿cuánto vale el corte 2?"
dan 0.95 de similitud, lo mismo que una reformulación legítima. Ningún umbral los separa, por
eso además se exige que las dos preguntas tengan los mismos números. Un fallo de caché cuesta
tokens; un acierto falso le da a un estudiante una respuesta equivocada.
"""

import base64
import json
import os
import re
import uuid

import numpy as np
from fastembed import TextEmbedding

MODELO = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
UMBRAL = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.90"))
MAX_ENTRADAS = int(os.getenv("CACHE_MAX_ENTRIES", "500"))
TTL = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
CLAVE = "cache:semantico"


def _numeros(texto: str) -> list[str]:
    return sorted(set(re.findall(r"\d+", texto)))


class CacheSemantico:
    def __init__(self, redis_client):
        self.r = redis_client
        self.modelo = TextEmbedding(model_name=MODELO, threads=2)

    def _vector(self, texto: str) -> np.ndarray:
        v = next(iter(self.modelo.embed([texto])))
        return (v / np.linalg.norm(v)).astype(np.float32)

    def buscar(self, pregunta: str) -> tuple[dict | None, np.ndarray]:
        """Devuelve (respuesta o None, embedding). El embedding se reutiliza al guardar."""
        vector = self._vector(pregunta)
        mejor, mejor_sim = None, UMBRAL
        numeros = _numeros(pregunta)
        for crudo in self.r.hvals(CLAVE):
            entrada = json.loads(crudo)
            if entrada["n"] != numeros:
                continue
            guardado = np.frombuffer(base64.b64decode(entrada["v"]), dtype=np.float32)
            similitud = float(np.dot(vector, guardado))
            if similitud >= mejor_sim:
                mejor, mejor_sim = entrada["r"], similitud
        return mejor, vector

    def guardar(self, pregunta: str, vector: np.ndarray, respuesta: dict) -> None:
        if self.r.hlen(CLAVE) >= MAX_ENTRADAS:
            self.r.delete(CLAVE)  # tope simple: una caché que crece sin límite también es un ataque
        entrada = {"q": pregunta, "n": _numeros(pregunta), "v": base64.b64encode(vector.tobytes()).decode(), "r": respuesta}
        self.r.hset(CLAVE, uuid.uuid4().hex, json.dumps(entrada, ensure_ascii=False))
        self.r.expire(CLAVE, TTL)
