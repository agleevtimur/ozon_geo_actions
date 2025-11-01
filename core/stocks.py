from collections import defaultdict

# Embedded mapping (warehouse NAME → cluster)
WAREHOUSE_NAME_TO_CLUSTER = {}

# Optional ID mapping (fill later if you provide numeric IDs from /v1/warehouse/list)
WAREHOUSE_ID_TO_CLUSTER = {}

def _cluster_by_wh(wh: dict):
    # try by name
    for key in ("warehouse_name", "name", "warehouse"):
        if key in wh and wh[key]:
            nm = str(wh[key]).strip()
            if nm in WAREHOUSE_NAME_TO_CLUSTER:
                return WAREHOUSE_NAME_TO_CLUSTER[nm]
    # try by id
    wid = wh.get("warehouse_id")
    if wid is not None:
        try:
            wid_int = int(wid)
        except Exception:
            wid_int = None
        if wid_int is not None and wid_int in WAREHOUSE_ID_TO_CLUSTER:
            return WAREHOUSE_ID_TO_CLUSTER[wid_int]
    return None

def aggregate_by_cluster(stocks_resp):
    result = {}
    for item in stocks_resp.get("result", []):
        sku = int(item.get("sku"))
        cmap = defaultdict(int)
        for wh in (item.get("warehouses", []) or []):
            cluster = _cluster_by_wh(wh)
            if not cluster:
                continue
            qty = int(wh.get("present", 0) or 0)
            cmap[cluster] += qty
        result[sku] = dict(cmap)
    return result
