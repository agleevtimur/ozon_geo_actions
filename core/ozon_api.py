import os, requests
OZON_API = "https://api-seller.ozon.ru"
def HEADERS():
    return {"Client-Id": os.getenv("OZON_CLIENT_ID"),
            "Api-Key": os.getenv("OZON_API_KEY"),
            "Content-Type": "application/json"}
def post(path, payload):
    r = requests.post(OZON_API + path, headers=HEADERS(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()
def get_stocks(skus: list[int]):
    return post("/v4/product/info/stocks", {"sku": skus})
