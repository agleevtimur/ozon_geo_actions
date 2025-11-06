# /app/app/geo_mapping.py
import json
import os
from typing import Optional, Dict, Any


class GeoResolver:
    """
    Читает уже ГОТОВЫЙ geo.json формата:
    {
      "country": {"name": "Россия", "uid": "..." },
      "regions": [
        {"name": "Московская область", "uid": "...", "cities": [
          {"name": "Химки", "uid": "..."},
          ...
        ]},
        ...
      ]
    }

    Никакой конвертации «сырого» вида не делает.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        # По умолчанию ждём файл в /app/data/geo.json (Railway)
        self.path: str = path or os.getenv("GEO_JSON_PATH", "/app/data/geo.json")

        self.country: Dict[str, Any] = {}
        self.regions: Dict[str, str] = {}  # region_name -> uid
        self.cities: Dict[str, str] = {}   # city_name   -> uid

        self._load_and_index()

    def _load_and_index(self) -> None:
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"geo.json not found at {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise RuntimeError("geo.json must be a JSON object at the top level")

        if "regions" not in data or not isinstance(data["regions"], list):
            raise RuntimeError("geo.json missing 'regions' (array)")

        # country — опционально; если задан, кладём как есть
        self.country = data.get("country", {}) or {}

        # Индексация регионов и городов
        for region in data["regions"]:
            rname = (region.get("name") or "").strip()
            ruid = region.get("uid")
            if not rname or not ruid:
                # пропускаем битые элементы
                continue

            self.regions[rname] = ruid

            for city in region.get("cities", []) or []:
                cname = (city.get("name") or "").strip()
                cuid = city.get("uid")
                if not cname or not cuid:
                    continue
                self.cities[cname] = cuid

        if not self.regions:
            raise RuntimeError("No regions found in geo.json")

    # ---------- Публичные методы ----------
    def get_country_uid(self) -> Optional[str]:
        return self.country.get("uid")

    def get_region_uid(self, name: str) -> Optional[str]:
        return self.regions.get(name.strip())

    def get_city_uid(self, name: str) -> Optional[str]:
        return self.cities.get(name.strip())

    def resolve(self, name: str) -> Optional[str]:
        """
        Универсальный резолвер: сначала ищем город,
        если не нашли — пробуем регион.
        """
        key = name.strip()
        return self.cities.get(key) or self.regions.get(key)


# Для быстрой диагностики при запуске как модуля:
if __name__ == "__main__":
    geo = GeoResolver()
    print(
        f"✅ geo.json loaded: country_uid={geo.get_country_uid()} | "
        f"regions={len(geo.regions)} | cities={len(geo.cities)} | path={geo.path}"
    )
