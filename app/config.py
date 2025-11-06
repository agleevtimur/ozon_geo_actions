import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OZON_COOKIE_PLAIN = os.getenv("OZON_COOKIE_PLAIN", "")
OZON_COMPANY_ID = os.getenv("OZON_COMPANY_ID", "1297124")  # override if needed
OZON_LANGUAGE = os.getenv("OZON_LANGUAGE", "ru")
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "30"))
BASE_ACTION_UPDATE_URL_TEMPLATE = "https://seller.ozon.ru/api/site/marketplace-seller-actions/v1/action/{action_id}/update"

# Optional: path to your locations file (страна/регион/город -> uid)
LOCATIONS_PATH = os.getenv("LOCATIONS_PATH", "data/locations.json")