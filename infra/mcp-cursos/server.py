"""
Servidor MCP con las herramientas del curso. El RAG vive aquí: al arrancar lee los .md de
/docs, los parte en fragmentos y los mete a Chroma.

`borrar_indice` existe a propósito y NO está aprobada en agentgateway. Sirve para probar que
el gateway la oculta y la rechaza aunque el servidor la tenga (capa 5 del ADR: solo tools
registradas). Si algún día alguien logra llamarla, la prueba de seguridad debe fallar.
"""

import json
import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

import chromadb
from fastembed import TextEmbedding
from mcp.server.fastmcp import FastMCP

DOCS = Path(os.getenv("DOCS_DIR", "/docs"))
MODELO = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
MAX_CARACTERES = 450
# Palabras que no ayudan a encontrar un documento
VACIAS = set(
    "a al algo ante cada como con cual cuales cuando cuanto cuanta cuantos cuantas de del dame dime donde el ella en entre es "
    "esa ese esta este explica explicame fue hay la las le lo los me mi muy no o para pero por que quien se si sin sobre son "
    "su sus te tiene tienen un una uno y ya".split()
)
K_FUSION = 10  # corpus pequeño: con el 60 habitual, el puesto casi no cambiaría el puntaje

embedder = TextEmbedding(model_name=MODELO, threads=2)
coleccion = chromadb.Client().get_or_create_collection("course_docs", metadata={"hnsw:space": "cosine"})


terminos_por_id: dict[str, set[str]] = {}
apariciones: Counter = Counter()


def embeber(textos: list[str]) -> list[list[float]]:
    return [v.tolist() for v in embedder.embed(textos)]


def terminos(texto: str) -> set[str]:
    """Palabras significativas, sin tildes y recortadas a 6 letras: derivada y derivadas coinciden."""
    plano = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return {p[:6] for p in re.findall(r"[a-z0-9-]+", plano) if p not in VACIAS and len(p) > 1}


def cobertura(consulta: set[str], fragmento: set[str]) -> float:
    """Qué parte de la consulta aparece en el fragmento, dándole más peso a las palabras raras."""
    total = len(terminos_por_id) or 1
    pesos = {t: math.log(1 + total / (1 + apariciones[t])) for t in consulta}
    return sum(p for t, p in pesos.items() if t in fragmento) / (sum(pesos.values()) or 1)


def partir(texto: str) -> list[str]:
    """Parte por líneas sin pasarse de MAX_CARACTERES; cada fragmento conserva el título."""
    lineas = [l for l in texto.splitlines() if l.strip()]
    titulo, resto = lineas[0].lstrip("# ").strip(), lineas[1:]
    fragmentos, actual = [], ""
    for linea in resto:
        if actual and len(actual) + len(linea) > MAX_CARACTERES:
            fragmentos.append(actual)
            actual = ""
        actual = f"{actual}\n{linea}" if actual else linea
    if actual:
        fragmentos.append(actual)
    return [f"{titulo}\n{f}" for f in fragmentos]


def indexar() -> int:
    ids, textos, metadatos = [], [], []
    for archivo in sorted(DOCS.glob("*.md")):
        for i, fragmento in enumerate(partir(archivo.read_text(encoding="utf-8"))):
            ids.append(f"{archivo.stem}-{i}")
            textos.append(fragmento)
            metadatos.append({"documento": archivo.name})
            terminos_por_id[ids[-1]] = terminos(fragmento)
            apariciones.update(terminos_por_id[ids[-1]])
    if ids:
        coleccion.add(ids=ids, documents=textos, embeddings=embeber(textos), metadatas=metadatos)
    return len(ids)


mcp = FastMCP("cursos", host="0.0.0.0", port=8000, stateless_http=True, json_response=True)


@mcp.tool()
def buscar_documentos(consulta: str, max_fragmentos: int = 5) -> str:
    """Busca en los documentos del curso los fragmentos más parecidos a la consulta."""
    # Búsqueda híbrida: con el significado solo, "taller de derivadas" dejaba el taller de derivadas
    # en el puesto 6 de 15. Se combinan los dos órdenes por posición (reciprocal rank fusion).
    total = coleccion.count()
    r = coleccion.query(query_embeddings=embeber([consulta]), n_results=max(1, total))
    pedidos = terminos(consulta)
    filas = [
        {"id": i, "texto": t, "documento": m["documento"], "distancia": round(d, 4), "cobertura": round(cobertura(pedidos, terminos_por_id[i]), 3)}
        for i, t, m, d in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]
    por_palabras = {f["id"]: n for n, f in enumerate(sorted(filas, key=lambda f: -f["cobertura"]))}
    puntaje = {f["id"]: 1 / (K_FUSION + n) + 1 / (K_FUSION + por_palabras[f["id"]]) for n, f in enumerate(filas)}
    filas.sort(key=lambda f: -puntaje[f["id"]])
    return json.dumps([{k: v for k, v in f.items() if k != "id"} for f in filas[:max(1, max_fragmentos)]], ensure_ascii=False)


@mcp.tool()
def listar_documentos() -> str:
    """Lista los documentos del curso que están indexados."""
    return json.dumps(sorted(p.name for p in DOCS.glob("*.md")), ensure_ascii=False)


@mcp.tool()
def borrar_indice() -> str:
    """Herramienta NO aprobada: no hace nada, solo existe para probar que el gateway la bloquea."""
    return "ALERTA: el gateway dejó pasar una herramienta no aprobada"


if __name__ == "__main__":
    print(f"indexados {indexar()} fragmentos de {DOCS}", flush=True)
    mcp.run(transport="streamable-http")
