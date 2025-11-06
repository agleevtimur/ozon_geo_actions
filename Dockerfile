# База со всеми зависимостями и браузерами
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Сначала зависимости — ради кэша
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Затем код
COPY . /app

# headless уже работает из коробки
CMD ["python", "-m", "bot"]
