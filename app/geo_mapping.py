import json
import os

class GeoResolver:
    """Простой загрузчик geo.json с готовой структурой country/regions/cities."""

    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("GEO_JSON_PATH", "/app/data/geo.json")
        self.country = None
        self.regions = {}
        self.cities = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"geo.json not found at {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "regions" not in data:
            raise RuntimeError("geo.json missing 'regions' key")

        self.country = data.get("country", {})
        for region in data["regions"]:
            rname = region["name"].strip()
            self.regions[rname] = region["uid"]
            for city in region.get("cities", []):
                cname = city["name"].strip()
                self.cities[cname] = city["uid"]

        if not self.regions:
            raise RuntimeError("No regions found in geo.json")

    def get_country_uid(self) -> str | None:
        return self.country.get("uid")

    def get_region_uid(self, name: str) -> str | None:
        """Поиск UID региона по названию."""
        return self.regions.get(name.strip())

    def get_city_uid(self, name: str) -> str | None:
        """Поиск UID города по названию."""
        return self.cities.get(name.strip())

    def resolve(self, name: str) -> str | None:
        """Возвращает UID по названию города или региона."""
        return self.cities.get(name.strip()) or self.regions.get(name.strip())


if __name__ == "__main__":
    geo = GeoResolver()
    print(f"✅ Loaded {len(geo.regions)} regions, {len(geo.cities)} cities")
