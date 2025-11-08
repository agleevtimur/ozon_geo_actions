import os
import sys
import json
import logging
import requests
import traceback
from datetime import timedelta
from typing import Any, Dict, List

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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

# === Расписание массового обновления ===
MASS_UPDATE_ENABLED = os.getenv("MASS_UPDATE_ENABLED", "false").strip().lower() in ("1", "true", "yes")
# Интервал в часах между запусками
MASS_UPDATE_INTERVAL_HOURS = int(os.getenv("MASS_UPDATE_INTERVAL_HOURS", "6").strip() or "6")
# Куда присылать ошибки (chat_id администратора / ваш чат)
MASS_UPDATE_CHAT_ID = os.getenv("MASS_UPDATE_CHAT_ID", "").strip()
# Если хотите получать и успешные отчёты, включите:
MASS_UPDATE_NOTIFY_OK = os.getenv("MASS_UPDATE_NOTIFY_OK", "false").strip().lower() in ("1", "true", "yes")

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
    logger.info("🗺️ Регионы для акции %s: %s", action_name, ", ".join(regions))
    if not regions:
        await update.message.reply_text("Не найдено регионов с наличием > 0 по заданным SKU")
        return

    # 4) regions -> addresses (uid региона + uid его городов)
    geo = GeoResolver()  # читает GEO_JSON_PATH или /app/data/geo.json
    addresses = geo.regions_to_addresses(regions)
    logger.info("📦 Адреса (UID) для акции %s: %d шт.", action_name, len(addresses))
    for addr in addresses:
        logger.debug("→ %s", addr)
    if not addresses:
        await update.message.reply_text("Не удалось сопоставить регионы в addresses (UID). Проверь data/geo.json")
        return

    logger.info(addresses)
    logger.info(
        "🚀 Отправляю обновление акции %s (id=%s): %d адресов",
        action_name, action_id, len(addresses)
    )
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
            f"✅ Обновил акцию «{action_name}» (id={action_id}). HTTP {status}\n"
            f"Регионов: {len(regions)}, адресов: {len(addresses)}"
        )
        return

    # Теоретически сюда не попадём (raise_for_status выше), но оставим на всякий
    await update.message.reply_text(f"❌ Обновление вернуло HTTP {status}\n{snippet}")
    logger.error("Update HTTP %s: %s", status, (resp.text or "")[:5000])

async def cmd_update_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
   # Запускаем джоб синхронно один раз «прямо сейчас»
    await _job_mass_update(context)

async def _compute_addresses_for_action_name(action_name: str) -> Dict[str, Any]:
    """
    Возвращает:
      {
        "action_id": int,
        "regions": List[str],
        "addresses": List[str]
      }
    или бросает исключение с человеческим текстом.
    """
    if action_name not in ACTIONS:
        raise RuntimeError(f"Акция «{action_name}» не найдена в config.ACTIONS")

    cfg = ACTIONS[action_name]
    action_id = int(cfg["id"])
    skus = [str(x) for x in cfg.get("skus", [])]
    if not skus:
        raise RuntimeError("В акции нет SKU в config.ACTIONS")

    # 1) загрузим карту кластер->регионы
    mapping_path = os.getenv("CLUSTER_MAP_PATH", "/app/data/cluster_regions.json")
    cluster_map = _load_cluster_mapping(mapping_path)

    # 2) остатки из OpenAPI
    api = OzonOpenApi()
    raw = api.fetch_stocks_for_skus(skus)
    items = _extract_items_from_openapi(raw)

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
        raise RuntimeError("Не найдено регионов с наличием > 0 по заданным SKU")

    # 4) regions -> addresses (uid региона + uid его городов)
    geo = GeoResolver()  # читает GEO_JSON_PATH или /app/data/geo.json
    addresses = geo.regions_to_addresses(regions)
    if not addresses:
        raise RuntimeError("Не удалось сопоставить регионы в addresses (UID). Проверь data/geo.json")

    logger.info("🗺️ [%s] регионов: %d; адресов: %d", action_name, len(regions), len(addresses))
    logger.debug("→ regions: %s", regions)
    if logger.isEnabledFor(logging.DEBUG):
        for addr in addresses[:50]:
            logger.debug("addr: %s", addr)
        if len(addresses) > 50:
            logger.debug("... и ещё %d адресов", len(addresses) - 50)

    return {"action_id": action_id, "regions": regions, "addresses": addresses}

