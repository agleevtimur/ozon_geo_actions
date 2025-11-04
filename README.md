# Ozon Geo Actions Bot (Playwright + Telegram)

Бот управляет географией «Своих акций» в Seller Ozon в зависимости от остатков.

## Команды
- `/dry_sync_geo` — показать план географии (без изменений)
- `/apply_geo` — применить географию для всех
- `/apply_geo_one <название или GEO-Gx>` — применить для одной акции

## Настройка
Редактируй `core/rules.py`:
- `GROUP_TO_PROMO_NAME` — GEO-код → «Название акции»
- `GROUP_TO_SKUS` — список SKU для каждой группы

## ENV
- `TELEGRAM_BOT_TOKEN` — токен бота
- `OZON_API_CLIENT_ID`, `OZON_API_KEY` — ключи Ozon API
- `OZON_COOKIES_JSON` — cookies JSON для seller.ozon.ru
- `TG_ALLOWED_USER_IDS` — whitelist id через запятую
- `PLAYWRIGHT_HEADLESS=1` — безголовый браузер

## Деплой
Есть `Dockerfile` и `requirements.txt`. Для Railway просто подключи репо и задай ENV.
