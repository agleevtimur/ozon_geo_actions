import os
import httpx
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)

BASE_URL = os.getenv("OZON_API_BASE", "https://api-seller.ozon.ru")

def _headers() -> Dict[str, str]:
    client_id = os.getenv("OZON_CLIENT_ID")
    api_key = os.getenv("OZON_API_KEY")
    if not client_id or not api_key:
        raise RuntimeError("OZON_CLIENT_ID / OZON_API_KEY are not set")
    return {
        "Client-Id": client_id,
        "Api-Key": api_key,
        "Content-Type": "application/json",
    }

def post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    timeout = float(os.getenv("OZON_API_TIMEOUT", "30"))
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=_headers(), json=payload)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    if r.status_code != 200:
        log.error("OZON API error %s %s: %s", r.status_code, path, body)
        raise RuntimeError(f"OZON API error {r.status_code} {path}: {body}")
    return body
