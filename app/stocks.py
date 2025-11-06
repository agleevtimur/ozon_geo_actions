from typing import Dict, Any, List, Set, DefaultDict
from collections import defaultdict
import logging

log = logging.getLogger("stocks")

# === LEGACY aggregation ===
# Сырые данные -> агрегировать по кластерам, затем по регионам.
# Эта функция реализует старую логику:
# - разбирает ответ вашего бэкенда (адаптируйте ключи в местах помеченных 'ADAPT')
# - суммирует остатки по регионам внутри кластера
#
# Ожидаемый интерфейс: aggregate_by_cluster(raw) -> {cluster_name: {region_name: qty}}

def aggregate_by_cluster(raw: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    by_cluster: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))

    # ---- ADAPT: разбор 'raw' под вашу старую схему ----
    # Примерные структуры (поставьте ваши ключи):
    # raw = {
    #   "clusters": [
    #       {"name": "Центральный", "regions": [
    #           {"name": "Москва и МО", "qty": 123, "items": [...]},
    #       ]},
    #       ...
    #   ]
    # }
    clusters = raw.get("clusters") or []
    if clusters:
        for cl in clusters:
            cname = cl.get("name") or cl.get("cluster") or "UNKNOWN"
            regions = cl.get("regions") or []
            for r in regions:
                rname = r.get("name") or r.get("region") or "UNKNOWN"
                qty = int(r.get("qty", 0))
                by_cluster[cname][rname] += qty
        return {c: dict(r) for c, r in by_cluster.items()}

    # Вариант 2: если ваш ответ — это список позиций со свойствами cluster/region/qty
    items = raw.get("items") or raw.get("data") or []
    for it in items:
        cname = it.get("cluster") or "UNKNOWN"
        rname = it.get("region") or "UNKNOWN"
        qty = int(it.get("qty", 0))
        by_cluster[cname][rname] += qty

    return {c: dict(r) for c, r in by_cluster.items()}

def pick_regions_with_stock_by_cluster(by_cluster: Dict[str, Dict[str, int]]) -> List[str]:
    """Собираем список регионов, где есть товар (qty>0), объединяя по всем кластерам."""
    regions: Set[str] = set()
    for _cluster, regmap in by_cluster.items():
        for rname, qty in regmap.items():
            if qty > 0:
                regions.add(rname)
    return sorted(regions)

# Перевод регионов в addresses происходит в GeoResolver.regions_to_addresses
def regions_to_addresses(regions: List[str]) -> List[str]:
    raise NotImplementedError("Use GeoResolver.regions_to_addresses")  # держим интерфейс явным
