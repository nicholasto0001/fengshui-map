"""Shared helpers for the Feng Shui pipeline.

Pure standard library on purpose: the whole pipeline must run on a bare
`python3` (GitHub Actions, any Mac) with nothing to install.
"""
from __future__ import annotations

import json
import math
import ssl
import time
import urllib.parse
import urllib.request

UA = "hk-fengshui-map/1.0 (+https://github.com/)"


def _ssl_context() -> ssl.SSLContext:
    """python.org builds on macOS ship without a root store; certifi fills the gap."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CTX = _ssl_context()

# Local equirectangular plane centred on Hong Kong.
# Good to ~0.1% over the territory - far below the precision the Feng Shui
# distance bands (100 m steps) actually need.
LAT0 = 22.36
M_PER_DEG_LAT = 110_900.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))  # ~103,050 m

HK_BOUNDS = (113.78, 22.10, 114.47, 22.62)  # west, south, east, north


def to_plane(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 -> local metres (x east, y north)."""
    return lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT


def to_wgs(x: float, y: float) -> tuple[float, float]:
    return x / M_PER_DEG_LON, y / M_PER_DEG_LAT


def get_json(url: str, params: dict, retries: int = 4, pause: float = 1.5):
    """GET with retries. ArcGIS occasionally 500s under load."""
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - want any transport failure retried
            last = exc
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"request failed after {retries} tries: {full[:180]} :: {last}")


def centroid_of(geometry: dict) -> tuple[float, float] | None:
    """Mean vertex of any GeoJSON geometry. Good enough for a building footprint."""
    pts: list[list[float]] = []

    def walk(a):
        if not a:
            return
        if isinstance(a[0], (int, float)):
            pts.append(a)
        else:
            for sub in a:
                walk(sub)

    walk(geometry.get("coordinates"))
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


# --------------------------------------------------------------------------
# Direction handling
#
# The reference layer uses the ArcGIS `Near` convention: degrees measured
# counter-clockwise from due EAST, in the range -180..180.
#   East = 0, North = 90, South = -90, West = 180
# Verified empirically against the published layer.
# --------------------------------------------------------------------------
DIRS_16 = ["E", "ENE", "NE", "NNE", "N", "NNW", "NW", "WNW",
           "W", "WSW", "SW", "SSW", "S", "SSE", "SE", "ESE"]

# 16-point -> 8-point: three-letter names collapse to their ordinal
TO_8 = {"ENE": "NE", "NNE": "NE", "NNW": "NW", "WNW": "NW",
        "WSW": "SW", "SSW": "SW", "SSE": "SE", "ESE": "SE"}
# 16-point -> 4-point: keep the cardinal embedded in the name
TO_4 = {"ENE": "E", "ESE": "E", "NNE": "N", "NNW": "N",
        "WNW": "W", "WSW": "W", "SSE": "S", "SSW": "S"}


def angle_to_dir16(angle_deg: float) -> str:
    return DIRS_16[int(round((angle_deg % 360) / 22.5)) % 16]


def dir8(d16: str) -> str | None:
    if d16 in ("N", "NE", "E", "SE", "S", "SW", "W", "NW"):
        return d16
    return TO_8.get(d16)


def dir4(d16: str) -> str | None:
    if d16 in ("N", "E", "S", "W"):
        return d16
    return TO_4.get(d16)


# --------------------------------------------------------------------------
# Period 9 (2024-2043) Luoshu flying-star mountain/water scoring table.
# Mountain must sit in the star's palace, water in the opposite palace.
# Star auspiciousness in Period 9 runs 9 > 1 > 2 > 3 > 4 > 5 > 6 > 7 > 8.
# Any other mountain/water combination scores 0.
# --------------------------------------------------------------------------
MWDS_TABLE = {
    ("S", "N"): 9,
    ("N", "S"): 8,
    ("SW", "NE"): 7,
    ("E", "W"): 6,
    ("SE", "NW"): 5,
    # ("M", "M"): 4  - centre palace, not reachable from a nearest-feature bearing
    ("NW", "SE"): 3,
    ("W", "E"): 2,
    ("NE", "SW"): 1,
}


def mwds(mountain_dir: str | None, water_dir: str | None) -> int:
    if not mountain_dir or not water_dir:
        return 0
    return MWDS_TABLE.get((mountain_dir, water_dir), 0)


# --------------------------------------------------------------------------
# Uniform grid spatial index - replaces a KD-tree with zero dependencies.
# --------------------------------------------------------------------------
class GridIndex:
    def __init__(self, points: list[tuple[float, float]], cell: float = 400.0):
        self.cell = cell
        self.points = points
        self.buckets: dict[tuple[int, int], list[int]] = {}
        for i, (x, y) in enumerate(points):
            self.buckets.setdefault((int(x // cell), int(y // cell)), []).append(i)

    def nearest(self, x: float, y: float, max_rings: int = 60):
        """Return (distance, index) of the closest indexed point, or (None, None)."""
        cx, cy = int(x // self.cell), int(y // self.cell)
        best_d2, best_i = float("inf"), None
        ring = 0
        while ring <= max_rings:
            found_any = False
            for gx in range(cx - ring, cx + ring + 1):
                for gy in range(cy - ring, cy + ring + 1):
                    # only the shell of the ring after the first pass
                    if ring and max(abs(gx - cx), abs(gy - cy)) != ring:
                        continue
                    for i in self.buckets.get((gx, gy), ()):
                        px, py = self.points[i]
                        d2 = (px - x) ** 2 + (py - y) ** 2
                        if d2 < best_d2:
                            best_d2, best_i = d2, i
                            found_any = True
            # once something is found, one more ring guarantees correctness
            if best_i is not None and not found_any:
                break
            if best_i is not None and ring >= 1 and math.sqrt(best_d2) <= ring * self.cell:
                break
            ring += 1
        if best_i is None:
            return None, None
        return math.sqrt(best_d2), best_i


# --------------------------------------------------------------------------
# Normalisation: z-score -> standard normal CDF -> 0-100 percentile,
# exactly as the reference methodology specifies.
# --------------------------------------------------------------------------
def percentile_scores(values: list[float]) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = math.sqrt(var)
    if sd == 0:
        return [50.0] * n
    return [100.0 * 0.5 * (1.0 + math.erf(((v - mean) / sd) / math.sqrt(2))) for v in values]
