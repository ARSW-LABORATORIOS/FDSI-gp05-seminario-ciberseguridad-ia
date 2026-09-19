"""
Esta parte es la que buscan los documentos del curso para responder una pregunta (RAG).
Es la misma para unsecure y secure -- lo que cambia entre las dos versiones NO es cómo
se busca, sino si hay límite a cuántos documentos se pueden traer de una sola vez.
Eso se controla desde afuera con el parámetro max_chunks.
"""

# TODO: instalar chromadb (pip install chromadb) y sentence-transformers
import chromadb
from sentence_transformers import SentenceTransformer


class DocumentRetriever:
    """
    Esta clase es para cargar los documentos del curso (reglamentos, guías, apuntes)
    y poder buscar cuáles tienen que ver con una pregunta.
    """

    def __init__(self, docs_folder: str = "./course_docs"):
        # TODO: aquí va la carpeta real donde guarden los PDFs/txt del curso
        self.docs_folder = docs_folder
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")  # modelo liviano, corre en CPU
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection("course_docs")
        # TODO: acá falta la función que lee los archivos de docs_folder, los parte en
        # pedazos (chunks) y los mete a self.collection con self.collection.add(...)

    def search(self, question: str, max_chunks: int = 5) -> list[str]:
        """
        Busca los `max_chunks` documentos más parecidos a la pregunta.
        En unsecure llamamos esto con max_chunks bien alto (o sin límite real);
        en secure lo llamamos con un tope bajo (ej. 3-5) a propósito.
        """
        query_embedding = self.embedder.encode(question).tolist()
        results = self.collection.query(query_embeddings=[query_embedding], n_results=max_chunks)
        return results["documents"][0] if results["documents"] else []
