"""Split the scored buildings into map tiles the browser can stream.

scores.json is ~50 MB. No page should fetch that. The map only ever shows one
viewport, so the data is cut into slippy tiles at zoom 13 (~5 km across) and the
page pulls the handful it needs, the same way the basemap works.

Rows are arrays rather than objects: the keys repeat 200,000 times otherwise.
COLUMNS below is the contract with the page -- keep the two in step.

Output: data/tiles/13/<x>/<y>.json  +  data/tiles/index.json
"""
from __future__ import annotations

import json
import math
import pathlib
import shutil

Z = 13
DATA = pathlib.Path(__file__).parent.parent / "data"
OUT = DATA / "tiles"

# Column order for each building row. Mirrored in index.html.
COLUMNS = [
    "id",        # 0  BuildingCSUID
    "tc",        # 1  Chinese name (null when unnamed)
    "en",        # 2  English name
    "lon",       # 3
    "lat",       # 4
    "total",     # 5  0-100 overall score
    "env",       # 6  environment component
    "traffic",   # 7
    "ancil",     # 8
    "mt_d",      # 9  metres to nearest mountain
    "mt_dir",    # 10 8-point direction of it
    "wt_d",      # 11 metres to nearest water
    "wt_dir",    # 12
    "mwds8",     # 13 flying-star mountain/water pair score, 0-9
    "h",         # 14 building height in metres
    "storeys",   # 15
    "op_year",   # 16 occupation permit year, null when unknown
    "period",    # 17 元運 1-9, null when unknown
    "facing",    # 18 derived 向 in degrees, null when not derivable
    "sit_m",     # 19 坐 as one of the 24 mountains
    "face_m",    # 20 向 as one of the 24 mountains
    "pattern",   # 21 旺山旺向 / 上山下水 / 雙星到向 / 雙星到坐
    "conf",      # 22 confidence in the derived facing, 0-1
    "ring",      # 23 flat [lon,lat,...] footprint, null when unavailable
]


def keep(r: dict) -> bool:
    """Which buildings belong on the map.

    The full Active+Tower set is 213k, but most of the tail is pump houses,
    guard posts and plant rooms — visual noise on a map for choosing a home,
    and the bulk of the payload once footprints are attached. Keep anything
    that is named, known to be residential, or tall enough to be somewhere
    people live. That lands near the 2023 layer's 63k, plus the new stock it
    never had.
    """
    if r.get("tc") or r.get("en"):
        return True
    if r.get("residential"):
        return True
    storeys = r.get("storeys")
    return bool(storeys and storeys >= 3)


def deg2tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * n)
    return x, y


def row_for(r: dict) -> list:
    ring = r.get("ring")
    flat = None
    if ring:
        flat = [round(v, 5) for pt in ring for v in pt]
    return [
        r.get("id"), r.get("tc"), r.get("en"),
        r.get("lon"), r.get("lat"),
        r.get("total"), r.get("env"), r.get("traffic"), r.get("ancil"),
        r.get("mt_d"), r.get("mt_dir"), r.get("wt_d"), r.get("wt_dir"),
        r.get("mwds8"), r.get("h"), r.get("storeys"),
        r.get("op_year"), r.get("period"),
        r.get("facing"), r.get("sit_m"), r.get("face_m"), r.get("pattern"),
        r.get("conf"),
        flat,
    ]


def main() -> None:
    all_scores = json.loads((DATA / "scores.json").read_text())
    scores = [r for r in all_scores if keep(r)]
    print(f"{len(all_scores):,} scored buildings -> {len(scores):,} on the map "
          f"({len(all_scores) - len(scores):,} unnamed low-rise structures dropped)")

    if OUT.exists():
        shutil.rmtree(OUT)

    tiles: dict[tuple[int, int], list] = {}
    for r in scores:
        lon, lat = r.get("lon"), r.get("lat")
        if lon is None or lat is None:
            continue
        tiles.setdefault(deg2tile(lon, lat, Z), []).append(row_for(r))

    total_bytes = 0
    for (x, y), rows in tiles.items():
        p = OUT / str(Z) / str(x) / f"{y}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps({"c": COLUMNS, "b": rows}, separators=(",", ":"), ensure_ascii=False)
        p.write_text(blob)
        total_bytes += len(blob.encode())

    counts = {f"{x}/{y}": len(rows) for (x, y), rows in tiles.items()}
    (OUT / "index.json").write_text(json.dumps({
        "z": Z,
        "columns": COLUMNS,
        "tiles": counts,
        "buildings": sum(len(v) for v in tiles.values()),
    }, separators=(",", ":")))

    sizes = sorted(len(json.dumps({"c": COLUMNS, "b": r}, ensure_ascii=False).encode())
                   for r in tiles.values())
    print(f"{len(tiles):,} tiles, {total_bytes/1e6:.1f} MB total")
    print(f"  median tile {sizes[len(sizes)//2]/1024:.0f} KB, "
          f"largest {sizes[-1]/1024:.0f} KB")

    build_search(scores)
    build_districts(scores)


def build_search(scores: list[dict]) -> None:
    """Named buildings only, so typing an estate name can find one without
    downloading every tile. Unnamed structures are findable on the map."""
    rows = []
    for r in scores:
        tc, en = r.get("tc"), r.get("en")
        if not tc and not en:
            continue
        rows.append([tc, en, r.get("district"), r.get("lon"), r.get("lat"),
                     r.get("total"), r.get("pattern")])
    rows.sort(key=lambda x: -(x[5] or 0))
    p = DATA / "search.json"
    p.write_text(json.dumps({"c": ["tc", "en", "district", "lon", "lat", "total", "pattern"],
                             "b": rows}, separators=(",", ":"), ensure_ascii=False))
    print(f"search index: {len(rows):,} named buildings, {p.stat().st_size/1e6:.1f} MB")


def build_districts(scores: list[dict]) -> None:
    """Per-district aggregates for the overview the page shows before you zoom in."""
    import collections
    acc = collections.defaultdict(lambda: {"n": 0, "sum": 0.0, "lon": 0.0, "lat": 0.0,
                                           "patterns": collections.Counter()})
    for r in scores:
        d = r.get("district")
        if not d:
            continue
        a = acc[d]
        a["n"] += 1
        a["sum"] += r["total"]
        a["lon"] += r["lon"]
        a["lat"] += r["lat"]
        if r.get("pattern"):
            a["patterns"][r["pattern"]] += 1

    out = [{"tc": d,
            "n": a["n"],
            "avg": round(a["sum"] / a["n"], 2),
            "lon": round(a["lon"] / a["n"], 5),
            "lat": round(a["lat"] / a["n"], 5),
            "patterns": dict(a["patterns"])}
           for d, a in acc.items()]
    out.sort(key=lambda r: -r["avg"])
    (DATA / "district_stats.json").write_text(
        json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(f"district stats: {len(out)} districts")
    for r in out:
        print(f"  {r['tc']:<7} {r['avg']:>6.2f}  ({r['n']:,} buildings)")


if __name__ == "__main__":
    main()
