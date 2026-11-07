FROM python:3.12-slim
RUN pip install --no-cache-dir fastapi==0.115.0 "uvicorn[standard]==0.30.6" "httpx>=0.27,<1"
WORKDIR /app
COPY app.py .
USER 1000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000", "--log-level", "warning"]
