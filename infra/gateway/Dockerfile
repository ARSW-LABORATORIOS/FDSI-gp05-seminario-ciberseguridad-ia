FROM python:3.12-slim
ENV FASTEMBED_CACHE_PATH=/modelos TIKTOKEN_CACHE_DIR=/modelos/tiktoken
RUN pip install --no-cache-dir fastapi==0.115.0 "uvicorn[standard]==0.30.6" "httpx>=0.27,<1" "redis>=5,<7" \
    "tiktoken>=0.7,<1" "fastembed>=0.7,<1" "altcha>=2.3,<3" "pyjwt>=2.9,<3" "prometheus-client>=0.20,<1"
# modelo y codificación quedan dentro de la imagen: en ejecución no se necesita internet
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); import tiktoken; tiktoken.get_encoding('cl100k_base')" && chmod -R a+rX /modelos
WORKDIR /app
COPY *.py .
USER 1000
ENV HOME=/tmp
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
