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

def get_stocks(skus: list[int]):
    # новый FBO-метод
    return post("/v1/analytics/stocks", {"sku": skus})

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
