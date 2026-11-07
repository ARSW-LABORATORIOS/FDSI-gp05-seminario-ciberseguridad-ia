## Calibración con gemini (gemini-3.5-flash-lite)

Preguntas: 30, correctas: 30, cortadas por el tope de salida: 0
Tokens por pregunta: mediana 431, p95 736, máximo 763
Errores del proveedor: 0
Latencia: mediana 1.15 s, p95 3.85 s (el modelo: mediana 1.06 s, la búsqueda: 0.049 s)

| Variable sugerida          | Valor   |
|----------------------------|---------|
| TOKEN_RESERVE_PER_QUESTION | 1.200   |
| QUOTA_TOKENS_SESSION       | 23.000  |
| QUOTA_TOKENS_IP_DAY        | 86.000  |
| QUOTA_TOKENS_GLOBAL_DAY    | 260.000 |
| QUOTA_TOKENS_IP_AHORRO     | 3.600   |
| LLM_RPM_GLOBAL             | 13      |
| LLM_RPM_POR_IP             | 4       |

## Calibración con ollama (qwen2.5:1.5b)

Preguntas: 30, correctas: 28, cortadas por el tope de salida: 1
Tokens por pregunta: mediana 538, p95 904, máximo 986
Errores del proveedor: 0
Latencia: mediana 0.69 s, p95 2.55 s (el modelo: mediana 0.62 s, la búsqueda: 0.049 s)

| Variable sugerida          | Valor   |
|----------------------------|---------|
| TOKEN_RESERVE_PER_QUESTION | 1.300   |
| QUOTA_TOKENS_SESSION       | 28.000  |
| QUOTA_TOKENS_IP_DAY        | 107.000 |
| QUOTA_TOKENS_GLOBAL_DAY    | 330.000 |
| QUOTA_TOKENS_IP_AHORRO     | 3.900   |

## Calibración con simulado (simulado)

Preguntas: 30, correctas: no aplica, cortadas por el tope de salida: 0
Tokens por pregunta: mediana 489, p95 761, máximo 764
Errores del proveedor: 0
Latencia: mediana 0.33 s, p95 0.38 s (el modelo: mediana 0.26 s, la búsqueda: 0.046 s)

| Variable sugerida          | Valor   |
|----------------------------|---------|
| TOKEN_RESERVE_PER_QUESTION | 1.000   |
| QUOTA_TOKENS_SESSION       | 23.000  |
| QUOTA_TOKENS_IP_DAY        | 98.000  |
| QUOTA_TOKENS_GLOBAL_DAY    | 300.000 |
| QUOTA_TOKENS_IP_AHORRO     | 3.000   |

## gemini (gemini-3.5-flash-lite)  2026-11-07T04:58

| Prueba                                        | Sin controles  | Con controles | Cambio |
|-----------------------------------------------|----------------|---------------|--------|
| T01 Flooding 60 s, tokens                     | 73.200         | 1.524         | -97,9% |
|     llamadas que llegaron al modelo           | 41             | 4             | -90,2% |
|     rechazadas por el proveedor               | 1.645          | 0             |        |
| T04 Ráfaga 30 IP 120 s, tokens                | 121.018        | 10.969        | -90,9% |
|     llamadas que llegaron al modelo           | 68             | 27            | -60,3% |
|     rechazadas por el proveedor               | 3.327          | 0             |        |
| T02 "Resume todo", tokens                     | 1.735          | 862           | -50,3% |
|     tokens de entrada (lo que sí controlamos) | 1.726          | 566           | -67,2% |
|     fragmentos enviados                       | 15             | 4             |        |
|     prompt gigante, tokens                    | 3.403          | 0 (HTTP 400)  |        |
| T03 Pregunta repetida, tokens                 | 14.038         | 669           | -95,2% |
|     aciertos de caché (igual/reformulada)     | 0/4, 0/3       | 4/4, 3/3      |        |
| T05 Estudiantes respondidos con ataque        | 0.0%           | 100.0%        |        |
|     latencia p95 sin ataque                   | 5.2 s          | 4.361 s       |        |
|     latencia p95 con ataque                   | sin respuestas | 2.403 s       |        |
|     muestras con ataque                       | 0              | 27            |        |

