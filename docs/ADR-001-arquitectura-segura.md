# ADR-001 — Arquitectura segura con servicios gestionados

**Fecha:** 13/10/2026 · **Autores:** Grupo 5 FDSI · **Estado:** Propuesto (pendiente de revisión del equipo GP-05)

Versión original en PDF: [ADR-001_Arquitectura_segura_servicios_gestionados.pdf](ADR-001_Arquitectura_segura_servicios_gestionados.pdf). Diagrama: [`../diagrams/secure.png`](../diagrams/secure.png).

## Contexto

El asistente académico con RAG del repo hoy no tiene ningún freno al consumo. La versión Unsecure deja que cualquiera pregunte sin login, sin cuota y trayendo hasta 50 fragmentos por consulta. Ese es el riesgo **OWASP LLM10:2025 Unbounded Consumption**: además de tumbar el servicio, un atacante puede disparar la factura del LLM (*denial of wallet*).

La versión Secure actual mete los controles como clases dentro de una sola API FastAPI con Redis local (rate limiter por tokens, caché semántica en memoria, tope `MAX_CHUNKS_RAG = 5`). Sirve para medir en una laptop, pero tiene tres huecos:

- Todo control vive en el mismo proceso que atacan: si la API se satura, los controles caen con ella.
- El `usuario_id` llega en el body, así que un atacante puede rotarlo y saltarse la cuota.
- No hay perímetro ni capa de red: no se filtra tráfico volumétrico antes de que llegue a Python.

En clase se pidió llevar esto a una arquitectura con servicios gestionados, por capas (defensa en profundidad), con un AI Gateway delante de los modelos, un orquestador de agente, RAG sobre documentos `.md`, varios proveedores de LLM y herramientas expuestas por MCP.

## Decisión

Desplegar el asistente en **Google Cloud** con tres zonas separadas (pública, perímetro, privada) y un **AI Gateway gestionado (Apigee)** como único punto por donde entra una pregunta y por donde sale cualquier llamada a un LLM. Así el consumo se corta antes de gastar un token, no después.

Reglas que fija la decisión:

- **Defensa en profundidad.** Cada capa frena un tipo de abuso distinto: Cloud Armor frena volumen, la sesión anónima con reCAPTCHA frena bots y el AI Gateway frena el gasto en tokens.
- **Sin login, la identidad es una sesión anónima firmada.** Tras pasar reCAPTCHA, la app recibe un token de sesión corto firmado por el backend. El gateway valida la firma y usa su `sub` como llave de cuota, junto con la IP y la huella TLS; además hay un tope global de tokens por día. Rotar `usuario_id` deja de servir.
- **Cuota por tokens reales, no por peticiones.** Es la idea del Token Bucket del repo, aplicada en el gateway con `PromptTokenLimit` y `LLMTokenQuota`.
- **El orquestador del agente vive en zona privada**, sin IP pública. Solo recibe tráfico del gateway y solo sale a LLMs o herramientas a través de gateways, lo que evita el pivoteo.
- **Varios proveedores de LLM detrás del mismo gateway** (Gemini, Claude, OpenAI, open source). Cuota y caché aplican igual sin importar el modelo; si un proveedor falla se cambia de ruta.
- **Herramientas solo por MCP aprobado**, a través de Agent Gateway y registradas en Agent Registry.

La versión de laboratorio (FastAPI + Redis) se mantiene para medir: este ADR es la arquitectura objetivo que esa versión simula.

## Componentes por capa

