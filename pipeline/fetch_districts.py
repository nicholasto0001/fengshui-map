"""The 18 district boundaries.

The CSDI Building layer carries no district field, so buildings are assigned by
point-in-polygon against the Home Affairs Department boundary set. The 2023
reference layer had a district column only because its authors did this same
join themselves.

Output: data/districts.json -> [{"tc": ..., "en": ..., "rings": [[[lon,lat],...], ...]}]
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import get_json  # noqa: E402

REST = ("https://portal.csdi.gov.hk/server/rest/services/common/"
        "had_rcd_1634523272907_75218/MapServer/0")
OUT = pathlib.Path(__file__).parent.parent / "data" / "districts.json"

# Boundaries follow a crenellated coastline; 50 m of detail is ample for
# deciding which district a building sits in and keeps the file small.
SIMPLIFY_DEG = 0.0005


def main() -> None:
    meta = get_json(REST, {"f": "json"})
    names = [f["name"] for f in meta.get("fields", [])]
    print("fields:", ", ".join(names))

    gj = get_json(f"{REST}/query", {
        "where": "1=1", "outFields": "*", "returnGeometry": "true",
        "outSR": "4326", "geometryPrecision": "5",
        "maxAllowableOffset": str(SIMPLIFY_DEG), "f": "geojson",
    })

    out = []
    for f in gj.get("features") or []:
        p = f["properties"]
        tc = next((p[k] for k in p if "TC" in k.upper() and isinstance(p[k], str)), None)
        en = next((p[k] for k in p if "EN" in k.upper() and isinstance(p[k], str)), None)
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") or []
        rings = ([coords[0]] if geom.get("type") == "Polygon"
                 else [poly[0] for poly in coords if poly])
        if not rings:
            continue
        out.append({"tc": tc, "en": en,
                    "rings": [[[round(x, 5), round(y, 5)] for x, y in r] for r in rings]})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(f"\n{len(out)} districts -> {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    for d in out:
        pts = sum(len(r) for r in d["rings"])
        print(f"  {str(d['tc']):<8} {str(d['en']):<24} {len(d['rings'])} ring(s), {pts} pts")


if __name__ == "__main__":
    main()
