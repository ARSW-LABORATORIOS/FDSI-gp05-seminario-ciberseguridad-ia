FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "httpx>=0.27,<1" "redis>=5,<7" "altcha>=2.3,<3" "pyjwt>=2.9,<3"
WORKDIR /app
COPY *.py .
CMD ["python", "ataques.py"]
