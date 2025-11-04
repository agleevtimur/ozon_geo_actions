from __future__ import annotations
import os
import httpx
import json
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)

OZON_BASE = "https://api-seller.ozon.ru"

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

def post(path: str, payload: Dict[str, Any]) -> Any:
    url = OZON_BASE + path
    body = json.dumps(payload, ensure_ascii=False)
    with httpx.Client(timeout=30) as client:
        r = client.post(url, headers=_headers(), content=body)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    if r.status_code >= 300:
        raise RuntimeError(f"OZON API error {r.status_code} {path}: {data}")
    return data