async def _job_mass_update(context: ContextTypes.DEFAULT_TYPE):
    """
    Периодическая задача: обновить все (или перечисленные) акции.
    Шлёт в ТГ только ошибки (и опционально успешный отчёт).
    """
    # Куда слать отчёты
    chat_id = MASS_UPDATE_CHAT_ID or None
    if not chat_id:
        logger.warning("MASS_UPDATE_CHAT_ID не задан — отчёты слать некуда, пишем только в логи")

    action_names = list(ACTIONS.keys())

    if not action_names:
        msg = "Нет акций для массового обновления (проверьте MASS_UPDATE_ACTION_NAMES / config.ACTIONS)."
        logger.warning(msg)
        if chat_id:
            await context.bot.sendMessage(chat_id=chat_id, text=f"⚠️ {msg}")
        return

    logger.info("⏱ Запуск массового обновления: %d акций", len(action_names))

    errors: List[str] = []
    ok_list: List[str] = []

    for action_name in action_names:
        try:
            # 1) посчитать адреса
            comp = await _compute_addresses_for_action_name(action_name)
            action_id = comp["action_id"]
            addresses = comp["addresses"]

            # 2) апдейт акции
            resp = update_action_via_proxy(
                action_id=action_id,
                addresses=addresses,
                title=action_name
            )
            resp.raise_for_status()
            ok_list.append(f"✅ {action_name} (id={action_id}): {len(addresses)} адресов")

        except requests.HTTPError as e:
            body = (e.response.text or "") if getattr(e, "response", None) is not None else str(e)
            snippet = (body[:800] + "…") if len(body) > 800 else body
            logger.error("HTTPError для «%s»: %s\n%s", action_name, e, snippet)
            errors.append(f"❌ {action_name}: HTTP {getattr(e.response, 'status_code', '???')} — {snippet}")
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            logger.error("Ошибка «%s»: %s\n%s", action_name, e, tb)
            errors.append(f"❌ {action_name}: {e}")

    # Отчёт в ТГ: только если есть ошибки — либо если включён флаг уведомлять об успехе
    if chat_id:
        if errors:
            head = f"⚠️ Массовое обновление завершилось с ошибками ({len(errors)} шт.)."
            text = head + "\n\n" + "\n".join(errors[:15])
            if len(errors) > 15:
                text += f"\n…и ещё {len(errors)-15} ошибок"
            await context.bot.sendMessage(chat_id=chat_id, text=text)
        elif MASS_UPDATE_NOTIFY_OK:
            text = "✅ Массовое обновление: всё успешно.\n\n" + "\n".join(ok_list[:20])
            if len(ok_list) > 20:
                text += f"\n…и ещё {len(ok_list)-20} акций"
            await context.bot.sendMessage(chat_id=chat_id, text=text)

    logger.info("⏱ Массовое обновление завершено: ok=%d, err=%d", len(ok_list), len(errors))

def register_handlers(application):
    application.add_handler(CommandHandler("update_geo", cmd_update_geo))
    application.add_handler(CommandHandler("update_all", cmd_update_all))

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

    # Планировщик массового обновления
    if MASS_UPDATE_ENABLED:
        interval = max(1, MASS_UPDATE_INTERVAL_HOURS)
        app.job_queue.run_repeating(
            _job_mass_update,
            interval=timedelta(hours=interval),
            first=timedelta(seconds=10),  # первый запуск через 10 сек после старта
            name="mass_update_job",
        )
        logger.info("Планировщик включён: каждые %d ч. Получатель: %s", interval, MASS_UPDATE_CHAT_ID or "—")
    else:
        logger.info("Планировщик выключен (MASS_UPDATE_ENABLED=false)")
    
    logger.info("Bot is starting polling...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
