"""Fetch the negative ancillary facilities used by the Feng Shui scoring.

The reference methodology penalises proximity to: bridges, filling stations,
fire stations, main roads / highways, hospitals and police stations.

Three of those have clean CSDI dataset IDs and are wired up here. Hospitals,
filling stations and the road network come from sources that need their own
handling (GeoInfo Map, Consumer Council, a line layer rather than points) --
those are listed below as TODO rather than silently dropped, because leaving
them out makes the ancillary component incomplete, not wrong.

Output: data/facilities.json  -> { "<name>": [[x, y], ...] }  local metres
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import HK_BOUNDS, centroid_of, get_json, to_plane  # noqa: E402

BASE = "https://portal.csdi.gov.hk/server/rest/services/common"
OUT = pathlib.Path(__file__).parent.parent / "data" / "facilities.json"
PAGE = 1000

DATASETS = {
    "bridge":        "hyd_rcd_1632360050986_38630",
    "fire_station":  "hkfsd_rcd_1634798867463_89696",
    "police_station": "police_rcd_1639562064290_95464",
    # TODO hospital        - GeoInfo Map searchNearby, HK80 coords, needs conversion
    # TODO filling_station - Consumer Council oil-price site, needs scraping
    # TODO main_road       - CSDI td_rcd_1638949160594_2844, line geometry:
    #                        sample vertices along each centreline
}


def fetch_points(dataset_id: str) -> list[list[float]]:
    pts: list[list[float]] = []
    offset = 0
    while True:
        gj = get_json(f"{BASE}/{dataset_id}/MapServer/0/query", {
            "where": "1=1",
            "geometry": ",".join(str(v) for v in HK_BOUNDS),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "",
            "returnGeometry": "true",
            "geometryPrecision": "6",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "geojson",
        })
        batch = gj.get("features") or []
        for f in batch:
            c = centroid_of(f.get("geometry") or {})
            if c:
                x, y = to_plane(c[0], c[1])
                pts.append([round(x, 1), round(y, 1)])
        if len(batch) < PAGE:
            break
        offset += PAGE
    return pts


def main() -> None:
    out: dict[str, list[list[float]]] = {}
    for name, ds in DATASETS.items():
        try:
            pts = fetch_points(ds)
            out[name] = pts
            print(f"  {name:16s} {len(pts):6,}")
        except Exception as exc:  # noqa: BLE001 - one bad dataset must not kill the run
            print(f"  {name:16s} FAILED: {exc}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
