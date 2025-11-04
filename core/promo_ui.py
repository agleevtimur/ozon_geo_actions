from __future__ import annotations

import json
import os
import re
import time
import logging
from contextlib import contextmanager
from typing import Iterable, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

log = logging.getLogger(__name__)

OZON_SELLER_BASE = os.getenv("OZON_SELLER_BASE", "https://seller.ozon.ru")
OZON_COOKIES_JSON = os.getenv("OZON_COOKIES_JSON")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "1") in ("1","true","TRUE","yes")
SLOWMO_MS = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0"))

URL_OWN_PROMO = os.getenv("OZON_OWN_PROMO_URL", f"{OZON_SELLER_BASE}/app/promo/own")

NAV_TIMEOUT = int(os.getenv("PW_NAV_TIMEOUT_MS", "30000"))
UI_TIMEOUT  = int(os.getenv("PW_UI_TIMEOUT_MS", "10000"))

def _playwright_context(headless: bool = PLAYWRIGHT_HEADLESS):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=SLOWMO_MS)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        if OZON_COOKIES_JSON:
            try:
                cookies = json.loads(OZON_COOKIES_JSON)
                if isinstance(cookies, list) and cookies:
                    for c in cookies:
                        if "domain" not in c:
                            c["domain"] = ".ozon.ru"
                    context.add_cookies(cookies)
                    log.info("Загружены %d cookies из OZON_COOKIES_JSON", len(cookies))
            except Exception as e:
                log.warning("Не удалось прочитать OZON_COOKIES_JSON: %s", e)
        try:
            yield context
        finally:
            context.close()
            browser.close()

def _goto(page, url: str):
    log.info("Открываю: %s", url)
    page.goto(url, timeout=NAV_TIMEOUT, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PWTimeout:
        pass

def _open_promo(page, promo_name: str):
    _goto(page, URL_OWN_PROMO)
    try:
        # поиск по таблице / поиску
        search = page.get_by_placeholder(re.compile("Поиск|Фильтр|Найти", re.I)).first
        search.fill(promo_name)
        time.sleep(0.2)
    except Exception:
        pass
    row = page.get_by_text(promo_name, exact=True).first
    row.click(timeout=UI_TIMEOUT)
    page.wait_for_load_state("networkidle", timeout=8000)
    try:
        page.get_by_role("button", name=re.compile("Изменить|Редакт", re.I)).first.click(timeout=2000)
    except Exception:
        pass

def _open_geo(page):
    try:
        page.get_by_role("button", name=re.compile("Географ|Регион|Город", re.I)).first.click(timeout=UI_TIMEOUT)
    except Exception:
        page.get_by_text(re.compile("Географ|Регион|Город", re.I)).first.click(timeout=UI_TIMEOUT)

def _clear_regions(page):
    # попробуем нажать «Очистить»
    try:
        page.get_by_role("button", name=re.compile("Очистить|Сбросить", re.I)).first.click(timeout=1500)
    except Exception:
        pass
    # снять выбраные теги (если есть)
    try:
        chips = page.locator("[class*=chip]").locator("button").all()
        for b in chips:
            try: b.click(timeout=400)
            except Exception: pass
    except Exception:
        pass

def _select_region(page, reg: str):
    try:
        search = page.get_by_placeholder(re.compile("Поиск|Найти", re.I)).first
        search.click(); search.fill(reg); time.sleep(0.2)
    except Exception:
        pass
    loc = page.get_by_role("option", name=re.compile(rf"^{re.escape(reg)}$", re.I)).first
    if not loc or not loc.is_visible():
        loc = page.get_by_text(re.compile(rf"^{re.escape(reg)}$", re.I)).first
    loc.click(timeout=UI_TIMEOUT)

def _close_geo(page):
    try:
        page.get_by_role("button", name=re.compile("Готово|Выбрать|Закрыть", re.I)).first.click(timeout=1500)
    except Exception:
        page.mouse.click(50, 50)

def _save(page):
    for name in ("Сохранить", "Применить", "Сохранить изменения"):
        try:
            page.get_by_role("button", name=re.compile(name, re.I)).first.click(timeout=UI_TIMEOUT)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PWTimeout:
                pass
            return
        except Exception:
            continue

def get_current_regions(page) -> list[str]:
    regs = []
    try:
        chips = page.locator("[class*=chip]").all()
        for c in chips:
            t = (c.text_content() or "").strip()
            if t: regs.append(t)
    except Exception:
        pass
    return regs

def upsert_promo_geography(promo_name: str, regions: Iterable[str], headless: Optional[bool]=None) -> str:
    if headless is None:
        headless = PLAYWRIGHT_HEADLESS
    regions = sorted({r.strip() for r in regions if r and r.strip()})
    if not regions:
        return "error"
    try:
        with _playwright_context(headless=headless) as ctx:
            page = ctx.new_page()
            _open_promo(page, promo_name)
            _open_geo(page)
            current = sorted(get_current_regions(page))
            if current == regions:
                return "skipped"
            _clear_regions(page)
            for r in regions:
                try:
                    _select_region(page, r)
                except Exception as e:
                    log.warning("Не выбрал регион '%s': %s", r, e)
            _close_geo(page)
            _save(page)
            return "updated"
    except Exception as e:
        log.error("Ошибка upsert '%s': %s", promo_name, e)
        return "error"
