FROM python:3.12-slim
ENV FASTEMBED_CACHE_PATH=/modelos ANONYMIZED_TELEMETRY=False
RUN pip install --no-cache-dir "mcp>=1.20,<2" "chromadb>=1.1,<2" "fastembed>=0.7,<1"
# el modelo queda dentro de la imagen: en ejecución este contenedor no necesita internet
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" && chmod -R a+rX /modelos
WORKDIR /app
COPY server.py .
USER 1000
ENV HOME=/tmp
CMD ["python", "server.py"]
