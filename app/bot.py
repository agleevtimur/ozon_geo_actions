import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler
from .ozon_client import OzonClient
from .geo_mapping import GeoResolver
from .stocks import aggregate_by_cluster, pick_regions_with_stock_by_cluster, regions_to_addresses

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ACTIONS_IDS = [s.strip() for s in os.getenv("ACTIONS_IDS", "").split(",") if s.strip()]

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
if not ACTIONS_IDS:
    log.warning("ACTIONS_IDS is empty; you can still call /update_geo <id>")

client = OzonClient()
geo = GeoResolver()

async def update_geo_for_action(action_id: str) -> str:
    # 1) SKU внутри акции (если требуется вашим стоковым сервисом)
    skus = client.list_action_skus(action_id)

    # 2) Сырые остатки по кластерам (под ваш сервис/API)
    raw = client.fetch_stocks_raw_for_skus(skus)

    # 3) Агрегация: кластер → {регион: qty}
    by_cluster = aggregate_by_cluster(raw)

    # 4) Сбор регионов для адресов
    regions = pick_regions_with_stock_by_cluster(by_cluster)

    # 5) Преобразование регионов → список UID (регион + его города)
    addresses = geo.regions_to_addresses(regions)

    # 6) Получить текущие параметры акции и заменить addresses
    current = client.view_action(action_id)
    if current is None:
        # fallback: минимальная замена только addresses на update
        ok = client.update_action_addresses_only(action_id, addresses)
        return f"action {action_id}: addresses updated via fallback={ok}, regions={len(regions)}, addresses={len(addresses)}"

    # заменить addresses в текущем параметр-объекте
    body = client.build_update_body_from_view(current, addresses)
    ok = client.update_action_with_body(action_id, body)
    return f"action {action_id}: addresses updated={ok}, regions={len(regions)}, addresses={len(addresses)}"

async def cmd_update_geo(update, context):
    # /update_geo [action_id]
    args = context.args
    ids = ACTIONS_IDS if not args else [args[0]]
    if not ids:
        await update.message.reply_text("Укажите ID: /update_geo <id> или задайте ACTIONS_IDS в ENV")
        return

    results = []
    for aid in ids:
        try:
            msg = await update_geo_for_action(aid)
        except Exception as e:
            msg = f"action {aid}: ERROR {e}"
            log.exception(msg)
        results.append(msg)

    await update.message.reply_text("\n".join(results))

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("update_geo", cmd_update_geo))
    app.run_polling(allowed_updates=["message", "edited_message"])

if __name__ == "__main__":
    main()
