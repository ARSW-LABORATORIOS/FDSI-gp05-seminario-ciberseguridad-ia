# Seguridad del proyecto — evidencia del laboratorio

## 1. Alcance autorizado
- Repositorio: https://github.com/ARSW-LABORATORIOS/FDSI-gp05-seminario-ciberseguridad-ia
- Rama evaluada: `security/lab-fsi`
- URL de staging propio (si aplica): N/A
- Responsable / autorización: GP-05 / 2026
- Fuera de alcance: producción, sistemas de terceros, datos reales y pruebas destructivas.

## 2. Línea base y herramientas

| Herramienta | Tipo | Fecha | Resultado | Enlace a evidencia |
|---|---|---|---|---|
| Semgrep | SAST | 2026 | Ver artefacto `resultado-semgrep` | Actions → Seguridad estática |
| Gitleaks CLI | Secretos | 2026 | Sin secretos detectados | Actions → Seguridad estática |
| Dependabot | SCA | 2026 | 1 crítica, 1 moderada | Ver sección 3 |
| OWASP ZAP Baseline | DAST pasivo | 2026 | 9 WARN antes / 6 WARN después | `docs/images/zap-report.html` |

> **Limitación Gitleaks:** `gitleaks/gitleaks-action@v3` requiere `GITLEAKS_LICENSE` en repositorios de organizaciones. Se usa Gitleaks CLI directamente como alternativa. GitHub secret scanning no está disponible en el plan actual de la organización.

> **Limitación DAST:** No se cuenta con staging HTTPS propio. Se documenta como alternativa pendiente.

## 3. Hallazgos y gestión

| ID | Categoría | Descripción | Riesgo | Archivo/ruta | Cambio propuesto | Estado |
|---|---|---|---|---|---|---|
| F-01 | SCA | sentence-transformers < 5.6.0 permite ejecución de código arbitrario al cargar modelos locales | Crítico | requirements.txt | Actualizar a 5.6.0 | Corregido |
| F-02 | SCA | python-dotenv < 1.2.2 permite sobreescritura de archivos arbitrarios via symlink | Moderado | requirements.txt | Actualizar a 1.2.2 | Corregido |

### Evidencia F-01 — sentence-transformers (Critical)

![Critical 1](images/Critical%201.png)

### Evidencia F-02 — python-dotenv (Moderate)

![Moderate 1](images/Moderate%201.png)
![Moderate 2](images/Moderate%202.png)
![Moderate 3](images/Moderate%203.png)
![Moderate 4](images/Moderate%204.png)
![Moderate 5](images/Moderate%205.png)
![Moderate 6](images/Moderate%206.png)

| F-03 | DAST | Headers de seguridad HTTP faltantes (X-Frame-Options, CSP, COEP, etc) | Media | `chatbot/main.py` | Agregar middleware de headers | Corregido |

- Evidencia inicial: capturas en `docs/images/`
- Pull request con corrección: `security/lab-fsi` — commit `fix(deps): actualizar sentence-transformers 3.1.1->5.6.0 y python-dotenv 1.0.1->1.2.2`
- Evidencia de reescaneo: Dependabot alerts cerradas automáticamente tras el fix
- Riesgo residual: ninguno para estos dos hallazgos

## 5. Pentest autorizado
- Hipótesis: N/A — sin staging disponible
- Entorno de pruebas aislado: N/A
- Solicitudes inocuas y respuestas observadas: N/A
- Resultado: no aplicable en este ciclo
- Recomendación: desplegar staging local con Docker para habilitar DAST en próxima iteración
