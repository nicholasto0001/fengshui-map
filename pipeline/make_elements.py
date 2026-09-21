"""五行屬性 — working out what element each district actually is, from its form.

Why this exists
---------------
Every circulating "which element is which Hong Kong district" list traces back
to one anonymous 2011 blog post that contradicts itself (上環 metal, 中環 water,
both inside 中西區) and leaves most of the territory unanswered. See
docs/district-research.md. Copying it would be copying a guess.

The classical method never was a lookup table. 楊筠松《撼龍經》 assigns the five
elements by FORM -- 金圓、木直、水曲、火尖、土方 -- and that is measurable. Every
residential building here carries its height, its footprint polygon and its
distance to the nearest mountain and water edge, so a district's form can be
computed rather than looked up.

What each element is read from
------------------------------
  木 直   tall and slender: height, and height over footprint width
  土 方   the opposite -- low and broad-based
  火 尖   sharp: buildings rising well above their own neighbourhood, and density
  水 曲   water: how much of the district's housing sits on the shoreline
  金 圓   NOT COMPUTED FROM FORM. Roundness needs the footprint outline, and the
          median footprint in this data has four vertices -- half the stock is a
          simplified rectangle. A circularity figure off that would be noise
          wearing a number's clothes. 金 falls back to direction alone, and the
          output says so.

Alongside that sits the older and simpler leg: 五行配方位, 東木 南火 西金 北水
中土, which is the frame Hong Kong masters use when they answer this question in
print (區晉豪〈五行方向搵屋〉《新玄機》231). Both legs are reported. They are NOT
merged into one number -- merging two systems that disagree is how you end up
telling everybody that every district suits them.

Ranks, not raw values
---------------------
An element score is a rank among the 18 districts, because "this district is
wood" only ever means "compared with the rest of Hong Kong". The raw figures
travel with it so the app can say why.

Output: data/elements.json
Self-test: `python3 pipeline/make_elements.py`
"""
from __future__ import annotations

import json
import math
import pathlib
import statistics as st
from collections import defaultdict

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "data" / "elements.json"

M_PER_DEG_LAT = 110540.0
NEAR_M = 300.0      # radius that counts as "its own neighbourhood"
SPIKE = 2.0         # twice the neighbourhood's height is a 尖
SHORE_M = 200.0     # within this of the water edge is 近水

WX = ("木", "火", "土", "金", "水")


def m_per_deg_lon(lat: float) -> float:
    return 111320.0 * math.cos(math.radians(lat))


def ring_area_perimeter(ring: list) -> tuple[float, float]:
    """Shoelace area (m²) and perimeter (m) of a lon/lat ring."""
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx = m_per_deg_lon(lat0)
    pts = [(p[0] * kx, p[1] * M_PER_DEG_LAT) for p in ring]
    a = per = 0.0
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        a += x1 * y2 - x2 * y1
        per += math.hypot(x2 - x1, y2 - y1)
    return abs(a) / 2, per


def prominence(rows: list[dict]) -> dict[str, float]:
    """How far each building stands above the roofline around it.

    A 300 m grid, so each building is compared with the block it belongs to
    rather than with the territory. Everything is used as context, offices
    included -- a tower is not sharp if it sits among other towers.
    """
    cell: dict[tuple[int, int], list[float]] = defaultdict(list)
    for r in rows:
        h = r.get("h")
        if not h:
            continue
        kx = m_per_deg_lon(r["lat"])
        cell[(int(r["lon"] * kx / NEAR_M), int(r["lat"] * M_PER_DEG_LAT / NEAR_M))].append(h)

    med = {k: st.median(v) for k, v in cell.items()}
    out: dict[str, float] = {}
    for r in rows:
        h = r.get("h")
        if not h:
            continue
        kx = m_per_deg_lon(r["lat"])
        cx = int(r["lon"] * kx / NEAR_M)
        cy = int(r["lat"] * M_PER_DEG_LAT / NEAR_M)
        # the 3x3 block, so a building at a cell edge is not judged against a
        # sliver of neighbours
        near = [med[(cx + dx, cy + dy)]
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (cx + dx, cy + dy) in med]
        base = st.median(near) if near else h
        out[r["id"]] = h / max(base, 1.0)
    return out


def rank_pct(values: dict[str, float], low_is_high: bool = False) -> dict[str, float]:
    """Position among the districts: the largest value scores 100.

    `low_is_high` flips it, for the measures where being close counts -- the
    district with the SHORTEST distance to water is the one most on the water.
    """
    order = sorted(values, key=lambda k: values[k], reverse=not low_is_high)
    n = len(order) - 1
    return {k: (round(100.0 * (n - i) / n, 1) if n else 50.0)
            for i, k in enumerate(order)}


# 五行配方位 -- the leg that does cover all five.
DIR_WX = {"東": "木", "南": "火", "西": "金", "北": "水", "中": "土"}


CENTRE_R = 0.25   # inside this fraction of the half-extent counts as 中


