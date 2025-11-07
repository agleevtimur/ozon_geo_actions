import os
import sys
import json
import logging
import requests
from typing import Any, Dict, List

from telegram.ext import ApplicationBuilder, CommandHandler

from app.config import ACTIONS
from app.geo_mapping import GeoResolver
from app.ozon_openapi import OzonOpenApi
from app.ozon_client import update_action_via_proxy  # UI-домен с куками (seller.ozon.ru)

# базовое логирование в stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _extract_items_from_openapi(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Нормализуем ответ OpenAPI по /v1/analytics/stocks:
    возвращаем список items, где у каждого ожидаем:
      sku, cluster_name, available_stock_count
    """
    items = (
        resp.get("result")
        or resp.get("items")
        or resp.get("data")
        or (resp.get("result", {}) or {}).get("items")
        or []
    )
    if not isinstance(items, list):
        logger.warning("Unexpected stocks payload: keys=%s", list(resp.keys()))
        return []
    return items


def _load_cluster_mapping(mapping_path: str) -> Dict[str, List[str]]:
    with open(mapping_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {row["cluster"]: row["regions"] for row in data}


async def cmd_update_geo(update, context):
    """
    /update_geo <название_акции>
      1) action_id, skus из config.ACTIONS
      2) stocks = OzonOpenApi.fetch_stocks_for_skus(skus)
      3) union регионов через соответствие cluster_name -> regions (cluster_regions.json)
      4) regions -> addresses (GeoResolver)
      5) POST https://seller.ozon.ru/api/site/marketplace-seller-actions/v1/action/{id}/update
    """
    if not context.args:
        await update.message.reply_text("Формат: /update_geo <название_акции>")
        return

    action_name = " ".join(context.args).strip().strip('"').strip("'")
    if action_name not in ACTIONS:
        await update.message.reply_text(f"Акция «{action_name}» не найдена в config.ACTIONS")
        return

    cfg = ACTIONS[action_name]
    action_id = int(cfg["id"])
    skus = [str(x) for x in cfg.get("skus", [])]
    if not skus:
        await update.message.reply_text("В акции нет SKU в config.ACTIONS")
        return

    # 1) загрузим карту кластер->регионы
    mapping_path = os.getenv("CLUSTER_MAP_PATH", "/app/data/cluster_regions.json")
    try:
        cluster_map = _load_cluster_mapping(mapping_path)
    except Exception as e:
        await update.message.reply_text(f"Не удалось прочитать {mapping_path}: {e}")
        return

    # 2) остатки из OpenAPI
    try:
        api = OzonOpenApi()
        raw = api.fetch_stocks_for_skus(skus)
        items = _extract_items_from_openapi(raw)
    except requests.HTTPError as e:
        snippet = e.response.text if getattr(e, "response", None) is not None else str(e)
        if snippet and len(snippet) > 1500:
            snippet = snippet[:1500] + "…"
        await update.message.reply_text(f"Ошибка stocks OpenAPI: {getattr(e.response,'status_code','???')}\n{snippet}")
        return
    except Exception as e:
        logger.exception("OpenAPI stocks failed")
        await update.message.reply_text(f"Ошибка stocks OpenAPI: {e}")
        return

    # 3) собираем регионы (union по всем SKU, где available_stock_count > 0)
    regions_set = set()
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

        regions_set.update(regs)

    regions = sorted(regions_set, key=str.lower)
    if not regions:
        await update.message.reply_text("Не найдено регионов с наличием > 0 по заданным SKU")
        return

    # 4) regions -> addresses (uid региона + uid его городов)
    geo = GeoResolver()  # читает GEO_JSON_PATH или /app/data/geo.json
    addresses = geo.regions_to_addresses(regions)
    if not addresses:
        await update.message.reply_text("Не удалось сопоставить регионы в addresses (UID). Проверь data/geo.json")
        return

    # 5) апдейт акции через seller.ozon.ru (куки в OzonClient)
    resp = update_action_via_proxy(
        action_id=action_id,
        addresses=addresses,
        title=action_name
    )

    # Всегда сообщаем итоги
    status = resp.status_code
    snippet = (resp.text or "")[:500]

    if 200 <= status < 300:
        await update.message.reply_text(
            f"✅ Обновил акцию «{title}» (id={action_id}). HTTP {status}\n"
            f"Регионов: {len(regions)}, адресов: {len(addresses)}"
        )
        return

    # Теоретически сюда не попадём (raise_for_status выше), но оставим на всякий
    await update.message.reply_text(f"❌ Обновление вернуло HTTP {status}\n{snippet}")
    logger.error("Update HTTP %s: %s", status, (resp.text or "")[:5000])


def register_handlers(application):
    application.add_handler(CommandHandler("update_geo", cmd_update_geo))


def main():
    token = (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_TOKEN")
        or ""
    ).strip()
    if not token:
        logger.error("Telegram bot token is missing. Set TELEGRAM_BOT_TOKEN/BOT_TOKEN.")
        raise SystemExit(2)

    app = ApplicationBuilder().token(token).build()
    register_handlers(app)
    logger.info("Bot is starting polling...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
