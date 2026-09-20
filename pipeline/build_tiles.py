"""Split the scored buildings into map tiles the browser can stream.

scores.json is ~50 MB. No page should fetch that. The map only ever shows one
viewport, so the data is cut into slippy tiles at zoom 13 (~5 km across) and the
page pulls the handful it needs, the same way the basemap works.

Rows are arrays rather than objects: the keys repeat 200,000 times otherwise.
COLUMNS below is the contract with the page -- keep the two in step.

Output: data/tiles/13/<x>/<y>.json  +  data/tiles/index.json
"""
from __future__ import annotations

import datetime
import json
import math
import pathlib
import shutil

# z13 put ~10k buildings and 2.7 MB into a single dense-Kowloon tile, which is a
# bad first fetch on mobile. z14 quarters that.
Z = 14
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
    "pattern",   # 21 本命格局 at the building's own 元運
    "now",       # 22 how that chart stands in the CURRENT period (九運)
    "res",       # 23 1 = looks like somewhere people live, 0 = not
    "conf",      # 24 confidence in the derived facing, 0-1
    "est",       # 25 estate name, when the Housing Authority register names it;
                 #    look the rest of the estate's detail up in estates.json
    "ring",      # 26 footprint: [lon0, lat0, then integer deltas x1e-5 deg]
]


# Names that give a building away as somewhere nobody lives. The occupation
# permit already settles ~13k buildings, but 39k carry no use text at all, so
# the name is the only signal left for those.
NOT_A_HOME = (
    # Infrastructure and plant
    "貨倉", "倉庫", "變壓", "變電", "電站", "配電", "電力", "電錶", "發電",
    "煤氣", "油庫", "油站", "污水", "焚化", "配水庫", "抽水站", "泵房",
    "水務", "濾水", "水缸", "水箱", "機房", "機樓", "垃圾", "廢物", "收集站",
    "停車場", "車場", "車房", "車廠", "公廁", "廁所", "洗手間",
    "工場", "工廠", "廠房", "貨櫃", "碼頭", "船塢", "機場",
    "基站", "天線", "發射", "雷達", "隧道", "天橋", "行人橋",
    # Civic, education, worship
    "中學", "小學", "幼稚園", "書院", "學校", "大學", "專上",
    "醫院", "診所", "警署", "消防局", "救護", "圖書館", "街市",
    "體育館", "游泳池", "運動場", "球場", "大會堂", "博物館",
    "郵政局", "法院", "軍營", "軍事", "劇院", "戲院", "會展",
    "政府合署", "辦事處", "總站", "電視城", "數據中心",
    "教堂", "禮拜堂", "寺", "廟", "祠堂", "道觀", "庵",
    "會所", "更亭", "崗亭", "警崗",
    # 陰宅
    "墳場", "骨灰", "靈灰", "殯儀", "火葬", "義莊",
)


def is_dwelling(r: dict) -> bool:
    """Would someone live here? The Buildings Department use class decides it
    where there is one; the name blacklist is only for what it does not cover.

    A property search that opens with a warehouse and a substation as its top
    two results is not answering the question that was asked.
    """
    if r.get("residential") is False:
        return False
    # Terms are multi-character on purpose: a bare 軍 would strike out every
    # estate in 將軍澳, and a bare 中心 would take 荃灣中心 with it.
    name = (r.get("tc") or "") + " " + (r.get("en") or "")
    if any(k in name for k in NOT_A_HOME):
        return False
    if r.get("residential") is True:
        return True
    # Unknown use: a tower with storeys is a reasonable default for housing.
    st = r.get("storeys")
    return bool(st and st >= 3)


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


def encode_ring(ring: list) -> list | None:
    """Footprints dominate tile size. Absolute coordinates cost ~10 characters
    each ("114.18523"); as integer deltas from the first vertex, in units of
    1e-5 degrees, a typical building's vertices become 2-3 character numbers.
    The page adds them back up."""
    if not ring:
        return None
    out = [round(ring[0][0], 5), round(ring[0][1], 5)]
    px = round(ring[0][0] * 1e5)
    py = round(ring[0][1] * 1e5)
    for x, y in ring[1:]:
        cx, cy = round(x * 1e5), round(y * 1e5)
        out.append(cx - px)
        out.append(cy - py)
        px, py = cx, cy
    return out


def row_for(r: dict) -> list:
    flat = encode_ring(r.get("ring"))
    return [
        r.get("id"), r.get("tc"), r.get("en"),
        r.get("lon"), r.get("lat"),
        r.get("total"), r.get("env"), r.get("traffic"), r.get("ancil"),
        r.get("mt_d"), r.get("mt_dir"), r.get("wt_d"), r.get("wt_dir"),
        r.get("mwds8"), r.get("h"), r.get("storeys"),
        r.get("op_year"), r.get("period"),
        r.get("facing"), r.get("sit_m"), r.get("face_m"), r.get("pattern"),
        r.get("now"), 1 if is_dwelling(r) else 0, r.get("conf"),
        (r.get("estate") or {}).get("estate") or None,
        flat,
    ]