def bearing_zone(lon: float, lat: float, box: tuple[float, float, float, float]) -> str:
    """East / south / west / north, or 中 when the district sits near the middle.

    The frame is Hong Kong's own bounding box -- every district polygon, not
    just the built-up parts -- and offsets are a fraction of it, so the long
    east-west axis does not push everything into 東 or 西.

    Checked against the only published Hong Kong statement of this framework,
    區晉豪〈五行方向搵屋〉《新玄機》231. Of his five calls this reproduces
    新界北=水, 九龍=中土, 西貢=東木 and 大嶼山=西金; it puts 沙田 in the north
    where he groups it with the southern New Territories. Four and a half of
    five, from geometry alone.
    """
    c_lon, c_lat, span_lon, span_lat = box
    dx = (lon - c_lon) / (span_lon / 2)
    dy = (lat - c_lat) / (span_lat / 2)
    if math.hypot(dx, dy) < CENTRE_R:
        return "中"
    return ("東" if dx > 0 else "西") if abs(dx) >= abs(dy) else ("北" if dy > 0 else "南")


def build() -> list[dict]:
    districts = json.loads((ROOT / "data" / "districts.json").read_text("utf8"))
    land = {}
    for d in districts:
        land[d["tc"]] = sum(ring_area_perimeter(r)[0] for r in d["rings"]) / 1e6

    rows = json.loads((ROOT / "data" / "scores.json").read_text("utf8"))
    prom = prominence(rows)

    homes = [r for r in rows if r.get("residential") and r.get("district") in land]
    by: dict[str, list[dict]] = defaultdict(list)
    for r in homes:
        by[r["district"]].append(r)

    raw: dict[str, dict] = {}
    for name, rs in by.items():
        hs, slen, spikes, shore, wts = [], [], 0, 0, []
        for r in rs:
            h = r.get("h") or 0.0
            ring = r.get("ring")
            if h > 0:
                hs.append(h)
                if ring and len(ring) >= 4:
                    area, _ = ring_area_perimeter(ring)
                    if area > 0:
                        slen.append(h / math.sqrt(area))
                if prom.get(r["id"], 0) >= SPIKE:
                    spikes += 1
            wd = r.get("wt_d")
            if wd is not None:
                wts.append(wd)
                if wd <= SHORE_M:
                    shore += 1
        cen_lon = st.median([r["lon"] for r in rs])
        cen_lat = st.median([r["lat"] for r in rs])
        raw[name] = dict(
            n=len(rs),
            km2=round(land[name], 1),
            h_med=round(st.median(hs), 1) if hs else 0.0,
            slender=round(st.median(slen), 2) if slen else 0.0,
            spike=round(100.0 * spikes / len(rs), 1),
            density=round(len(rs) / land[name]),
            shore=round(100.0 * shore / len(wts), 1) if wts else 0.0,
            wt_med=round(st.median(wts)) if wts else 0,
            lon=round(cen_lon, 5), lat=round(cen_lat, 5),
        )

    # The frame is the territory, not the spread of the 18 centroids -- the
    # latter is dragged north by the size of the New Territories, which pushed
    # every Kowloon district out of 中.
    xs = [p[0] for d in districts for r in d["rings"] for p in r]
    ys = [p[1] for d in districts for r in d["rings"] for p in r]
    box = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
           max(xs) - min(xs), max(ys) - min(ys))

    r_h = rank_pct({k: v["h_med"] for k, v in raw.items()})
    r_sl = rank_pct({k: v["slender"] for k, v in raw.items()})
    r_sp = rank_pct({k: v["spike"] for k, v in raw.items()})
    r_dn = rank_pct({k: v["density"] for k, v in raw.items()})
    r_sh = rank_pct({k: v["shore"] for k, v in raw.items()})
    r_wt = rank_pct({k: v["wt_med"] for k, v in raw.items()}, low_is_high=True)

    out = []
    for name, v in raw.items():
        zone = bearing_zone(v["lon"], v["lat"], box)
        form = {
            "木": round((r_h[name] + r_sl[name]) / 2),
            "土": round((100 - r_h[name] + 100 - r_sl[name]) / 2),
            "火": round((r_sp[name] + r_dn[name]) / 2),
            "水": round((r_sh[name] + r_wt[name]) / 2),
        }
        out.append(dict(tc=name, zone=zone, dir_wx=DIR_WX[zone], form=form, **v))

    out.sort(key=lambda r: -r["n"])
    return out


if __name__ == "__main__":
    recs = build()
    OUT.write_text(json.dumps(recs, ensure_ascii=False), "utf8")

    print(f"{'區':<7}{'住宅':>7}{'方位':>5}{'木':>5}{'火':>5}{'土':>5}{'水':>5}"
          f"   {'高中位':>7}{'瘦削':>6}{'尖%':>6}{'密度':>6}{'近水%':>7}")
    print("-" * 84)
    for r in sorted(recs, key=lambda r: -r["form"]["木"]):
        f = r["form"]
        print(f"{r['tc']:<7}{r['n']:>7,}{r['zone']:>5}"
              f"{f['木']:>5}{f['火']:>5}{f['土']:>5}{f['水']:>5}   "
              f"{r['h_med']:>7.1f}{r['slender']:>6.2f}{r['spike']:>6.1f}"
              f"{r['density']:>6}{r['shore']:>7.1f}")
    print(f"\n-> {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
    print("金 冇形嘅數據支持，只由方位定 —— 見檔案開頭。")
