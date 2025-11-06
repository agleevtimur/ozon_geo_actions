import os
import requests
from typing import List, Dict, Any

OZON_CLIENT_ID = os.getenv("OZON_CLIENT_ID", "").strip()
OZON_API_KEY = os.getenv("OZON_API_KEY", "").strip()

class OzonOpenApi:
    """
    Клиент для Ozon Open API (официальный), используется ТОЛЬКО для получения остатков.
    База: https://api-seller.ozon.ru
    Требуются заголовки: Client-Id, Api-Key.
    """
    def __init__(self) -> None:
        if not OZON_CLIENT_ID or not OZON_API_KEY:
            raise RuntimeError("OZON_CLIENT_ID / OZON_API_KEY are required envs for analytics stocks")
        self.sess = requests.Session()
        self.sess.headers.update({
            "Client-Id": OZON_CLIENT_ID,
            "Api-Key": OZON_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self.base = "https://api-seller.ozon.ru"

    def fetch_stocks_for_skus(self, skus: List[str]) -> Dict[str, Any]:
        """
        POST /v1/analytics/stocks
        body: {"skus": ["string", ...]}
        Возвращает сырой JSON ответа Open API.
        """
        url = f"{self.base}/v1/analytics/stocks"
        payload = {"skus": [str(s) for s in skus]}
        r = self.sess.post(url, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
