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

def run_sync_geo(rules_path: str = "rules.yaml"):
    dry = os.getenv("DRY_RUN", "0") == "1"
    headless = os.getenv("HEADLESS", "1") != "0"

    log.info("=== Синхронизация гео-акций (GEO-G → promo_name) ===")
    log.info("DRY_RUN=%s | HEADLESS=%s", dry, headless)

    # 1) Загружаем rules.yaml
    rules = load_rules(rules_path)
    groups: Dict[str, dict] = rules.get("promo_groups", {})
    if not groups:
        log.warning("Нет promo_groups в rules.yaml")
        return

    # 2) Собираем все SKU
    all_skus: List[int] = []
    for gname, cfg in groups.items():
        skus = cfg.get("skus", [])
        all_skus.extend(int(s) for s in skus)
    all_skus = sorted(set(all_skus))
    if not all_skus:
        log.warning("В rules.yaml нет SKU")
        return

    # 3) Готовим карту складов
    matched = ensure_id_map(fetch_warehouses_func=get_warehouses, force=False)
    log.info("Сопоставлено складов: %d", matched)

    # 4) Считаем по остаткам, где что есть
    agg = aggregate_by_cluster(all_skus)  # {sku -> set(clusters_with_stock)}
    if not agg:
        log.warning("aggregate_by_cluster вернул пусто — проверь OZON API")
        return

    # 5) Планируем обновления
    plan = []
    for group_name, cfg in groups.items():
        mode = cfg.get("mode", "union")
        skus = [int(s) for s in cfg.get("skus", [])]
        clusters_on = clusters_on_for_group(mode, skus, agg)
        regions = clusters_to_regions(clusters_on)
        promo_name = GROUP_TO_PROMO_NAME.get(group_name)

        if not promo_name:
            log.warning("⚠️ Нет promo_name для %s в GROUP_TO_PROMO_NAME", group_name)
            continue

        plan.append((group_name, promo_name, clusters_on, regions))

    # 6) Выполняем
    for group_name, promo_name, clusters_on, regions in plan:
        log.info("=== %s (%s) ===", group_name, promo_name)
        log.info("Кластеры: %s", clusters_on)
        log.info("Регионов: %d", len(regions))

        if not regions:
            log.warning("  → Пропуск: нет активных регионов")
            continue

        if dry:
            log.info("  [DRY_RUN] Только лог: %s (%d регионов)", promo_name, len(regions))
        else:
            try:
                update_promo_regions_ui(promo_name, regions, headless=headless)
                log.info("  ✅ Обновлено: %s (регионов: %d)", promo_name, len(regions))
            except Exception as e:
                log.exception("  ❌ Ошибка при обновлении '%s': %s", promo_name, e)

    log.info("=== Синхронизация завершена ===")

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "rules.yaml"
    run_sync_geo(path)
