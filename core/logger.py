import logging, os
def setup_logger():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    return logging.getLogger("ozon-geo-bot")
