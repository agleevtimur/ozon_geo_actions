import os
import requests
from typing import Dict, Any, List

OZON_COOKIES = os.getenv("OZON_COOKIES_PLAINTEXT", "").strip()
OZON_COMPANY_ID = os.getenv("OZON_COMPANY_ID", "1297124").strip()

HEADERS_BASE = {
    "x-o3-app-name": "seller-ui",
    "x-o3-language": "ru",
    "x-o3-page-type": "highlights-other",
    "x-o3-company-id": OZON_COMPANY_ID,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://seller.ozon.ru",
    "Priority": "u=3, i",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"
}

class OzonClient:
    """
    Клиент для seller.ozon.ru — изменение акции (update).
    """
    def __init__(self) -> None:
        if not OZON_COOKIES:
            raise RuntimeError("OZON_COOKIES_PLAINTEXT is required for seller-ui calls")
        self.sess = requests.Session()
        self.sess.headers.update(HEADERS_BASE)
        self.sess.headers["Cookie"] = OZON_COOKIES
        self.base = "https://seller.ozon.ru"

    def update_action_addresses(self, action_id: int, new_addresses: List[str], action_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Полный апдейт акции — отправляем action_parameters, где меняем только addresses.
        URL: /api/site/marketplace-seller-actions/v1/action/{id}/update
        """
        url = f"{self.base}/api/site/marketplace-seller-actions/v1/action/{action_id}/update"
        body = {"action_parameters": action_parameters | {"addresses": new_addresses}}
        r = self.sess.post(url, json=body, timeout=60)
        r.raise_for_status()
        return r.json()
