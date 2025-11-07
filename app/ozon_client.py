import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

def update_action_via_proxy(
    action_id: int,
    addresses: list[str],
    title: str
) -> requests.Response:
    """
    Обновляет акцию через UI-домен seller.ozon.ru
    Использует резидентный прокси и куки/заголовки из ENV.
    """

    base = "https://seller.ozon.ru"
    url = f"{base}/api/site/marketplace-seller-actions/v1/action/{action_id}/update"

    # Заголовки и куки
    cookie_header = os.getenv("OZON_COOKIE_HEADER", "").strip()
    if not cookie_header:
        raise RuntimeError("OZON_COOKIE_HEADER is empty. Укажи полный Cookie из Postman.")

    headers = {
        "Cookie": cookie_header,
        "x-o3-app-name": "seller-ui",
        "x-o3-company-id": os.getenv("OZON_COMPANY_ID", "1297124"),
        "x-o3-language": "ru",
        "x-o3-page-type": "highlights-other",
        "User-Agent": os.getenv(
            "BROWSER_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36",
        ),
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://seller.ozon.ru",
        "Referer": "https://seller.ozon.ru/",
        "Content-Type": "application/json",
    }

    # Тело запроса полностью, как в твоём curl
    body = {
        "action_parameters": {
            "title": title,
            "date_start": "2025-10-01T21:00:00.000Z",
            "date_end": "2026-05-03T20:59:59.000Z",
            "type": "DISCOUNT",
            "marketplace_id": 1,
            "warehouses": [],
            "addresses": addresses,
            "is_additional_discount": False,
            "marketplace_min_discount_percent": 1,
            "discount_type": "FINAL_PRICE",
        }
    }

    # Настройка прокси
    proxy = os.getenv("PROXY_URL", "").strip()
    sess = requests.Session()
    if proxy:
        sess.proxies = {"http": proxy, "https": proxy}
        logger.info("Используется прокси: %s", proxy)

    # Отправка запроса
    logger.info("POST %s", url)
    resp = sess.post(url, headers=headers, json=body, timeout=90, allow_redirects=False)

    # лог статуса и ключевых заголовков
    logger.info("Update response: %s | Location=%s | Content-Length=%s", resp.status_code, resp.headers.get("Location"), resp.headers.get("Content-Length"))

    if 300 <= resp.status_code >= 400:
        # короткое сообщение в логах
        snippet = resp.text[:1500] + "..." if len(resp.text) > 1500 else resp.text
        logger.error("Ошибка обновления акции (%s): %s", resp.status_code, snippet)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            pass

    return resp
