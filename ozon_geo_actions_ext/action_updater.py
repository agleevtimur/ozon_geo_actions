import json
from typing import List, Dict, Any
import requests
from .config import OzonConfig

OZON_ACTION_UPDATE_URL_TMPL = "https://seller.ozon.ru/api/site/marketplace-seller-actions/v1/action/{action_id}/update"

class OzonActionUpdater:
    """
    Клиент для POST /action/{id}/update.
    1) Куки читаются из OZON_COOKIES (plain text) и кладутся строго в заголовок Cookie.
    2) Прочие x-o3-* заголовки берутся из ENV (см. OzonConfig).
    """

    def __init__(self, session: requests.Session | None = None, config: OzonConfig | None = None):
        self.session = session or requests.Session()
        self.config = config or OzonConfig.from_env()

        # Жёсткие заголовки
        self.session.headers.update({
            "Cookie": self.config.cookies_plain,   # строго как есть
            "x-o3-app-name": "seller-ui",
            "x-o3-company-id": self.config.company_id,
            "x-o3-language": self.config.language,
            "x-o3-page-type": self.config.page_type,
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json",
            "Origin": "https://seller.ozon.ru",
            "Referer": "https://seller.ozon.ru/",
            "User-Agent": "Mozilla/5.0"
        })

    def update_action_addresses(
        self,
        action_id: int,
        addresses: List[str],
        *,
        title: str,
        date_start_iso: str,
        date_end_iso: str,
        marketplace_id: int = 1,
        is_additional_discount: bool = False,
        marketplace_min_discount_percent: int = 1,
        discount_type: str = "FINAL_PRICE",
        warehouses: List[str] | None = None,
        action_type: str = "DISCOUNT",
    ) -> Dict[str, Any]:
        url = OZON_ACTION_UPDATE_URL_TMPL.format(action_id=action_id)
        payload = {
            "action_parameters": {
                "title": title,
                "date_start": date_start_iso,
                "date_end": date_end_iso,
                "type": action_type,
                "marketplace_id": marketplace_id,
                "warehouses": warehouses or [],
                "addresses": addresses,
                "is_additional_discount": is_additional_discount,
                "marketplace_min_discount_percent": marketplace_min_discount_percent,
                "discount_type": discount_type
            }
        }
        resp = self.session.post(url, data=json.dumps(payload))
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}

        if not resp.ok:
            raise RuntimeError(f"Update failed [{resp.status_code}]: {data}")
        return data
