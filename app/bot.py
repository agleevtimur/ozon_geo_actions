import logging
from typing import List
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from .config import TELEGRAM_BOT_TOKEN
from .ozon_api import update_action_addresses

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

ACTION_MAP = {
    "10": 2983461,
    "9": 2983456,
    "8": 2983449,
    "7": 2983433,
    "6": 2983414,
    "5": 2983408,
    "4": 2983396,
    "2": 2983375,
    "1": 2983366,
    "3_common": 2772472,
}

def parse_addresses_arg(arg: str) -> List[str]:
    items = [x.strip() for x in arg.split(",") if x.strip()]
    return items

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я готов.\n"
        "/ping — проверить доступность\n"
        "/update_geo <action_key_or_id> <title> <days> <csv_uids>\n"
        "  Пример: /update_geo 10 \"10% скидка\" 180 c528e99b-...,8f41253d-...\n"
        "  <days> — длительность акции от сегодняшнего дня (UTC)."
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")

def _coerce_action_id(s: str) -> int:
    if s.isdigit() and len(s) > 4:
        return int(s)
    if s in ACTION_MAP:
        return ACTION_MAP[s]
    raise ValueError("Неизвестная акция. Передай полный ID или один из ключей: " + ", ".join(ACTION_MAP.keys()))

async def update_geo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) < 4:
            await update.message.reply_text(
                "Формат: /update_geo <action_key_or_id> <title> <days> <csv_uids>\n"
                "Пример: /update_geo 10 \"10% скидка\" 180 c528e99b-...,8f41253d-..."
            )
            return

        action_key_or_id = context.args[0]
        title = context.args[1]
        days = int(context.args[2])
        csv_uids = " ".join(context.args[3:])
        addresses = parse_addresses_arg(csv_uids)

        action_id = _coerce_action_id(action_key_or_id)

        now_utc = datetime.now(timezone.utc)
        date_start_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        date_end_iso = (now_utc + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        log.info("Updating action %s with %d addresses", action_id, len(addresses))
        res = update_action_addresses(
            action_id=action_id,
            title=title,
            date_start_iso=date_start_iso,
            date_end_iso=date_end_iso,
            addresses=addresses,
        )
        await update.message.reply_text(f"Ок. Обновил акцию {action_id}. Ответ OZON: {res}")
    except Exception as e:
        log.exception("update_geo failed")
        await update.message.reply_text(f"Ошибка: {e}")

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty. Set Railway variable TELEGRAM_BOT_TOKEN.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("update_geo", update_geo))

    log.info("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()