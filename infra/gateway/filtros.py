"""
Reemplazo básico de Model Armor: reglas para español e inglés, sin modelos ni servicios.

OJO: esto NO equivale a Model Armor. Un atacante que reformule la frase pasa por encima de
una expresión regular. Frena lo evidente y barato, y deja el punto de conexión listo para un
clasificador real (ver ADR-002). LLM Guard, la opción obvia, quedó archivada en julio de 2026.
"""

import re
import unicodedata

INYECCION = [
    r"(ignora|olvida|omite|descarta)\w*\s+(\w+\s+){0,3}(instruccion|indicacion|regla|prompt)",
    r"(ignore|disregard|forget)\s+(\w+\s+){0,3}(instruction|prompt|rule)",
    r"(prompt|instrucciones|mensaje)\s+(del\s+)?sistema",
    r"system\s+prompt",
    r"(revela|muestra|dime|imprime)\s+(\w+\s+){0,2}(instrucciones|prompt)",
    r"(modo|mode)\s+(desarrollador|developer|dan)\b",
    r"\bjailbreak\b",
    r"\bactua\s+como\s+(si|un|una|el|la)\b.*(sin|restric|filtro|limite)",
]
# prompts que buscan respuestas enormes: esto ya es denial of wallet, no solo inyección
GASTO = [
    r"(repite|repeat|escribe|write)\b.*\b\d{3,}\s*(veces|times|palabras|words|paginas|pages)",
    r"\b(infinitamente|sin\s+parar|forever|indefinitely)\b",
]
DATOS_PERSONALES = {
    "correo": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "cedula": r"\b(cedula|cc|documento)\D{0,12}\d{6,10}\b",
    "enlace": r"https?://\S+",
}
SECRETOS_SALIDA = [
    r"\bsk-[A-Za-z0-9_-]{16,}\b",
    r"\bAIza[A-Za-z0-9_-]{30,}\b",
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b",
]
CORREO = re.compile(DATOS_PERSONALES["correo"])


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def _luhn(digitos: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(digitos)):
        n = int(c)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def revisar_entrada(pregunta: str) -> str | None:
    """Equivale a SanitizeUserPrompt. Devuelve el motivo del bloqueo, o None si pasa."""
    texto = _normalizar(pregunta)
    if any(re.search(p, texto) for p in INYECCION):
        return "posible inyección de prompt"
    if any(re.search(p, texto) for p in GASTO):
        return "petición diseñada para generar una respuesta enorme"
    for nombre, patron in DATOS_PERSONALES.items():
        if re.search(patron, texto):
            return f"la pregunta incluye un dato sensible ({nombre})"
    for numero in re.findall(r"(?:\d[ -]?){13,19}", texto):
        digitos = re.sub(r"\D", "", numero)
        if 13 <= len(digitos) <= 19 and _luhn(digitos):
            return "la pregunta incluye un dato sensible (tarjeta)"
    return None


def limpiar_salida(respuesta: str) -> str:
    """Equivale a SanitizeModelResponse: tacha secretos y correos antes de responder."""
    for patron in SECRETOS_SALIDA:
        respuesta = re.sub(patron, "[oculto]", respuesta)
    return CORREO.sub("[correo oculto]", respuesta)
