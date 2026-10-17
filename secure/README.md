# Arquitectura Secure

`main.py` junta las tres piezas de control, cada una en su propio archivo:

- `rate_limiter.py` — cuota de tokens por usuario (Redis).
- `semantic_cache.py` — caché por significado, no por texto exacto.
- el límite de documentos del RAG se controla desde `main.py` (parámetro `MAX_CHUNKS_RAG`).

Igual que en unsecure, faltan los TODO (documentos reales y API del LLM).

## Relación con el ADR-001

Esta carpeta es la versión de laboratorio: los controles viven como clases dentro de la misma API FastAPI, lo que sirve para medir cada uno por separado. La arquitectura objetivo está en [`docs/ADR-001-arquitectura-segura.md`](../docs/ADR-001-arquitectura-segura.md) y en `/diagrams/secure.png`.

| Capa del ADR-001 | Servicio gestionado | Qué la simula aquí |
|---|---|---|
| 1. Borde | Cloud Armor | No existe todavía |
| 2. Identidad | Sesión anónima firmada + reCAPTCHA | `usuario_id` en el body (débil: se puede rotar) |
| 3. AI Gateway | Apigee: `SpikeArrest`, `PromptTokenLimit`, `LLMTokenQuota` | `RateLimiter` (`rate_limiter.py`) |
| 3. Filtro de prompts | Model Armor | No existe todavía |
| 3. Caché semántica | `SemanticCacheLookup` / `SemanticCachePopulate` | `SemanticCache` en memoria (`semantic_cache.py`) |
| 4. Orquestador | Hermes Agent en Cloud Run | No existe todavía (no hay tope de pasos, timeout ni límite de salida) |
| 4. RAG | Cloud Storage + Vertex AI Vector Search | `MAX_CHUNKS_RAG = 5` con ChromaDB |
| 5. Egreso a LLMs | Apigee (routing y failover) | `ask_llm` en `common/llm_client.py` (un solo proveedor) |
| 5. Red privada | VPC + Secret Manager | `.env` local |
| 6. Detección y costo | Logging, Billing, SCC | Métricas de Locust |

Los tres huecos que señala el ADR para esta versión: los controles caen junto con la API si se satura, el `usuario_id` se puede falsificar desde el body y no hay perímetro que filtre tráfico antes de Python.
