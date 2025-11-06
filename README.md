# ozon_geo_bot_full

Telegram-бот для управления географией акций Ozon:
- Парсит географию из `data/geo.json` (страна → регионы → города) и строит быстрые индексы UID.
- Знает кластеры и соответствующие им регионы (из `data/clusters_mapping.json`).
- Может подтягивать остатки по кластерам (на основе простого вызова API; при необходимости доработай под свою старую реализацию).
- Обновляет географию акции через POST `https://seller.ozon.ru/api/site/marketplace-seller-actions/v1/action/{action_id}/update`.
- Все операции выполняются **через Telegram-бота** (никакого CLI).

## Быстрый старт (локально)

1. Установи зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Подготовь переменные окружения (можно через `.env` в корне):
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...      # токен бота
   OZON_COOKIE=__Secure-access-token=...; ... # ПЛОСКАЯ СТРОКА Cookie целиком, БЕЗ path/expire
   OZON_COMPANY_ID=1297124
   OZON_LANGUAGE=ru
   DEFAULT_ACTION_ID=2983461                  # по умолчанию "10 скидка"
   DEFAULT_TITLE_TEMPLATE={discount} скидка # динамический шаблон
   ```

3. Заполни данные:
   - `data/geo.json` — **сырой** JSON со структурой страна/регион/города/uid (ты уже присылал).
   - `data/clusters_mapping.json` — словарь `cluster_code -> [region_names]` (пример уже лежит).

4. Запусти:
   ```bash
   python -m app.bot
   ```

## Docker

```bash
docker build -t ozon-geo-bot .
docker run --rm -e TELEGRAM_BOT_TOKEN=... -e OZON_COOKIE="..." -e OZON_COMPANY_ID=1297124 ozon-geo-bot
```

## Railway

Вынеси `OZON_COOKIE` в **глобальную переменную Railway** (plain text). Никаких JSON, никакого `path/expire` — просто строка Cookie, как её даёт браузер.

## Команды Telegram-бота

- `/start` — подсказка.
- `/status` — показать текущие настройки.
- `/set_action <id>` — установить ID акции (см. список ниже).
- `/set_title <шаблон>` — установить шаблон заголовка, например: `{discount} скидка`.
- `/set_clusters <список>` — указать кластеры, например: `MSK SPB KZN`.
- `/preview_geo` — показать, какие регионы/города попадут в `addresses`.
- `/apply_geo <discount>` — применить географию к акции, сформировав `title` из шаблона.

### ID акций (из твоего списка)

- 2983461 — 10 скидка
- 2983456 — 9 скидка
- 2983449 — 8 скидка
- 2983433 — 7 скидка
- 2983414 — 6 скидка
- 2983408 — 5 скидка
- 2983396 — 4 скидка
- 2983375 — 2 скидка
- 2983366 — 1 скидка
- 2772472 — 3 ОБЩАЯ скидка

## Как работает подтяжка остатков

Файл `app/core/stocks.py` реализует функцию `get_clusters_with_stock(...)`.
По умолчанию сделан безопасный каркас:
- Пытается запросить агрегированные остатки по товарам и адресам (внутренний `seller.ozon.ru` эндпоинт, заголовки те же — при необходимости замени URL на твою старую логику).
- Маппит адреса к регионам и кластерам через `geo_index`.
- Возвращает список кластеров, где суммарный остаток > 0.

> Если хочешь **в точности** твою старую логику из `ozon_geo_actions`, просто перенеси код запроса в функцию `fetch_raw_stocks(...)` и/или адаптируй расчёт агрегатов — вся обвязка уже готова.

## Структура

```
app/
  bot.py
  config.py
  ozon_api.py
  geo_loader.py
  mappings.py
  core/
    stocks.py
  utils/
    log.py
data/
  geo.json                 # заполни своей "сырой" географией
  clusters_mapping.json    # пример внутри
Dockerfile
requirements.txt
README.md
```

---

**Внимание.** Проект готов к пушу в GitHub. Просто проверь `data/geo.json` и `data/clusters_mapping.json`, пропиши `.env` или переменные Railway, и можно тестировать на любой акции из списка.
