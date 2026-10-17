from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from knowledge import search

AQUI = Path(__file__).parent

app = FastAPI(title="Chatbot – Denial of Wallet")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    message: str


@app.get("/")
def index():
    # ruta absoluta para que funcione aunque uvicorn se lance desde otra carpeta
    return FileResponse(AQUI / "index.html")


@app.get("/health")
def health():
    """Lo usa la interfaz para mostrar si el servidor está conectado."""
    return {"status": "ok"}


@app.post("/ask")
def ask(q: Question):
    return search(q.message)
