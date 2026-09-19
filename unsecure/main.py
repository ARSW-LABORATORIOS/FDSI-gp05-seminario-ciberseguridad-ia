"""
Esta es la versión SIN controles. Cualquiera pregunta lo que quiera, las veces que
quiera, y el sistema busca todos los documentos que pueda y se los manda al LLM sin
revisar nada. Esto es a propósito -- es la que vamos a "atacar" en las pruebas para
mostrar que sin control el sistema se cae o se dispara el gasto.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from pydantic import BaseModel
from common.rag import DocumentRetriever
from common.llm_client import ask_llm

app = FastAPI(title="Asistente académico - UNSECURE")
retriever = DocumentRetriever()


class Pregunta(BaseModel):
    texto: str


@app.post("/ask")
def preguntar(pregunta: Pregunta):
    """
    No hay login, no hay límite de tokens, no hay límite de cuántos documentos
    se pueden traer, y no hay caché. Todo se procesa siempre desde cero.
    """
    # max_chunks alto a propósito -- no hay ningún control de tamaño de contexto
    contexto = retriever.search(pregunta.texto, max_chunks=50)
    resultado = ask_llm(pregunta.texto, contexto)
    return resultado
