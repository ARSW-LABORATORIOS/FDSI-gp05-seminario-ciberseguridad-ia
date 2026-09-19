# Arquitectura Secure

`main.py` junta las tres piezas de control, cada una en su propio archivo:

- `rate_limiter.py` — cuota de tokens por usuario (Redis).
- `semantic_cache.py` — caché por significado, no por texto exacto.
- el límite de documentos del RAG se controla desde `main.py` (parámetro `MAX_CHUNKS_RAG`).

Igual que en unsecure, faltan los TODO (documentos reales y API del LLM).

Ver diagrama en `/diagrams/secure.png`.
