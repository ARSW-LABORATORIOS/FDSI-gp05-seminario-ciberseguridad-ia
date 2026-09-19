"""
Este archivo es para las pruebas de carga (T01 flooding, T04 ráfaga multiusuario,
T05 usuario legítimo bajo ataque). Se corre con Locust apuntando primero a
unsecure (puerto 8000) y después a secure (puerto 8001), para comparar.

Cómo correrlo (con interfaz web, más fácil para ver los resultados):
    locust -f tests/locustfile.py --host http://localhost:8000
Y luego abrir http://localhost:8089 para configurar cuántos usuarios simular.
"""

from locust import HttpUser, task, between

PREGUNTAS_NORMALES = [
    "¿Cuándo es el parcial?",
    "¿Qué temas entran en el corte 2?",
    "¿Cómo se entrega el taller?",
]


class EstudianteNormal(HttpUser):
    """Simula un estudiante usando el asistente de forma normal (T05)."""
    wait_time = between(2, 5)  # espera entre preguntas, como lo haría alguien de verdad

    @task
    def preguntar(self):
        import random
        pregunta = random.choice(PREGUNTAS_NORMALES)
        self.client.post("/ask", json={"texto": pregunta, "usuario_id": "estudiante_normal"})


class AtacanteFlooding(HttpUser):
    """Simula flooding: un mismo usuario mandando muchas preguntas seguidas (T01)."""
    wait_time = between(0, 0.1)  # casi sin esperar entre peticiones, a propósito

    @task
    def preguntar_rapido(self):
        self.client.post("/ask", json={"texto": "pregunta de flooding", "usuario_id": "atacante_1"})


# Para T04 (ráfaga multiusuario), en Locust simplemente se levantan varios
# "AtacanteFlooding" con usuario_id distinto -- eso se configura desde la
# interfaz web de Locust (número de usuarios concurrentes) o con un
# LoadTestShape si quieren algo más controlado. Lo dejamos como TODO para
# cuando tengan el backend corriendo.
