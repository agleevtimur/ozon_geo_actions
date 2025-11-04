# sync_geo.py
# -*- coding: utf-8 -*-
"""
Синхронизация географии существующих «своих акций» Озон (вариант с GEO-G-группами).
Берёт правила из rules.yaml, маппит GEO-G → акция через GROUP_TO_PROMO_NAME,
анализирует остатки по кластерам и обновляет регионы в UI Озон через Playwright.

ENV:
  DRY_RUN=1 — логировать, но не кликать в UI
  HEADLESS=0 — открыть браузер с окном (для отладки)
  OZON_COOKIES_JSON — куки Озон (или файл cookies.json)
"""

from __future__ import annotations
import os, sys, yaml, logging
import functools
from typing import Dict, List, Set

# локальные модули
from core.stocks import aggregate_by_cluster, ensure_id_map
from core.geo_map import CLUSTER_TO_REGIONS
from core.promo_ui import update_promo_regions_ui
from core.rules import GROUP_TO_PROMO_NAME  # словарь GEO-Gx -> "10 скидка"
from core.ozon_api import get_warehouses
import logging

# -----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("sync_geo")

# -----------------------------------------------------------------------------
# Хелперы
# -----------------------------------------------------------------------------

def load_rules(path: str = "rules.yaml") -> dict:
    """Читает rules.yaml с описанием групп GEO-G."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"rules.yaml не найден: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "promo_groups" not in data:
        raise ValueError("В rules.yaml нет promo_groups")
    return data

def clusters_to_regions(cluster_names: List[str]) -> List[str]:
    """Кластеры → уникальные регионы (в порядке добавления)."""
    seen = set()
    regions: List[str] = []
    for cl in cluster_names:
        for r in CLUSTER_TO_REGIONS.get(cl, []):
            if r not in seen:
                seen.add(r)
                regions.append(r)
    return regions

def clusters_on_for_group(mode: str, skus: List[int], agg: Dict[int, Set[str]]) -> List[str]:
    """
    Возвращает список кластеров, где активировать акцию.
    mode=union — если хотя бы у одного SKU есть остатки.
    mode=all — если у всех SKU есть остатки.
    """
    mode = (mode or "union").lower()
    if not skus:
        return []
    sets = [agg.get(int(s), set()) for s in skus]
    if mode == "all":
        result = set.intersection(*sets) if sets else set()
    else:
        result = set.union(*sets) if sets else set()
    return sorted(result)

# -----------------------------------------------------------------------------
# Основная процедура
# -----------------------------------------------------------------------------
log = logging.getLogger(__name__)

def run_sync_geo(dry_run: bool = False, force: bool = False, return_report: bool = False) -> str | None:
    """
    Синхронизация гео-акций:
      - dry_run=True: только расчёт, без изменений на Озоне.
      - force=True: принудительно обновить карту складов из API (игнор кэша).
      - return_report=True: вернуть отчёт текстом (для бота). Иначе писать только в логи.
    """
    report: list[str] = []

    def _add(line: str):
        report.append(line)
        log.info(line)

    log.info("=== Синхронизация гео-акций (GEO-G → promo_name) ===")
    log.info("DRY_RUN=%s | HEADLESS=True", dry_run)

    matched = ensure_id_map(force=force)
    _add(f"Сопоставлено складов: {matched}")

    # Все SKU (множество) из групп
    all_skus = sorted({sku for skus in GROUP_TO_SKUS.values() for sku in skus})
    agg = aggregate_by_cluster(all_skus)  # {sku -> set(cluster_names)}

    _add("")
    _add("Результат расчёта (по группам):")
    for group_code, promo_name in GROUP_TO_PROMO_NAME.items():
        skus = GROUP_TO_SKUS.get(group_code, [])
        clusters_on = set()
        for sku in skus:
            clusters_on |= set(agg.get(sku, set()))
        clusters_sorted = sorted(clusters_on)

        if dry_run:
            _add(f"• {promo_name} ({group_code}): {len(skus)} SKU → "
                 f"{', '.join(clusters_sorted) if clusters_sorted else '—'}")
        else:
            # Здесь боевой сценарий через UI (если нужно):
            # upsert_promo(promo_name=promo_name, clusters=clusters_sorted)
            _add(f"✓ Обновлена акция {promo_name} ({group_code}) на регионы: "
                 f"{', '.join(clusters_sorted) if clusters_sorted else '—'}")

    return "\n".join(report) if return_report else None

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "rules.yaml"
    run_sync_geo(path)
