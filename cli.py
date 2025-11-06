import argparse
from ozon_geo_actions_ext.geo_builder import load_mapping, build_addresses_for_action
from ozon_geo_actions_ext.action_updater import OzonActionUpdater

def main():
    p = argparse.ArgumentParser(description="Update Ozon action geography via addresses list (cookie header version).")
    p.add_argument("--action-id", type=int, help="ID акции (обязателен, если не --print-addresses-only).")
    p.add_argument("--mapping", required=True, help="Путь к mapping.json.")
    p.add_argument("--regions", default="", help="Список регионов через запятую. По умолчанию все.")
    p.add_argument("--title", default="Geo update", help="Заголовок акции.")
    p.add_argument("--date-start", required=False, default="", help="ISO, если пусто — Ozon потребует валидное значение.")
    p.add_argument("--date-end", required=False, default="", help="ISO, если пусто — Ozon потребует валидное значение.")
    p.add_argument("--print-addresses-only", type=int, default=0, help="1 — только вывести addresses и выйти.")
    p.add_argument("--exclude-country-and-region-uids", type=int, default=0, help="1 — отправлять только города.")
    args = p.parse_args()

    mapping = load_mapping(args.mapping)
    regions = [s.strip() for s in args.regions.split(",") if s.strip()] or None
    include_cr = not bool(args.exclude_country_and_region_uids)

    addresses = build_addresses_for_action(
        mapping,
        regions=regions,
        include_country_and_region_uids=include_cr
    )

    if args.print_addresses_only == 1:
        for a in addresses:
            print(a)
        return

    if not args.action_id:
        raise SystemExit("--action-id обязателен (или используй --print-addresses-only 1).")
    if not args.date_start or not args.date_end:
        raise SystemExit("--date-start и --date-end обязательны для запроса к Ozon.")

    updater = OzonActionUpdater()
    resp = updater.update_action_addresses(
        action_id=args.action_id,
        addresses=addresses,
        title=args.title,
        date_start_iso=args.date_start,
        date_end_iso=args.date_end
    )
    print(resp)

if __name__ == "__main__":
    main()
