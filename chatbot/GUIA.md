# Guía para correr el Chatbot Académico

## Requisitos previos

### 1. Instalar Python
- Ve a **https://www.python.org/downloads** y descarga la última versión
- Durante la instalación marca obligatoriamente esta casilla:

  ☑ **Add python.exe to PATH**

- Una vez instalado, abre una terminal nueva y verifica:
  ```bash
  py --version
  ```
  Debe mostrar algo como `Python 3.13.x`

### 2. Instalar Git
- Ve a **https://git-scm.com/downloads** y descarga la versión para Windows
- Instala con las opciones por defecto
- Verifica:
  ```bash
  git --version
  ```

---

## Pasos para correr el chatbot

### 1. Clonar el repositorio
```bash
git clone https://github.com/MabelBernalAmaya/FDSI-gp05-seminario-ciberseguridad-ia.git
```

### 2. Entrar a la carpeta del chatbot
```bash
cd FDSI-gp05-seminario-ciberseguridad-ia/chatbot
```

### 3. Instalar dependencias
```bash
py -m pip install -r requirements.txt
```

### 4. Arrancar el servidor
```bash
py -m uvicorn main:app --reload
```

### 5. Abrir en el navegador
```
http://localhost:8000
```

---

## ¿Qué puedo preguntarle?

El chatbot responde preguntas sobre 4 materias simuladas:

| Materia | Ejemplos de preguntas |
|---|---|
| Arquitectura de Software | "syllabus de arquitectura", "apuntes de MVC", "taller de diagramas C4" |
| Fundamentos de Seguridad | "syllabus de seguridad", "apuntes de CIA", "guía de análisis de riesgos" |
| Matemáticas Básicas | "syllabus de matemáticas", "apuntes de derivadas", "taller de cálculo" |
| Historia de Colombia | "syllabus de historia", "apuntes de independencia", "guía del ensayo" |

También puedes usar los chips de sugerencias que aparecen encima del campo de texto.

---

## Solución de problemas

**`py` no se reconoce** → Python no está instalado o no se marcó "Add to PATH". Reinstala Python marcando esa casilla.

**`git` no se reconoce** → Git no está instalado. Descárgalo de https://git-scm.com/downloads

**El servidor arranca pero el navegador no carga** → Asegúrate de abrir `http://localhost:8000` y no `https://`.

**Error al instalar dependencias** → Asegúrate de estar dentro de la carpeta `chatbot/` antes de correr el comando.
