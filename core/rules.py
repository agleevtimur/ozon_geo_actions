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
