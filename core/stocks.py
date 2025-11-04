from __future__ import annotations
import time
import logging
from typing import Dict, List, Set, Iterable, Any
from core.ozon_api import post

log = logging.getLogger(__name__)

NONLOCAL_CLUSTERS = {"Казахстан", "Беларусь", "Армения"}

def _chunks(seq: List[Any], n: int) -> Iterable[List[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def _normalize_items(resp: Any) -> List[dict]:
    if isinstance(resp, dict):
        return resp.get("items") or []
    if isinstance(resp, list):
        return resp
    return []

def _clusters_from_items(items: List[dict], min_available: int = 1) -> Dict[int, Set[str]]:
    result: Dict[int, Set[str]] = {}
    for it in items:
        try:
            sku = int(it.get("sku"))
            cluster_name = it.get("cluster_name") or ""
            avail = int(it.get("available_stock_count") or 0)
            if not cluster_name or cluster_name in NONLOCAL_CLUSTERS:
                continue
            if avail >= min_available:
                result.setdefault(sku, set()).add(cluster_name)
        except Exception:
            continue
    return result

def aggregate_by_cluster(skus: List[int], *, batch_size: int = 100) -> Dict[int, Set[str]]:
    if not skus:
        return {}
    agg: Dict[int, Set[str]] = {}
    for batch in _chunks(list(map(str, skus)), batch_size):
        payload = {"skus": batch}
        resp = post("/v1/analytics/stocks", payload)
        items = _normalize_items(resp)
        part = _clusters_from_items(items)
        for sku, clusters in part.items():
            agg.setdefault(sku, set()).update(clusters)
        time.sleep(0.2)
    return agg
