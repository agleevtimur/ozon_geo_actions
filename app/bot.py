import os
import json
import logging
import requests

from app.ozon_client import OzonClient
from app.geo_mapping import GeoResolver
from app.config import ACTIONS

logger = logging.getLogger(__name__)


async def cmd_update_geo(update, context):
    """
    /update_geo <название_акции>
    1) Берём action_id и skus из config.ACTIONS[<name>]
    2) Тянем остатки через /v1/analytics/stocks
    3) По cluster_name → regions (из data/cluster_regions.json)
    4) Переводим regions → addresses (uid региона + uid всех его городов)
    5) POST /api/site/marketplace-seller-actions/v1/action/{id}/update
    """
    if not context.args:
        await update.message.reply_text("Формат: /update_geo <название_акции>")
        return

    action_name = " ".join(context.args).strip().strip('"').strip("'")
    if action_name not in ACTIONS:
        await update.message.reply_text(f"Акция «{action_name}» не найдена в config.ACTIONS")
        return

    action_info = ACTIONS[action_name]
    action_id = int(action_info["id"])
    skus = [str(x) for x in action_info.get("skus", [])]
    if not skus:
        await update.message.reply_text("В акции нет SKU в config.ACTIONS")
        return

    # 1) Ozon клиент
    client = OzonClient()

    # 2) Остатки по /v1/analytics/stocks
    url_stocks = f"{client.base}/v1/analytics/stocks"
    body = {"limit": 1000, "offset": 0, "skus": skus}
    rs = client.sess.post(url_stocks, json=body, timeout=60)
    try:
        rs.raise_for_status()
    except requests.HTTPError:
        await update.message.reply_text(f"Ошибка stocks: {rs.status_code} {rs.text}")
        return

    rj = rs.json()
    items = (
        rj.get("result")
        or rj.get("items")
        or rj.get("data")
        or (rj.get("result", {}) or {}).get("items")
        or []
    )

    # 3) Маппинг кластер→регионы
    mapping_path = os.getenv("CLUSTER_MAP_PATH", "/app/data/cluster_regions.json")
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            cluster_map = {i["cluster"]: i["regions"] for i in json.load(f)}
    except Exception as e:
        await update.message.reply_text(f"Не удалось прочитать {mapping_path}: {e}")
        return

    # Собираем регионы (объединение по всем SKU с наличием > 0)
    regions_set = set()
    sku2regions = {}
    for it in items:
        sku = str(it.get("sku", "")).strip()
        cluster = str(it.get("cluster_name", "")).strip()
        available = it.get("available_stock_count", 0)
        try:
            available = int(available)
        except Exception:
            available = 0
        if not sku or not cluster or available <= 0:
            continue

        regs = cluster_map.get(cluster)
        if not regs:
            logger.warning("Нет маппинга для кластера %s (SKU %s)", cluster, sku)
            continue

        sku2regions.setdefault(sku, set()).update(regs)
        regions_set.update(regs)

    regions = sorted(regions_set, key=str.lower)
    if not regions:
        await update.message.reply_text("Не найдено регионов с наличием > 0 (по заданным SKU)")
        return

    # 4) regions → addresses
    geo = GeoResolver()  # использует GEO_JSON_PATH или /app/data/geo.json по умолчанию
    addresses = geo.regions_to_addresses(regions)
    if not addresses:
        await update.message.reply_text("Не удалось сопоставить регионы в addresses (UID). Проверь data/geo.json")
        return

    # 5) Обновляем акцию
    url_update = f"{client.base}/api/site/marketplace-seller-actions/v1/action/{action_id}/update"
    update_body = {"action_parameters": {"addresses": addresses}}

    ru = client.sess.post(url_update, json=update_body, timeout=60)
    try:
        ru.raise_for_status()
    except requests.HTTPError:
        await update.message.reply_text(f"Ошибка обновления акции: {ru.status_code} {ru.text}")
        return

    await update.message.reply_text(
        f"OK. Обновил адреса акции «{action_name}» (id={action_id}). "
        f"Регионов: {len(regions)}, адресов (uid): {len(addresses)}"
    )


def register_handlers(application):
    """Вызови из инициализации бота, чтобы повесить команду."""
    from telegram.ext import CommandHandler
    application.add_handler(CommandHandler("update_geo", cmd_update_geo))
