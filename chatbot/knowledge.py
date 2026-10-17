import re

DOCS = [
    # ── ARQUITECTURA DE SOFTWARE ──────────────────────────────────────────
    {
        "materia": "Arquitectura de Software",
        "tipo": "Syllabus",
        "keywords": ["arquitectura", "software"],
        "contenido": (
            "Syllabus – Arquitectura de Software\n"
            "Corte 1 (30%): Introducción a estilos arquitectónicos, taller de diagramas C4.\n"
            "Corte 2 (35%): Patrones (MVC, Hexagonal, Event-Driven), parcial escrito.\n"
            "Corte 3 (35%): Proyecto final: diseño de una arquitectura real con ADRs.\n"
            "Docente: Ing. Ramírez | Salón: B-204 | Martes y jueves 6-8pm."
        )
    },
    {
        "materia": "Arquitectura de Software",
        "tipo": "Apuntes",
        "keywords": ["mvc", "hexagonal", "capas", "patron", "patrón", "estilos", "componentes", "diagrama", "c4"],
        "contenido": (
            "Apuntes – Patrones Arquitectónicos\n"
            "MVC (Model-View-Controller): separa datos, lógica y presentación. Usado en apps web.\n"
            "Arquitectura Hexagonal (Ports & Adapters): el dominio no depende de frameworks ni BD.\n"
            "Event-Driven: los componentes se comunican por eventos, útil para microservicios.\n"
            "Diagrama C4: 4 niveles — Contexto, Contenedor, Componente, Código.\n"
            "ADR (Architecture Decision Record): documento que registra por qué se tomó una decisión."
        )
    },
    {
        "materia": "Arquitectura de Software",
        "tipo": "Taller",
        "keywords": ["taller arquitectura", "ejercicio arquitectura", "actividad arquitectura"],
        "contenido": (
            "Taller 1 – Diagramas C4\n"
            "1. Dibuja el diagrama de Contexto de una app de biblioteca universitaria.\n"
            "2. Identifica los contenedores: frontend, backend, base de datos.\n"
            "3. Elige un patrón (MVC o Hexagonal) y justifica con un ADR de mínimo 3 párrafos.\n"
            "Entrega: PDF en el aula virtual antes del viernes 11:59pm."
        )
    },

    # ── FUNDAMENTOS DE SEGURIDAD DE LA INFORMACIÓN ───────────────────────
    {
        "materia": "Fundamentos de Seguridad de la Información",
        "tipo": "Syllabus",
        "keywords": ["seguridad", "fdsi", "syllabus seguridad", "programa seguridad", "corte seguridad"],
        "contenido": (
            "Syllabus – Fundamentos de Seguridad de la Información\n"
            "Corte 1 (30%): CIA Triad, amenazas, vulnerabilidades, taller de análisis de riesgos.\n"
            "Corte 2 (35%): Criptografía básica, autenticación, parcial teórico-práctico.\n"
            "Corte 3 (35%): OWASP Top 10, proyecto de auditoría simulada.\n"
            "Docente: Ing. Torres | Salón: A-101 | Lunes y miércoles 4-6pm."
        )
    },
    {
        "materia": "Fundamentos de Seguridad de la Información",
        "tipo": "Apuntes",
        "keywords": ["cia", "confidencialidad", "integridad", "disponibilidad", "amenaza", "vulnerabilidad",
                     "riesgo", "cifrado", "criptografia", "criptografía", "owasp", "autenticacion", "autenticación"],
        "contenido": (
            "Apuntes – Conceptos Clave\n"
            "CIA Triad: Confidencialidad (solo quien debe ver los datos los ve), "
            "Integridad (los datos no se alteran sin autorización), "
            "Disponibilidad (el sistema funciona cuando se necesita).\n"
            "Amenaza: evento que puede causar daño. Vulnerabilidad: debilidad que la amenaza explota.\n"
            "Riesgo = Probabilidad × Impacto.\n"
            "Criptografía simétrica: misma clave para cifrar y descifrar (AES). "
            "Asimétrica: clave pública y privada (RSA).\n"
            "OWASP Top 10 2021: Broken Access Control, Cryptographic Failures, Injection, "
            "Insecure Design, Security Misconfiguration, entre otros."
        )
    },
    {
        "materia": "Fundamentos de Seguridad de la Información",
        "tipo": "Guía",
        "keywords": ["guia seguridad", "guía seguridad", "laboratorio seguridad", "practica seguridad"],
        "contenido": (
            "Guía de Laboratorio – Análisis de Riesgos\n"
            "Objetivo: identificar activos, amenazas y controles en un sistema web.\n"
            "Paso 1: Lista los activos (base de datos, servidor, usuarios).\n"
            "Paso 2: Para cada activo identifica al menos 2 amenazas.\n"
            "Paso 3: Calcula el riesgo (Alto/Medio/Bajo) con la matriz Probabilidad × Impacto.\n"
            "Paso 4: Propón un control para cada riesgo Alto.\n"
            "Entrega individual, máximo 2 páginas."
        )
    },

    # ── MATEMÁTICAS BÁSICAS ───────────────────────────────────────────────
    {
        "materia": "Matemáticas Básicas",
        "tipo": "Syllabus",
        "keywords": ["matematicas", "matemáticas", "syllabus matematicas", "calculo", "cálculo", "algebra", "álgebra"],
        "contenido": (
            "Syllabus – Matemáticas Básicas\n"
            "Corte 1 (30%): Conjuntos, lógica proposicional, números reales, taller de ejercicios.\n"
            "Corte 2 (35%): Funciones, límites, introducción a derivadas, parcial.\n"
            "Corte 3 (35%): Integrales básicas, aplicaciones, examen final.\n"
            "Docente: Prof. Gómez | Salón: C-310 | Lunes, miércoles y viernes 8-10am."
        )
    },
    {
        "materia": "Matemáticas Básicas",
        "tipo": "Apuntes",
        "keywords": ["derivada", "integral", "limite", "límite", "funcion", "función", "conjunto",
                     "logica", "lógica", "proposicion", "proposición"],
        "contenido": (
            "Apuntes – Derivadas e Integrales\n"
            "Derivada: mide la tasa de cambio de una función. d/dx(xⁿ) = n·xⁿ⁻¹.\n"
            "Regla de la cadena: d/dx[f(g(x))] = f'(g(x))·g'(x).\n"
            "Integral definida: área bajo la curva entre dos puntos. ∫f(x)dx.\n"
            "Regla de la potencia: ∫xⁿdx = xⁿ⁺¹/(n+1) + C.\n"
            "Límite: valor al que se acerca f(x) cuando x tiende a un punto. lim(x→a) f(x).\n"
            "Lógica proposicional: AND (∧), OR (∨), NOT (¬), implicación (→), bicondicional (↔)."
        )
    },
    {
        "materia": "Matemáticas Básicas",
        "tipo": "Taller",
        "keywords": ["taller matematicas", "taller matemáticas", "ejercicio matematicas", "ejercicio matemáticas"],
        "contenido": (
            "Taller 2 – Derivadas\n"
            "1. Calcula la derivada de f(x) = 3x⁴ - 2x² + 5.\n"
            "2. Aplica la regla de la cadena a g(x) = (2x+1)³.\n"
            "3. Encuentra los puntos críticos de h(x) = x³ - 6x² + 9x.\n"
            "4. Determina si cada punto crítico es máximo, mínimo o punto de inflexión.\n"
            "Entrega en clase el próximo miércoles, desarrollo a mano."
        )
    },

    # ── HISTORIA DE COLOMBIA ──────────────────────────────────────────────
    {
        "materia": "Historia de Colombia",
        "tipo": "Syllabus",
        "keywords": ["historia", "colombia", "syllabus historia", "programa historia"],
        "contenido": (
            "Syllabus – Historia de Colombia\n"
            "Corte 1 (30%): Período colonial, independencia, ensayo corto.\n"
            "Corte 2 (35%): Siglo XIX, guerras civiles, La Regeneración, parcial.\n"
            "Corte 3 (35%): Siglo XX, Violencia, Frente Nacional, Constitución 1991, proyecto final.\n"
            "Docente: Prof. Herrera | Salón: D-105 | Martes y jueves 2-4pm."
        )
    },
    {
        "materia": "Historia de Colombia",
        "tipo": "Apuntes",
        "keywords": ["independencia", "colonial", "simon bolivar", "simón bolívar", "regeneracion", "regeneración",
                     "violencia", "frente nacional", "constitucion", "constitución", "guerra", "siglo xix", "siglo xx"],
        "contenido": (
            "Apuntes – Hitos de la Historia de Colombia\n"
            "Independencia (1810-1819): el 20 de julio de 1810 es el grito de independencia. "
            "La batalla de Boyacá (1819) consolidó la libertad con Simón Bolívar.\n"
            "La Regeneración (1886): Rafael Núñez impulsó la Constitución de 1886 y el centralismo.\n"
            "La Violencia (1948-1958): conflicto bipartidista tras el Bogotazo (asesinato de Gaitán).\n"
            "Frente Nacional (1958-1974): acuerdo entre liberales y conservadores para alternarse el poder.\n"
            "Constitución de 1991: nueva carta magna, reconoció el Estado Social de Derecho y la diversidad."
        )
    },
    {
        "materia": "Historia de Colombia",
        "tipo": "Guía",
        "keywords": ["guia historia", "guía historia", "ensayo historia", "taller historia"],
        "contenido": (
            "Guía – Ensayo Corte 1\n"
            "Tema: ¿Fue la independencia de Colombia un proceso popular o de élites?\n"
            "Estructura: introducción (contexto), desarrollo (2 argumentos con evidencia histórica), conclusión.\n"
            "Extensión: 2 a 3 páginas, normas APA, fuentes mínimo 3.\n"
            "Criterios: claridad argumentativa 40%, uso de fuentes 30%, redacción 30%.\n"
            "Fecha de entrega: dos semanas antes del parcial."
        )
    },
]

