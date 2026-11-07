"""Crea infra/.env a partir de .env.example con secretos aleatorios. No pisa uno que ya exista."""

import secrets
import sys
from pathlib import Path

AQUI = Path(__file__).parent
SECRETOS = ("SESSION_SECRET", "ALTCHA_HMAC_KEY", "LITELLM_MASTER_KEY", "GRAFANA_ADMIN_PASSWORD")

destino = AQUI / ".env"
if destino.exists():
    sys.exit(f"{destino} ya existe: no lo toqué.")

lineas = []
for linea in (AQUI / ".env.example").read_text(encoding="utf-8").splitlines():
    clave = linea.split("=", 1)[0]
    lineas.append(f"{clave}={secrets.token_urlsafe(32)}" if clave in SECRETOS else linea)
destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
print(f"Creado {destino}")
