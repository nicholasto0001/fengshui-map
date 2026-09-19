"""Rebuild the mountain and water reference geometry.

Why this exists
---------------
Scoring a NEW building needs to know where the nearest mountain edge and the
nearest water edge are. The authoritative way to get those is to process the
Lands Department DTM plus the terrestrial habitat map -- a heavy, one-off GIS
job (see docs/fengshui-logic.md).

There is a much cheaper route that gives the same answer. The 2023 reference
layer already stores, for each of its 62,751 buildings, the DISTANCE and BEARING
to the nearest mountain and to the nearest water body. Project each building by
its own distance and bearing and you land exactly on the nearest point of the
mountain (or water) boundary. Do that 62,751 times and you have recovered a
dense point cloud tracing Hong Kong's mountain edges and coastline.

That point cloud is what new buildings get scored against.

Terrain and coastline barely move, so this runs rarely -- not daily.

Output: data/terrain.json
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import centroid_of, get_json, to_plane  # noqa: E402

FS = ("https://services4.arcgis.com/jim2f7B8UyqRDApI/arcgis/rest/services/"
      "HKFengShui_WFL1/FeatureServer/0")
PAGE = 2000
OUT = pathlib.Path(__file__).parent.parent / "data" / "terrain.json"

# Snap the recovered points to a grid so the file stays small; 25 m is well
# inside the precision the 100 m distance bands need.
SNAP = 25.0


def fetch_all() -> list[dict]:
    feats: list[dict] = []
    offset = 0
    while True:
        gj = get_json(f"{FS}/query", {
            "where": "1=1",
            "outFields": "FID,Mt_NearDIS,Mt_NearAng,Wt_NearDIS,Wt_NearAng",
            "returnGeometry": "true",
            "geometryPrecision": "6",
            "outSR": "4326",
            "orderByFields": "FID",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "geojson",
        })
        batch = gj.get("features") or []
        feats.extend(batch)
        print(f"  fetched {len(feats):,}", flush=True)
        if len(batch) < PAGE:
            break
        offset += PAGE
    return feats


def main() -> None:
    print("fetching reference layer ...")
    feats = fetch_all()
    print(f"got {len(feats):,} reference buildings")

    mountain: set[tuple[int, int]] = set()
    water: set[tuple[int, int]] = set()
    skipped = 0

    for f in feats:
        c = centroid_of(f.get("geometry") or {})
        if not c:
            skipped += 1
            continue
        x, y = to_plane(c[0], c[1])
        p = f["properties"]

        for dist_key, ang_key, sink in (
            ("Mt_NearDIS", "Mt_NearAng", mountain),
            ("Wt_NearDIS", "Wt_NearAng", water),
        ):
            d, a = p.get(dist_key), p.get(ang_key)
            if d is None or a is None or d <= 0:
                continue
            rad = math.radians(a)          # CCW from east
            px = x + d * math.cos(rad)
            py = y + d * math.sin(rad)
            sink.add((int(round(px / SNAP)), int(round(py / SNAP))))

    payload = {
        "note": "Mountain/water boundary points recovered from the 2023 reference "
                "layer's nearest-feature distance+bearing fields. Units: local "
                "equirectangular metres (see pipeline/common.py).",
        "snap_m": SNAP,
        "mountain": sorted(mountain),
        "water": sorted(water),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"mountain edge points: {len(mountain):,}")
    print(f"water edge points   : {len(water):,}")
    print(f"skipped (no geometry): {skipped:,}")
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
