
import os, asyncio, logging, json
from dotenv import load_dotenv
import functools
from functools import wraps
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.logger import setup_logger
from core.rules import load_rules, save_rules
from core.ozon_api import get_stocks, get_warehouses
from core.stocks import aggregate_by_cluster, ensure_id_map
from core.decide import clusters_on_for_sku, clusters_for_group, discount_for_group
from run_once import main as run_pipeline
from sync_geo import run_sync_geo
import traceback

class TempEnv:
    """
    Контекстный менеджер для временной установки ENV-переменных.
    Пример:
        with TempEnv(DRY_RUN="1", HEADLESS="1"):
            run_sync_geo()
    После выхода из блока все переменные вернутся в исходное состояние.
    """
    def __init__(self, **pairs):
        self.pairs = pairs
        self.prev = {}

    def __enter__(self):
        for k, v in self.pairs.items():
            self.prev[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)

    def __exit__(self, exc_type, exc, tb):
        for k, old in self.prev.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old

load_dotenv()
log = setup_logger()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_CHAT_IDS","").split(",") if x.strip()}

# Auto-create cookies.json from env if provided
if not os.path.exists("cookies.json") and os.getenv("COOKIES_JSON"):
    try:
        data = json.loads(os.getenv("COOKIES_JSON"))
        with open("cookies.json","w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        log.info("cookies.json created from COOKIES_JSON env")
    except Exception as e:
        log.warning(f"Failed to create cookies.json from env: {e}")

MAX_TG = 4096

async def _send_long(chat, text: str):
    # бьём по строкам, чтобы не резать слова
    chunk = []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > 3500:  # немного запас, чтобы не врезаться в 4096
            await chat.send_message("".join(chunk))
            chunk, size = [], 0
        chunk.append(line)
        size += len(line)
    if chunk:
        await chat.send_message("".join(chunk))
        
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("Доступ запрещён."); return
        return await func(update, context)
    return wrapper

@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я управляю гео-акциями Ozon.\n"
        "/status — сводка\n/run — запустить прогон\n"
        "/groups — список групп\n"
        "/group_mode <NAME|default> <union|intersection|threshold> [k]\n"
        "/group_discount <NAME|default> <pct>\n"
        "/group_add_sku <NAME> <SKU>\n/group_rm_sku <NAME> <SKU>\n"
        "/set_qmin <SKU|default> <qty>\n"
        "/enable <SKU> /disable <SKU>"
    )

@admin_only
async def status(update, context):
    rules = load_rules()
    groups = rules.get("promo_groups", {})
    all_skus = sorted({int(s) for g in groups.values() for s in g.get("skus", [])})
    if not all_skus:
        await update.message.reply_text("В promo_groups нет SKU."); return

    # загрузим кэш или один раз подтянем список складов
    matched = ensure_id_map(get_warehouses, force=False)

    try:
        stocks = get_stocks(all_skus)
    except Exception as e:
        await update.message.reply_text(f"Ошибка Ozon API при получении остатков:\n{e}")
        return

    agg = aggregate_by_cluster(stocks)
    sku_clusters_on = {sku: clusters_on_for_sku(sku, agg.get(sku, {}), rules) for sku in all_skus}

    lines = []
    for name, g in groups.items():
        gcls = clusters_for_group(g, sku_clusters_on, rules)
        disc = discount_for_group(g, rules)
        lines.append(f"{name}: mode={g.get('group_city_mode','union')} disc={disc}% skus={g.get('skus', [])} clusters={sorted(gcls)}")
    await update.message.reply_text("Статус групп:\n" + "\n".join(lines)[:4000])

@admin_only
async def refresh_warehouses(update, context):
    matched = ensure_id_map(get_warehouses, force=True)
    await update.message.reply_text(f"Обновил список складов. Сопоставлено: {matched}")

@admin_only
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запускаю прогон…")
    try:
        await asyncio.get_event_loop().run_in_executor(None, run_pipeline)
        await update.message.reply_text("Готово.")
    except Exception as e:
        logging.exception(e)
        await update.message.reply_text(f"Ошибка: {e}")

@admin_only
async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = load_rules()
    groups = rules.get("promo_groups", {})
    lines = []
    for k, v in groups.items():
        lines.append(f"{k}: enabled={v.get('enabled',True)} mode={v.get('group_city_mode','union')} disc={v.get('discount',12)} skus={v.get('skus',[])}")
    await update.message.reply_text("Группы:\n" + "\n".join(lines)[:4000])

