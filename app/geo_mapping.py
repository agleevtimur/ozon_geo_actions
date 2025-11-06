import os
import json


class GeoResolver:
    """
    Загружает geo.json (страна/регионы/города) и даёт функции:
      - get_region_uid(name)
      - get_city_uid(name)
      - regions_to_addresses(region_names) -> [uids]
    Формат ожидаем как у твоего большого geo.json:
    {
      "country": {...},
      "regions": [
        {
          "name": "Республика Татарстан",
          "uid": "...",
          "cities": [
            {"name": "Казань", "uid": "..."},
            ...
          ]
        },
        ...
      ]
    }
    """

    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("GEO_JSON_PATH", "/app/data/geo.json")

        self.regions: dict[str, str] = {}
        self.cities: dict[str, str] = {}
        self.region_to_city_uids: dict[str, list[str]] = {}

        self._load_and_index()

    def _load_and_index(self):
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for region in data.get("regions", []):
            rname = (region.get("name") or "").strip()
            ruid = region.get("uid")
            if rname and ruid:
                self.regions[rname] = ruid

            city_uids = []
            for city in (region.get("cities") or []):
                cname = (city.get("name") or "").strip()
                cuid = city.get("uid")
                if cname and cuid:
                    self.cities[cname] = cuid
                    city_uids.append(cuid)

            if rname:
                self.region_to_city_uids[rname] = city_uids

    def get_region_uid(self, region_name: str) -> str | None:
        return self.regions.get(region_name)

    def get_city_uid(self, city_name: str) -> str | None:
        return self.cities.get(city_name)

    def regions_to_addresses(self, region_names: list[str]) -> list[str]:
        """
        Возвращает список UID:
          - UID региона,
          - UID всех его городов.
        Уникализирует с сохранением порядка.
        """
        out = []
        seen = set()
        for r in region_names:
            ruid = self.get_region_uid(r)
            if ruid and ruid not in seen:
                out.append(ruid)
                seen.add(ruid)
            for cuid in self.region_to_city_uids.get(r, []):
                if cuid not in seen:
                    out.append(cuid)
                    seen.add(cuid)
        return out
