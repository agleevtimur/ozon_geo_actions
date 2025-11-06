import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler
from .ozon_client import OzonClient
from .geo_mapping import GeoResolver
from .stocks import aggregate_by_cluster, pick_regions_with_stock_by_cluster, regions_to_addresses
from .config import ACTIONS

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
    """
    /update_geo <название_акции>
    Пример:
      /update_geo "10 скидка"
      /update_geo 9
    """
    if not ctx.args:
        await update.message.reply_text("Формат: /update_geo <название_акции>")
        return

    # Собираем аргументы в строку — чтобы можно было писать с пробелами
    action_name = " ".join(ctx.args).strip().strip('"').strip("'")

    # Находим акцию по названию
    action = ACTIONS.get(action_name)
    if not action:
        # Попробуем частичный поиск по цифре или подстроке
        matches = [k for k in ACTIONS if action_name.lower() in k.lower()]
        if matches:
            await update.message.reply_text(
                f"Возможно, вы имели в виду: {', '.join(matches)}"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Акция '{action_name}' не найдена. Проверь config.py"
            )
        return

    action_id = action["id"]
    skus = action["skus"]
    if not skus:
        await update.message.reply_text(f"⚠️ В акции '{action_name}' нет SKU в config.py")
        return

    try:
        stocks_info = aggregate_by_cluster(skus)
        addresses = _resolve_addresses_from_stocks(stocks_info)
        resp = _update_action_addresses(action_id, addresses)
        summary = {
            "action_name": action_name,
            "action_id": action_id,
            "total_stock": stocks_info.get("total", 0),
            "addresses_count": len(addresses),
            "skus": skus,
        }
        msg = f"✅ Акция обновлена\n{json.dumps(summary, ensure_ascii=False, indent=2)}"
        await update.message.reply_text(msg)
    except requests.HTTPError as http_err:
        try:
            err_body = http_err.response.json()
        except Exception:
            err_body = http_err.response.text if http_err.response is not None else str(http_err)
        log.exception("HTTP error during update")
        await update.message.reply_text(f"HTTP {http_err.response.status_code if http_err.response else ''}: {err_body}")
    except Exception as e:
        log.exception("update_geo failed")
        await update.message.reply_text(f"Ошибка: {e}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("update_geo", cmd_update_geo))
    app.run_polling(allowed_updates=["message", "edited_message"])

if __name__ == "__main__":
    main()