| Capa | Servicio | Control | Frena | Equivalente en el repo |
|---|---|---|---|---|
| 1. Borde | Cloud Armor + balanceador HTTPS | WAF, anti-DDoS; *throttle* o *rate-based ban* por IP, huella TLS JA4 o ASN | Flooding volumétrico, bots | No existe (pendiente) |
| 2. Identidad | Sesión anónima firmada + reCAPTCHA | Reto anti-bot y token de sesión corto; cuota por sesión, IP y huella TLS | Bots, rotación de `usuario_id` | `usuario_id` en el body (débil) |
| 3. AI Gateway (ingreso) | Apigee AI gateway | `VerifyJWT`, `SpikeArrest`, `PromptTokenLimit`, `LLMTokenQuota` | Ráfagas, prompts gigantes, gasto diario sin tope | `RateLimiter` en `secure/rate_limiter.py` |
| 3. AI Gateway (ingreso) | Model Armor vía `SanitizeUserPrompt` | Filtra prompt injection, jailbreak, datos sensibles y URLs maliciosas | Prompts que fuerzan al agente a gastar o filtrar datos | No existe |
| 3. AI Gateway (ingreso) | Caché semántica de Apigee (`SemanticCacheLookup` / `SemanticCachePopulate`) | Responde preguntas parecidas sin llamar al LLM | Repetición (T03) | `SemanticCache` en memoria |
| 4. Orquestador | Hermes Agent en Cloud Run (ingreso interno) | Tope de pasos por pregunta, timeout, límite de tokens de salida | Bucles del agente, respuestas infinitas | No existe |
| 4. RAG | Cloud Storage (docs `.md`) + Vertex AI Vector Search | Máximo 5 fragmentos por consulta | Contexto masivo (T02) | `MAX_CHUNKS_RAG = 5` |
| 5. Egreso a LLMs | Apigee (flujo de salida) | Routing entre proveedores, failover, `SanitizeModelResponse`, conteo de tokens reales | Caída de un proveedor, fuga en respuestas | `ask_llm` en `common/llm_client.py` |
| 5. Egreso a tools | Agent Gateway + Agent Registry | Solo servidores MCP aprobados, IAM por herramienta, Model Armor | Pivoteo desde el agente, tools no autorizadas | No existe |
| 5. Red privada | VPC + VPC Service Controls, Secret Manager | Sin IP pública, datos dentro del perímetro, API keys fuera del código | Exfiltración, keys filtradas | `.env` local |
| 6. Detección y costo | Cloud Logging/Monitoring, presupuestos de Billing, Security Command Center, Google Security Operations | Alertas de consumo, corte automático por presupuesto, correlación de eventos | Denial of wallet que se escapa de las capas anteriores | Métricas de Locust |

Los nombres de política de Apigee y Model Armor salen de la documentación de Google; los valores de cuota (tokens por día, tope de pasos) se calibran con los datos de T01–T05.

## Flujo de una pregunta

Una pregunta solo gasta tokens si pasa los pasos 1 a 6; cualquier rechazo antes cuesta cero en el LLM.

1. El estudiante abre el chatbot sin login; reCAPTCHA descarta bots y el backend entrega un token de sesión anónimo, corto y firmado.
2. La pregunta llega al balanceador. Cloud Armor bloquea IPs o huellas TLS que superen la tasa y aplica el WAF.
3. Apigee valida la firma del token y toma su `sub` como identidad. `SpikeArrest` corta ráfagas y `PromptTokenLimit` rechaza prompts demasiado largos (HTTP 429/400).
4. `LLMTokenQuota` revisa la cuota de la sesión, la de la IP y el tope global. Si alguna se agotó: 429 sin tocar el LLM.
5. Model Armor revisa el prompt (`SanitizeUserPrompt`): inyección, jailbreak o datos sensibles se bloquean aquí.
6. `SemanticCacheLookup` busca una pregunta parecida. Si hay hit, responde de caché y termina.
7. Si no, el orquestador (zona privada) recupera máximo 5 fragmentos del RAG y arma el prompt.
8. La llamada al modelo sale otra vez por Apigee: routing, failover y `SanitizeModelResponse`.
9. Si el agente necesita una herramienta, la pide por MCP a través de Agent Gateway; solo se permiten las registradas.
10. Apigee descuenta los tokens reales, guarda en caché (`SemanticCachePopulate`) y todo queda en logs; Billing corta si se supera el presupuesto.

## Alternativas consideradas

