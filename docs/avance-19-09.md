# Avance 19/09

Desde que entregamos la propuesta el 05/09 no hemos hecho ninguna otra entrega formal. Esta semana nos pusimos a investigar antes de armar nada. Así no terminábamos construyendo algo que tocara cambiar después.

## Investigación

Miramos cómo han resuelto este tipo de ataques en otros proyectos y qué recomiendan las guías de seguridad que ya existen. El OWASP GenAI Security Project tiene un documento llamado "LLM10:2025 Unbounded Consumption" (https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/). Ahí explican justo el riesgo que nos tocó a nosotros y cómo pasó de llamarse "Model Denial of Service" en 2023 a incluir también el gasto económico. Eso lo llaman "denial of wallet".

También revisamos el OWASP API Security Top 10 en la parte de "API4:2023 Unrestricted Resource Consumption" (https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/). De ahí entendimos que no basta con limitar por IP o por cantidad de peticiones. Hay que limitar por lo que de verdad se está consumiendo.

Y encontramos un artículo de Hands-On Architects llamado "Denial of Wallet: Cost-Aware Rate Limiting for Generative AI Applications" (https://handsonarchitects.com/blog/2025/denial-of-wallet-cost-aware-rate-limiting-part-1/). De ahí sacamos la idea de usar un Token Bucket que cuente tokens reales en vez de solo peticiones.

## Qué nos pareció la mejor opción

Pensamos que la mejor combinación para la parte Secure era un rate limiter que cuente tokens de verdad usando Redis. No solo peticiones, porque una pregunta corta y una larga no cuestan lo mismo. Y una caché que compare el significado de la pregunta y no el texto exacto. Así no gastamos de nuevo en algo que ya se respondió antes con otras palabras.

También consideramos meter algo como vLLM para que la inferencia fuera más eficiente. Esto salió de la investigación que hizo un compañero. Pero necesita GPU y no tenemos, así que no era viable para nosotros. Mejor nos quedamos con algo que sí podamos correr en una laptop normal.

## Estructura que dejamos armada

Con esas decisiones ya armamos el esqueleto del código en el repo. Así cada uno completa su parte sin tener que pensar en cómo organizar todo desde cero:

```
common/
  rag.py            (clase DocumentRetriever)
  llm_client.py     (funciones ask_llm y count_tokens)
unsecure/
  main.py           (backend sin controles)
secure/
  main.py           (backend con controles)
  rate_limiter.py   (clase RateLimiter)
  semantic_cache.py (clase SemanticCache)
tests/
  locustfile.py             (pruebas T01, T04, T05)
  test_context_and_cache.py (pruebas T02, T03)
```

`DocumentRetriever` está en `common/rag.py` y busca en los documentos del curso los que tienen que ver con la pregunta. Es la misma clase para unsecure y secure. Lo único que cambia es cuántos documentos le dejamos traer de una vez.

`ask_llm` está en `common/llm_client.py`. Arma el prompt con la pregunta y lo que encontró el RAG, y llama al modelo. También cuenta los tokens que costó para poder medirlo en las pruebas.

`RateLimiter` está en `secure/rate_limiter.py`. Lleva la cuenta de cuántos tokens se ha gastado cada estudiante en el día usando Redis. Si ya se pasó, rechaza la pregunta. Esto es lo que evita el gasto descontrolado.

`SemanticCache` está en `secure/semantic_cache.py`. Guarda preguntas ya respondidas. Si alguien pregunta algo parecido aunque no sea el mismo texto, responde desde ahí sin volver a gastar en el LLM.

`unsecure/main.py` y `secure/main.py` son los que juntan todo eso en un endpoint `/ask`. La diferencia es que `secure` pasa la pregunta por el `RateLimiter` y la `SemanticCache` antes de llegar al LLM, y `unsecure` no.

## Monolito, API o microservicios

Cada arquitectura (unsecure y secure) va a ser una sola API con FastAPI, organizada por dentro en clases separadas: `RateLimiter`, `SemanticCache` y `DocumentRetriever`. Lo que estamos comparando es el comportamiento de la misma app con y sin esos controles, así que tenerlos como clases dentro de una sola API nos deja medir y aislar cada uno por separado, sin meter de por medio la latencia ni los posibles fallos de red que aparecerían si cada control fuera un servicio aparte.

Redis sí corre por fuera, en su propio contenedor con Docker. Eso no es negociable: el conteo de tokens tiene que ser compartido entre todas las peticiones que le lleguen a la API, y eso no se puede guardar solo en la memoria de un proceso de Python.
