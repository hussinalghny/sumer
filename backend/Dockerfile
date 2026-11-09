FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sumer ./sumer
RUN useradd -r -u 10001 sumer && mkdir -p /data /models && chown sumer /data
USER sumer
ENV SUMER_DATA_DIR=/data SUMER_MODELS_DIR=/models
EXPOSE 8000
CMD ["python", "-m", "sumer", "api", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
