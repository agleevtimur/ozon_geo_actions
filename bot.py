from __future__ import annotations
import os, asyncio, logging, functools, traceback, inspect
from telegram.ext import Application, CommandHandler

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

MAX_TG = 4096
async def _send_long(chat, text: str):
    chunk, size = [], 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > 3500:
            await chat.send_message("".join(chunk))
            chunk, size = [], 0
        chunk.append(line); size += len(line)
    if chunk:
        await chat.send_message("".join(chunk))

async def start(update, context):
    await update.message.reply_text("Привет! Доступные команды:\n/status — кратко\n/dry_sync_geo — расчёт регионов по акциям")

async def status(update, context):
    await update.message.reply_text("Бот онлайн ✅")

async def dry_sync_geo(update, context):
    try:
        await update.message.reply_text("⚙️ Запускаю dry-run синхронизации…")
        from sync_geo import run_sync_geo
        try:
            sig = inspect.signature(run_sync_geo)
            await update.message.reply_text(f"run_sync_geo signature: {sig}")
        except Exception:
            await update.message.reply_text("Не удалось прочитать сигнатуру run_sync_geo")

        report = None
        try:
            loop = asyncio.get_event_loop()
            func = functools.partial(run_sync_geo, dry_run=True, force=False, return_report=True)
            report = await loop.run_in_executor(None, func)
        except TypeError:
            loop = asyncio.get_event_loop()
            func = functools.partial(run_sync_geo)
            report = await loop.run_in_executor(None, func)

        if report:
            await _send_long(update.message.chat, "✅ Dry-run завершён.\n\n" + str(report))
        else:
            await update.message.reply_text("✅ Dry-run завершён (отчёт пуст).")

    except Exception as e:
        tb = traceback.format_exc()
        await update.message.reply_text(f"❌ Ошибка dry-run: {e}\n\n{tb}"[:4000])
        print(tb)

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("dry_sync_geo", dry_sync_geo))
    log.info("Bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
