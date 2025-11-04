from __future__ import annotations
import logging
from typing import List, Dict, Set
from core.stocks import aggregate_by_cluster
from core.rules import GROUP_TO_PROMO_NAME, GROUP_TO_SKUS

log = logging.getLogger(__name__)

def run_sync_geo(dry_run: bool = False, force: bool = False, return_report: bool = False) -> str | None:
    report: List[str] = []
    def _add(line: str):
        report.append(line); log.info(line)

    _add("=== Синхронизация гео-акций ===")
    _add(f"DRY_RUN={dry_run}")

    all_skus = sorted({sku for skus in GROUP_TO_SKUS.values() for sku in skus})
    agg = aggregate_by_cluster(all_skus)  # sku -> set(cluster_names)

    _add("Результат расчёта (по группам):")
    for code, promo_name in GROUP_TO_PROMO_NAME.items():
        skus: List[int] = GROUP_TO_SKUS.get(code, [])
        clusters_on: Set[str] = set()
        for sku in skus:
            clusters_on |= agg.get(sku, set())
        clusters_sorted = sorted(clusters_on)
        _add(f"• {promo_name} ({code}) — {len(skus)} SKU → {', '.join(clusters_sorted) if clusters_sorted else '—'}")

    return "\n".join(report) if return_report else None
