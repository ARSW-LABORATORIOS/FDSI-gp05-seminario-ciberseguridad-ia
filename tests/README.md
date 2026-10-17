# Pruebas

- `locustfile.py` — T01 (flooding), T04 (ráfaga multiusuario) y T05 (usuario legítimo bajo ataque). Se corre con Locust.
- `test_context_and_cache.py` — T02 (contexto masivo) y T03 (repetición para probar caché). Se corre directo con `python`.

Cada una se corre dos veces: una vez contra `unsecure` y otra contra `secure`, para poder comparar los números.

## Qué capa debe frenar cada prueba (ADR-001)

Cada prueba tiene que mostrar que el ataque se frena en una capa concreta y antes de llegar al LLM.

| Prueba | Ataque | Capa que debe frenarlo | Métrica Unsecure vs Secure |
|---|---|---|---|
| T01 | Flooding de un usuario | Cloud Armor + `SpikeArrest` + `LLMTokenQuota` | Tokens gastados por el atacante, % de 429 |
| T02 | Pregunta que fuerza contexto masivo | `PromptTokenLimit` + tope de 5 fragmentos | `tokens_entrada` por petición |
| T03 | Repetir la misma pregunta | Caché semántica | Tasa de aciertos de caché, latencia |
| T04 | Ráfaga de muchos usuarios | Cloud Armor (JA4, ASN), reCAPTCHA, presupuesto global | Costo total estimado, peticiones que llegan al LLM |
| T05 | Usuario legítimo durante el ataque | Cuotas por sesión e IP aíslan al atacante | Latencia p95 y % de éxito del usuario legítimo |

En el laboratorio (FastAPI + Redis) solo existen el rate limiter, la caché y el tope de fragmentos, así que T01, T02, T03 y T05 se pueden medir hoy. T04 también se puede correr, pero va a mostrar el hueco: sin borde ni identidad, un atacante con muchos `usuario_id` distintos esquiva la cuota por usuario. Los valores de cuota del ADR (tokens por día, tope de pasos) se calibran con los resultados de estas pruebas.
