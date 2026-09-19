"""Pull the current building stock from the CSDI portal.

This is the step that picks up new developments. CSDI is the Government's
live spatial data platform (Lands Department dataset
`landsd_rcd_1637211194312_35158`), refreshed continuously -- as of this
writing it carries ~342k buildings with date stamps into 2026, against the
62,751 frozen into the 2023 Feng Shui layer.

Runs daily. No API key.

Output: data/buildings.json
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import centroid_of, get_json, to_plane  # noqa: E402
from orientation import min_area_rect  # noqa: E402

REST = ("https://portal.csdi.gov.hk/server/rest/services/common/"
        "landsd_rcd_1637211194312_35158/MapServer/0")
PAGE = 1000
OUT = pathlib.Path(__file__).parent.parent / "data" / "buildings.json"

# Residential-ish filter. `Tower` excludes podiums, carports and plant rooms;
# `Active` excludes demolished stock. This is deliberately looser than a true
# residential filter -- see docs/fengshui-logic.md for why the reference layer's
# tighter filter still leaked substations and car parks.
WHERE = "Status = 'Active' AND BuildingBlockType = 'Tower'"

FIELDS = ("BuildingCSUID,BuildingNameTC,BuildingNameEN,TopHeight,BaseHeight,"
          "Storeys,StoreysInBasement,DateCreate,DateStamp")


def outer_ring(geometry: dict) -> list[tuple[float, float]] | None:
    """Largest outer ring of a (Multi)Polygon, as (lon, lat) pairs."""
    t, coords = geometry.get("type"), geometry.get("coordinates")
    if not coords:
        return None
    rings = [coords[0]] if t == "Polygon" else [poly[0] for poly in coords if poly]
    if not rings:
        return None
    best = max(rings, key=len)
    return [(pt[0], pt[1]) for pt in best]


def main() -> None:
    out: list[dict] = []
    offset = 0
    while True:
        gj = get_json(f"{REST}/query", {
            "where": WHERE,
            "outFields": FIELDS,
            "returnGeometry": "true",
            "geometryPrecision": "6",
            "outSR": "4326",
            # Simplify server-side: ~2 m of detail is plenty for both the map
            # and the long-axis fit, and it roughly halves the payload.
            "maxAllowableOffset": "0.00002",
            "orderByFields": "BuildingCSUID",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "geojson",
        })
        batch = gj.get("features") or []
        for f in batch:
            geom = f.get("geometry") or {}
            c = centroid_of(geom)
            if not c:
                continue
            p = f["properties"]
            top, base = p.get("TopHeight"), p.get("BaseHeight")

            ring = outer_ring(geom)
            axis = elong = None
            if ring and len(ring) >= 3:
                plane = [to_plane(x, y) for x, y in ring]
                bearing, long_side, short_side = min_area_rect(plane)
                if long_side:
                    axis = round(bearing, 1)
                    elong = round(long_side / short_side, 2) if short_side else None

            out.append({
                "id": p.get("BuildingCSUID"),
                "tc": p.get("BuildingNameTC"),
                "en": p.get("BuildingNameEN"),
                "lon": round(c[0], 6),
                "lat": round(c[1], 6),
                # real building height, not the mPD elevation the 2023 layer exposed
                "h": round(top - base, 1) if (top is not None and base is not None) else None,
                "storeys": p.get("Storeys"),
                "created": p.get("DateCreate"),
                # footprint long axis + how slab-like it is; 坐向 is derived from
                # these in score.py, where neighbouring buildings are indexed
                "axis": axis,
                "elong": elong,
                "ring": [[round(x, 5), round(y, 5)] for x, y in ring] if ring else None,
            })
        print(f"  {len(out):,}", flush=True)
        if len(batch) < PAGE:
            break
        offset += PAGE

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {len(out):,} buildings -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
