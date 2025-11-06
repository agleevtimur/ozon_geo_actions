from typing import List, Dict, Any, Optional
import requests
from .config import (
    OZON_COOKIE_PLAIN,
    OZON_COMPANY_ID,
    OZON_LANGUAGE,
    DEFAULT_TIMEOUT,
    BASE_ACTION_UPDATE_URL_TEMPLATE,
)

class OzonAuthError(Exception):
    pass

def _headers() -> Dict[str, str]:
    if not OZON_COOKIE_PLAIN:
        raise OzonAuthError("OZON_COOKIE_PLAIN is empty. Set Railway variable OZON_COOKIE_PLAIN to full cookie string.")
    return {
        "Cookie": OZON_COOKIE_PLAIN,
        "x-o3-app-name": "seller-ui",
        "x-o3-company-id": str(OZON_COMPANY_ID),
        "x-o3-language": OZON_LANGUAGE,
        "x-o3-page-type": "highlights-other",
        "Content-Type": "application/json",
    }

def update_action_addresses(
    *,
    action_id: int,
    title: str,
    date_start_iso: str,
    date_end_iso: str,
    addresses: List[str],
    marketplace_id: int = 1,
    is_additional_discount: bool = False,
    marketplace_min_discount_percent: int = 1,
    discount_type: str = "FINAL_PRICE",
    warehouses: Optional[List[str]] = None,
    req_timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    '''
    Minimal wrapper around the OZON 'update action' endpoint.
    - `addresses` must be a list of address UIDs (страна/регион/город).
    - `title` is required by backend; pass what you need (can be unchanged current title).
    '''
    if warehouses is None:
        warehouses = []

    url = BASE_ACTION_UPDATE_URL_TEMPLATE.format(action_id=action_id)
    payload = {
        "action_parameters": {
            "title": title,
            "date_start": date_start_iso,
            "date_end": date_end_iso,
            "type": "DISCOUNT",
            "marketplace_id": marketplace_id,
            "warehouses": warehouses,
            "addresses": addresses,
            "is_additional_discount": is_additional_discount,
            "marketplace_min_discount_percent": marketplace_min_discount_percent,
            "discount_type": discount_type,
        }
    }
    resp = requests.post(url, headers=_headers(), json=payload, timeout=req_timeout)
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}
    if not resp.ok:
        raise RuntimeError(f"Update failed [{resp.status_code}]: {data}")
    return data