T04, estudiante respondido durante el ataque: sin controles 0.0%, con controles 66.7%
T04, estudiante nuevo después del ataque: HTTP 200

## ollama (qwen2.5:1.5b)  2026-11-07T05:47

| Prueba                                        | Sin controles | Con controles | Cambio |
|-----------------------------------------------|---------------|---------------|--------|
| T01 Flooding 60 s, tokens                     | 100.514       | 3.758         | -96,3% |
|     llamadas que llegaron al modelo           | 47            | 6             | -87,2% |
|     rechazadas por el proveedor               | 0             | 0             |        |
| T04 Ráfaga 30 IP 120 s, tokens                | 171.497       | 20.651        | -88,0% |
|     llamadas que llegaron al modelo           | 80            | 33            | -58,8% |
|     rechazadas por el proveedor               | 0             | 0             |        |
| T02 "Resume todo", tokens                     | 2.431         | 870           | -64,2% |
|     tokens de entrada (lo que sí controlamos) | 1.918         | 648           | -66,2% |
|     fragmentos enviados                       | 15            | 4             |        |
|     prompt gigante, tokens                    | 4.116         | 0 (HTTP 400)  |        |
| T03 Pregunta repetida, tokens                 | 16.031        | 727           | -95,5% |
|     aciertos de caché (igual/reformulada)     | 0/4, 0/3      | 4/4, 3/3      |        |
| T05 Estudiantes respondidos con ataque        | 100.0%        | 100.0%        |        |
|     latencia p95 sin ataque                   | 1.991 s       | 1.295 s       |        |
|     latencia p95 con ataque                   | 47.743 s      | 3.096 s       |        |
|     muestras con ataque                       | 15            | 27            |        |

T04, estudiante respondido durante el ataque: sin controles 0.0%, con controles 66.7%
T04, estudiante nuevo después del ataque: HTTP 200

## simulado (simulado)  2026-11-07T06:26

| Prueba                                        | Sin controles | Con controles | Cambio |
|-----------------------------------------------|---------------|---------------|--------|
| T01 Flooding 15 s, tokens                     | 792.894       | 1.362         | -99,8% |
|     llamadas que llegaron al modelo           | 411           | 3             | -99,3% |
|     rechazadas por el proveedor               | 0             | 0             |        |
| T04 Ráfaga 30 IP 120 s, tokens                | 7.280.519     | 208.632       | -97,1% |
|     llamadas que llegaron al modelo           | 3.774         | 447           | -88,2% |
|     rechazadas por el proveedor               | 0             | 0             |        |
| T02 "Resume todo", tokens                     | 1.942         | 652           | -66,4% |
|     tokens de entrada (lo que sí controlamos) | 1.457         | 490           | -66,4% |
|     fragmentos enviados                       | 15            | 4             |        |
|     prompt gigante, tokens                    | 4.708         | 0 (HTTP 400)  |        |
| T03 Pregunta repetida, tokens                 | 15.404        | 648           | -95,8% |
|     aciertos de caché (igual/reformulada)     | 0/4, 0/3      | 4/4, 3/3      |        |
| T05 Estudiantes respondidos con ataque        | 100.0%        | 100.0%        |        |
|     latencia p95 sin ataque                   | 0.324 s       | 0.336 s       |        |
|     latencia p95 con ataque                   | 0.721 s       | 0.432 s       |        |
|     muestras con ataque                       | 9             | 9             |        |

T04, estudiante respondido durante el ataque: sin controles 100.0%, con controles 100.0%
T04, estudiante nuevo después del ataque: HTTP 200
