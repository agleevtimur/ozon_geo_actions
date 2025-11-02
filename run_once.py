import os
from core.logger import setup_logger
from core.rules import load_rules
from core.decide import clusters_on_for_sku, clusters_for_group, discount_for_group
from core.promo_ui import upsert_promo
from core.ozon_api import get_stocks, get_warehouses
from core.stocks import aggregate_by_cluster, ensure_id_map

def main():
    rules = load_rules()
    groups = rules.get("promo_groups", {})
    if not groups:
        log.warning("В rules.yaml нет promo_groups"); return

    all_skus = sorted({int(s) for g in groups.values() for s in g.get("skus", [])})
    if not all_skus:
        log.warning("В promo_groups нет SKU."); return

    # обеспечиваем ID→кластер (из кэша или разово из API)
    matched = ensure_id_map(get_warehouses, force=False)
    log.info(f"ID→кластер: сопоставлено {matched} складов (кэш {'OK' if matched else 'empty'})")

    stocks = get_stocks(all_skus)
    agg = aggregate_by_cluster(stocks)

    # дальше как было...

    sku_clusters_on = {sku: clusters_on_for_sku(sku, agg.get(sku, {}), rules) for sku in all_skus}

    for group_name, g in groups.items():
        if not g.get("enabled", True): continue
        group_clusters = clusters_for_group(g, sku_clusters_on, rules)
        cities = []
        for cl in sorted(group_clusters):
            cities.extend(rules.get("clusters", {}).get(cl, []))
        discount = discount_for_group(g, rules)
        offer_ids = [str(s) for s in g.get("skus", [])]
        log.info(f"{group_name}: clusters={sorted(group_clusters)} cities={len(cities)} discount={discount}% skus={offer_ids}")
        upsert_promo(group_name, cities, discount,
                     offer_ids=offer_ids,
                     cookies_path=os.getenv("COOKIES_PATH","./cookies.json"),
                     headless=os.getenv("HEADLESS","true").lower()=="true")

if __name__ == "__main__":
    main()
