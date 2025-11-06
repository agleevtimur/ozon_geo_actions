from typing import List, Dict, Any, Optional
import json

def load_mapping(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_addresses_for_action(
    region_city_uid_mapping: Dict[str, Any],
    regions: Optional[List[str]] = None,
    include_country_and_region_uids: bool = True,
) -> List[str]:
    """
    region_city_uid_mapping формат:
    {
      "Россия": {
        "uid": "<country_uid>",
        "regions": {
          "Свердловская область": {
            "uid": "<region_uid>",
            "cities": [
              {"title": "Екатеринбург", "uid": "...", "type":"city"},
              ...
            ]
          },
          ...
        }
      }
    }
    """
    addresses: List[str] = []

    for _country, cdata in region_city_uid_mapping.items():
        c_uid = cdata.get("uid")
        if include_country_and_region_uids and c_uid:
            addresses.append(c_uid)

        rmap = cdata.get("regions", {})
        for rname, rdata in rmap.items():
            if regions and rname not in regions:
                continue
            r_uid = rdata.get("uid")
            if include_country_and_region_uids and r_uid:
                addresses.append(r_uid)
            for city in rdata.get("cities", []):
                cu = city.get("uid")
                if cu:
                    addresses.append(cu)

    # dedup preserving order
    seen = set()
    uniq: List[str] = []
    for a in addresses:
        if a not in seen:
            uniq.append(a)
            seen.add(a)
    return uniq
