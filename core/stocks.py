# core/stocks.py
from collections import defaultdict
from pathlib import Path
import json
import time
import re
from typing import Callable, List, Dict, Optional
from collections import defaultdict
from core.warehouses_map import WAREHOUSE_NAME_TO_CLUSTER

# Кластеры стран СНГ — считаем «нелокальными» и пропускаем (по твоему правилу)
NON_LOCAL_CLUSTERS = {"Казахстан", "Беларусь", "Армения"}
# Соответствия названий кластеров из API → названия как в твоём Excel
API_CLUSTER_TO_OUR = {
    "МОСКВАМОИДАЛЬНИЕРЕГИОНЫ": "Москва, МО и Дальние регионы",
    "САНКТПЕТЕРБУРГИСЗО": "Санкт-Петербург и СЗО",
    "КАЗАНЬ": "Казань и Поволжье",
    "УФА": "Уфа",
    "ЮГ": "Краснодар и Юг",
    "УРАЛ": "Екатеринбург и Урал",
    "СИБИРЬ": "Новосибирск и Сибирь",
    "ДАЛЬНИЙВОСТОК": "Дальний Восток",
    "САРАТОВ": "Саратов",
    "КАВКАЗ": "Кавказ",
    "КАЛИНИНГРАД": "Калининград",
    "ВОРОНЕЖ": "Воронеж",
    "ЯРОСЛАВЛЬ": "Ярославль",
    "САМАРА": "Самара",
}

def _norm(s: str) -> str:
    s = (s or "").upper()
    s = s.replace("РФЦ", "").replace("RFC", "")
    return re.sub(r"[^А-ЯA-Z0-9]", "", s)

def _map_cluster(api_cluster: str, wh_name: str) -> str | None:
    """1) пробуем по имени кластера из API; 2) по имени склада из Excel; 3) иначе возвращаем API-кластер как есть."""
    if api_cluster:
        if api_cluster in NON_LOCAL_CLUSTERS:
            return None  # отбрасываем нелокальные страны
        norm = _norm(api_cluster)
        if norm in API_CLUSTER_TO_OUR:
            return API_CLUSTER_TO_OUR[norm]
        # прямое совпадение с Excel-именем
        for excel_cluster in set(WAREHOUSE_NAME_TO_CLUSTER.values()):
            if _norm(excel_cluster) == norm:
                return excel_cluster

    if wh_name:
        # точное имя склада из Excel
        if wh_name in WAREHOUSE_NAME_TO_CLUSTER:
            return WAREHOUSE_NAME_TO_CLUSTER[wh_name]
        # нормализованное совпадение имени склада
        wnorm = _norm(wh_name)
        for wh, cl in WAREHOUSE_NAME_TO_CLUSTER.items():
            if _norm(wh) == wnorm:
                return cl

    # ничего не нашли — используем API-кластер как есть (если он не нелокальный)
    return None if api_cluster in NON_LOCAL_CLUSTERS else (api_cluster or None)

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
    s = (s or "").upper()
    s = s.replace("РФЦ", "").replace("RFC", "")
    s = re.sub(r"[^А-ЯA-Z0-9]", "", s)   # убираем всё, кроме букв/цифр
    return s

def build_id_map(warehouses: list[dict], persist: bool = True) -> int:
    """
    Создаём ID->кластер:
    1) по имени склада (нормализованный ключ),
    2) если не нашли — по имени кластера из API:
       ищем Excel-кластер, который содержит это имя (нормализованно).
    """
    global WAREHOUSE_ID_TO_CLUSTER
    WAREHOUSE_ID_TO_CLUSTER.clear()
    matched = 0

    # Нормализуем МАП из Excel: "ИМЯ СКЛАДА" -> "наш кластер"
    norm_excel_by_wh = { _normalize(name): cluster
                         for name, cluster in WAREHOUSE_NAME_TO_CLUSTER.items() }

    # Список всех названий КЛАСТЕРОВ из Excel (нормализованных) для подсказочного поиска
    excel_clusters_norm = list({ _normalize(cluster) for cluster in WAREHOUSE_NAME_TO_CLUSTER.values() })
    # Мап «нормализованный кластер -> исходный» для обратного восстановления
    excel_norm_to_raw = { _normalize(cluster): cluster for cluster in WAREHOUSE_NAME_TO_CLUSTER.values() }

    for w in warehouses or []:
        wid = w.get("warehouse_id")
        wname = (w.get("name") or "").strip()
        api_cluster = (w.get("cluster_name_from_api") or "").strip()
        if not wid:
            continue

        # 1) Сначала пробуем по имени склада
        target_cluster = norm_excel_by_wh.get(_normalize(wname))

        # 2) Если не нашли — пробуем по названию кластера из API (подстрока)
        if not target_cluster and api_cluster:
            ac = _normalize(api_cluster)
            # Ищем Excel-кластер, где имя кластера из API является подстрокой
            candidates = [c for c in excel_clusters_norm if ac in c or c in ac]
            if candidates:
                target_cluster = excel_norm_to_raw[candidates[0]]

        if target_cluster:
            try:
                WAREHOUSE_ID_TO_CLUSTER[int(wid)] = target_cluster
            except Exception:
                WAREHOUSE_ID_TO_CLUSTER[int(str(wid))] = target_cluster
            matched += 1

    if persist and matched:
        _save_cache()
    return matched

def ensure_id_map(fetch_warehouses_func: Optional[Callable[[], List[dict]]] = None, *, force: bool = False) -> int:
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
        if fetch_warehouses_func is None:
            # ленивый импорт, чтобы избежать циклов
            from core.ozon_api import get_warehouses
            fetch_warehouses_func = get_warehouses

        warehouses = fetch_warehouses_func() or []
        return build_id_map(warehouses, persist=True)
    except Exception:
        # fallback — хотя бы поднимем старый кэш
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


def aggregate_by_cluster(resp: dict) -> dict[int, dict[str, int]]:
    """
    Новый ответ /v1/analytics/stocks:
      items: [ { sku, cluster_name, warehouse_name, available_stock_count, ... }, ... ]
    Возвращает: { sku: { cluster: total_available, ... }, ... }
    """
    buckets = defaultdict(lambda: defaultdict(int))
    for it in (resp.get("items") or []):
        try:
            sku = int(it.get("sku"))
        except Exception:
            continue

        qty = int(it.get("available_stock_count") or 0)
        if qty <= 0:
            continue

        api_cluster = it.get("cluster_name") or ""
        wh_name = it.get("warehouse_name") or ""
        cluster = _map_cluster(api_cluster, wh_name)
        if not cluster:
            continue  # либо нелокальная страна, либо не смогли сматчить

        buckets[sku][cluster] += qty

    return {sku: dict(cmap) for sku, cmap in buckets.items()}
