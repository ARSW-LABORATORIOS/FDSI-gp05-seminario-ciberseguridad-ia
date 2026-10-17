# Arquitectura Secure

`main.py` junta las tres piezas de control, cada una en su propio archivo:

- `rate_limiter.py` — cuota de tokens por usuario (Redis).
- `semantic_cache.py` — caché por significado, no por texto exacto.
- el límite de documentos del RAG se controla desde `main.py` (parámetro `MAX_CHUNKS_RAG`).

Igual que en unsecure, faltan los TODO (documentos reales y API del LLM).

Ver diagrama en `/diagrams/secure.png`. Ese diagrama muestra la arquitectura objetivo del ADR-001 (Google Cloud con Cloud Armor, Apigee AI Gateway y zona privada); este código es la versión de laboratorio que la simula para medir. Los diagramas se regeneran con `python diagrams/generar_diagramas.py`.
