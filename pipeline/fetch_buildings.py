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
from common import centroid_of, get_json  # noqa: E402

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
            "orderByFields": "BuildingCSUID",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "geojson",
        })
        batch = gj.get("features") or []
        for f in batch:
            c = centroid_of(f.get("geometry") or {})
            if not c:
                continue
            p = f["properties"]
            top, base = p.get("TopHeight"), p.get("BaseHeight")
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
