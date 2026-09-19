# FDSI-GP-05: Seminario de Ciberseguridad en IA

Repo del equipo GP-05 para el Seminario Aplicado de Ciberseguridad en IA (FDSI/SPTI, 2026-2). Nos tocó el tema de denegación de servicio y consumo económico en aplicaciones con LLM.

## Equipo

Mabel Bernal, Juan Pablo Vélez, Esteban Caicedo, Nicolás Prieto.

## De qué va esto

La idea del reto es mostrar qué pasa cuando una app con LLM no tiene ningún control sobre cuánto puede pedir un usuario. Y comparar eso contra la misma app pero con controles encima.

Escogimos como caso un asistente que responde preguntas de estudiantes buscando en los documentos del curso, como reglamentos y guías. Lo primero que se nos ocurrió fue lo más simple: pegarle al LLM todo el material del curso directo en el prompt. Pero no tiene sentido. Ni cabe todo en el contexto ni sale barato mandar lo mismo una y otra vez. Por eso usamos RAG. El sistema busca solo los documentos que tienen que ver con la pregunta y le manda al modelo solo esos, no todo el temario.

El problema es que ese buscar y mandar contexto tampoco tiene límite. Si alguien pregunta algo como "resume todo el curso", el sistema igual termina trayendo un montón de documentos de una sola vez y el gasto se dispara.

Vamos a armar dos versiones. La Unsecure no tiene ningún control: cualquiera pregunta lo que quiera las veces que quiera. La Secure sí tiene límite de peticiones por usuario, tope diario de tokens, caché para no repetir respuestas ya dadas y límite a cuántos documentos puede traer el RAG por consulta.

## Hitos

| Fecha | Qué toca | Estado |
|---|---|---|
| 05/09 | Propuesta estructurada | Entregada |
| 12/09 | Arquitecturas + PPT + plan de pruebas + video | No se entregó |
| 26/09 | Demo completa + paper IEEE + sustentación | En proceso |
| 14/11 | Sustentación final, si quedamos entre los 2 mejores | Pendiente |

## Estructura

```
docs/       -> propuesta y avances
diagrams/   -> los dos diagramas de arquitectura
common/     -> código compartido (búsqueda RAG, llamada al LLM)
unsecure/   -> la versión sin controles
secure/     -> la versión con controles
tests/      -> los scripts de las pruebas
```

## Tecnologías

Python con FastAPI para el backend. Redis para el rate limiter y la caché, contando tokens reales con `tiktoken` en vez de solo peticiones. Locust para simular carga. Pensamos meter también vLLM para optimizar la parte de inferencia, pero necesita GPU y no tenemos. Nos quedamos con algo que sí corra en una laptop normal.

## Uso de IA

Usamos Claude para ayudarnos a organizar la propuesta y pensar la arquitectura. Las decisiones y el contenido final los revisamos y ajustamos nosotros como equipo.
