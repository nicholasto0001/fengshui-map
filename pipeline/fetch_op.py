"""Occupation permits — the real completion year, and a usable residential filter.

`Building.DateCreate` is when the record was digitised, not when the building
went up: The Park Lane (1970s) carries 2005-04-30. Flying star needs the actual
完成年份 to pick the 元運, so it has to come from the occupation permit.

The join runs across three CSDI tables:

    Building.BuildingCSUID
      -> BuildingRelateOPStructure -> BuildingStructureID
      -> OPStructure               -> OPNo  (+ OPBuildingType)
      -> OP                        -> OPDate

`OPBuildingType` is free text, but it names what the permit was issued for
("Apartment", "Residence", "Hotel", "Columbarium"...), which is the closest
thing in open data to a residential flag. The 2023 layer had no such filter and
leaked substations and car parks into its results.

Coverage is partial by nature: roughly 53k of the 213k active towers have an OP
record. Buildings without one keep their geographic score and are marked
元運不詳 rather than being given a fabricated chart.

Output: data/op.json  -> { "<BuildingCSUID>": {"year": 1998, "type": "...", "residential": true} }
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import get_json  # noqa: E402

REST = ("https://portal.csdi.gov.hk/server/rest/services/common/"
        "landsd_rcd_1637211194312_35158/MapServer")
PAGE = 2000
OUT = pathlib.Path(__file__).parent.parent / "data" / "op.json"

# Keyword classification over OPBuildingType.
#
# The text describes everything the permit covered, main use first, so a genuine
# apartment block routinely reads "Apartment Refuse storage chamber" or
# "Apartment Transformer room (Phase 2B)". Screening on those ancillary words
# first throws away most of the housing stock, so the order is:
#   1. a hard exclusion (the 陰宅 cases) always wins
#   2. otherwise any residential word makes it residential
#   3. otherwise not residential
HARD_EXCLUDE = ("columbarium", "crematorium", "funeral", "cemetery", "mortuary")

# Bare "house" is not usable - guard house, pump house, club house all match.
RESIDENTIAL = ("apartment", "residence", "residential", "domestic",
               "single family house", "town house", "tenement",
               "quarters", "hostel", "dwelling", "flat")


def classify(op_type: str | None) -> bool | None:
    if not op_type:
        return None
    t = op_type.lower()
    if any(k in t for k in HARD_EXCLUDE):
        return False
    return any(k in t for k in RESIDENTIAL)


def fetch_table(layer: int, fields: str, where: str = "1=1") -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        d = get_json(f"{REST}/{layer}/query", {
            "where": where, "outFields": fields, "returnGeometry": "false",
            "orderByFields": "OBJECTID", "resultOffset": offset,
            "resultRecordCount": PAGE, "f": "json",
        })
        batch = [f["attributes"] for f in (d.get("features") or [])]
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    print(f"  layer {layer}: {len(rows):,} rows", flush=True)
    return rows


def merge_works_history(out: dict) -> None:
    """Fill gaps from BuildingWorksHistory.

    That table carries its own "Completion Date" and "OP Date" rows for
    buildings the permit join never reaches. Only the EARLIEST is used, for the
    same reason as above — its later rows are renovations, which is why a naive
    read of it disagreed with the permit join on 97.8% of shared buildings.

    It is a fallback only: where a permit exists, the permit wins.
    """
    rows = []
    offset = 0
    while True:
        d = get_json(f"{REST}/1000/query", {
            "where": "WorksType IN ('Completion Date','OP Date')",
            "outFields": "BuildingCSUID,WorksDate",
            "returnGeometry": "false",
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "json",
        })
        batch = [f["attributes"] for f in (d.get("features") or [])]
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE

    added = 0
    for r in rows:
        cs, raw = r.get("BuildingCSUID"), r.get("WorksDate")
        if not cs or cs in out or not raw:
            continue
        parts = str(raw).strip().split("/")          # dd/mm/yyyy in this table
        if len(parts) != 3 or len(parts[2]) != 4:
            continue
        try:
            year = int(parts[2])
        except ValueError:
            continue
        if not (1864 <= year <= 2043):
            continue
        prev = out.get(cs)
        if prev is None:
            out[cs] = {"year": year, "type": None, "residential": None,
                       "block": None, "src": "works"}
            added += 1
        elif year < prev["year"]:
            prev["year"] = year

    print(f"  works history filled {added:,} more buildings")


def main() -> None:
    relate = fetch_table(1002, "BuildingCSUID,BuildingStructureID")
    structure = fetch_table(1003, "BuildingStructureID,OPNo,OPBuildingType,OPBlockType")
    permits = fetch_table(1004, "OPNo,OPDate,DomesticGFA")

    op_by_no = {r["OPNo"]: r for r in permits if r.get("OPNo")}
    struct_by_id = {r["BuildingStructureID"]: r for r in structure if r.get("BuildingStructureID")}

    out: dict[str, dict] = {}
    for r in relate:
        csuid, sid = r.get("BuildingCSUID"), r.get("BuildingStructureID")
        if not csuid or sid not in struct_by_id:
            continue
        st = struct_by_id[sid]
        permit = op_by_no.get(st.get("OPNo"))
        if not permit or not permit.get("OPDate"):
            continue
        year = datetime.datetime.fromtimestamp(permit["OPDate"] / 1000, datetime.UTC).year

        op_type = st.get("OPBuildingType")
        rec = {
            "year": year,
            "type": (op_type or "")[:120] or None,
            "residential": classify(op_type),
            "block": st.get("OPBlockType"),
        }
        # 元運 is set by when the building was COMPLETED, so where a building
        # carries several permits the EARLIEST is the original structure; later
        # ones are alterations. Taking the latest silently aged 樂生蓮社 from
        # 1969 to 2019 — a fifty-year error that would have put it in the wrong
        # 運 entirely.
        #
        # Deliberately no 換天心 handling: whether a major renovation resets the
        # period is genuinely disputed between schools, and there is no
        # renovation data here to act on either way.
        prev = out.get(csuid)
        if prev is None or year < prev["year"]:
            out[csuid] = rec

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

    merge_works_history(out)

    res = sum(1 for v in out.values() if v["residential"])
    years = sorted(v["year"] for v in out.values())
    print(f"\n{len(out):,} buildings with an occupation permit")
    print(f"  residential by OP type : {res:,}")
    print(f"  OP year range          : {years[0]} – {years[-1]}")

    import collections
    periods = collections.Counter()
    for v in out.values():
        y = v["year"]
        periods["九運 2024-2043" if y >= 2024 else
                "八運 2004-2023" if y >= 2004 else
                "七運 1984-2003" if y >= 1984 else
                "六運 1964-1983" if y >= 1964 else
                "五運或更早" ] += 1
    print("  by 元運:")
    for k in ("五運或更早", "六運 1964-1983", "七運 1984-2003", "八運 2004-2023", "九運 2024-2043"):
        print(f"    {k:<18} {periods[k]:>7,}")


if __name__ == "__main__":
    main()
