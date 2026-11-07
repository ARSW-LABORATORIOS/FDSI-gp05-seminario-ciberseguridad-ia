"""
Capa 2 del ADR: sin login, la identidad es una sesión anónima firmada. ALTCHA reemplaza a
reCAPTCHA: es una prueba de trabajo que resuelve el navegador, sin servicios externos ni
rastreo. No detiene a un atacante decidido, pero le cobra CPU por cada sesión que abre.

Con CAPTCHA_ENABLED=false la sesión se entrega sin reto (para pruebas de carga y demos).
La firma y las cuotas siguen aplicando igual.
"""

import hashlib
import os
import random
import secrets
import time

import altcha
import jwt

CAPTCHA_ENABLED = os.getenv("CAPTCHA_ENABLED", "true").strip().lower() in ("1", "true", "si", "sí", "yes", "on")
SESSION_SECRET = os.environ["SESSION_SECRET"]
ALTCHA_KEY = os.environ["ALTCHA_HMAC_KEY"]
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
ALTCHA_COST = int(os.getenv("ALTCHA_COST", "500"))
ALTCHA_CONTADOR_MIN = int(os.getenv("ALTCHA_COUNTER_MIN", "2000"))
ALTCHA_CONTADOR_MAX = int(os.getenv("ALTCHA_COUNTER_MAX", "6000"))
RETO_TTL = 300


def crear_reto() -> dict:
    # con `counter` el servidor calcula una sola derivación; el cliente tiene que probar
    # miles hasta llegar a ese contador, así el trabajo cae en quien pide la sesión
    return altcha.create_challenge(
        "PBKDF2/SHA-256",
        ALTCHA_COST,
        counter=random.randint(ALTCHA_CONTADOR_MIN, ALTCHA_CONTADOR_MAX),
        expires_at=int(time.time()) + RETO_TTL,
        hmac_secret=ALTCHA_KEY,
        hmac_key_secret=ALTCHA_KEY,
    ).to_dict()


def verificar_reto(payload: str, redis_client) -> bool:
    try:
        resultado = altcha.verify_solution(payload, ALTCHA_KEY, hmac_key_secret=ALTCHA_KEY)
    except Exception:  # payload malformado: base64 o JSON inválidos
        return False
    if not resultado.verified:
        return False
    # cada solución sirve una sola vez; si no, se podría abrir muchas sesiones con un solo reto
    huella = hashlib.sha256(payload.encode()).hexdigest()
    return bool(redis_client.set(f"altcha:usado:{huella}", 1, nx=True, ex=RETO_TTL))


def crear_sesion() -> dict:
    ahora = int(time.time())
    claims = {"sub": secrets.token_urlsafe(16), "iat": ahora, "exp": ahora + SESSION_TTL}
    return {"token": jwt.encode(claims, SESSION_SECRET, algorithm="HS256"), "expira_en": SESSION_TTL}


def validar_sesion(authorization: str | None) -> str | None:
    """Devuelve el sub si el token es auténtico y no ha vencido; si no, None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        claims = jwt.decode(authorization[7:], SESSION_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.InvalidTokenError:
        return None
    return claims["sub"]
