FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sumermail ./sumermail
RUN useradd -r -u 10002 sumermail
USER sumermail
EXPOSE 8100
CMD ["uvicorn", "sumermail.app:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "2", "--no-access-log", "--proxy-headers"]