@admin_only
async def group_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Формат: /group_mode <NAME|default> <union|intersection|threshold> [k]"); return
    name, mode = args[0], args[1]
    k = int(args[2]) if len(args) > 2 else None
    rules = load_rules()
    if name == "default":
        rules.setdefault("defaults", {})["group_city_mode"] = mode
        if mode == "threshold" and k is not None:
            rules["defaults"]["group_city_threshold"] = k
    else:
        g = rules.setdefault("promo_groups", {}).setdefault(name, {})
        g["group_city_mode"] = mode
        if mode == "threshold" and k is not None:
            g["group_city_threshold"] = k
    save_rules(rules)
    await update.message.reply_text(f"Режим для {name} = {mode}" + (f" (k={k})" if k else ""))

@admin_only
async def group_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Формат: /group_discount <NAME|default> <pct>"); return
    name, pct = args[0], int(args[1])
    rules = load_rules()
    if name == "default":
        rules.setdefault("defaults", {})["discount"] = pct
    else:
        rules.setdefault("promo_groups", {}).setdefault(name, {})["discount"] = pct
    save_rules(rules)
    await update.message.reply_text(f"Скидка для {name} = {pct}%")

@admin_only
async def group_add_sku(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Формат: /group_add_sku <NAME> <SKU>"); return
    name, sku = args[0], int(args[1])
    rules = load_rules()
    g = rules.setdefault("promo_groups", {}).setdefault(name, {})
    g.setdefault("skus", [])
    if sku not in g["skus"]:
        g["skus"].append(sku)
    save_rules(rules)
    await update.message.reply_text(f"Добавил SKU {sku} в {name}")

@admin_only
async def group_rm_sku(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Формат: /group_rm_sku <NAME> <SKU>"); return
    name, sku = args[0], int(args[1])
    rules = load_rules()
    g = rules.setdefault("promo_groups", {}).setdefault(name, {})
    g.setdefault("skus", [])
    g["skus"] = [s for s in g["skus"] if s != sku]
    save_rules(rules)
    await update.message.reply_text(f"Удалил SKU {sku} из {name}")

@admin_only
async def set_qmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Формат: /set_qmin <SKU|default> <qty>"); return
    key, qty = args[0], int(args[1])
    rules = load_rules()
    if key == "default":
        rules.setdefault("defaults", {})["q_min"] = qty
    else:
        rules.setdefault("skus", {}).setdefault(str(int(key)), {})["q_min"] = qty
    save_rules(rules)
    await update.message.reply_text(f"q_min для {key} = {qty}")

@admin_only
async def enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Формат: /enable <SKU>"); return
    sku = str(int(args[0]))
    rules = load_rules()
    rules.setdefault("skus", {}).setdefault(sku, {})["enabled"] = True
    save_rules(rules)
    await update.message.reply_text(f"SKU {sku} включён.")

@admin_only
async def disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Формат: /disable <SKU>"); return
    sku = str(int(args[0]))
    rules = load_rules()
    rules.setdefault("skus", {}).setdefault(sku, {})["enabled"] = False
    save_rules(rules)
    await update.message.reply_text(f"SKU {sku} выключен.")

@admin_only
async def dump_warehouses(update, context):
    from core.ozon_api import get_warehouses
    ws = get_warehouses()
    lines = []
    for w in ws[:20]:
        lines.append(f"{w.get('warehouse_id')} | {w.get('name')} | api_cluster={w.get('cluster_name_from_api')}")
    if not lines:
        lines = ["(пусто)"]
    await update.message.reply_text("Примеры складов из Ozon:\n" + "\n".join(lines))

@admin_only
async def debug_stocks(update, context):
    import json
    from core.ozon_api import get_stocks, get_warehouses
    from core.stocks import aggregate_by_cluster, ensure_id_map

    # 1) Кэш ID→кластер
    matched = ensure_id_map(get_warehouses, force=False)

    # 2) Все SKU из правил
    from core.rules import load_rules
    rules = load_rules()
    groups = rules.get("promo_groups", {})
    all_skus = sorted({int(s) for g in groups.values() for s in g.get("skus", [])})
    if not all_skus:
        await update.message.reply_text("В rules.yaml нет SKU.")
        return

    # 3) Запрос к Ozon
    try:
        resp = get_stocks(all_skus)
    except Exception as e:
        await update.message.reply_text(f"Ozon API error: {e}")
        return

    items = resp.get("items") or []
    if not items:
        await update.message.reply_text(
            "API вернул пустой items — вероятно, нет остатков FBO по этим SKU.\n"
            f"Сопоставлено складов ID→кластер: {matched}"
        )
        return

    # 4) Соберём примеры строк
    sample = []
    empty_stocks = 0
    for it in items[:10]:  # покажем максимум 10 товаров
        stocks = it.get("stocks") or []
        if not stocks:
            empty_stocks += 1
            # попробуем показать offer_id/product_id, чтобы было понятно что за позиция
            offer_id = it.get("offer_id")
            product_id = it.get("product_id")
            sample.append(f"(no-stocks) offer_id={offer_id} product_id={product_id}")
            continue
        for st in stocks[:3]:  # на товар максимум 3 строки
            sku = st.get("sku")
            present = st.get("present")
            whs = st.get("warehouse_ids")
            sample.append(f"sku={sku} present={present} warehouses={whs}")

    # 5) Если даже после прохода нечего показать — пусть будет понятное сообщение
    if not sample:
        # Покажем компактный JSON-фрагмент первых 1-2 items для диагностики
        preview = json.dumps(items[:2], ensure_ascii=False)[:1000]
        await update.message.reply_text(
            "Получены items, но в них нет stocks для показа.\n"
            f"empty_stocks={empty_stocks}, matched={matched}\n"
            f"preview: {preview}"
        )
        return

    # 6) Отправим собранные примеры
    text = "Примеры строк из /v1/analytics/stocks:\n" + "\n".join(sample)
    if len(text) > 3800:
        text = text[:3800] + "\n… (обрезано)"
    await update.message.reply_text(text)

# /dry_sync_geo — только лог, без кликов в UI
async def dry_sync_geo(update, context):
    await update.message.reply_text("Запускаю dry-run синхронизации гео…")
    loop = asyncio.get_running_loop()
    try:
        func = functools.partial(run_sync_geo, "rules.yaml")
        # DRY_RUN=1, HEADLESS=1 (по умолчанию)
        with TempEnv(DRY_RUN="1"):
            await loop.run_in_executor(None, func)
        await update.message.reply_text("✅ Dry-run завершён. Смотри логи Railway.")
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"❌ Ошибка dry-run: {e}\n\n{tb}"
        await update.message.reply_text(msg[:4000])  # чтобы Telegram не обрезал
        print(tb)  # чтобы ушло и в Railway-логи

# /sync_geo — реальный апдейт географии через UI
async def sync_geo_cmd(update, context):
    await update.message.reply_text("Запускаю синхронизацию гео (боевой режим)…")
    loop = asyncio.get_running_loop()
    try:
        func = functools.partial(run_sync_geo, "rules.yaml")
        # DRY_RUN=0 (или убрать), HEADLESS по умолчанию 1
        with TempEnv(DRY_RUN=None):  # очистим, чтобы было не-dry
            await loop.run_in_executor(None, func)
        await update.message.reply_text("✅ Синхронизация завершена. Проверяй ЛК Озона.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка sync_geo: {e}")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    # регистрируем handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("group_mode", group_mode))
    app.add_handler(CommandHandler("group_discount", group_discount))
    app.add_handler(CommandHandler("group_add_sku", group_add_sku))
    app.add_handler(CommandHandler("group_rm_sku", group_rm_sku))
    app.add_handler(CommandHandler("set_qmin", set_qmin))
    app.add_handler(CommandHandler("enable", enable))
    app.add_handler(CommandHandler("disable", disable))
    app.add_handler(CommandHandler("refresh_warehouses", refresh_warehouses))
    app.add_handler(CommandHandler("dump_warehouses", dump_warehouses))
    app.add_handler(CommandHandler("debug_stocks", debug_stocks))
    app.add_handler(CommandHandler("dry_sync_geo", dry_sync_geo))
    app.add_handler(CommandHandler("sync_geo", sync_geo_cmd))

    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    if webhook_url:
        # если решишь когда-нибудь перейти на вебхук
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", "8080")),
            url=webhook_url,
            secret_token=os.getenv("WEBHOOK_SECRET", "")
        )
    else:
        # обычный прод-режим через polling
        app.run_polling()

if __name__ == "__main__":
    main()
