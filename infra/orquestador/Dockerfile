FROM python:3.12-slim
RUN pip install --no-cache-dir "fastapi>=0.115,<1" "uvicorn[standard]>=0.31,<1" "httpx>=0.27,<1" "mcp>=1.20,<2"
WORKDIR /app
COPY app.py .
USER 1000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
