"""坐向 — deriving a building's facing direction from its footprint.

Xuan Kong flying star needs 向 (facing) to within a 15° sector. A surveyor
gets that with a compass at the door. From open data we only have the footprint
polygon, so this module does the next best thing:

  1. minimum-area bounding rectangle of the footprint (rotating calipers)
  2. the two candidate facings are perpendicular to the rectangle's LONG axis
     -- a slab block faces broadside, not end-on
  3. pick between the two by which side has more open space in front of it
     (the 明堂 principle: 向 opens onto the bright hall, 坐 backs onto support)

Accuracy is roughly +/-10-20 degrees, so a building near a sector boundary can
land in the wrong one of the 24 mountains. `confidence` reports that honestly:
a long thin slab is reliable, a near-square tower is a coin flip.

Self-test: `python3 pipeline/orientation.py`
"""
from __future__ import annotations

import math

Point = tuple[float, float]


def convex_hull(pts: list[Point]) -> list[Point]:
    """Andrew's monotone chain. Returns CCW hull without the duplicated endpoint."""
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def min_area_rect(pts: list[Point]) -> tuple[float, float, float]:
    """Minimum-area bounding rectangle.

    Returns (long_axis_bearing, long_side, short_side) where the bearing is
    compass degrees (0 = north, clockwise).
    """
    hull = convex_hull(pts)
    if len(hull) < 3:
        return 0.0, 0.0, 0.0

    best = None
    n = len(hull)
    # The optimal rectangle shares an edge with the hull, so only hull edge
    # angles need testing.
    for i in range(n):
        x1, y1 = hull[i]
        x2, y2 = hull[(i + 1) % n]
        theta = math.atan2(y2 - y1, x2 - x1)
        c, s = math.cos(-theta), math.sin(-theta)
        xs = [p[0] * c - p[1] * s for p in hull]
        ys = [p[0] * s + p[1] * c for p in hull]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        area = w * h
        if best is None or area < best[0]:
            best = (area, theta, w, h)

    _, theta, w, h = best
    if w >= h:
        long_side, short_side = w, h
        long_dir = theta                      # along the tested edge
    else:
        long_side, short_side = h, w
        long_dir = theta + math.pi / 2

    # math angle (CCW from +x/east) -> compass bearing (CW from north)
    bearing = (90.0 - math.degrees(long_dir)) % 180.0
    return bearing, long_side, short_side


def facing_candidates(long_axis_bearing: float) -> tuple[float, float]:
    """The two directions perpendicular to the long axis."""
    a = (long_axis_bearing + 90.0) % 360.0
    return a, (a + 180.0) % 360.0


def openness(cx: float, cy: float, bearing: float, neighbours, probe_m: float = 120.0) -> float:
    """How clear is the view this way? Distance to the nearest building centroid
    inside a cone in that direction, capped at `probe_m`. Bigger is more open."""
    rad = math.radians(90.0 - bearing)        # compass -> math
    px = cx + probe_m * math.cos(rad)
    py = cy + probe_m * math.sin(rad)
    d, _ = neighbours.nearest(px, py)
    return probe_m if d is None else min(d, probe_m)


def derive(footprint: list[Point], neighbours=None) -> dict:
    """Full derivation for one building footprint (local metres)."""
    bearing, long_side, short_side = min_area_rect(footprint)
    if long_side == 0:
        return {"facing": None, "confidence": 0.0, "reason": "degenerate footprint"}

    a, b = facing_candidates(bearing)
    elongation = long_side / short_side if short_side else 1.0

    if neighbours is None:
        facing, reason = a, "no neighbour data - arbitrary side of the long axis"
    else:
        cx = sum(p[0] for p in footprint) / len(footprint)
        cy = sum(p[1] for p in footprint) / len(footprint)
        oa, ob = openness(cx, cy, a, neighbours), openness(cx, cy, b, neighbours)
        facing, reason = (a, "faces the more open side") if oa >= ob else (b, "faces the more open side")

    # A square footprint gives no meaningful long axis; say so rather than
    # dressing a coin flip up as a measurement.
    confidence = max(0.0, min(1.0, (elongation - 1.0) / 1.5))

    return {
        "facing": round(facing, 1),
        "sitting": round((facing + 180.0) % 360.0, 1),
        "long_axis": round(bearing, 1),
        "elongation": round(elongation, 2),
        "confidence": round(confidence, 2),
        "reason": reason,
    }


def _selftest() -> None:
    # A slab running east-west: long axis 90 deg, so it faces north or south.
    slab_ew = [(0, 0), (60, 0), (60, 12), (0, 12)]
    r = min_area_rect(slab_ew)
    print(f"E-W slab  long axis {r[0]:5.1f} deg  ({r[1]:.0f} x {r[2]:.0f} m)")
    assert abs(r[0] - 90.0) < 0.1, r
    a, b = facing_candidates(r[0])
    assert {round(a), round(b)} == {0, 180}, (a, b)

    # A slab running north-south: long axis 0 deg, faces east or west.
    slab_ns = [(0, 0), (12, 0), (12, 60), (0, 60)]
    r = min_area_rect(slab_ns)
    print(f"N-S slab  long axis {r[0]:5.1f} deg  ({r[1]:.0f} x {r[2]:.0f} m)")
    assert abs(r[0] % 180) < 0.1 or abs(r[0] % 180 - 180) < 0.1, r
    a, b = facing_candidates(r[0])
    assert {round(a), round(b)} == {90, 270}, (a, b)

    # 45-degree slab
    d = [(0, 0), (40, 40), (37, 43), (-3, 3)]
    r = min_area_rect(d)
    print(f"NE slab   long axis {r[0]:5.1f} deg  ({r[1]:.0f} x {r[2]:.0f} m)")
    assert abs(r[0] - 45.0) < 1.0, r

    # A square tower: no reliable long axis, confidence must be ~0
    square = [(0, 0), (30, 0), (30, 30), (0, 30)]
    res = derive(square)
    print(f"square tower -> confidence {res['confidence']}  (elongation {res['elongation']})")
    assert res["confidence"] == 0.0, res

    res = derive(slab_ew)
    print(f"E-W slab     -> facing {res['facing']}  confidence {res['confidence']}")
    assert res["confidence"] == 1.0, res

    print("\nall orientation tests passed")


if __name__ == "__main__":
    _selftest()
