# app/geo_mapping.py
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Iterable
import logging
import unicodedata

log = logging.getLogger(__name__)

def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip().lower()

# Варианты ключей, которые могут встретиться в «сыром» geo.json
TYPE_KEYS = ["type", "nodeType", "level", "kind", "address_type", "category"]
UID_KEYS  = ["uid", "id", "uuid", "guid", "addressUid", "address_uid", "code"]
NAME_KEYS = ["name", "title", "label", "text", "address", "fullName"]
CHILD_KEYS = ["children", "items", "regions", "cities", "nodes", "elements", "data"]

PARENT_KEYS = ["parentUid", "parent_uid", "parentId", "parent_id", "parent", "regionUid", "region_uid"]

# Русские и английские эвристики типов
def _classify_type(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    t = _norm(raw)
    # «город»
    if any(k in t for k in ["city", "город"]):
        return "city"
    # «регион»
    if any(k in t for k in ["region", "область", "край", "республика", "округ", "ao", "ао"]):
        return "region"
    # «страна»
    if any(k in t for k in ["country", "страна"]):
        return "country"
    # Иногда уровень задают числами
    if t in {"0", "root"}:
        return "country"
    if t in {"1", "region", "admin1"}:
        return "region"
    if t in {"2", "city", "admin2", "settlement"}:
        return "city"
    return None

def _get_first(d: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None

def _children_of(d: Dict[str, Any]) -> List[Any]:
    out: List[Any] = []
    for k in CHILD_KEYS:
        v = d.get(k)
        if isinstance(v, list):
            out.extend(v)
        elif isinstance(v, dict):
            out.append(v)
    return out

def _extract_name(d: Dict[str, Any]) -> Optional[str]:
    v = _get_first(d, NAME_KEYS)
    return str(v).strip() if v is not None else None

def _extract_uid(d: Dict[str, Any]) -> Optional[str]:
    v = _get_first(d, UID_KEYS)
    return str(v).strip() if v is not None else None

def _extract(d: dict) -> str:
    return d.get("name", "").strip()
