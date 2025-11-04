from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, Iterable, List, Optional, Set

from .ozon_api import post

log = logging.getLogger(__name__)

CACHE_PATH = os.getenv("WAREHOUSE_CACHE_PATH", ".cache/warehouses_id_map.json")
CACHE_TTL_SEC = int(os.getenv("WAREHOUSE_CACHE_TTL_SEC", "86400"))  # 24h

WAREHOUSE_ID_TO_CLUSTER: Dict[int, str] = {}

def _cache_is_fresh(path: str = CACHE_PATH) -> bool:
    try:
        st = os.stat(path)
        return (time.time() - st.st_mtime) <= CACHE_TTL_SEC
    except FileNotFoundError:
        return False

def _load_cache(path: str = CACHE_PATH) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            WAREHOUSE_ID_TO_CLUSTER.clear()
            for k, v in data.items():
                try:
                    WAREHOUSE_ID_TO_CLUSTER[int(k)] = str(v)
                except Exception:
                    continue
            return True
        return False
    except FileNotFoundError:
        return False
    except Exception as e:
        log.warning("Не удалось загрузить кэш %s: %s", path, e)
        return False

def _save_cache(path: str = CACHE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in WAREHOUSE_ID_TO_CLUSTER.items()}, f, ensure_ascii=False, indent=2)

def build_id_map(warehouses: List[dict], persist: bool = True) -> int:
    WAREHOUSE_ID_TO_CLUSTER.clear()
    matched = 0
    for w in warehouses or []:
        try:
            wid = int(w.get("warehouse_id") or 0)
        except Exception:
            continue
        if not wid:
            continue
        cluster = w.get("cluster_name") or w.get("cluster") or w.get("api_cluster")
        if not cluster:
            continue
        WAREHOUSE_ID_TO_CLUSTER[wid] = str(cluster)
        matched += 1
    if persist and matched:
        _save_cache()
    return matched

def ensure_id_map(*, fetch_warehouses_func, force: bool = False) -> int:
    if WAREHOUSE_ID_TO_CLUSTER and not force:
        return len(WAREHOUSE_ID_TO_CLUSTER)
    if not force and _cache_is_fresh() and _load_cache():
        return len(WAREHOUSE_ID_TO_CLUSTER)
    try:
        warehouses = fetch_warehouses_func()
        return build_id_map(warehouses, persist=True)
    except Exception as e:
        log.warning("Не удалось обновить карту складов из API: %s. Пытаюсь загрузить кэш…", e)
        _load_cache()
        return len(WAREHOUSE_ID_TO_CLUSTER)

def get_warehouses_via_clusters() -> List[dict]:
    payload = {"cluster_type": "CLUSTER_TYPE_OZON"}
    resp = post("/v1/cluster/list", payload)
    out: List[dict] = []
    for c in resp.get("clusters", []) or []:
        cname = c.get("name")
        for lc in (c.get("logistic_clusters") or []):
            for w in (lc.get("warehouses") or []):
                out.append({
                    "warehouse_id": w.get("warehouse_id"),
                    "name": w.get("name"),
                    "cluster_name": cname
                })
    return out

def aggregate_by_cluster(skus: Iterable[int | str]) -> Dict[int, Set[str]]:
    skus_list = [str(s).strip() for s in skus if str(s).strip()]
    result: Dict[int, Set[str]] = {}
    if not skus_list:
        return result
    CHUNK = 100
    for i in range(0, len(skus_list), CHUNK):
        chunk = skus_list[i:i+CHUNK]
        payload = {"skus": chunk}
        resp = post("/v1/analytics/stocks", payload)
        items = resp.get("items") or resp
        if isinstance(items, dict):
            items = items.get("items", [])
        for it in (items or []):
            try:
                sku = int(it.get("sku") or it.get("product_id") or 0)
            except Exception:
                continue
            if not sku:
                continue
            avail = int(it.get("available_stock_count") or it.get("present") or 0)
            if avail <= 0:
                continue
            cname = it.get("cluster_name")
            if not cname:
                wid = it.get("warehouse_id")
                try:
                    if wid is not None:
                        cname = WAREHOUSE_ID_TO_CLUSTER.get(int(wid))
                except Exception:
                    cname = None
            if not cname:
                continue
            result.setdefault(sku, set()).add(str(cname))
    return result
