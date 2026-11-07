"""
Equivalente abierto de SpikeArrest y LLMTokenQuota (capa 3 del ADR). Cuenta en Valkey, fuera
del proceso de la API.

A diferencia de secure/rate_limiter.py, que primero lee y después suma, aquí se RESERVA el
estimado de forma atómica antes de llamar al LLM y luego se ajusta con lo gastado de verdad.
Si no, 50 peticiones simultáneas pasarían todas el chequeo antes de que la primera descuente.
"""

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

CUOTA_SESION = int(os.getenv("QUOTA_TOKENS_SESSION", "20000"))
CUOTA_IP = int(os.getenv("QUOTA_TOKENS_IP_DAY", "60000"))
CUOTA_GLOBAL = int(os.getenv("QUOTA_TOKENS_GLOBAL_DAY", "300000"))
SPIKE_MAX = int(os.getenv("SPIKE_MAX_REQUESTS", "5"))
SPIKE_VENTANA = int(os.getenv("SPIKE_WINDOW_SECONDS", "10"))
SESIONES_IP_HORA = int(os.getenv("SESSIONS_PER_IP_HOUR", "20"))
# Llamadas al modelo por minuto. 0 = sin límite. Sirven cuando el proveedor limita por minuto:
# en la capa gratuita de Gemini basta una sesión a 30 por minuto para dejar sin servicio a todos.
RPM_GLOBAL = int(os.getenv("LLM_RPM_GLOBAL", "0"))
RPM_IP = int(os.getenv("LLM_RPM_POR_IP", "0"))
# Una IP que ya fue frenada por abuso solo compite por esta parte del cupo global. El resto queda
# para las conexiones limpias: con 30 IP atacando, si no, el estudiante nunca encontraba cupo.
# No sirve contra un ataque lento y distribuido que nunca dispare el límite de ráfagas.
RPM_SOSPECHOSA_PCT = int(os.getenv("LLM_RPM_SOSPECHOSA_PCT", "50"))
SOSPECHA_SEGUNDOS = 300
# Modo de ahorro: pasado este % del tope global, cada IP solo puede llegar a CUOTA_IP_AHORRO. Quien
# ya gastó mucho queda fuera y el resto del presupuesto queda para los que apenas llegan. Sin esto,
# un ataque con muchas IP agotaba el tope y un estudiante nuevo recibía 429 (el riesgo del ADR).
AHORRO_PCT = int(os.getenv("QUOTA_AHORRO_PCT", "80"))
CUOTA_IP_AHORRO = int(os.getenv("QUOTA_TOKENS_IP_AHORRO", "4000"))

DIA = 86400

# Revisa los tres topes y, solo si caben todos, suma en los tres. Valkey ejecuta el script
# completo sin intercalar otras peticiones, por eso no hay carrera entre el chequeo y la suma.
RESERVAR = """
local costo = tonumber(ARGV[1])
local global = tonumber(redis.call('GET', KEYS[3]) or '0')
local ahorro = global + costo > tonumber(ARGV[6])
local tope_ip = tonumber(ARGV[3])
if ahorro then tope_ip = math.min(tope_ip, tonumber(ARGV[7])) end
local topes = {tonumber(ARGV[2]), tope_ip, tonumber(ARGV[4])}
for i = 1, 3 do
  local gastado = tonumber(redis.call('GET', KEYS[i]) or '0')
  if gastado + costo > topes[i] then
    if i == 2 and ahorro then return 4 end
    return i
  end
end
for i = 1, 3 do
  redis.call('INCRBY', KEYS[i], costo)
  redis.call('EXPIRE', KEYS[i], ARGV[5])
end
return 0
"""

# Ventana deslizante: con ventanas fijas una ráfaga justo en el cambio de ventana pasaba con
# hasta el doble del límite (lo vimos en las pruebas). Lo rechazado no se guarda: así el
# conjunto no crece más que el límite aunque el flooding sea enorme.
VENTANA_DESLIZANTE = """
local ahora = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ahora - tonumber(ARGV[2]))
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then return 1 end
redis.call('ZADD', KEYS[1], ahora, ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 0
"""

NIVELES = {1: "cuota_sesion", 2: "cuota_ip", 3: "cuota_global", 4: "modo_ahorro"}


@dataclass
class Reserva:
    claves: list[str]
    tokens: int


def _claves(sub: str, ip: str) -> list[str]:
    dia = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [f"cuota:sesion:{sub}", f"cuota:ip:{ip}:{dia}", f"cuota:global:{dia}"]


class Cuotas:
    def __init__(self, redis_client):
        self.r = redis_client
        self._reservar = redis_client.register_script(RESERVAR)
        self._ventana = redis_client.register_script(VENTANA_DESLIZANTE)

    def _ventana_excedida(self, clave: str, maximo: int, segundos: int) -> bool:
        return bool(self._ventana(keys=[clave], args=[time.time(), segundos, maximo, uuid.uuid4().hex]))

    def spike(self, sub: str) -> bool:
        return self._ventana_excedida(f"spike:{sub}", SPIKE_MAX, SPIKE_VENTANA)

    def sesiones_excedidas(self, ip: str) -> bool:
        return self._ventana_excedida(f"sesiones:{ip}", SESIONES_IP_HORA, 3600)

    def marcar_sospechosa(self, ip: str) -> None:
        self.r.set(f"sospechosa:{ip}", 1, ex=SOSPECHA_SEGUNDOS)

    def llamadas_excedidas(self, ip: str) -> str | None:
        """Primero por IP: quien ya pasó su parte no debe consumir también el cupo global."""
        if RPM_IP and self._ventana_excedida(f"rpm:ip:{ip}", RPM_IP, 60):
            self.marcar_sospechosa(ip)
            return "rpm_ip"
        if RPM_GLOBAL:
            cupo = RPM_GLOBAL * RPM_SOSPECHOSA_PCT // 100 if self.r.exists(f"sospechosa:{ip}") else RPM_GLOBAL
            if self._ventana_excedida("rpm:global", cupo, 60):
                return "rpm_global"
        return None

    def reservar(self, sub: str, ip: str, tokens: int) -> tuple[Reserva | None, str | None]:
        claves = _claves(sub, ip)
        rechazo = self._reservar(keys=claves, args=[tokens, CUOTA_SESION, CUOTA_IP, CUOTA_GLOBAL, DIA, CUOTA_GLOBAL * AHORRO_PCT // 100, CUOTA_IP_AHORRO])
        if rechazo:
            return None, NIVELES[int(rechazo)]
        return Reserva(claves, tokens), None

    def ajustar(self, reserva: Reserva, tokens_reales: int) -> None:
        """Devuelve lo que sobró de la reserva (o cobra lo que faltó)."""
        diferencia = tokens_reales - reserva.tokens
        if diferencia:
            pipe = self.r.pipeline()
            for clave in reserva.claves:
                pipe.incrby(clave, diferencia)
            pipe.execute()

    def gasto_global_hoy(self) -> int:
        dia = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return int(self.r.get(f"cuota:global:{dia}") or 0)
