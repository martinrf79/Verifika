FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Cache de pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY app/ ./app/
COPY data/ ./data/

# Cloud Run usa la variable PORT
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
