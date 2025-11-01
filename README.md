# Ozon Geo Promo Telegram Bot (v2)

Запуск на VPS, Railway или локально. Встроено:
- маппинг складов (по **имени** → кластер) в `core/stocks.py`,
- логика групп `union`,
- управление через команды Telegram,
- Playwright-автоматизация «Мои/Собственные акции» (города, скидки, товары).

## Быстрый старт (Railway)
1) Залей репозиторий на GitHub.
2) На railway.app → New Project → Deploy from GitHub.
3) Variables: TELEGRAM_BOT_TOKEN, ADMIN_CHAT_IDS, OZON_CLIENT_ID, OZON_API_KEY, HEADLESS=true, COOKIES_PATH=/app/cookies.json (опц. COOKIES_JSON=...).
4) Start Command: `python bot.py` (если нужно: `pip install -r requirements.txt && python -m playwright install --with-deps chromium && python bot.py`).

## Locally / Docker
см. инструкцию в чате.
