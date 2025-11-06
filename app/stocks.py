import os
import logging
from typing import Dict, Any, List
import requests

log = logging.getLogger(__name__)

# Эти переменные должны быть заданы в Railway:
# OZON_CLIENT_ID, OZON_API_KEY
OZON_CLIENT_ID = os.getenv("OZON_CLIENT_ID", "").strip()
OZON_API_KEY = os.getenv("OZON_API_KEY", "").strip()


def _ozon_openapi_session() -> requests.Session:
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        raise RuntimeError("OZON_CLIENT_ID / OZON_API_KEY are required for /v1/analytics/stocks")
    s = requests.Session()
    s.headers.update({
        "Client-Id": OZON_CLIENT_ID,
        "Api-Key": OZON_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    return s


def _fetch_stocks_for_skus(skus: List[str]) -> Dict[str, Any]:
    """
    Официальный Open API:
      POST https://api-seller.ozon.ru/v1/analytics/stocks
      body: {"skus": ["string", ...]}
    Возвращаем сырой JSON как есть.
    """
    sess = _ozon_openapi_session()
    url = "https://api-seller.ozon.ru/v1/analytics/stocks"
    payload = {"skus": [str(s) for s in skus]}
    r = sess.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    log.info("OpenAPI stocks fetched for %d skus", len(skus))
    return data


def aggregate_by_cluster(skus: List[str]) -> Dict[str, Any]:
    """
    'Старая логика' у тебя опиралась на агрегацию остатков -> кластеры.
    Здесь мы гарантированно тянем сырые остатки через Open API.
    Чтобы не ломать твой конвейер дальше, возвращаем структуру:
    {
      "raw": <сырой ответ Open API>,
      "per_sku_total": {"<sku>": int_total, ...},
      "total": <int>
    }

    Если понадобится – на этом уровне можно вернуть и кластеры,
    но поскольку конкретное разложение по кластерам зависит от
    твоего готового geo.json/правил, оставляем агрегацию адресов
    в bot.py (resolve из geo.json).
    """
    raw = _fetch_stocks_for_skus(skus)

    per_sku_total: Dict[str, int] = {}
    total = 0

    # Попробуем аккуратно разобрать наиболее типичные схемы ответа Open API,
    # но без жёсткой привязки к полям (бывают минорные отличия).
    # Обычный кейс: {"result":[{"sku":"123","stocks":[{"present":10, ...}, ...]}, ...]}
    result = raw.get("result") or raw.get("items") or []
    for item in result:
        sku = str(item.get("sku") or item.get("offer_id") or "")
        if not sku:
            continue
        sku_sum = 0

        # Часто остатки лежат в массиве "stocks" или "warehouses".
        buckets = item.get("stocks") or item.get("warehouses") or []
        for b in buckets:
            # Пытаемся взять очевидные поля количества
            for key in ("present", "free_to_sell_amount", "quantity", "stock"):
                if isinstance(b.get(key), int):
                    sku_sum += int(b[key])
                    break  # одно поле на запись достаточно

        per_sku_total[sku] = sku_sum
        total += sku_sum

    return {"raw": raw, "per_sku_total": per_sku_total, "total": total}
