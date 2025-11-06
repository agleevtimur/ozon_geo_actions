import os, json, base64, logging, pathlib
from typing import List, Dict, Any, Set

log = logging.getLogger("geo")

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "geo.json"

class GeoResolver:
    def __init__(self):
        self.data = self._load()
        # Построим быстрые индексы
        self.region_uid_map = {}  # region name -> uid
        self.region_to_cities_uids = {}  # region name -> set(city uid)
        self._index()

    def _load(self) -> Dict[str, Any]:
        b64 = os.getenv("GEO_JSON_BASE64")
        if b64:
            try:
                raw = base64.b64decode(b64)
                return json.loads(raw)
            except Exception as e:
                log.error("Invalid GEO_JSON_BASE64: %s", e)
        if DATA_PATH.exists():
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        raise RuntimeError("Geo JSON not found. Provide GEO_JSON_BASE64 or data/geo.json")

    def _index(self):
        # Ожидается иерархия: country -> regions -> cities, у каждого есть: name, uid, type
        # Допускаем разные корневые формы, ищем все регионы и их города
        def walk(node):
            t = node.get("type")
            name = node.get("name")
            uid = node.get("uid")
            children = node.get("children") or []

            if t == "region" and name and uid:
                self.region_uid_map[name] = uid
                city_uids = set()
                for ch in children:
                    if ch.get("type") == "city" and ch.get("uid"):
                        city_uids.add(ch["uid"])
                self.region_to_cities_uids[name] = city_uids

            for ch in children:
                walk(ch)

        # поддержим как список, так и одиночный объект
        root = self.data
        if isinstance(root, dict):
            walk(root)
        elif isinstance(root, list):
            for it in root:
                if isinstance(it, dict):
                    walk(it)

        if not self.region_uid_map:
            raise RuntimeError("No regions found in geo.json")

    def regions_to_addresses(self, region_names: List[str]) -> List[str]:
        uids: Set[str] = set()
        for r in region_names:
            uid = self.region_uid_map.get(r)
            if uid:
                uids.add(uid)
                uids |= self.region_to_cities_uids.get(r, set())
        return list(uids)
