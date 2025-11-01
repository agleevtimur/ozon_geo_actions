from collections import Counter
def clusters_on_for_sku(sku: int, cluster_qty: dict, rules: dict) -> set:
    dflt = rules.get("defaults", {})
    sku_over = rules.get("skus", {}).get(str(sku), {})
    q_min = sku_over.get("q_min", dflt.get("q_min", 15))
    return {cluster for cluster, q in (cluster_qty or {}).items() if q >= q_min}
def clusters_for_group(group_cfg: dict, sku_to_clusters: dict, rules: dict) -> set:
    mode = group_cfg.get("group_city_mode") or rules.get("defaults",{}).get("group_city_mode","union")
    skus = [int(s) for s in group_cfg.get("skus", [])]
    sets = [sku_to_clusters.get(s, set()) for s in skus]
    if not sets: return set()
    if mode == "union":
        out = set().union(*sets)
    elif mode == "threshold":
        k = int(group_cfg.get("group_city_threshold") or rules.get("defaults",{}).get("group_city_threshold",1))
        cnt = Counter(); [cnt.update(s) for s in sets]
        out = {c for c,n in cnt.items() if n >= k}
    else:
        out = set.intersection(*sets)
    return out
def discount_for_group(group_cfg: dict, rules: dict) -> int:
    return int(group_cfg.get("discount", rules.get("defaults",{}).get("discount", 12)))
