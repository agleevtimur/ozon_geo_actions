# core/ozon_api.py
import os, requests, json

OZON_API = "https://api-seller.ozon.ru"

def HEADERS():
    return {
        "Client-Id": os.getenv("OZON_CLIENT_ID"),
        "Api-Key": os.getenv("OZON_API_KEY"),
        "Content-Type": "application/json",
    }

def post(path, payload):
    r = requests.post(OZON_API + path, headers=HEADERS(), json=payload, timeout=60)
    if not r.ok:
        try: body = r.json()
        except Exception: body = r.text
        raise RuntimeError(f"OZON API error {r.status_code} {path}: {body}")
    return r.json()

def _stocks_page(skus_chunk, cursor=None, limit=100):
    payload = {"skus": skus_chunk, "limit": limit}  # <-- ВАЖНО: skus (мн. число)
    if cursor:
        payload["cursor"] = cursor
    return post("/v1/analytics/stocks", payload)

def get_stocks(skus: list[int]):
    """
    Возвращает единый словарь {"items":[...], "total":N}
    Делим запрос на чанки по 100 SKU, как требует API.
    """
    skus = [int(x) for x in (skus or []) if x is not None]
    if not skus:
        raise RuntimeError("Нет SKU для запроса остатков (список пуст).")

    all_items = []
    # пачкуем по 100
    for i in range(0, len(skus), 100):
        chunk = skus[i:i+100]
        cursor = None
        while True:
            page = _stocks_page(chunk, cursor=cursor, limit=100)
            items = page.get("items") or []
            all_items.extend(items)
            cursor = page.get("cursor")
            if not cursor or not items:
                break

    return {"items": all_items, "total": len(all_items)}

def get_warehouses():
    # список складов для авто-матчинга ID↔имя
    resp = post("/v1/warehouse/list", {})
    items = resp.get("result") or resp.get("warehouses") or []
    out = []
    for w in items:
        out.append({
            "warehouse_id": w.get("warehouse_id") or w.get("id"),
            "name": w.get("name") or w.get("warehouse_name"),
        })
    return out
