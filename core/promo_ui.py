import os, json
from playwright.sync_api import sync_playwright

PROMO_NAME_TPL = "{group_name}"

def _ensure_cookies_file(cookies_path="cookies.json"):
    if not os.path.exists(cookies_path) and os.getenv("COOKIES_JSON"):
        try:
            data = json.loads(os.getenv("COOKIES_JSON"))
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

def ensure_context(pw, cookies_path, headless=True):
    _ensure_cookies_file(cookies_path)
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context()
    if os.path.exists(cookies_path):
        with open(cookies_path, "r", encoding="utf-8") as f:
            context.add_cookies(json.load(f))
    page = context.new_page()
    page.goto("https://seller.ozon.ru/app/dashboard", wait_until="networkidle")
    try:
        page.get_by_role("button", name="Цены и акции").click(timeout=4000)
    except:
        page.get_by_text("Цены и акции", exact=False).first.click()
    if page.get_by_role("link", name="Мои акции").count():
        page.get_by_role("link", name="Мои акции").click()
    else:
        page.get_by_text("Собственные акции", exact=False).first.click()
    page.wait_for_load_state("networkidle")
    return browser, context, page

def find_or_create_promo(page, promo_name):
    try:
        page.fill('input[placeholder="Поиск"]', promo_name); page.keyboard.press("Enter"); page.wait_for_timeout(800)
    except: pass
    if page.locator(f"text={promo_name}").count() > 0:
        page.locator(f"text={promo_name}").first.click(); page.wait_for_load_state("networkidle"); return "edit"
    page.get_by_role("button", name="Создать акцию").click(); page.wait_for_load_state("networkidle")
    try: page.fill('input[name=\"promoName\"]', promo_name)
    except: page.get_by_placeholder("Название").fill(promo_name)
    return "create"

def set_cities(page, cities: list[str]):
    page.get_by_text("Города", exact=False).click()
    try:
        if page.get_by_role("button", name="Снять выделение").is_visible():
            page.get_by_role("button", name="Снять выделение").click()
    except: pass
    for city in cities:
        try:
            page.fill('input[placeholder="Поиск города"]', city); page.wait_for_timeout(200)
            page.get_by_role("checkbox", name=city, exact=False).check()
        except: pass
    try: page.get_by_role("button", name="Сохранить").click()
    except: pass

def set_discount(page, percent: int):
    page.get_by_text("Размер скидки", exact=False).click()
    fld = page.locator('input[name=\"discount\"]'); 
    if not fld.count(): fld = page.get_by_placeholder(\"%\")
    fld.fill(str(percent))
    try: page.get_by_role(\"button\", name=\"Сохранить\").click()
    except: pass

def set_products(page, offer_ids: list[str]):
    page.get_by_text(\"Товары\", exact=False).click()
    try:
        if page.get_by_role(\"button\", name=\"Снять все\").is_visible():
            page.get_by_role(\"button\", name=\"Снять все\").click()
    except: pass
    for oid in offer_ids:
        try:
            page.fill('input[placeholder=\"Поиск товара\"]', oid); page.wait_for_timeout(250)
            page.get_by_role(\"checkbox\", name=oid, exact=False).check()
        except: pass
    try: page.get_by_role(\"button\", name=\"Сохранить\").click()
    except: pass

def save_promo(page):
    try: page.get_by_role(\"button\", name=\"Запустить продвижение\").click()
    except:
        try: page.get_by_role(\"button\", name=\"Сохранить\").click()
        except: pass

def upsert_promo(group_name: str, cities: list[str], discount: int, offer_ids: list[str], cookies_path=\"cookies.json\", headless=True):
    with sync_playwright() as pw:
        browser, context, page = ensure_context(pw, cookies_path, headless=headless)
        promo_name = PROMO_NAME_TPL.format(group_name=group_name)
        _mode = find_or_create_promo(page, promo_name)
        set_cities(page, cities or [])
        set_discount(page, int(discount))
        if offer_ids: set_products(page, offer_ids)
        save_promo(page)
        context.storage_state(path=cookies_path); browser.close()
