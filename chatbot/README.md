# Chatbot – Prototipo Académico

Prototipo básico de asistente académico para demostrar el riesgo **Denial of Wallet** (OWASP LLM10:2025).

## Archivos

| Archivo | Descripción |
|---|---|
| `main.py` | Backend FastAPI, endpoint `POST /ask` |
| `knowledge.py` | Base de conocimiento simulada (4 materias) |
| `index.html` | Frontend del chat |
| `requirements.txt` | Dependencias: fastapi + uvicorn |

## Materias simuladas

- Arquitectura de Software
- Fundamentos de Seguridad de la Información
- Matemáticas Básicas
- Historia de Colombia

Cada materia tiene syllabus, apuntes y taller/guía simulados.

## Cómo correrlo

```bash
cd chatbot
py -m pip install -r requirements.txt
py -m uvicorn main:app --reload
```

Abrir `http://localhost:8000`

## Estado

Prototipo sin LLM real. La función `search()` en `knowledge.py` es el punto de extensión para conectar Gemini/OpenAI en la siguiente fase.
