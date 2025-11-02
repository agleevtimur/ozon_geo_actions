import os, time, json
from playwright.sync_api import sync_playwright

OZON_SELLER_BASE = "https://seller.ozon.ru"
PROMO_LIST_URL   = f"{OZON_SELLER_BASE}/app/highlights/my-highlights/list"  # список «Своих акций»
def _auth_with_cookies(context):
    """Авторизация в Озоне через cookies (из env или cookies.json)."""
    raw = os.getenv("OZON_COOKIES_JSON")
    if not raw and os.path.exists("cookies.json"):
        raw = open("cookies.json","r",encoding="utf-8").read()
    if not raw:
        raise RuntimeError("Нет cookies. Задай OZON_COOKIES_JSON или cookies.json")
    context.add_cookies(json.loads(raw))

def _find_promo(page, promo_name):
    """Находит и открывает карточку акции по названию."""
    page.goto(PROMO_LIST_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_load_state("networkidle")
    # Поиск по названию
    if page.get_by_placeholder("Поиск").count():
        search = page.get_by_placeholder("Поиск")
        search.fill(promo_name)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)
    promo_card = page.locator(f"text={promo_name}").first
    promo_card.wait_for(timeout=60_000)
    promo_card.click()

def _clear_regions(page):
    """Снимает все выбранные регионы, если есть кнопка 'Очистить'."""
    btn = page.get_by_role("button", name=lambda n: n and ("Очист" in n or "Снять" in n))
    if btn.count():
        btn.first.click()
        page.wait_for_timeout(300)

def _select_regions(page, region_names):
    """Отмечает регионы по именам (как в UI)."""
    def click_region(name):
        if page.get_by_placeholder("Поиск").count():
            f = page.get_by_placeholder("Поиск")
            f.fill(name)
            page.wait_for_timeout(400)
        label = page.locator(f"label:has-text('{name}')")
        if not label.count():
            label = page.locator(f"text={name}").first
        if label.count():
            label.click()
            page.wait_for_timeout(200)
        else:
            print(f"[warn] Регион '{name}' не найден")

    for n in region_names:
        click_region(n)

def update_promo_regions_ui(promo_name: str, region_names: list[str], headless=True):
    """
    Открывает акцию promo_name и обновляет список регионов.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = browser.new_context()
        _auth_with_cookies(context)
        page = context.new_page()

        try:
            _find_promo(page, promo_name)
            # нажать «Редактировать»
            edit_btn = page.get_by_role("button", name=lambda n: n and ("Редакт" in n or "Измен" in n))
            if not edit_btn.count():
                more = page.get_by_role("button", name=lambda n: n and ("…" in n or "Ещё" in n))
                if more.count():
                    more.first.click()
                    page.wait_for_timeout(300)
                    edit_btn = page.get_by_role("menuitem", name=lambda n: n and ("Редакт" in n or "Измен" in n))
            edit_btn.first.click()
            page.wait_for_timeout(700)

            # вкладка География
            geo_tab = page.locator("text=География").first
            if geo_tab.count():
                geo_tab.click()
                page.wait_for_timeout(400)

            _clear_regions(page)
            _select_regions(page, region_names)

            # сохранить
            save_btn = page.get_by_role("button", name=lambda n: n and ("Сохран" in n or "Примен" in n))
            save_btn.first.click()
            page.wait_for_timeout(1500)
            print(f"✅ {promo_name}: обновлены регионы ({len(region_names)})")

        finally:
            context.close()
            browser.close()
