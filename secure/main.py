"""
Esta es la versión CON controles. Hace lo mismo que unsecure (responder preguntas
buscando en los documentos del curso) pero antes de llamar al LLM pasa por tres
filtros: cuota de tokens, caché semántica, y límite de cuántos documentos trae el RAG.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from common.rag import DocumentRetriever
from common.llm_client import ask_llm, count_tokens
from secure.rate_limiter import RateLimiter
from secure.semantic_cache import SemanticCache

app = FastAPI(title="Asistente académico - SECURE")
retriever = DocumentRetriever()
rate_limiter = RateLimiter()
cache = SemanticCache()

MAX_CHUNKS_RAG = 5  # tope a cuántos documentos se pueden traer por consulta


class Pregunta(BaseModel):
    texto: str
    usuario_id: str  # acá en un caso real vendría del token de login (JWT), no del body


@app.post("/ask")
def preguntar(pregunta: Pregunta):
    # 1) primero miramos la caché -- si ya respondimos algo parecido, ni gastamos tokens
    respuesta_en_cache = cache.buscar(pregunta.texto)
    if respuesta_en_cache is not None:
        return {**respuesta_en_cache, "de_cache": True}

    # 2) calculamos cuánto costaría más o menos esta pregunta y revisamos la cuota
    #    ANTES de llamar al LLM, para no gastar nada si de todas formas se va a rechazar
    tokens_estimados = count_tokens(pregunta.texto) * 3  # estimado grosero, se ajusta con datos reales
    if not rate_limiter.tiene_cuota(pregunta.usuario_id, tokens_estimados):
        raise HTTPException(status_code=429, detail="Se te acabó la cuota de tokens de hoy")

    # 3) buscamos en los documentos del curso, pero con tope (a diferencia de unsecure)
    contexto = retriever.search(pregunta.texto, max_chunks=MAX_CHUNKS_RAG)

    # 4) ahora sí llamamos al LLM
    resultado = ask_llm(pregunta.texto, contexto)

    # 5) registramos lo que se gastó de verdad y guardamos en caché para la próxima
    rate_limiter.registrar_consumo(pregunta.usuario_id, resultado["tokens_total"])
    cache.guardar(pregunta.texto, resultado)

    return {**resultado, "de_cache": False}
