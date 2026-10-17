from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from knowledge import search

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
    return FileResponse("index.html")


@app.post("/ask")
def ask(q: Question):
    answer = search(q.message)
    return {"answer": answer}