def build_estates(scores: list[dict]) -> None:
    """How many blocks, how many flats, who manages it — what a buyer asks
    before anything else. The Housing Authority publishes it per estate, so it
    lives in one file the page fetches once, keyed by the name in column `est`.
    """
    out: dict[str, dict] = {}
    for r in scores:
        e = r.get("estate")
        if not e or not e.get("estate"):
            continue
        out.setdefault(e["estate"], {
            "kind": e.get("kind"),
            "mgmt": e.get("mgmt"),
            "flats": e.get("flats"),
            "nblocks": e.get("nblocks"),
            "year": e.get("year"),
        })
    p = DATA / "estates.json"
    p.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    named = sum(1 for r in scores if (r.get("estate") or {}).get("estate"))
    print(f"estates: {len(out):,} 個屋苑 · {named:,} 幢有屋苑資料 "
          f"-> {p.name} ({p.stat().st_size/1024:.0f} KB)")


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
    build_districts(scores)   # the on-map subset, so counts match the filter
    build_estates(scores)
    stamp(len(scores), len(all_scores))


def stamp(on_map: int, total: int) -> None:
    """A build stamp the page can display. Without one there is no way to tell a
    stale cached page from a current one just by looking at it."""
    (OUT / "build.json").write_text(json.dumps({
        "built": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "on_map": on_map,
        "total": total,
    }, separators=(",", ":")))
    print(f"build stamp written")


def build_search(scores: list[dict]) -> None:
    """One index of every named building, fetched once and searched locally.

    Splitting this by leading character produced ~12,000 tiny files — fine to
    serve, miserable to keep in a repo. GitHub Pages gzips on the wire, which
    takes the whole index from 5.3 MB to about 1.4 MB: one cached download, then
    every keystroke is instant with no further requests.
    """
    rows = []
    for r in scores:
        if not (r.get("tc") or r.get("en")):
            continue
        rows.append([r.get("tc"), r.get("en"), r.get("district"),
                     round(r["lon"], 5), round(r["lat"], 5),
                     r.get("total"), r.get("now"),
                     1 if is_dwelling(r) else 0])
    rows.sort(key=lambda x: -(x[5] or 0))
    p = OUT / "search.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"c": ["tc", "en", "district", "lon", "lat", "total", "now", "res"],
                             "b": rows}, separators=(",", ":"), ensure_ascii=False))
    print(f"  of which look residential: {sum(r[7] for r in rows):,}")
    print(f"search index: {len(rows):,} named buildings, "
          f"{p.stat().st_size/1e6:.1f} MB raw (~1.4 MB gzipped on the wire)")


# Must match LEVELS/BREAKS in index.html.
BANDS = [("bad", 0, 41), ("poor", 41, 46), ("mid", 46, 52), ("good", 52, 58), ("best", 58, 999)]


def band_of(v: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= v < hi:
            return name
    return "best"


def build_districts(scores: list[dict]) -> None:
    """Per-district aggregates for the overview the page shows before you zoom in.

    Band counts let the filter answer "which district has the most good stock"
    without the page having to download every tile to count for itself.
    """
    import collections
    acc = collections.defaultdict(lambda: {"n": 0, "sum": 0.0, "lon": 0.0, "lat": 0.0,
                                           "patterns": collections.Counter(),
                                           "bands": collections.Counter()})
    for r in scores:
        d = r.get("district")
        if not d:
            continue
        a = acc[d]
        a["n"] += 1
        a["sum"] += r["total"]
        a["lon"] += r["lon"]
        a["lat"] += r["lat"]
        a["bands"][band_of(r["total"])] += 1
        if r.get("pattern"):
            a["patterns"][r["pattern"]] += 1

    out = [{"tc": d,
            "n": a["n"],
            "avg": round(a["sum"] / a["n"], 2),
            "lon": round(a["lon"] / a["n"], 5),
            "lat": round(a["lat"] / a["n"], 5),
            "patterns": dict(a["patterns"]),
            "bands": dict(a["bands"])}
           for d, a in acc.items()]
    out.sort(key=lambda r: -r["avg"])
    (DATA / "district_stats.json").write_text(
        json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(f"district stats: {len(out)} districts")
    for r in out:
        b = r["bands"]
        print(f"  {r['tc']:<7} {r['avg']:>6.2f}  {r['n']:>6,} 棟 "
              f"| 大吉 {b.get('best',0):>5,}  吉 {b.get('good',0):>5,}  "
              f"差 {b.get('bad',0):>5,}")


if __name__ == "__main__":
    main()
