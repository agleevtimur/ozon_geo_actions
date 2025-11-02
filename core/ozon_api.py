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
    """
    Собирает FBO (FULL_FILLMENT) склады из /v1/cluster/list под фактический ответ:
    { "clusters":[ { "type":"OZON", "name":"...", "logistic_clusters":[{"warehouses":[...]}] } ] }
    """
    # Параметр не обязателен, но можно оставить:
    payload = {"cluster_type": "OZON"}
    resp = post("/v1/cluster/list", payload)

    clusters = resp.get("clusters") or []
    out = []

    for c in clusters:
        c_name = c.get("name")  # например: "Кавказ", "Казань", "Москва, МО и Дальние регионы"
        # тип кластера может быть "OZON" — НЕ отфильтровываем его жёстко
        for lc in c.get("logistic_clusters", []) or []:
            for w in lc.get("warehouses", []) or []:
                if (w.get("type") or "").upper() != "FULL_FILLMENT":
                    continue
                out.append({
                    "warehouse_id": w.get("warehouse_id"),  # может быть str или int — ок
                    "name": w.get("name"),                  # например: "НЕВИННОМЫССК_РФЦ"
                    "cluster_name_from_api": c_name,        # например: "Кавказ"
                })
    return out
