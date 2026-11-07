# Arquitectura segura con piezas open source

Implementa en Docker Compose la arquitectura del [ADR-001](../docs/ADR-001-arquitectura-segura.md) sin servicios de pago. El porqué de cada pieza, sus límites y los resultados están en el [ADR-002](../docs/ADR-002-alternativa-open-source.md).

Corre en una laptop con Docker: 10 contenedores, unos 3 GB de RAM y 7 GB de disco para las imágenes (sin contar Ollama y su modelo). El primer arranque tarda unos minutos: construye imágenes y LiteLLM demora cerca de un minuto en quedar listo.

## Cómo levantarlo

Desde esta carpeta (`infra/`):

```bash
python crear_env.py
```

```bash
docker compose up -d --build
```

Con eso quedan:

| Dirección | Qué es |
|---|---|
| http://localhost:8080 | El chatbot, entrando por el borde |
| http://localhost:3000 | Grafana (usuario `admin`, la clave está en `infra/.env`) |
| http://localhost:9090/alerts | Alertas de Prometheus |

Para apagarlo:

```bash
docker compose --profile pruebas --profile ollama down
```

## Interruptores

Se cambian en `infra/.env` y se aplican con `docker compose up -d`.

| Variable | Valores | Para qué |
|---|---|---|
| `CAPTCHA_ENABLED` | `true` / `false` | Prende o apaga la verificación ALTCHA. Las firmas y las cuotas siguen activas |
| `GEMINI_API_KEY` | Tu llave | Para usar Gemini. Solo llega a LiteLLM o al medidor, y `.env` no se sube a git |

## Perfiles: con qué modelo corre

Cada perfil de `perfiles/` trae el modelo y las cuotas calibradas para él. Sin perfil, `docker compose up -d` usa el LLM simulado.

| Perfil | Modelo | Cuándo usarlo |
|---|---|---|
| `perfiles/gemini.env` | Gemini 3.5 Flash-Lite, con el local de respaldo | La demo: acertó 30 de 30 preguntas |
| `perfiles/ollama.env` | Qwen2.5 1.5B en la GPU | Sin internet ni llave. Inventó un dato en 30 preguntas |
| `perfiles/simulado.env` | Simulado | Probar los controles, sin gasto ni GPU |

Para el chatbot con Gemini y respaldo local (si no hay GPU NVIDIA, quitar los dos `-f`):

```bash
docker compose --env-file .env --env-file perfiles/gemini.env -f docker-compose.yml -f docker-compose.gpu.yml --profile ollama up -d --build
```

La primera vez hay que descargar el modelo local. Después de eso, sin calentarlo, su primera respuesta puede tardar más de dos minutos:

```bash
docker compose --profile ollama exec ollama ollama pull qwen2.5:1.5b
```

```bash
docker compose --profile ollama exec ollama ollama run qwen2.5:1.5b "hola"
```

La capa gratuita de Gemini da 15 llamadas por minuto y 500 al día por modelo. Google [puede usar ese contenido](https://aistudio.google.com/docs/pricing) para mejorar sus productos: revisar eso antes de cargar documentos reales.

## Cómo probarlo

Un solo comando levanta todo, corre las pruebas e imprime las tablas de resultados:

```bash
python medir.py --modelo gemini
```

| Comando | Qué hace | Tarda |
|---|---|---|
| `python medir.py --modelo gemini` | Calibración y T01–T05 con Gemini (unas 340 de las 500 llamadas del día) | Unos 35 min |
| `python medir.py --modelo ollama` | Lo mismo con el modelo local | Unos 35 min |
| `python medir.py --modelo simulado` | Las comprobaciones y T01–T05, sin modelo real | Unos 15 min |
| `python medir.py --resumen` | Vuelve a mostrar los últimos resultados, sin correr nada | Segundos |

Opciones: `--rapido` (solo calibración, T02 y T03), `--solo-calibrar`, `--sin-calibrar`, `--pruebas T01,T05`, `--versiones secure`, `--gemini-modelo gemini-3.1-flash-lite`, `--apagar`.

Los resultados quedan en `pruebas/resultados/`: `<modelo>.json`, `calibracion-<modelo>.json` y `resumen.md`. En `extra/` están las corridas intermedias que se citan en el ADR-002. Estas pruebas borran las cuotas y la caché de Valkey.

`calibrar.py` sugiere las cuotas a partir de 30 preguntas reales. Sus supuestos de uso (estudiantes, preguntas al día) están al inicio del archivo: cámbienlos si conocen los datos del curso, y pasen los valores a `perfiles/`.

Con un proveedor real, el medidor cuenta los tokens que él reporta. Si responde 429 con un tiempo de espera, no lo vuelve a llamar hasta que pase, y corta la medición en 2 millones de tokens por si la llave tuviera facturación.

## Qué hay en cada carpeta

| Carpeta | Capa del ADR | Contenido |
|---|---|---|
| `edge/` | 1. Borde | nginx + ModSecurity + OWASP CRS, límite por IP |
| `gateway/` | 2 y 3. Identidad y AI Gateway | Sesión firmada, ALTCHA, cuotas, caché, filtros. Es el único código propio de seguridad |
| `orquestador/` | 4. Orquestador | Topes de fragmentos, pasos, salida y tiempo. También corre como `unsecure` |
| `mcp-cursos/` | 4. RAG | Servidor MCP con Chroma sobre `../course_docs/*.md` |
| `agentgateway/` | 5. Egreso a tools | Lista blanca de herramientas MCP |
| `litellm/` | 5. Egreso a LLMs | Routing y failover. `config.gemini.yaml` para la demo, `config.medicion.yaml` para medir |
| `mock-llm/` | Solo pruebas | LLM simulado o, con `DESTINO_URL`, medidor de tokens reales |
| `perfiles/` | Calibración | Modelo y cuotas para cada caso |
| `observabilidad/` | 6. Detección y costo | Prometheus, alertas y tablero de Grafana |
| `pruebas/` | Validación | Comprobaciones, calibración y ataques T01–T05 |

## Lo que todavía no es

- No sirve HTTPS: el borde escucha en HTTP y solo en `localhost`. Antes de exponerlo hay que poner TLS.
- Es un entorno de laboratorio en una sola máquina: no tiene alta disponibilidad, y un ataque que sature la máquina tumba todo.
- `course_docs/` son los documentos simulados del prototipo, no material real del curso.
- Un ataque lento, repartido entre muchas IP, puede ocupar el cupo de llamadas por minuto: no dispara el límite de ráfagas. No se ha probado ese caso.
