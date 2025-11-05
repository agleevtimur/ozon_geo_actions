import os
import time
import base64
import asyncio
import logging
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

log = logging.getLogger(__name__)

# === СКРИНШОТЫ: сохраняем + логируем base64 ===

def _log_base64_png(path: str, tag: str) -> None:
    """Печатает png в лог как base64 (кусочками, чтобы не порезало по длине строки)."""
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        chunk = 7000
        log.info("=== SCREENSHOT:%s:BEGIN ===", tag)
        for i in range(0, len(b64), chunk):
            log.info("SS:%s:%05d-%05d %s", tag, i, min(i + chunk, len(b64)), b64[i:i + chunk])
        log.info("=== SCREENSHOT:%s:END ===", tag)
    except Exception as e:
        log.warning("Не удалось вывести скриншот в лог (%s): %s", tag, e)

def _ss(page, tag: str) -> str:
    """
    Делает скрин и:
      1) сохраняет файл в /app/screens
      2) дублирует в логи base64 (если LOG_BASE64_SCREENS=1)
    Возвращает путь к файлу.
    """
    out_dir = "/app/screens"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{int(time.time())}_{tag}.png")
    try:
        page.screenshot(path=path, full_page=True)
        log.info("Скриншот: %s", path)
        if os.getenv("LOG_BASE64_SCREENS", "1") == "1":
            _log_base64_png(path, tag)
    except Exception as e:
        log.warning("Не удалось сделать скриншот (%s): %s", tag, e)
    return path


# === ОСНОВНАЯ ЛОГИКА ===

@contextmanager
def playwright_context(headless: bool = True):
    """
    Контекстный менеджер для запуска браузера Playwright.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright не установлен. Установи: pip install playwright && playwright install chromium")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()


def _safe_set_env(name: str, value: str):
    """Безопасно установить переменную окружения только на время контекста."""
    old = os.environ.get(name)
    os.environ[name] = value
    return old


def upsert_promo(promo_name: str, clusters: list[str]) -> str:
    """
    Открывает страницу акций, находит акцию по названию и проставляет географию (регионы).
    Если не найдено — делает скрин и выбрасывает исключение.
    """
    log.info("=== Обновление акции '%s' ===", promo_name)

    # Принудительно headless режим
    old_headless = _safe_set_env("PLAYWRIGHT_HEADLESS", "1")

    try:
        with playwright_context(headless=True) as page:
            # Переходим на страницу акций
            url = "https://seller.ozon.ru/app/highlights/my-highlights/list"
            log.info("Открываю страницу: %s", url)
            page.goto(url, timeout=60000)
            time.sleep(3)
            _ss(page, "list_opened")

            # Ищем акцию по названию
            row = page.get_by_text(promo_name).first
            if not row or not row.is_visible():
                _ss(page, "promo_not_found")
                raise RuntimeError(f"Акция '{promo_name}' не найдена/не открылась")

            row.click()
            time.sleep(3)
            _ss(page, "promo_opened")

            # Открываем вкладку "География"
            try:
                geo_tab = page.get_by_text("География", exact=True)
                geo_tab.click()
                time.sleep(2)
            except Exception:
                log.warning("Не удалось открыть вкладку География для '%s'", promo_name)
                _ss(page, "geo_tab_fail")

            # Проставляем регионы
            for region in clusters:
                try:
                    checkbox = page.get_by_text(region, exact=False)
                    if checkbox.is_visible():
                        checkbox.click()
                        log.info("Выбран регион: %s", region)
                        time.sleep(0.2)
                except Exception as e:
                    log.warning("Не удалось выбрать регион '%s': %s", region, e)

            # Сохраняем изменения
            try:
                save_btn = page.get_by_text("Сохранить", exact=True)
                save_btn.click()
                log.info("Нажата кнопка 'Сохранить'")
                time.sleep(2)
                _ss(page, "after_save")
            except Exception as e:
                _ss(page, "save_failed")
                raise RuntimeError(f"Не удалось сохранить '{promo_name}': {e}")

            return f"✅ '{promo_name}' обновлена ({len(clusters)} регионов)."

    except Exception as e:
        _ss(page, "upsert_failed")
        log.error("Ошибка upsert '%s': %s", promo_name, e)
        raise

    finally:
        # Восстанавливаем HEADLESS
        if old_headless is None:
            os.environ.pop("PLAYWRIGHT_HEADLESS", None)
        else:
            os.environ["PLAYWRIGHT_HEADLESS"] = old_headless


# === ТЕСТОВЫЙ ЗАПУСК ===

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(upsert_promo("10 скидка", ["Москва, МО и Дальние регионы", "Казань"]))
