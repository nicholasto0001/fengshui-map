"""Compute Period 9 Feng Shui scores for the current building stock.

Reimplements the 2023 reference methodology from first principles, against
live CSDI data, so new developments get scored. Every constant here was
reverse-engineered from the published layer and verified against it -- see
docs/fengshui-logic.md for the derivation and the verification table.

Inputs :  data/terrain.json     (mountain + water boundary points)
          data/buildings.json   (live CSDI building stock)
          data/facilities.json  (optional; negative ancillary features)
Output :  data/scores.json
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import (GridIndex, angle_to_dir16, dir4, dir8, mwds,  # noqa: E402
                    percentile_scores, to_plane)

DATA = pathlib.Path(__file__).parent.parent / "data"

# Weights, straight from the reference methodology diagram (docs/weighting-flow.png)
W_MWDS8, W_MWDS4 = 0.75, 0.25
W_DIR, W_MTDIS, W_WTDIS = 0.6, 0.2, 0.2
W_ENV, W_TRAFFIC, W_ANCIL = 0.8, 0.05, 0.15

# Ancillary penalty: 10 points within 100 m, decaying by 1 per extra 100 m,
# zero beyond 1000 m. Summed over every negative feature type, then negated.
ANCIL_MAX_M = 1000.0


def load(name: str):
    p = DATA / name
    if not p.exists():
        return None
    return json.loads(p.read_text())


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
    print(f"terrain: {len(mt_pts):,} mountain pts, {len(wt_pts):,} water pts")
    mt_idx, wt_idx = GridIndex(mt_pts), GridIndex(wt_pts)

    facilities = load("facilities.json") or {}
    fac_idx = {k: GridIndex([tuple(p) for p in v]) for k, v in facilities.items() if v}
    if fac_idx:
        print(f"facilities: {', '.join(f'{k}={len(v)}' for k, v in facilities.items())}")
    else:
        print("facilities: none available - ancillary component will be neutral")

    rows = []
    for b in buildings:
        x, y = to_plane(b["lon"], b["lat"])

        md, mi = mt_idx.nearest(x, y)
        wd, wi = wt_idx.nearest(x, y)
        if md is None or wd is None:
            continue

        mx, my = mt_pts[mi]
        wx, wy = wt_pts[wi]
        m_ang = math.degrees(math.atan2(my - y, mx - x))
        w_ang = math.degrees(math.atan2(wy - y, wx - x))
        m16, w16 = angle_to_dir16(m_ang), angle_to_dir16(w_ang)

        s8 = mwds(dir8(m16), dir8(w16))
        s4 = mwds(dir4(m16), dir4(w16))

        pen = 0.0
        for idx in fac_idx.values():
            d, _ = idx.nearest(x, y)
            if d is not None:
                pen += ancillary_penalty(d)

        rows.append({
            "b": b, "md": md, "wd": wd,
            "m16": m16, "w16": w16, "s8": s8, "s4": s4,
            "ancil_raw": -pen,
        })

    print(f"scored {len(rows):,} buildings")

    # Normalise. Distance raw scores are NEGATED: closer to mountain/water is
    # better, which the reference layer confirms (distance 0 -> 74.7, 1555 m -> 1.0).
    p_s8 = percentile_scores([r["s8"] for r in rows])
    p_s4 = percentile_scores([r["s4"] for r in rows])
    p_md = percentile_scores([-r["md"] for r in rows])
    p_wd = percentile_scores([-r["wd"] for r in rows])
    p_an = percentile_scores([r["ancil_raw"] for r in rows])

    out = []
    for i, r in enumerate(rows):
        direction = W_MWDS8 * p_s8[i] + W_MWDS4 * p_s4[i]
        env = W_DIR * direction + W_MTDIS * p_md[i] + W_WTDIS * p_wd[i]
        ancil = p_an[i] if fac_idx else 50.0
        traffic = 50.0            # placeholder until the traffic census layer is wired
        total = W_ENV * env + W_TRAFFIC * traffic + W_ANCIL * ancil

        b = r["b"]
        out.append({
            "id": b["id"], "tc": b["tc"], "en": b["en"],
            "lon": b["lon"], "lat": b["lat"], "h": b["h"], "storeys": b["storeys"],
            "mt_d": round(r["md"]), "mt_dir": dir8(r["m16"]),
            "wt_d": round(r["wd"]), "wt_dir": dir8(r["w16"]),
            "mwds8": r["s8"], "mwds4": r["s4"],
            "env": round(env, 2), "traffic": round(traffic, 2),
            "ancil": round(ancil, 2), "total": round(total, 2),
        })

    out.sort(key=lambda r: -r["total"])
    (DATA / "scores.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

    tot = [r["total"] for r in out]
    mean = sum(tot) / len(tot)
    sd = math.sqrt(sum((t - mean) ** 2 for t in tot) / len(tot))
    print(f"min {min(tot):.1f}  mean {mean:.1f}  sd {sd:.1f}  max {max(tot):.1f}")
    print("top 5:")
    for r in out[:5]:
        print(f"  {r['total']:5.1f}  {r['tc'] or r['en'] or '(unnamed)'}  "
              f"[山 {r['mt_dir']} {r['mt_d']}m / 水 {r['wt_dir']} {r['wt_d']}m, MWDS-8 {r['mwds8']}]")


if __name__ == "__main__":
    main()
