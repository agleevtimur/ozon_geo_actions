FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends     libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2     libxcb1 libxkbcommon0 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2     libgbm1 libasound2 libatspi2.0-0 libpango-1.0-0 libcairo2 libexpat1 libgio-2.0-0     libdbus-1-3 wget ca-certificates fonts-liberation  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install --with-deps chromium

COPY . /app
CMD ["python", "bot.py"]
