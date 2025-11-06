import os
import json
import logging
from typing import List, Dict, Any, Optional
import requests

log = logging.getLogger("ozon")

BASE = "https://seller.ozon.ru/api/site"
COMPANY_ID = os.getenv("OZON_COMPANY_ID")  # e.g. 1297124
COOKIE = os.getenv("OZON_COOKIE_PLAIN", "")
APP_NAME = os.getenv("OZON_APP_NAME", "seller-ui")
LANGUAGE = os.getenv("OZON_LANGUAGE", "ru")

ACTION_HEADERS = {
    "Cookie": COOKIE,
    "x-o3-app-name": APP_NAME,
    "x-o3-company-id": COMPANY_ID or "",
    "x-o3-language": LANGUAGE,
    "x-o3-page-type": "highlights-other",
    "Content-Type": "application/json; charset=utf-8",
}

class OzonClient:
    # ---- Stocks / SKUs ----
    def list_action_skus(self, action_id: str) -> List[str]:
        """Вернуть список SKU, входящих в акцию. 
        Если ваш сервис остатков не требует фильтрации по SKU — верните пустой список.
        Здесь заглушка обращения к UI-эндпоинту, замените на свой, если нужно.
        """
        try:
            # Если у вас есть конкретный эндпоинт, замените ниже.
            # Здесь возвращаем пустой список — агрегация сработает и без него.
            return []
        except Exception as e:
            log.warning(f"list_action_skus failed: {e}")
            return []

    def fetch_stocks_raw_for_skus(self, skus: List[str]) -> Dict[str, Any]:
        """Вернуть СЫРОЙ ответ вашего старого эндпоинта по остаткам.
        Подмените на вызов, который использует вашу «старую логику» (как в вашем репозитории).
        """
        # Пример: POST на analytics v1 stock (адаптируйте под свой точный путь)
        url = f"{BASE}/analytics/v1/stock"
        payload = {"company_id": COMPANY_ID, "skus": skus}
        r = requests.post(url, headers=ACTION_HEADERS, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()

    # ---- Actions: view / update ----
    def view_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"{BASE}/marketplace-seller-actions/v1/action/{action_id}/view"
            r = requests.get(url, headers=ACTION_HEADERS, timeout=60)
            if r.status_code // 100 != 2:
                log.warning("view_action non-2xx: %s %s", r.status_code, r.text[:300])
                return None
            return r.json()
        except Exception as e:
            log.warning("view_action failed: %s", e)
            return None

    def build_update_body_from_view(self, view_json: Dict[str, Any], addresses: List[str]) -> Dict[str, Any]:
        """Построить тело update, основываясь на исходных параметрах (title/date_start/...)."""
        # Ожидаем, что в view_json есть те же поля, что шлёт UI.
        ap = view_json.get("action_parameters") or view_json  # страхуемся
        body = {
            "action_parameters": {
                "title": ap.get("title"),
                "date_start": ap.get("date_start"),
                "date_end": ap.get("date_end"),
                "type": ap.get("type", "DISCOUNT"),
                "marketplace_id": ap.get("marketplace_id", 1),
                "warehouses": ap.get("warehouses", []),
                "addresses": addresses,
                "is_additional_discount": ap.get("is_additional_discount", False),
                "marketplace_min_discount_percent": ap.get("marketplace_min_discount_percent", 1),
                "discount_type": ap.get("discount_type", "FINAL_PRICE")
            }
        }
        return body

    def update_action_with_body(self, action_id: str, body: Dict[str, Any]) -> bool:
        url = f"{BASE}/marketplace-seller-actions/v1/action/{action_id}/update"
        r = requests.post(url, headers=ACTION_HEADERS, json=body, timeout=60)
        if r.status_code // 100 != 2:
            log.error("update_action non-2xx: %s %s", r.status_code, r.text[:400])
            return False
        return True

    def update_action_addresses_only(self, action_id: str, addresses: List[str]) -> bool:
        """Пробуем частичное обновление только addresses (если сервер примет)."""
        body = {"action_parameters": {"addresses": addresses}}
        return self.update_action_with_body(action_id, body)
