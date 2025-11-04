from __future__ import annotations

import logging

from core.rules import GROUP_TO_PROMO_NAME, GROUP_TO_SKUS
from core.stocks import aggregate_by_cluster, ensure_id_map, get_warehouses_via_clusters
from core.promo_ui import upsert_promo

log = logging.getLogger(__name__)

def apply_geo_for_group(group: str) -> str:
    promo_name = GROUP_TO_PROMO_NAME.get(group)
    if not promo_name:
        return f"❌ {group} — нет promo_name"
    skus = GROUP_TO_SKUS.get(group, [])
    if not skus:
        return f"⚠️ {promo_name} ({group}) — нет SKU (пропуск)"
    agg = aggregate_by_cluster(skus)
    clusters = sorted({c for arr in agg.values() for c in arr})
    if not clusters:
        return f"• {promo_name} ({group}) — нет остатков"
    status = upsert_promo(promo_name, clusters)
    if status == "skipped":
        return f"⚪ {promo_name} ({group}) — уже актуальна ({len(clusters)} регионов)"
    elif status == "updated":
        return f"✅ {promo_name} ({group}) — обновлена ({len(clusters)} регионов)"
    else:
        return f"❌ {promo_name} ({group}) — ошибка"

def run_sync_geo(dry_run: bool = False) -> str:
    matched = ensure_id_map(fetch_warehouses_func=get_warehouses_via_clusters)
    log.info("Сопоставлено складов: %d", matched)
    lines = []
    for group in GROUP_TO_PROMO_NAME.keys():
        if dry_run:
            skus = GROUP_TO_SKUS.get(group, [])
            agg = aggregate_by_cluster(skus)
            clusters = sorted({c for arr in agg.values() for c in arr})
            promo_name = GROUP_TO_PROMO_NAME[group]
            if clusters:
                lines.append(f"• {promo_name} ({group}) — {len(skus)} SKU → {', '.join(clusters)}")
            else:
                lines.append(f"• {promo_name} ({group}) — нет остатков")
        else:
            lines.append(apply_geo_for_group(group))
    return "\n".join(lines)

def run_sync_geo_apply_one(identifier: str) -> str:
    ident = identifier.lower().strip()
    for g, promo in GROUP_TO_PROMO_NAME.items():
        if g.lower() == ident or promo.lower() == ident:
            return apply_geo_for_group(g)
    return f"❌ Не найдена акция '{identifier}'."
