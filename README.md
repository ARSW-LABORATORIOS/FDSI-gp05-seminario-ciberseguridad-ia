# FDSI-GP-05: Seminario de Ciberseguridad en IA

Repo del equipo GP-05 para el Seminario Aplicado de Ciberseguridad en IA (FDSI/SPTI, 2026-2). Nos tocó el tema de denegación de servicio y consumo económico en aplicaciones con LLM.

## Equipo

Mabel Bernal, Juan Pablo Vélez, Esteban Caicedo, Nicolás Prieto.

## De qué va esto

La idea del reto es mostrar qué pasa cuando una app con LLM no tiene ningún control sobre cuánto puede pedir un usuario. Y comparar eso contra la misma app pero con controles encima.

Escogimos como caso un asistente que responde preguntas de estudiantes buscando en los documentos del curso, como reglamentos y guías. Lo primero que se nos ocurrió fue lo más simple: pegarle al LLM todo el material del curso directo en el prompt. Pero no tiene sentido. Ni cabe todo en el contexto ni sale barato mandar lo mismo una y otra vez. Por eso usamos RAG. El sistema busca solo los documentos que tienen que ver con la pregunta y le manda al modelo solo esos, no todo el temario.

El problema es que ese buscar y mandar contexto tampoco tiene límite. Si alguien pregunta algo como "resume todo el curso", el sistema igual termina trayendo un montón de documentos de una sola vez y el gasto se dispara.

Vamos a armar dos versiones. La Unsecure no tiene ningún control: cualquiera pregunta lo que quiera las veces que quiera. La Secure sí tiene límite de peticiones por usuario, tope diario de tokens, caché para no repetir respuestas ya dadas y límite a cuántos documentos puede traer el RAG por consulta.

## Arquitectura objetivo (ADR-001)

En clase se pidió llevar la versión Secure a una arquitectura con servicios gestionados y defensa en profundidad. La decisión quedó en el [ADR-001](docs/ADR-001-arquitectura-segura.md): desplegar en Google Cloud con tres zonas (pública, perímetro y privada) y un AI Gateway gestionado (Apigee) como único punto por donde entra una pregunta y sale cualquier llamada a un LLM. Así el consumo se corta antes de gastar un token, no después.

Cada capa frena un abuso distinto:

- **Borde:** Cloud Armor frena el flooding volumétrico y los bots (por IP, huella TLS JA4 o ASN).
- **Identidad:** el chatbot no tiene login, así que tras pasar reCAPTCHA el backend entrega una sesión anónima firmada. La cuota va por sesión, IP y un tope global, y ya no sirve rotar el `usuario_id`.
- **AI Gateway:** Apigee aplica `SpikeArrest`, `PromptTokenLimit`, `LLMTokenQuota` (tokens reales, no peticiones), Model Armor contra prompt injection y caché semántica.
- **Zona privada:** el orquestador del agente (Hermes Agent en Cloud Run) recupera máximo 5 fragmentos del RAG y solo sale a los LLMs o a herramientas MCP aprobadas a través de gateways.
- **Detección y costo:** logs, alertas y presupuestos de Billing con corte automático.

Lo que tenemos en el código (FastAPI + Redis) es la versión de laboratorio que simula esa arquitectura para poder medir. La tabla "Equivalente en el repo" del ADR dice qué parte simula cada capa y cuáles todavía no existen. Queda abierto si la demo final corre en Google Cloud, en Azure o en la laptop con un gateway open source (LiteLLM o Kong).

## Hitos

| Fecha | Qué toca | Estado |
|---|---|---|
| 05/09 | Propuesta estructurada | Entregada |
| 12/09 | Arquitecturas + PPT + plan de pruebas + video | No se entregó |
| 26/09 | Demo completa + paper IEEE + sustentación | En proceso |
| 14/11 | Sustentación final, si quedamos entre los 2 mejores | Pendiente |

## Estructura

```
docs/       -> propuesta, avances y ADR-001 (arquitectura objetivo)
diagrams/   -> los dos diagramas de arquitectura (unsecure y secure según el ADR-001)
common/     -> código compartido (búsqueda RAG, llamada al LLM)
unsecure/   -> la versión sin controles
secure/     -> la versión con controles (laboratorio que simula el ADR-001)
chatbot/    -> prototipo con interfaz web del asistente (sin LLM real todavía)
tests/      -> los scripts de las pruebas T01-T05
```

## Tecnologías

Python con FastAPI para el backend. Redis para el rate limiter y la caché, contando tokens reales con `tiktoken` en vez de solo peticiones. Locust para simular carga. Pensamos meter también vLLM para optimizar la parte de inferencia, pero necesita GPU y no tenemos. Nos quedamos con algo que sí corra en una laptop normal.

Para la arquitectura objetivo (ADR-001): Google Cloud con Cloud Armor, Apigee AI gateway, Model Armor, Cloud Run, Vertex AI Vector Search y Agent Gateway para MCP. Con créditos de estudiante el plan es pedirle al profesor los créditos de docencia de Google, usar la evaluación gratuita de Apigee y dejar Gemini como modelo principal; Claude, OpenAI y modelos open source quedan como rutas de failover documentadas. Azure (API Management) queda como alternativa equivalente y AWS como plan B.

## Uso de IA

Usamos Claude para ayudarnos a organizar la propuesta y pensar la arquitectura. Las decisiones y el contenido final los revisamos y ajustamos nosotros como equipo.
