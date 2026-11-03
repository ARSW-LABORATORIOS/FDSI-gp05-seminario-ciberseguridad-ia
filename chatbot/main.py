from pathlib import Path

from fastapi import FastAPI, Request
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


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response


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
