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
    Возвращает список FBO-складов с их ID и именами из /v1/cluster/list.
    Поддерживает схему:
    {
      "clusters":[
        {
          "id":...,
          "name":"...",
          "type":"CLUSTER_TYPE_OZON",
          "logistic_clusters":[
            {"warehouses":[{"warehouse_id":..., "name":"...", "type":"FULL_FILLMENT"}, ...]}
          ]
        }
      ]
    }
    """
    resp = post("/v1/cluster/list", {})
    clusters = resp.get("clusters") or []
    out = []
    for c in clusters:
      # интересуют только склады Озона
      if (c.get("type") or "").upper() != "CLUSTER_TYPE_OZON":
          continue
      c_name = c.get("name")
      for lc in c.get("logistic_clusters", []) or []:
          for w in lc.get("warehouses", []) or []:
              if (w.get("type") or "").upper() != "FULL_FILLMENT":
                  continue
              out.append({
                  "warehouse_id": w.get("warehouse_id"),
                  "name": w.get("name"),
                  "cluster_name_from_api": c_name,  # на всякий случай сохраняем
              })
    return out
