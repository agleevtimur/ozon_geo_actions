FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

# Healthcheck: бот должен быть онлайн
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import socket; s=socket.socket(); s.connect(('api.telegram.org', 443))" || exit 1

CMD ["python", "-m", "app.bot"]
