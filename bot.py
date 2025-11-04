from __future__ import annotations

import asyncio
import logging
import os

from telegram.ext import Application, CommandHandler

from sync_geo import run_sync_geo, run_sync_geo_apply_one

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_IDS = {i.strip() for i in os.getenv("TG_ALLOWED_USER_IDS", "").split(",") if i.strip()}

def _allowed(user_id):
    if not ALLOWED_IDS:
        return True
    return user_id and str(user_id) in ALLOWED_IDS

def guard(func):
    async def wrapper(update, context):
        uid = update.effective_user.id if update and update.effective_user else None
        if not _allowed(uid):
            await update.message.reply_text("Access denied.")
            return
        return await func(update, context)
    return wrapper

@guard
async def start(update, context):
    await update.message.reply_text(
        "Команды:\n"
        "/dry_sync_geo — показать географию по остаткам (без изменений)\n"
        "/apply_geo — применить для всех акций\n"
        "/apply_geo_one <название или GEO-Gx> — применить для одной акции"
    )

@guard
async def dry_sync_geo(update, context):
    await update.message.reply_text("Считаю (dry-run)…")
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, lambda: run_sync_geo(dry_run=True))
    await update.message.reply_text(text[:4000] if text else "Пусто.")

@guard
async def apply_geo(update, context):
    await update.message.reply_text("Применяю…")
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, run_sync_geo)
    await update.message.reply_text(text[:4000] if text else "Готово.")

@guard
async def apply_geo_one(update, context):
    if not context.args:
        await update.message.reply_text("Использование: /apply_geo_one <название акции или GEO-код>")
        return
    ident = " ".join(context.args)
    await update.message.reply_text(f"Запускаю для '{ident}'…")
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, run_sync_geo_apply_one, ident)
    await update.message.reply_text(text[:4000] if text else "Готово.")

def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("dry_sync_geo", dry_sync_geo))
    application.add_handler(CommandHandler("apply_geo", apply_geo))
    application.add_handler(CommandHandler("apply_geo_one", apply_geo_one))
    application.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
