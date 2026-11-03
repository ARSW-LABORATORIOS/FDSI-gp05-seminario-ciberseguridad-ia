# Informe técnico de hallazgos

**Proyecto:** FDSI-GP-05: Seminario de Ciberseguridad en IA
**Integrantes:** Mabel Bernal, Juan Pablo Vélez, Esteban Caicedo, Nicolás Prieto
**Repositorio / commit:** https://github.com/ARSW-LABORATORIOS/FDSI-gp05-seminario-ciberseguridad-ia / rama `security/lab-fsi`
**Entorno autorizado:** Repositorio propio de laboratorio, sin staging externo
**Fecha:** 2026

## Resumen ejecutivo

Se identificaron dos vulnerabilidades en dependencias directas del proyecto mediante análisis SCA con Dependabot. La más crítica permite ejecución de código arbitrario al cargar modelos locales con `sentence-transformers`, lo que representa un riesgo directo para la confidencialidad e integridad del sistema. La segunda permite sobreescritura de archivos arbitrarios via symlink en `python-dotenv`, afectando la integridad y disponibilidad. Ambas fueron corregidas actualizando a las versiones parcheadas en el mismo PR del laboratorio.

## Metodología

Identificación del alcance → SAST (Semgrep) → detección de secretos (Gitleaks CLI) → SCA (Dependabot) → validación manual no destructiva → corrección → reescaneo.

---

## Hallazgo F-01

- **Título:** sentence-transformers — ejecución de código arbitrario al cargar modelos locales
- **Categoría OWASP/CWE:** CWE-284 (Improper Access Control) / OWASP A05:2021 Security Misconfiguration
- **Severidad:** Crítica
- **Justificación:** Un atacante que controle el contenido de un directorio de modelos en disco puede colocar archivos Python maliciosos referenciados via `modules.json`. Al cargar el modelo con `SentenceTransformer(path, trust_remote_code=False)`, el código se ejecuta en tiempo de importación, ignorando el argumento `trust_remote_code=False`.
- **Evidencia:**

  ![Critical 1](images/Critical%201.png)

- **Versión afectada:** `sentence-transformers < 5.6.0`
- **Versión parcheada:** `5.6.0`
- **Impacto:**
  - Confidencialidad: Alto — el atacante puede exfiltrar datos del proceso
  - Integridad: Alto — puede modificar el comportamiento del modelo
  - Disponibilidad: Medio — puede interrumpir el servicio
- **Pasos de validación segura en entorno propio:** Verificar que la versión instalada sea >= 5.6.0 con `pip show sentence-transformers`. No reproducir el exploit en entornos reales.
- **Corrección:** Actualización de `sentence-transformers==3.1.1` a `sentence-transformers==5.6.0` en `requirements.txt`
- **Resultado del reescaneo:** Alerta cerrada automáticamente por Dependabot tras el fix

---

## Hallazgo F-02

- **Título:** python-dotenv — sobreescritura de archivos arbitrarios via symlink (cross-device rename)
- **Categoría OWASP/CWE:** CWE-61 (UNIX Symbolic Link Following) / OWASP A01:2021 Broken Access Control
- **Severidad:** Moderada
- **Justificación:** `set_key()` y `unset_key()` siguen enlaces simbólicos al reescribir archivos `.env`. Cuando `/tmp` y el directorio del `.env` están en dispositivos distintos (común en Linux con tmpfs), `shutil.move()` cae en un fallback que escribe en el destino del symlink en lugar de reemplazarlo, permitiendo sobreescribir archivos arbitrarios.
- **Evidencia:**

  ![Moderate 1](images/Moderate%201.png)
  ![Moderate 2](images/Moderate%202.png)
  ![Moderate 3](images/Moderate%203.png)
  ![Moderate 4](images/Moderate%204.png)
  ![Moderate 5](images/Moderate%205.png)
  ![Moderate 6](images/Moderate%206.png)

- **Versión afectada:** `python-dotenv < 1.2.2`
- **Versión parcheada:** `1.2.2`
- **Impacto:**
  - Confidencialidad: Bajo — no expone datos directamente
  - Integridad: Alto — puede corromper archivos de configuración o credenciales
  - Disponibilidad: Medio — puede destruir archivos críticos del sistema
- **Pasos de validación segura en entorno propio:** Verificar versión con `pip show python-dotenv`. La explotación requiere acceso de escritura al directorio del `.env` y `/tmp` en dispositivo distinto; no reproducir en entornos reales.
- **Corrección:** Actualización de `python-dotenv==1.0.1` a `python-dotenv==1.2.2` en `requirements.txt`
- **Resultado del reescaneo:** Alerta cerrada automáticamente por Dependabot tras el fix

---

## Reflexión final

Dependabot identificó de forma automática y precisa las dos vulnerabilidades en dependencias directas, con información detallada de versiones afectadas y parches disponibles. Semgrep y Gitleaks no reportaron hallazgos críticos en el código fuente propio, lo que indica que el riesgo principal del proyecto en este ciclo proviene de la cadena de suministro de software (SCA) y no del código desarrollado internamente. Para integrar seguridad de forma continua al ciclo de desarrollo, se recomienda mantener Dependabot activo con actualizaciones automáticas, agregar un paso de verificación de versiones mínimas en el pipeline CI y establecer un proceso de triage periódico de alertas.