| Opción | Cómo se vería | A favor | En contra | Decisión |
|---|---|---|---|---|
| Google Cloud + Apigee AI gateway | La de este ADR | Políticas nativas para tokens, caché semántica, Model Armor y MCP; Gemini y Claude en Vertex AI | Apigee es de pago; más piezas que configurar | **Elegida** |
| AWS | CloudFront + WAF/Shield, API Gateway con usage plans, Bedrock + Guardrails, ElastiCache | El equipo ya conoce AWS; Bedrock da varios modelos | Cuota por tokens y caché semántica hay que programarlas en Lambda | Plan B |
| Gateway open source (LiteLLM o Kong AI Gateway) en contenedor | Mismo diseño por zonas, gateway autoadministrado | Barato, corre en laptop, sirve para la demo | Nosotros operamos el gateway; sin anti-DDoS gestionado | Útil para el laboratorio |
| Quedarse en el monolito actual (FastAPI + Redis) | Controles como clases dentro de la API | Fácil de medir y aislar cada control | El control cae junto con la API atacada; sin perímetro ni identidad fuerte | Solo como entorno de pruebas |

### Azure, capa por capa

Azure API Management (APIM) trae cuota por tokens, caché semántica, filtro de contenido y gobierno de MCP como políticas nativas, igual que Apigee.

| Capa | Google (este ADR) | Azure | Control en Azure |
|---|---|---|---|
| 1. Borde | Cloud Armor | Azure Front Door + WAF, DDoS Protection | Rate limit por IP de socket en ventanas de 1 o 5 min |
| 2. Identidad | Sesión anónima + reCAPTCHA | Reto anti-bot + token de sesión del backend | APIM valida la firma con `validate-jwt` |
| 3. AI Gateway | Apigee | APIM AI gateway | `llm-token-limit` por llave (suscripción, IP o `sub` del JWT); puede rechazar sin llamar al modelo |
| 3. Filtro de prompts | Model Armor | Azure AI Content Safety vía `llm-content-safety` | Categorías de daño, `shield-prompt`, blocklists; también revisa tráfico MCP |
| 3. Caché semántica | Política de Apigee | `llm-semantic-cache-lookup` / `-store` | Necesita Azure Managed Redis y un modelo de embeddings |
| 4. Orquestador | Hermes Agent en Cloud Run | Hermes Agent en Container Apps (ingreso interno) | Mismos topes de pasos, timeout y tokens de salida |
| 4. RAG | Cloud Storage + Vertex AI Vector Search | Blob Storage + Azure AI Search | Máximo 5 fragmentos |
| 5. Egreso a LLMs | Apigee + Vertex AI | Backends de APIM + Microsoft Foundry | Balanceo y circuit breaker según `Retry-After` |
| 5. Egreso a tools | Agent Gateway + Agent Registry | APIM como gateway de MCP | OAuth con credential manager |
| 5. Red privada | VPC + Service Controls, Secret Manager | VNet + Private Endpoints, Key Vault | Sin IP pública; keys fuera del código |
| 6. Detección y costo | Billing budgets, SCC, Google SecOps | Cost Management, Azure Monitor (`llm-emit-token-metric`), Defender for Cloud, Sentinel | Métricas de tokens por usuario; alertas a Sentinel |

**Dónde se diferencia:** Azure for Students da USD 100 por 12 meses sin tarjeta, pero no cubre Claude ni Marketplace. El rate limit de Front Door agrupa solo por IP de socket (más débil para T01/T04 que JA4/ASN en Cloud Armor). La caché semántica exige pagar Azure Managed Redis aparte.

**Veredicto:** Azure queda como alternativa equivalente en controles. Con presupuesto cero solo sirve con Azure OpenAI; los créditos de docencia de Google son la otra vía sin tarjeta.

## Consecuencias y validación

La arquitectura se valida con las mismas pruebas del repo: cada prueba debe mostrar que el ataque se frena en una capa concreta y antes del LLM.

| Prueba | Ataque | Capa que debe frenarlo | Métrica Unsecure vs Secure |
|---|---|---|---|
| T01 | Flooding de un usuario | Cloud Armor + `SpikeArrest` + `LLMTokenQuota` | Tokens gastados por el atacante, % de 429 |
| T02 | Pregunta que fuerza contexto masivo | `PromptTokenLimit` + tope de 5 fragmentos | `tokens_entrada` por petición |
| T03 | Repetir la misma pregunta | Caché semántica | Tasa de aciertos de caché, latencia |
| T04 | Ráfaga de muchos usuarios | Cloud Armor (JA4, ASN), reCAPTCHA, presupuesto global | Costo total estimado, peticiones que llegan al LLM |
| T05 | Usuario legítimo durante el ataque | Cuotas por sesión e IP aíslan al atacante | Latencia p95 y % de éxito del usuario legítimo |

