# core/promo_sync.py
from core.rules import load_rules
from core.ozon_api import get_stocks
from core.stocks import aggregate_by_cluster
from core.geo_map import CLUSTER_TO_REGIONS  # кластер -> [имена регионов из UI]
from core.promo_ui import update_promo_regions_ui

# сопоставление групп -> названия акций в ЛК (заполни под себя)
GROUP_TO_PROMO_NAME = {
    "GEO-G1": "10 скидка",
    "GEO-G2": "9 скидка",
    "GEO-G3": "8 скидка",
    "GEO-G4": "7 скидка",
    "GEO-G5": "6 скидка",
    "GEO-G6": "5 скидка",
    "GEO-G7": "4 скидка",
    "GEO-G8": "3 ОБЩАЯ скидка",
    "GEO-G9": "2 скидка",
    "GEO-G10": "1 скидка",
    # ...если у тебя другие имена акций — впиши их здесь
}

def compute_regions_for_group(skus: list[int]) -> list[str]:
    """Из остатков получаем список регионов для включения в акцию."""
    resp = get_stocks(skus)
    agg = aggregate_by_cluster(resp)  # {sku: {cluster: qty}}
    clusters = set()
    for sku, cmap in agg.items():
        for cl, qty in cmap.items():
            if qty > 0:
                clusters.add(cl)
    # переводим кластеры -> регионы (ИМЕНА, как в UI)
    regions = []
    for cl in clusters:
        regions += CLUSTER_TO_REGIONS.get(cl, [])
    # уникализируем, сохраняем порядок
    seen = set()
    out = []
    for r in regions:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

def sync_geo_promos_ui() -> list[str]:
    """
    Для каждой группы из rules.yaml:
      - считаем нужные регионы
      - открываем акцию в ЛК и обновляем «географию»
    Возвращает лог-строки.
    """
    logs = []
    rules = load_rules()
    groups = rules.get("promo_groups", {})

    for group_name, cfg in groups.items():
        promo_name = GROUP_TO_PROMO_NAME.get(group_name)
        if not promo_name:
            logs.append(f"⚠️ Пропуск {group_name}: нет сопоставления promo_name")
            continue

        skus = [int(x) for x in cfg.get("skus", [])]
        regions = compute_regions_for_group(skus)
        if not regions:
            logs.append(f"⚠️ {group_name}/{promo_name}: нет регионов (0 остатков) — географию оставляем как есть")
            continue

        try:
            update_promo_regions_ui(promo_name, regions, headless=True)
            logs.append(f"✅ {group_name}/{promo_name}: обновлено регионов — {len(regions)}")
        except Exception as e:
            logs.append(f"❌ {group_name}/{promo_name}: ошибка UI-обновления: {e}")

    return logs