DEFAULT = (
    "No encontré información específica sobre eso. "
    "Puedes preguntarme sobre las materias: **Arquitectura de Software**, "
    "**Fundamentos de Seguridad de la Información**, **Matemáticas Básicas** o **Historia de Colombia**. "
    "Por ejemplo: 'syllabus de matemáticas', 'apuntes de seguridad', 'taller de arquitectura'."
)


# Palabras que indican QUÉ tipo de documento se pide (no de qué materia).
# Antes "syllabus" estaba en las keywords del primer documento, así que cualquier
# pregunta con "syllabus" devolvía el de Arquitectura sin importar la materia.
TIPOS = {
    "Syllabus": ["syllabus", "programa", "corte", "notas", "evaluacion", "evaluación", "parcial", "docente", "horario", "salon", "salón"],
    "Apuntes": ["apuntes", "resumen", "concepto", "teoria", "teoría", "que es", "qué es", "explica", "define", "definicion", "definición"],
    "Taller": ["taller", "ejercicio", "actividad"],
    "Guía": ["guia", "guía", "laboratorio", "practica", "práctica", "ensayo"],
}
# si la materia no tiene el tipo pedido, se usa el equivalente (talleres y guías)
EQUIVALENTE = {"Taller": "Guía", "Guía": "Taller"}


