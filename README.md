# Ozon Geo Bot – Railway scaffold

Минимальный каркас Telegram‑бота, который умеет обновлять географию в акции OZON с помощью списка UID адресов.

## Быстрый старт (Railway)

1. Создай новый проект и подключи репозиторий с этим кодом.
2. В **Variables** добавь:
   - `TELEGRAM_BOT_TOKEN` — токен бота
   - `OZON_COOKIE_PLAIN` — вся строка Cookie (plain text), без `path`/`expires`
   - `OZON_COMPANY_ID` — твой company id (по умолчанию 1297124)
3. Деплоится автоматически. Стартовая команда берётся из `Procfile`:
   ```
   worker: PYTHONPATH=$(pwd) python -m app.bot
   ```

## Команды

- `/ping` — проверка доступности
- `/update_geo <action_key_or_id> <title> <days> <csv_uids>`
  - Пример:
    `/update_geo 10 "10% скидка" 180 c528e99b-...,8f41253d-...`

`action_key_or_id` можно передать как:
- Полный ID акции (например, `2983461`), или
- Короткий ключ из карты в `app/bot.py`: `10`, `9`, `8`, ..., `3_common`

## Что добавить под тебя

- Реальную логику «остатков по кластерам» и «кластер → регионы → города → UID`.
  - Сохрани её модулями в `app/` и вызывай из команд бота.
  - При желании храни JSON‑маппинг в `data/locations.json`.

## Локальный запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...
export OZON_COOKIE_PLAIN='__Secure-access-token=...; ...'
PYTHONPATH=$(pwd) python -m app.bot
```