import os
import json
import time
import logging
from typing import List

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

log = logging.getLogger("core.promo_ui")

URL_ROOT = "https://seller.ozon.ru/"
# Новая страница 'Свои акции' (highlights)
URL_OWN_PROMO = "https://seller.ozon.ru/app/highlights/my-highlights/list"
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

    # На странице "Свои подсветки/акции" есть таблица/список.
    # Сначала попробуем поле поиска.
    try:
        search = None
        for placeholder in ("Поиск", "Фильтр", "Найти", "Название", "Название подсветки", "Название акции"):
            try:
                loc = page.get_by_placeholder(placeholder)
                if loc and loc.count():
                    search = loc.first
                    break
            except Exception:
                continue
        if search:
            search.click()
            search.fill(promo_name)
            time.sleep(0.4)

        # Затем кликаем по найденной строке списка/таблицы
        # Пробуем несколько стратегий: точный текст и роль-ссылку/кнопку
        tried = False
        try:
            page.locator(f"text={promo_name}").first.click(timeout=8000)
            tried = True
        except Exception:
            pass
        if not tried:
            for role in ("link", "button"):
                try:
                    page.get_by_role(role, name=promo_name).first.click(timeout=8000)
                    tried = True
                    break
                except Exception:
                    continue
        if tried:
            log.info("Акция '%s' открыта", promo_name)
            return True
    except Exception as e:
        log.error("Не удалось открыть акцию '%s' через поиск: %s", promo_name, e)

    # Фоллбек: попробуем просто клик по тексту без поиска
    try:
        page.locator(f"text={promo_name}").first.click(timeout=10000)
        log.info("Акция '%s' открыта (fallback)", promo_name)
        return True
    except Exception as e:
        log.error("Не удалось открыть акцию '%s': %s", promo_name, e)
        return False


def _open_geo_tab(page) -> bool:
    """Открывает вкладку/секцию 'География'. Возвращает True при успехе."""
    # На новых формах это может быть вкладка/кнопка/дропдаун.
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
    log.error("Не удалось открыть вкладку/секцию 'География'")
    return False


def _read_current_regions(page) -> List[str]:
    """Собирает текущие выбранные регионы из UI (насколько это возможно)."""
    regions = []
    try:
        # Часто выбранные регионы отображаются как теги/чипсы/плашки
        candidates = [
            "[data-testid='selected-region']",
            "div.tag, div.chips, span.tag, span.chip",
            # Общая эвристика около формы географии
            "section:has-text('Гео') span, section:has-text('Регион') span",
        ]
        for css in candidates:
            try:
                loc = page.locator(css)
                n = loc.count()
                if n:
                    for i in range(min(n, 250)):
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
    # 1) Очистка
    for btn_txt in ("Очистить", "Сбросить", "Удалить все"):
        try:
            page.get_by_role("button", name=btn_txt).first.click()
            time.sleep(0.2)
            break
        except Exception:
            pass

    try:
        # Точечное удаление выбранных
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

    # 2) Добавление
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
            # запасной путь — чекбокс/лейбл
            try:
                page.get_by_label(region).check()
                added = True
            except Exception:
                pass
        if added:
            log.info("Добавлен регион: %s", region)
        else:
            log.warning("Не удалось добавить регион: %s", region)

    # 3) Сохранение
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
    regions — список строк регионов (на русский):
        ["Москва, МО и Дальние регионы", "Новосибирск и Сибирь", ...]
    Если dry_run=True — только логируем действия.
    """
    if dry_run:
        log.info("🧪 DRY-RUN: '%s' → (%d регионов) %s", promo_name, len(regions), ", ".join(regions))
        return

    prev = os.environ.get("PLAYWRIGHT_HEADLESS")
    os.environ["PLAYWRIGHT_HEADLESS"] = "1"  # headless на Railway/Docker
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            )
            context = browser.new_context()
            _apply_cookies_if_any(context)
            page = context.new_page()

            # Прогрев
            _goto(page, URL_ROOT)

            # Открыть акцию
            if not _open_promo(page, promo_name):
                raise RuntimeError(f"Акция '{promo_name}' не найдена/не открылась")

            # География
            if not _open_geo_tab(page):
                raise RuntimeError("Вкладка/секция 'География' не найдена")

            # Сравнить с текущим
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

            # Применить
            _set_regions(page, need_set)

            context.close()
            browser.close()
            log.info("✅ Акция '%s' обновлена (регионов: %d)", promo_name, len(need_set))
    finally:
        if prev is None:
            os.environ.pop("PLAYWRIGHT_HEADLESS", None)
        else:
            os.environ["PLAYWRIGHT_HEADLESS"] = prev
