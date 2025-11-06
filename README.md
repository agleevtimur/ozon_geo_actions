# Ozon Geo Action Updater (cookie header version)

Минималистичный CLI‑проект, который **не трогает твою «старую» логику**,
а лишь отправляет POST на `seller.ozon.ru` для изменения географии акции
через список `addresses` (UID страны/региона/города).

Ключевые особенности:
- Куки читаются из ENV `OZON_COOKIES` **в виде plain text** и передаются **строго в заголовке `Cookie:`** (без `path`, `expires` и т.п.).
- Заголовки `x-o3-*` выносим в ENV.
- Маппинг (страна → регионы → города) берём из файла `mapping.json` формата ниже.
- Есть CLI‑команда для быстрой проверки.

> Если у тебя уже есть основной проект (бот/скрипт с «старой» логикой),
подключи модуль `ozon_geo_actions_ext.action_updater` и передай туда
готовый список `addresses` — ничего больше менять не нужно.

---

## Установка

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Переменные окружения

Создай `.env` (можно на Railway переменными окружения):

```
OZON_COOKIES=__Secure-access-token=...; __Secure-refresh-token=...; __Secure-user-id=...; ...
OZON_COMPANY_ID=1297124
OZON_LANGUAGE=ru
OZON_PAGE_TYPE=highlights-other
```

- `OZON_COOKIES` — **весь** cookie‑стринг в виде plain text (как в DevTools → Request Headers → `Cookie:`).
- `OZON_COMPANY_ID` — значение для заголовка `x-o3-company-id`.
- `OZON_LANGUAGE` (опционально, по умолчанию `ru`).
- `OZON_PAGE_TYPE` (опционально, по умолчанию `highlights-other`).

## Формат `mapping.json`

Ожидается компактная иерархия:

```json
{
  "Россия": {
    "uid": "country-uid-here",
    "regions": {
      "Свердловская область": {
        "uid": "region-uid-here",
        "cities": [
          {"title": "Екатеринбург", "uid": "city-uid-1", "type": "city"},
          {"title": "Нижний Тагил", "uid": "city-uid-2", "type": "city"}
        ]
      },
      "Тюменская область": {
        "uid": "region-uid-here-2",
        "cities": []
      }
    }
  }
}
```

> Если у тебя «сырой» JSON другого вида — можешь построить этот файл заранее
в своём основном проекте. При желании добавь конвертер сюда позже.

## Использование CLI

### Обновить конкретную акцию

```bash
python cli.py   --action-id 2983461   --mapping mapping.json   --title "10 скидка"   --date-start "2025-11-01T21:00:00.000Z"   --date-end   "2026-05-03T20:59:59.000Z"
```

По умолчанию будут использованы **все** регионы из `mapping.json`.
Чтобы ограничить список:

```bash
python cli.py   --action-id 2983461   --mapping mapping.json   --regions "Свердловская область,Тюменская область"   --title "10 скидка"   --date-start "2025-11-01T21:00:00.000Z"   --date-end   "2026-05-03T20:59:59.000Z"
```

### Только собрать addresses и вывести в stdout (без запроса)

```bash
python cli.py --mapping mapping.json --print-addresses-only 1
```

## Встраивание в «старую» логику

```python
from ozon_geo_actions_ext.action_updater import OzonActionUpdater
from ozon_geo_actions_ext.geo_builder import build_addresses_for_action, load_mapping

mapping = load_mapping("mapping.json")
addresses = build_addresses_for_action(mapping, regions=["Свердловская область"])

updater = OzonActionUpdater()  # берёт куки из OZON_COOKIES (plain text)
resp = updater.update_action_addresses(
    action_id=2983461,
    addresses=addresses,
    title="10 скидка",
    date_start_iso="2025-11-01T21:00:00.000Z",
    date_end_iso="2026-05-03T20:59:59.000Z",
)
print(resp)
```

## Предостережения

- Проект не прячет куки — они должны храниться только в ENV (Railway).
- Никаких `CookieJar` и установки cookie по ключам — мы **строго** шлём один
  заголовок `Cookie:` с твоей строкой.
- Если Ozon вернёт 401/403 — проверь свежесть и полноту cookie‑строки,
  а также актуальность `x-o3-company-id`.
