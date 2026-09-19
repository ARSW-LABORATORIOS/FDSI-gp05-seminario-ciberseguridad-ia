"""
Esta clase es para no dejar que un mismo estudiante se gaste más tokens de los que
le tocan en el día. Usamos Redis porque necesitamos que el conteo sea compartido
entre todas las peticiones (no sirve guardarlo en memoria de Python, se perdería
cada vez que se reinicie el servidor, y no serviría si corremos varias instancias).

La idea del "Token Bucket": cada estudiante tiene un balde con, por ejemplo, 5000
tokens por día. Cada vez que pregunta algo, se le resta lo que gastó. Si el balde
se vacía, se le rechaza la siguiente pregunta hasta que el balde se recarga al otro día.
"""

import redis


class RateLimiter:
    """Controla cuántos tokens le quedan a cada estudiante por día."""

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, limite_diario: int = 5000):
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.limite_diario = limite_diario

    def _clave(self, usuario_id: str) -> str:
        # una clave distinta por usuario y por día, así el balde se "recarga" solo cada día
        from datetime import date
        return f"tokens:{usuario_id}:{date.today().isoformat()}"

    def tiene_cuota(self, usuario_id: str, tokens_estimados: int) -> bool:
        """Revisa si al usuario le alcanza la cuota ANTES de llamar al LLM
        (así no gastamos nada si de todas formas lo íbamos a rechazar)."""
        clave = self._clave(usuario_id)
        gastado = int(self.redis.get(clave) or 0)
        return (gastado + tokens_estimados) <= self.limite_diario

    def registrar_consumo(self, usuario_id: str, tokens_usados: int):
        """Se llama DESPUÉS de que el LLM respondió, para sumar lo que se gastó de verdad."""
        clave = self._clave(usuario_id)
        nuevo_total = self.redis.incrby(clave, tokens_usados)
        if nuevo_total == tokens_usados:
            # es el primer registro del día para este usuario -> le ponemos vencimiento de 24h
            self.redis.expire(clave, 86400)
