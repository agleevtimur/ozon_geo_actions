import yaml, threading
from pathlib import Path
_LOCK = threading.Lock()
RULES_PATH = Path("rules.yaml")
def load_rules():
    with _LOCK:
        with RULES_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
def save_rules(data: dict):
    with _LOCK:
        tmp = RULES_PATH.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        tmp.replace(RULES_PATH)

GROUP_TO_PROMO_NAME = {
    "GEO-G1": "10 скидка",
    "GEO-G2": "9 скидка",
    "GEO-G3": "8 скидка",
    "GEO-G4": "7 скидка",
    "GEO-G5": "6 скидка",
    "GEO-G6": "5 скидка",
    "GEO-G7": "4 скидка",
    "GEO-G8": "3 ОБЩАЯ скидка",
    "GEO-G9": "2 скидка",
    "GEO-G10": "1 скидка",
    # ...если у тебя другие имена акций — впиши их здесь
}