**Lo que ganamos:** los controles ya no comparten proceso con la API atacada, la identidad no se puede falsificar desde el body y el gasto se corta en el borde.

**Lo que cuesta:** más servicios que configurar y pagar; hay que revisar si Apigee ofrece una organización de evaluación antes de desplegar.

**Riesgos residuales:**

- Sin login, un atacante puede abrir muchas sesiones desde IPs distintas (proxies) y cada una gasta dentro de su cuota. Lo frena el tope global y la huella TLS, no la cuota por sesión. Si agota el tope global el chatbot se cae para todos: se cambia *denial of wallet* por una denegación de servicio acotada y barata.
- La caché semántica puede devolver una respuesta de otro usuario si la pregunta tenía datos personales. Solo se cachean preguntas sobre material del curso.
- La estimación de tokens antes de llamar al LLM es aproximada; el descuento real se hace con la respuesta.
- Hermes Agent es open source y tiene acceso a herramientas; corre con cuenta de servicio de mínimo privilegio y solo con tools registradas.

**Pregunta abierta:** ¿la demo final corre en Google Cloud, en Azure (crédito de Azure for Students) o se simula en laptop con un gateway open source? Define qué columna de la tabla de componentes se implementa.

## Viabilidad con créditos de estudiante

Con créditos de estudiante se puede desplegar casi toda la arquitectura, pero no los modelos de terceros: Claude (y en Google cualquier modelo de un socio) no se paga con crédito, solo con tarjeta. La demo con créditos queda con un proveedor propio de cada nube: Gemini en Google o Azure OpenAI en Azure.

| Programa | Crédito | ¿Tarjeta? | Qué bloquea |
|---|---|---|---|
| Google Cloud, créditos de docencia | Lo pide el profesor por curso; vale 12 meses | No | No está claro si cubren Marketplace o modelos de socios (Claude en Vertex); confirmar con CloudEduGrants@google.com |
| Google Cloud, prueba gratuita | USD 300 por 90 días | Sí | Sin Marketplace, sin modelos de terceros, sin aumento de cuotas |
| Azure for Students | USD 100 por 12 meses, renovable | No | No paga Marketplace ni terceros; Claude en Foundry excluye cuentas de estudiante; unas cinco regiones por suscripción |

Otras restricciones:

- **Apigee:** organización de evaluación de 60 días gratis; el plan pago arranca cerca de USD 365/mes por región según un comparador externo (verificar el precio oficial).
- **Azure API Management:** `llm-token-limit` no está en el nivel Consumption; se necesita al menos Developer. El soporte para la API de Anthropic solo está en los niveles v2.
- **OpenAI directo:** requiere API key con pago aparte; ningún crédito de estudiante la cubre.

**Recomendación:** pedirle al profesor los créditos de docencia de Google, usar la organización de evaluación de Apigee durante la demo y dejar Gemini como modelo principal. Los otros proveedores quedan en el diseño como rutas de failover, documentadas pero no desplegadas.

## Referencias

- OWASP LLM10:2025 Unbounded Consumption
- OWASP API4:2023 Unrestricted Resource Consumption
- Hands-On Architects: Denial of Wallet, cost-aware rate limiting
- Apigee: capacidades de AI gateway; políticas PromptTokenLimit, LLMTokenQuota y SemanticCacheLookup
- Model Armor: visión general e integración con Apigee
- Cloud Armor: rate limiting
- Agent Gateway en Gemini Enterprise Agent Platform (codelab)
- Anuncios de seguridad de Google Cloud Next 2026
- Hermes Agent (Nous Research)
- Azure API Management: AI gateway y política llm-content-safety; Azure Front Door WAF: rate limiting
- Claude GA en Microsoft Foundry (Redmond Magazine); Defender for Cloud para cargas de IA; Azure for Students

Los enlaces completos están en el PDF.
