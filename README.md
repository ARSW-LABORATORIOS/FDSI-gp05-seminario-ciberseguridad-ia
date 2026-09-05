# FDSI-gp05-seminario-ciberseguridad-ia
Seminario Aplicado de Ciberseguridad en IA (FDSI/SPTI 2026-2) — Grupo GP-05. Comparación de arquitectura Unsecure vs. Secure para un asistente académico con RAG, evaluando denegación de servicio y consumo económico (tokens) mediante rate limiting, cuotas, caché y límites de contexto
# FDSI-GP-05 · Seminario Aplicado de Ciberseguridad en IA

Repositorio de trabajo del equipo **GP-05** para el Seminario Aplicado de Ciberseguridad en IA (FDSI / SPTI · ECI · 2026-2).

**Tema asignado:** Denegación de servicio y consumo económico en aplicaciones basadas en LLM.

## Equipo

| Integrante | GitHub |
|---|---|
| Mabel Bernal | [@MabelBernalAmaya](https://github.com/MabelBernalAmaya) |
| Juan Pablo Vélez | |
| Esteban Caicedo | |
| Nicolás Prieto | |

## De qué se trata el proyecto

Vamos a comparar dos versiones de un **asistente académico basado en LLM con RAG** (responde preguntas de estudiantes consultando documentos del curso):

- **Unsecure:** sin ningún control. Cualquiera puede mandar todas las preguntas que quiera, sin límite de tamaño de contexto, sin cuota y sin caché.
- **Secure:** con rate limiting por usuario, cuota diaria de tokens, caché de respuestas frecuentes, límite al contexto que se recupera por RAG, y timeout/circuit breaker hacia el LLM.

La idea es demostrar, con pruebas reproducibles y métricas concretas, que esos controles bajan el consumo de tokens y evitan que el servicio se sature — sin dañar la experiencia de un usuario que lo use de forma normal.

La lógica que debemos poder explicar en cualquier momento:

```
Problema → Arquitectura Unsecure → Prueba → Evidencia → Control → Arquitectura Secure → Métrica
```

## Hoja de ruta

| Fecha | Hito | Entrega |
|---|---|---|
| 05/09/2026 | Hito 1 · Propuesta estructurada | PDF de la propuesta técnica ✅ |
| 12/09/2026 | Hito 2 · Entrega preliminar | Arquitecturas + PPT técnico + plan de pruebas + criterios + video demo preliminar |
| 26/09/2026 | Hito 3 · Entrega final (Corte 2) | Demo completa + paper formato IEEE + presentación + sustentación |
| 14/11/2026 | Seminario final | Sustentación (solo los 2 mejores proyectos entre FDSI y SPTI) |

## Estructura del repo (irá creciendo con cada hito)

```
├── docs/
│   └── Propuesta_Estructurada_FDSI-GP-05.pdf
├── diagrams/
│   ├── unsecure.png
│   └── secure.png
├── unsecure/      # implementación de la arquitectura sin controles (Hito 2)
├── secure/        # implementación de la arquitectura con controles (Hito 2)
├── tests/         # scripts de las pruebas T01-T05 (Hito 2)
└── README.md
```

> **Estado actual:** solo tenemos la propuesta estructurada (Hito 1). Todavía no hay nada implementado — eso empieza para el Hito 2.

## Tecnologías previstas

Python (FastAPI) · LLM vía API o modelo local (Ollama) · Chroma/FAISS + embeddings para el RAG · Redis (rate limiting, cuotas, caché) · tiktoken · Locust/scripts propios para simular carga · Docker.

## Declaración de uso de IA

Se usó Claude (Anthropic) como apoyo para redactar la propuesta estructurada, generar los diagramas preliminares de arquitectura y organizar este README, siguiendo la plantilla y los lineamientos del curso. Todo el contenido fue revisado y ajustado por el equipo.
