import os
import json
import time
import logging
from typing import List

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

log = logging.getLogger("core.promo_ui")

URL_ROOT = "https://seller.ozon.ru/"
URL_OWN_PROMO = "https://seller.ozon.ru/app/promo/actions"
NAV_TIMEOUT = 30000


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


def _goto(page, url: str):
    log.info("Открываю: %s", url)
    page.goto(url, timeout=NAV_TIMEOUT, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PWTimeout:
        pass


def _open_promo(page, promo_name: str) -> bool:
    """Открывает страницу акции по имени. Возвращает True при успехе."""
    _goto(page, URL_OWN_PROMO)
    # Поиск по строке фильтра / поиску
    try:
        # Поищем любой понятный плейсхолдер
        search = None
        for placeholder in ("Поиск", "Фильтр", "Найти", "Название акции"):
            try:
                search = page.get_by_placeholder(placeholder)
                if search and search.count():
                    search = search.first
                    break
            except Exception:
                continue
        if search:
            search.click()
            search.fill(promo_name)
            time.sleep(0.3)
        else:
            log.info("Поле поиска не найдено, пробую найти акцию кликом по тексту")

        # Клик по строке таблицы
        page.locator(f"text={promo_name}").first.click(timeout=8000)
        log.info("Акция '%s' открыта", promo_name)
        return True
    except Exception as e:
        log.error("Не удалось открыть акцию '%s': %s", promo_name, e)
        return False


def _open_geo_tab(page) -> bool:
    """Открывает вкладку 'География'. Возвращает True при успехе."""
    try:
        # Иногда это именно вкладка с текстом "География"
        page.locator("text=География").first.click(timeout=6000)
        time.sleep(0.3)
        return True
    except Exception:
        # Иногда это секция/кнопка где-то в настройках
        try:
            page.get_by_text("География").first.click(timeout=6000)
            time.sleep(0.3)
            return True
        except Exception as e:
            log.error("Не удалось открыть вкладку 'География': %s", e)
            return False


def _read_current_regions(page) -> List[str]:
    """Собирает текущие выбранные регионы из UI (насколько это возможно)."""
    regions = []
    try:
        # Часто выбранные регионы отображаются как теги или элементы списка
        candidates = [
            "div:has-text('Регион') >> .. >> span",  # эвристика
            "[data-testid='selected-region']",
            "div.tag, div.chips, span.tag, span.chip",
        ]
        for css in candidates:
            try:
                loc = page.locator(css)
                n = loc.count()
                if n:
                    for i in range(min(n, 200)):
                        txt = (loc.nth(i).inner_text() or "").strip()
                        if txt and len(txt) < 80 and txt not in regions:
                            regions.append(txt)
            except Exception:
                continue
    except Exception as e:
        log.warning("Не удалось прочитать текущие регионы: %s", e)
    return regions


def _set_regions(page, regions: List[str]) -> None:
    """Сбрасывает и устанавливает указанные регионы в UI."""
    # 1) Сначала очистка
    try:
        # массовый сброс, если есть
        for txt in ("Очистить", "Сбросить", "Удалить все"):
            btns = page.get_by_role("button", name=txt)
            if btns and btns.count():
                btns.first.click()
                time.sleep(0.2)
                break
    except Exception:
        pass

    try:
        # точечное удаление выбранных
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

    # 2) Добавляем новые
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
                    page.locator(f"text={region}").first.click(timeout=5000)
                    added = True
                    break
            except Exception:
                continue
        if not added:
            # запасной путь: попробуем искать чекбокс с этим текстом
            try:
                page.get_by_label(region).check()
                added = True
            except Exception:
                pass
        if added:
            log.info("Добавлен регион: %s", region)
        else:
            log.warning("Не удалось добавить регион: %s", region)

    # 3) Сохранить
    for btn_text in ("Сохранить", "Применить"):
        try:
            page.get_by_role("button", name=btn_text).first.click(timeout=4000)
            time.sleep(0.3)
            return
        except Exception:
            continue
    log.warning("Кнопка сохранения не найдена — проверьте селекторы")


def upsert_promo(promo_name: str, regions: List[str], dry_run: bool = False) -> None:
    """
    Обновляет (upsert) географию акции по имени promo_name.
    regions — список строк регионов (на русский), например:
        ["Москва, МО и Дальние регионы", "Новосибирск и Сибирь"]
    Если dry_run=True — только логируем действия.
    """
    if dry_run:
        log.info("🧪 DRY-RUN: '%s' → (%d регионов) %s", promo_name, len(regions), ", ".join(regions))
        return

    prev = os.environ.get("PLAYWRIGHT_HEADLESS")
    os.environ["PLAYWRIGHT_HEADLESS"] = "1"  # headless обязателен на Railway/Docker
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            )
            context = browser.new_context()
            _apply_cookies_if_any(context)
            page = context.new_page()

            # 1) заходим на главную, прогреваем сессию
            _goto(page, URL_ROOT)

            # 2) открываем акцию
            if not _open_promo(page, promo_name):
                raise RuntimeError(f"Акция '{promo_name}' не найдена/не открылась")

            # 3) открываем Географию
            if not _open_geo_tab(page):
                raise RuntimeError("Вкладка 'География' не найдена")

            # 4) читаем текущие регионы и сравниваем
            current = _read_current_regions(page)
            need_set = sorted(set(regions))
            to_apply = need_set

            if current:
                cur_norm = sorted(set([c.strip() for c in current if c and c.strip()]))
                if cur_norm == need_set:
                    log.info("География '%s' уже корректная. Изменений не требуется.", promo_name)
                    context.close()
                    browser.close()
                    return
                else:
                    log.info("Текущие регионы: %s", ", ".join(cur_norm))

            # 5) выставляем регионы
            _set_regions(page, to_apply)

            context.close()
            browser.close()
            log.info("✅ Акция '%s' обновлена (регионов: %d)", promo_name, len(to_apply))
    finally:
        if prev is None:
            os.environ.pop("PLAYWRIGHT_HEADLESS", None)
        else:
            os.environ["PLAYWRIGHT_HEADLESS"] = prev
