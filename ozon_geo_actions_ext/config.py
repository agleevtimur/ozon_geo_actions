from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class OzonConfig:
    cookies_plain: str
    company_id: str
    language: str = "ru"
    page_type: str = "highlights-other"

    @staticmethod
    def from_env() -> "OzonConfig":
        cookies_plain = os.getenv("OZON_COOKIES", "").strip()
        if not cookies_plain:
            raise RuntimeError("ENV OZON_COOKIES пуст. Ожидается plain text строка всего Cookie-заголовка.")
        company_id = os.getenv("OZON_COMPANY_ID", "").strip()
        if not company_id:
            raise RuntimeError("ENV OZON_COMPANY_ID пуст.")
        language = os.getenv("OZON_LANGUAGE", "ru").strip() or "ru"
        page_type = os.getenv("OZON_PAGE_TYPE", "highlights-other").strip() or "highlights-other"
        return OzonConfig(cookies_plain=cookies_plain, company_id=company_id, language=language, page_type=page_type)
