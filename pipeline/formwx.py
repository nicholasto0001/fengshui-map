"""逐幢樓嘅形 — the two element readings that belong to a building itself.

撼龍經 assigns the five elements by form: 金圓、木直、水曲、火尖、土方. Of those,
three can be read off one building on its own:

  木 / 土   how tall it is, and how tall against how wide its base is. These are
            one number from two ends -- 直 and 方 are opposites -- so the file
            carries `mu`, and 土 is 100 - mu.
  水        how close it stands to the water's edge, as `wa`.

火 is missing on purpose. 尖 means standing clear of what is around you, so it
is a fact about the block, not about the building; it is aggregated per district
in make_elements.py and the page reads it from there. 金 is missing because
roundness needs an outline and the median footprint here has four vertices.

Both numbers are positions in the territory's own distribution, because "22
metres tall" says nothing until it is placed against the other 53,633 homes.
The ladder is rebuilt from the data each run rather than pinned to constants,
so it follows the stock as it changes.

Used by build_tiles.py (which writes mu/wa into the tiles and the search index)
and by make_elements.py (which aggregates the same measurements per district).

Self-test: `python3 pipeline/formwx.py`
"""
from __future__ import annotations

import math

M_PER_DEG_LAT = 110540.0
STEPS = 20          # ladder rungs: one per 5%


def m_per_deg_lon(lat: float) -> float:
    return 111320.0 * math.cos(math.radians(lat))


def ring_area_perimeter(ring: list) -> tuple[float, float]:
    """Shoelace area (m²) and perimeter (m) of a lon/lat ring."""
    if not ring or len(ring) < 4:
        return 0.0, 0.0
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx = m_per_deg_lon(lat0)
    pts = [(p[0] * kx, p[1] * M_PER_DEG_LAT) for p in ring]
    a = per = 0.0
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        a += x1 * y2 - x2 * y1
        per += math.hypot(x2 - x1, y2 - y1)
    return abs(a) / 2, per


def slenderness(row: dict) -> float | None:
    """Height over the width of the base. A tower is slender; a shed is not."""
    h = row.get("h") or 0.0
    if h <= 0:
        return None
    area, _ = ring_area_perimeter(row.get("ring"))
    return h / math.sqrt(area) if area > 0 else None


def ladders(homes: list[dict]) -> dict[str, list[float]]:
    """Where the whole residential stock sits on each measure, in 5% steps."""
    hs, sl, wt = [], [], []
    for r in homes:
        h = r.get("h") or 0.0
        if h > 0:
            hs.append(h)
            s = slenderness(r)
            if s is not None:
                sl.append(s)
        if r.get("wt_d") is not None:
            wt.append(r["wt_d"])

    def rungs(vals: list[float]) -> list[float]:
        v = sorted(vals)
        if not v:
            return [0.0] * (STEPS + 1)
        return [v[min(len(v) - 1, len(v) * i // STEPS)] for i in range(STEPS + 1)]

    return {"h": rungs(hs), "slender": rungs(sl), "wt_d": rungs(wt)}


def place(ladder: list[float], v: float | None) -> float | None:
    """0-100 position on a ladder, straight-line between the rungs."""
    if v is None or not ladder:
        return None
    if v <= ladder[0]:
        return 0.0
    for i in range(1, len(ladder)):
        if v <= ladder[i]:
            span = ladder[i] - ladder[i - 1]
            frac = (v - ladder[i - 1]) / span if span else 0.0
            return (i - 1 + frac) * (100.0 / STEPS)
    return 100.0


def profile(row: dict, lad: dict[str, list[float]]) -> tuple[int | None, int | None]:
    """(mu, wa) for one building. Either is None when it cannot be measured.

    None matters: a building with no recorded height is not an average one, and
    scoring it 50 would quietly tell somebody it half suits them.
    """
    tall = place(lad["h"], row.get("h") if (row.get("h") or 0) > 0 else None)
    slim = place(lad["slender"], slenderness(row))
    if tall is None:
        mu = None
    else:
        mu = round(tall if slim is None else (tall + slim) / 2)

    wt = place(lad["wt_d"], row.get("wt_d"))
    wa = None if wt is None else round(100 - wt)
    return mu, wa


if __name__ == "__main__":
    import json
    import pathlib

    rows = json.loads((pathlib.Path(__file__).parent.parent
                       / "data" / "scores.json").read_text("utf8"))
    homes = [r for r in rows if r.get("residential")]
    lad = ladders(homes)
    print(f"{len(homes):,} 幢住宅")
    for k in ("h", "slender", "wt_d"):
        q = lad[k]
        print(f"  {k:<8} 最低 {q[0]:>8.1f} · 中位 {q[10]:>8.1f} · 最高 {q[20]:>9.1f}")

    got = [profile(r, lad) for r in homes]
    mus = [m for m, _ in got if m is not None]
    was = [w for _, w in got if w is not None]
    print(f"\n木／土 計到 {len(mus):,}（{100*len(mus)/len(homes):.1f}%）"
          f"　水 計到 {len(was):,}（{100*len(was)/len(homes):.1f}%）")

    # 一把尺如果大部分樓都排喺同一格，咁佢就分唔到樓，等於冇用。
    from collections import Counter
    for name, vals in (("mu", mus), ("wa", was)):
        c = Counter(v // 10 for v in vals)
        bars = " ".join(f"{k*10}:{100*c[k]/len(vals):.0f}%" for k in sorted(c))
        print(f"  {name} 分佈  {bars}")

    tall = max(homes, key=lambda r: r.get("h") or 0)
    print(f"\n最高嗰幢 {tall.get('tc')} {tall.get('h')}m -> mu={profile(tall, lad)[0]}")
