import os
import json
import time
import logging
from typing import List

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

log = logging.getLogger("core.promo_ui")

URL_ROOT = "https://seller.ozon.ru/"
URL_OWN_PROMO = "https://seller.ozon.ru/app/highlights/my-highlights/list"
NAV_TIMEOUT = 35000
SS_DIR = os.environ.get("PW_DEBUG_DIR", "/tmp")


def _apply_cookies_if_any(context):
    """Подхватывает ozon_cookies.json, если он есть рядом с проектом."""
    try:
        if os.path.exists("ozon_cookies.json"):
            with open("ozon_cookies.json", "r", encoding="utf-8") as f:
                cookies = json.load(f)
            if isinstance(cookies, list) and cookies:
                context.add_cookies(cookies)
                log.info("Куки загружены (%d шт.) и применены", len(cookies))
    except Exception as e:
        log.warning("Не удалось применить куки: %s", e)


def _ss(page, name: str):
    try:
        path = os.path.join(SS_DIR, f"{int(time.time())}_{name}.png")
        page.screenshot(path=path, full_page=True)
        log.info("Скриншот: %s", path)
    except Exception:
        pass


def _goto(page, url: str):
    log.info("Открываю: %s", url)
    page.goto(url, timeout=NAV_TIMEOUT, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PWTimeout:
        pass


def _normalize(text: str) -> str:
    t = (text or "").strip()
    t = " ".join(t.split())
    return t.lower()


def _open_promo(page, promo_name: str) -> bool:
    """Открывает страницу акции по имени. Возвращает True при успехе."""
    wanted = _normalize(promo_name)

    _goto(page, URL_OWN_PROMO)
    _ss(page, "list_opened")

    # Снять фильтры: попробуем нажать "Все" или "Активные"
    for name in ("Все", "Активные", "Мои подсветки", "Мои акции"):
        try:
            page.get_by_role("tab", name=name).first.click(timeout=3000)
            time.sleep(0.2)
        except Exception:
            pass

    # Поиск по полю ввода
    search = None
    for placeholder in ("Поиск", "Фильтр", "Найти", "Название", "Название подсветки", "Название акции"):
        try:
            loc = page.get_by_placeholder(placeholder)
            if loc and loc.count():
                search = loc.first
                break
        except Exception:
            continue
    if not search:
        # fallback: любой текстовый input
        try:
            cand = page.locator("input[type='text']")
            if cand.count():
                search = cand.first
        except Exception:
            pass

    if search:
        try:
            search.click()
            search.fill(promo_name)
            time.sleep(0.6)
        except Exception:
            pass

    # Общий локатор ряда по тексту
    def try_click_by_text(name: str) -> bool:
        try:
            page.locator(f"text={name}").first.click(timeout=5000)
            return True
        except Exception:
            pass
        # Ячейка таблицы
        try:
            page.locator(f"tr:has-text('{name}')").first.click(timeout=5000)
            return True
        except Exception:
            pass
        # Ссылка/кнопка
        for role in ("link", "button"):
            try:
                page.get_by_role(role, name=name).first.click(timeout=5000)
                return True
            except Exception:
                continue
        return False

    # 1) Прямой клик
    if try_click_by_text(promo_name):
        log.info("Акция '%s' открыта", promo_name)
        return True

    # 2) Скроллим список и ищем по частичному совпадению
    try:
        for _ in range(40):
            items = page.locator("text=/./").all()
            found = None
            for it in items[:200]:
                try:
                    txt = it.inner_text()
                    if not txt:
                        continue
                    if _normalize(txt) == wanted or wanted in _normalize(txt):
                        found = it
                        break
                except Exception:
                    continue
            if found:
                try:
                    found.click(timeout=3000)
                    log.info("Акция '%s' открыта (scroll+partial)", promo_name)
                    return True
                except Exception:
                    pass
            # скролл вниз
            page.mouse.wheel(0, 1600)
            time.sleep(0.25)
    except Exception:
        pass

    # 3) Пагинация
    for btn in ("Следующая", "Дальше", "→"):
        try:
            for _ in range(8):
                page.get_by_role("button", name=btn).first.click(timeout=3000)
                time.sleep(0.5)
                if try_click_by_text(promo_name):
                    log.info("Акция '%s' открыта (pagination)", promo_name)
                    return True
        except Exception:
            pass

    _ss(page, "open_promo_failed")
    log.error("Не удалось открыть акцию '%s'", promo_name)
    return False


def _open_geo_tab(page) -> bool:
    """Открывает вкладку/секцию 'География'. Возвращает True при успехе."""
    for txt in ("География", "Регион", "Гео", "Регионы"):
        try:
            page.get_by_text(txt).first.click(timeout=6000)
            time.sleep(0.3)
            return True
        except Exception:
            pass
        try:
            page.locator(f"button:has-text('{txt}')").first.click(timeout=6000)
            time.sleep(0.3)
            return True
        except Exception:
            pass
        try:
            page.locator(f"[role='tab']:has-text('{txt}')").first.click(timeout=6000)
            time.sleep(0.3)
            return True
        except Exception:
            pass
    _ss(page, "geo_tab_fail")
    log.error("Не удалось открыть вкладку/секцию 'География'")
    return False


def _read_current_regions(page) -> List[str]:
    """Собирает текущие выбранные регионы из UI (насколько это возможно)."""
    regions = []
    try:
        candidates = [
            "[data-testid='selected-region']",
            "div.tag, div.chips, span.tag, span.chip",
            "section:has-text('Гео') span, section:has-text('Регион') span",
        ]
        for css in candidates:
            try:
                loc = page.locator(css)
                n = loc.count()
                if n:
                    for i in range(min(n, 250)):
                        txt = (loc.nth(i).inner_text() or "").strip()
                        if txt and len(txt) < 80:
                            if txt not in regions:
                                regions.append(txt)
            except Exception:
                continue
    except Exception as e:
        log.warning("Не удалось прочитать текущие регионы: %s", e)
    return regions


def _set_regions(page, regions: List[str]) -> None:
    """Сбрасывает и устанавливает указанные регионы в UI."""
    for btn_txt in ("Очистить", "Сбросить", "Удалить все"):
        try:
            page.get_by_role("button", name=btn_txt).first.click()
            time.sleep(0.2)
            break
        except Exception:
            pass

    try:
        clear_btns = page.locator("button:has-text('Удалить')")
        cnt = clear_btns.count()
        for i in range(cnt):
            try:
                clear_btns.nth(i).click()
            except Exception:
                pass
        if cnt:
            log.info("Удалено %d ранее выбранных регионов", cnt)
    except Exception:
        pass

    for region in regions:
        added = False
        for placeholder in ("Поиск регионов", "Поиск", "Регион", "Выберите регион"):
            try:
                fld = page.get_by_placeholder(placeholder)
                if fld and fld.count():
                    fld = fld.first
                    fld.click()
                    fld.fill(region)
                    time.sleep(0.25)
                    page.locator(f"text={region}").first.click(timeout=6000)
                    added = True
                    break
            except Exception:
                continue
        if not added:
            try:
                page.get_by_label(region).check()
                added = True
            except Exception:
                pass
        if added:
            log.info("Добавлен регион: %s", region)
        else:
            log.warning("Не удалось добавить регион: %s", region)

    for btn in ("Сохранить", "Применить"):
        try:
            page.get_by_role("button", name=btn).first.click(timeout=5000)
            time.sleep(0.4)
            return
        except Exception:
            continue
    log.warning("Кнопка сохранения не найдена — проверьте селекторы/верстку")


def upsert_promo(promo_name: str, regions: List[str], dry_run: bool = False) -> None:
    """
    Обновляет (upsert) географию акции по имени promo_name.
    regions — список строк регионов (на русский).
    Если dry_run=True — только логируем действия.
    """
    if dry_run:
        log.info("🧪 DRY-RUN: '%s' → (%d регионов) %s", promo_name, len(regions), ", ".join(regions))
        return

    prev = os.environ.get("PLAYWRIGHT_HEADLESS")
    os.environ["PLAYWRIGHT_HEADLESS"] = "1"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            )
            context = browser.new_context()
            _apply_cookies_if_any(context)
            page = context.new_page()

            _goto(page, URL_ROOT)

            if not _open_promo(page, promo_name):
                _ss(page, "promo_not_found")
                raise RuntimeError(f"Акция '{promo_name}' не найдена/не открылась")

            if not _open_geo_tab(page):
                raise RuntimeError("Вкладка/секция 'География' не найдена")

            current = _read_current_regions(page)
            need_set = sorted(set([r.strip() for r in regions if r and r.strip()]))
            if current:
                cur_norm = sorted(set([c.strip() for c in current if c and c.strip()]))
                if cur_norm == need_set:
                    log.info("География '%s' уже корректная. Изменений не требуется.", promo_name)
                    context.close()
                    browser.close()
                    return
                else:
                    log.info("Текущие регионы: %s", ", ".join(cur_norm))

            _set_regions(page, need_set)

            _ss(page, "after_save")
            context.close()
            browser.close()
            log.info("✅ Акция '%s' обновлена (регионов: %d)", promo_name, len(need_set))
    finally:
        if prev is None:
            os.environ.pop("PLAYWRIGHT_HEADLESS", None)
        else:
            os.environ["PLAYWRIGHT_HEADLESS"] = prev