def _contiene(texto: str, palabra: str) -> bool:
    # coincide al inicio de una palabra: "derivadas" activa "derivada",
    # pero "independencia" no activa "cia"
    return re.search(r"(?<!\w)" + re.escape(palabra), texto) is not None


def _tipo_pedido(q: str):
    for tipo, palabras in TIPOS.items():
        if any(_contiene(q, p) for p in palabras):
            return tipo
    return None


def search(question: str) -> dict:
    """Elige la materia con más coincidencias y, dentro de ella, el tipo de documento pedido."""
    q = question.lower()
    puntaje_doc = [sum(len(kw) for kw in doc["keywords"] if _contiene(q, kw)) for doc in DOCS]

    puntaje_materia = {}
    for doc, puntaje in zip(DOCS, puntaje_doc):
        puntaje_materia[doc["materia"]] = puntaje_materia.get(doc["materia"], 0) + puntaje
    materia = max(puntaje_materia, key=puntaje_materia.get)
    if puntaje_materia[materia] == 0:
        return {"answer": DEFAULT, "materia": None, "tipo": None, "contenido": None}

    candidatos = [(doc, p) for doc, p in zip(DOCS, puntaje_doc) if doc["materia"] == materia]
    tipo = _tipo_pedido(q)
    elegido = next((d for d, _ in candidatos if d["tipo"] == tipo), None)
    if elegido is None and tipo in EQUIVALENTE:
        elegido = next((d for d, _ in candidatos if d["tipo"] == EQUIVALENTE[tipo]), None)
    if elegido is None:
        # sin tipo pedido gana la coincidencia más específica; el syllabus solo tiene
        # palabras de la materia ("historia", "arquitectura"), así que va de último
        especificos = [(d, p) for d, p in candidatos if p > 0 and d["tipo"] != "Syllabus"]
        elegido = max(especificos, key=lambda c: c[1])[0] if especificos else candidatos[0][0]

    return {
        "answer": f"📚 {elegido['materia']} — {elegido['tipo']}\n\n{elegido['contenido']}",
        "materia": elegido["materia"],
        "tipo": elegido["tipo"],
        "contenido": elegido["contenido"],
    }
