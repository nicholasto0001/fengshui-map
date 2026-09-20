"""Score the current building stock: 巒頭 (geography) and 理氣 (flying star).

Two separate judgements, deliberately NOT blended into one number:

  total    0-100 geographic score, reimplementing the 2023 reference
           methodology against live data (see docs/fengshui-logic.md)
  pattern  the classical 玄空飛星 outcome for the building's 元運 and 坐向

Mixing a percentile-normalised proximity index with a classical 理氣 verdict
would produce a number that means nothing in either system, so the page shows
them side by side instead.

Inputs :  data/terrain.json     mountain + water boundary points
          data/buildings.json   live CSDI stock, with footprint long axis
          data/facilities.json  negative ancillary features
          data/op.json          occupation permit year + type (optional)
Output :  data/scores.json
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import flyingstar  # noqa: E402
from common import (GridIndex, PolygonSet, angle_to_dir16, dir4, dir8,  # noqa: E402
                    mwds, percentile_scores, to_plane)
from orientation import facing_candidates, openness  # noqa: E402

DATA = pathlib.Path(__file__).parent.parent / "data"

# Weights, straight from the reference methodology diagram (docs/weighting-flow.png)
W_MWDS8, W_MWDS4 = 0.75, 0.25
W_DIR, W_MTDIS, W_WTDIS = 0.6, 0.2, 0.2
W_ENV, W_TRAFFIC, W_ANCIL = 0.8, 0.05, 0.15

ANCIL_MAX_M = 1000.0


def load(name: str):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else None


def ancillary_penalty(dist_m: float) -> float:
    if dist_m >= ANCIL_MAX_M:
        return 0.0
    return max(0.0, 10.0 - math.floor(dist_m / 100.0))


def main() -> None:
    terrain = load("terrain.json")
    buildings = load("buildings.json")
    if terrain is None or buildings is None:
        sys.exit("missing data/terrain.json or data/buildings.json - run the fetch steps first")

    snap = terrain["snap_m"]
    mt_pts = [(gx * snap, gy * snap) for gx, gy in terrain["mountain"]]
    wt_pts = [(gx * snap, gy * snap) for gx, gy in terrain["water"]]
    mt_idx, wt_idx = GridIndex(mt_pts), GridIndex(wt_pts)
    print(f"terrain: {len(mt_pts):,} mountain pts, {len(wt_pts):,} water pts")

    facilities = load("facilities.json") or {}
    fac_idx = {k: GridIndex([tuple(p) for p in v]) for k, v in facilities.items() if v}
    print("facilities: " + (", ".join(f"{k}={len(v)}" for k, v in facilities.items())
                            if fac_idx else "none - ancillary component neutral"))

    op = load("op.json") or {}
    print(f"occupation permits: {len(op):,} buildings")

    # Buildings Department age records: more occupation years, and an official
    # use classification instead of guessing from building names.
    bd_raw = load("bd_age.json") or {}
    bd_pts, bd_vals = [], []
    for key, v in bd_raw.items():
        try:
            lat, lon = (float(x) for x in key.split(","))
        except ValueError:
            continue
        bd_pts.append(to_plane(lon, lat))
        bd_vals.append(v)
    bd_idx = GridIndex(bd_pts, cell=120.0) if bd_pts else None
    print(f"BD age records: {len(bd_pts):,} points")

    BD_TOL = 35.0        # metres between a footprint centroid and a BD point
    BD_HOME = "住宅"      # 住宅/綜合用途 is the only class people live in

    # Public housing is excluded from RVD's completion years by policy and the
    # permit join never reaches it, so these blocks had no 元運 at all.
    housing = load("housing.json") or {}
    print(f"housing authority blocks: {len(housing):,}")

    import re as _re, unicodedata as _ud
    def hkey(s):
        s = _ud.normalize("NFKC", s or "").upper()
        return _re.sub(r"[\s·・,，.。\-–—()（）'’\"]", "", s)

    # CSDI's building layer carries no district, so assign it here.
    districts = load("districts.json")
    dsets = PolygonSet(districts) if districts else None
    print(f"districts: {len(districts) if districts else 0}")

    # Every building centroid, for the 明堂 openness test that picks 向 out of
    # the two candidates perpendicular to the footprint's long axis.
    plane = [to_plane(b["lon"], b["lat"]) for b in buildings]
    neighbours = GridIndex(plane, cell=200.0)

    rows = []
    for b, (x, y) in zip(buildings, plane):
        md, mi = mt_idx.nearest(x, y)
        wd, wi = wt_idx.nearest(x, y)
        if md is None or wd is None:
            continue

        mx, my = mt_pts[mi]
        wx, wy = wt_pts[wi]
        m16 = angle_to_dir16(math.degrees(math.atan2(my - y, mx - x)))
        w16 = angle_to_dir16(math.degrees(math.atan2(wy - y, wx - x)))

        pen = 0.0
        for idx in fac_idx.values():
            d, _ = idx.nearest(x, y)
            if d is not None:
                pen += ancillary_penalty(d)

        # ---- 理氣: 坐向 then the chart -------------------------------------
        facing = sit_m = face_m = pattern = period = now_code = None
        conf = 0.0
        axis, elong = b.get("axis"), b.get("elong")
        rec = op.get(b["id"] or "")
        op_year = rec["year"] if rec else None
        residential = rec["residential"] if rec else None

        # Fall back to the BD record for anything the permit join missed, and
        # always prefer its use class — it is an official classification, not
        # an inference from a name.
        # Housing Authority block names are exact, so they outrank a spatial
        # guess; they only ever fill a gap, never overwrite a permit.
        est = None
        if housing and op_year is None:
            for nm in (b.get("tc"), b.get("en")):
                h = housing.get(hkey(nm))
                if h:
                    op_year = h["year"]
                    residential = True
                    est = h
                    break

        if bd_idx:
            bd_d, bd_i = bd_idx.nearest(x, y)
            if bd_d is not None and bd_d <= BD_TOL:
                bv = bd_vals[bd_i]
                if op_year is None and bv.get("year"):
                    op_year = bv["year"]
                if bv.get("use") and est is None:
                    residential = BD_HOME in bv["use"]

        if axis is not None:
            a, c = facing_candidates(axis)
            oa = openness(x, y, a, neighbours)
            oc = openness(x, y, c, neighbours)
            facing = a if oa >= oc else c
            conf = max(0.0, min(1.0, ((elong or 1.0) - 1.0) / 1.5))

            if op_year and 1864 <= op_year <= 2043:
                ch = flyingstar.chart(op_year, facing)
                period = ch["period"]
                sit_m, face_m = ch["sitting"], ch["facing"]
                pattern = ch["pattern"]["code"]
                now_code = ch["now"]["code"]

        d = dsets.find(b["lon"], b["lat"]) if dsets else None

        rows.append({
            "district": d["tc"] if d else None,
            "b": b, "md": md, "wd": wd, "m16": m16, "w16": w16,
            "s8": mwds(dir8(m16), dir8(w16)), "s4": mwds(dir4(m16), dir4(w16)),
            "ancil_raw": -pen,
            "facing": round(facing, 1) if facing is not None else None,
            "conf": round(conf, 2),
            "op_year": op_year, "period": period,
            "sit_m": sit_m, "face_m": face_m, "pattern": pattern, "now": now_code,
            "estate": est,
            "residential": residential,
        })

    print(f"scored {len(rows):,} buildings")

    # Distance raw scores are NEGATED: closer to mountain/water scores higher,
    # which the reference layer confirms (0 m -> 74.7, 1555 m -> 1.0).
    p_s8 = percentile_scores([r["s8"] for r in rows])
    p_s4 = percentile_scores([r["s4"] for r in rows])
    p_md = percentile_scores([-r["md"] for r in rows])
    p_wd = percentile_scores([-r["wd"] for r in rows])
    p_an = percentile_scores([r["ancil_raw"] for r in rows])

    out = []
    for i, r in enumerate(rows):
        env = (W_DIR * (W_MWDS8 * p_s8[i] + W_MWDS4 * p_s4[i])
               + W_MTDIS * p_md[i] + W_WTDIS * p_wd[i])
        ancil = p_an[i] if fac_idx else 50.0
        traffic = 50.0            # placeholder until the traffic census layer is wired
        b = r["b"]
        out.append({
            "id": b["id"], "tc": b["tc"], "en": b["en"],
            "district": r["district"],
            "lon": b["lon"], "lat": b["lat"], "h": b["h"], "storeys": b["storeys"],
            "ring": b.get("ring"),
            "mt_d": round(r["md"]), "mt_dir": dir8(r["m16"]),
            "wt_d": round(r["wd"]), "wt_dir": dir8(r["w16"]),
            "mwds8": r["s8"], "mwds4": r["s4"],
            "env": round(env, 2), "traffic": round(traffic, 2), "ancil": round(ancil, 2),
            "total": round(W_ENV * env + W_TRAFFIC * traffic + W_ANCIL * ancil, 2),
            "facing": r["facing"], "conf": r["conf"],
            "op_year": r["op_year"], "period": r["period"],
            "sit_m": r["sit_m"], "face_m": r["face_m"], "pattern": r["pattern"],
            "now": r["now"], "residential": r["residential"],
            "estate": r.get("estate"),
        })

    out.sort(key=lambda r: -r["total"])
    (DATA / "scores.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

    tot = [r["total"] for r in out]
    mean = sum(tot) / len(tot)
    sd = math.sqrt(sum((t - mean) ** 2 for t in tot) / len(tot))
    print(f"\ngeographic score: min {min(tot):.1f}  mean {mean:.1f}  sd {sd:.1f}  max {max(tot):.1f}")

    import collections
    print(f"\n坐向 derived      : {sum(1 for r in out if r['facing'] is not None):,}")
    print(f"  high confidence : {sum(1 for r in out if r['conf'] >= 0.6):,}")
    print(f"元運 known        : {sum(1 for r in out if r['period']):,}")
    charted = [r for r in out if r["pattern"]]
    print(f"飛星盤 built      : {len(charted):,}")
    print("  本命格局（建成元運）:")
    for code, n in collections.Counter(r["pattern"] for r in charted).most_common():
        print(f"    {code:<10} {n:>7,}")
    print("  九運當下:")
    for code, n in collections.Counter(r["now"] for r in charted).most_common():
        print(f"    {code:<10} {n:>7,}")
    print(f"\n住宅              : {sum(1 for r in out if r['residential']):,}")
    print(f"明確非住宅        : {sum(1 for r in out if r['residential'] is False):,}")
    print(f"用途不詳          : {sum(1 for r in out if r['residential'] is None):,}")
    print(f"分區已判定        : {sum(1 for r in out if r['district']):,}")


if __name__ == "__main__":
    main()
