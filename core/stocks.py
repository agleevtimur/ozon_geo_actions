# core/stocks.py
from collections import defaultdict
from pathlib import Path
import json
import time
import re
from typing import Dict, List, Optional
from core.warehouses_map import WAREHOUSE_NAME_TO_CLUSTER

# Рантайм-словарь ID→кластер (заполняется из кэша/из API)
WAREHOUSE_ID_TO_CLUSTER: Dict[int, str] = {}

# Файл кэша на диске (лежит рядом с кодом)
CACHE_PATH = Path("warehouse_id_to_cluster.json")
# Сколько часов считаем кэш «свежим» (по умолчанию ~30 дней)
CACHE_TTL_HOURS = 24 * 30

def _now_ts() -> int:
    return int(time.time())


def _load_cache() -> bool:
    """Пробуем загрузить кэш из файла. Возвращает True, если кэш применён."""
    global WAREHOUSE_ID_TO_CLUSTER
    if not CACHE_PATH.exists():
        return False
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        mapping = data.get("map") or {}
        # применяем
        WAREHOUSE_ID_TO_CLUSTER = {int(k): v for k, v in mapping.items()}
        return True
    except Exception:
        return False


def _save_cache() -> None:
    """Сохраняем кэш на диск."""
    data = {
        "updated_at": _now_ts(),
        "map": {int(k): v for k, v in WAREHOUSE_ID_TO_CLUSTER.items()},
    }
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_is_fresh() -> bool:
    if not CACHE_PATH.exists():
        return False
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        ts = int(data.get("updated_at") or 0)
        age_hours = ( _now_ts() - ts ) / 3600
        return age_hours <= CACHE_TTL_HOURS and bool(data.get("map"))
    except Exception:
        return False

def _normalize(s: str) -> str:
    """Нормализуем имя: верхний регистр, убираем пробелы/знаки, выкидываем РФЦ/RFC"""
    s = (s or "").upper()
    s = s.replace("РФЦ", "").replace("RFC", "")
    s = re.sub(r"[^А-ЯA-Z0-9]", "", s)  # только буквы/цифры
    return s

# Маппинг названий кластеров из API -> твои кластеры (можно оставить пустым и дополнять по /dump_warehouses)
API_CLUSTER_TO_OUR: dict[str, str] = {
    # "МОСКВАИМО": "Москва, МО и Дальние регионы",
    # "САНКТПЕТЕРБУРГИЛЕНОБЛАСТЬ": "Санкт-Петербург и СЗО",
    # "КАЗАНЬИПОВОЛЖЬЕ": "Казань",
    # ...
}

def build_id_map(warehouses: list[dict], persist: bool = True) -> int:
    """
    Создаём ID->кластер:
    1) пытаемся по имени склада (фаззи-матч),
    2) если не нашли — по имени кластера из API (через API_CLUSTER_TO_OUR).
    """
    global WAREHOUSE_ID_TO_CLUSTER
    WAREHOUSE_ID_TO_CLUSTER.clear()
    matched = 0

    # Нормализуем ключи Excel-маппинга
    norm_excel = { _normalize(name): cluster for name, cluster in WAREHOUSE_NAME_TO_CLUSTER.items() }
    # Нормализуем словарь «имя кластера API -> наш кластер»
    norm_api_cluster = { _normalize(k): v for k, v in API_CLUSTER_TO_OUR.items() }

    for w in warehouses or []:
        wid = w.get("warehouse_id")
        wname = (w.get("name") or "").strip()
        api_cluster = (w.get("cluster_name_from_api") or "").strip()
        if not wid:
            continue

        target_cluster = None

        # 1) матч по имени склада (строгий нормализованный ключ)
        n = _normalize(wname)
        target_cluster = norm_excel.get(n)

        # 1a) частичное совпадение (если строгого нет)
        if not target_cluster:
            for key, val in norm_excel.items():
                if key in n or n in key:
                    target_cluster = val
                    break

        # 2) матч по имени кластера из API (если по складу не нашли)
        if not target_cluster and api_cluster:
            cn = _normalize(api_cluster)
            target_cluster = norm_api_cluster.get(cn)

        if target_cluster:
            try:
                WAREHOUSE_ID_TO_CLUSTER[int(wid)] = target_cluster
            except Exception:
                # на случай, если wid приходит строкой странного формата
                WAREHOUSE_ID_TO_CLUSTER[int(str(wid))] = target_cluster
            matched += 1

    if persist and matched:
        _save_cache()
    return matched
    
def ensure_id_map(fetch_warehouses_func, force: bool = False) -> int:
    """
    Обеспечить наличие актуального ID→кластер.
    1) Если force=True — всегда тянем из API и перезаписываем кэш.
    2) Если кэш свежий — грузим из файла и НЕ звоним в API.
    3) Если кэш старый/пустой — звоним в API и сохраняем на диск.
    Возвращает число сопоставленных складов.
    """
    # если уже есть в памяти и не принудительно — используем
    if WAREHOUSE_ID_TO_CLUSTER and not force:
        return len(WAREHOUSE_ID_TO_CLUSTER)

    # кэш свежий? грузим
    if not force and _cache_is_fresh() and _load_cache():
        return len(WAREHOUSE_ID_TO_CLUSTER)

    # иначе — обновляем из API
    try:
        warehouses = fetch_warehouses_func()  # ожидаем список dict'ов
        return build_id_map(warehouses, persist=True)
    except Exception:
        # как fallback попытаемся хотя бы загрузить старый кэш
        _load_cache()
        return len(WAREHOUSE_ID_TO_CLUSTER)


def _cluster_by_id(wh_id) -> Optional[str]:
    try:
        return WAREHOUSE_ID_TO_CLUSTER.get(int(wh_id))
    except Exception:
        return None


def _qty_present(stock_rec: dict) -> int:
    # /v1/analytics/stocks: поле количества — present
    try:
        return int(stock_rec.get("present", 0) or 0)
    except Exception:
        return 0


def aggregate_by_cluster(stocks_resp: dict) -> dict[int, dict[str, int]]:
    """
    Формат /v1/analytics/stocks:
    {
      "items":[
        {
          "offer_id":"...",
          "product_id":...,
          "stocks":[
            {"present":10, "reserved":1, "sku":123, "warehouse_ids":[112..., 112...]},
            ...
          ]
        }
      ],
      "total": ...
    }
    → Возвращаем: { sku: { cluster: qty, ... }, ... }
    """
    out = {}
    buckets = defaultdict(list)

    for it in (stocks_resp.get("items") or []):
        for s in (it.get("stocks") or []):
            try:
                sku = int(s.get("sku"))
                buckets[sku].append(s)
            except Exception:
                continue

    for sku, recs in buckets.items():
        cmap = defaultdict(int)
        for rec in recs:
            qty = _qty_present(rec)
            for wh_id in (rec.get("warehouse_ids") or []):
                cluster = _cluster_by_id(wh_id)
                if cluster:
                    cmap[cluster] += qty
        out[sku] = dict(cmap)

    return out
