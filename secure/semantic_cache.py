"""
Esta clase es para no volver a gastar en llamar al LLM cuando alguien pregunta algo
que ya se respondió antes, aunque no lo haya escrito exactamente igual. Por eso se
llama "semántica": en vez de comparar el texto letra por letra, compara el significado
usando embeddings (vectores) y una similitud de coseno.

Ejemplo: si un estudiante pregunta "¿cuándo son los parciales?" y otro pregunta
"fechas de los exámenes", para nosotros son básicamente la misma pregunta -- con
caché semántica, la segunda pregunta puede responderse sin volver a llamar al LLM.
"""

from sentence_transformers import SentenceTransformer, util


class SemanticCache:
    """Guarda preguntas ya respondidas y busca si una pregunta nueva se parece a alguna."""

    def __init__(self, umbral_similitud: float = 0.90):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.umbral_similitud = umbral_similitud
        # MVP en memoria: lista de (pregunta, embedding, respuesta).
        # TODO: si da tiempo, pasar esto a Redis para que sobreviva a un reinicio
        # y se pueda compartir entre varias instancias del backend.
        self._entradas = []

    def buscar(self, pregunta: str):
        """Devuelve la respuesta guardada si hay una pregunta parecida, o None si no."""
        if not self._entradas:
            return None
        embedding_nuevo = self.embedder.encode(pregunta, convert_to_tensor=True)
        for pregunta_guardada, embedding_guardado, respuesta in self._entradas:
            similitud = util.cos_sim(embedding_nuevo, embedding_guardado).item()
            if similitud >= self.umbral_similitud:
                return respuesta
        return None

    def guardar(self, pregunta: str, respuesta: dict):
        """Guarda la pregunta y su respuesta para la próxima vez."""
        embedding = self.embedder.encode(pregunta, convert_to_tensor=True)
        self._entradas.append((pregunta, embedding, respuesta))
