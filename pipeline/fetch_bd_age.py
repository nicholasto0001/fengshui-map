"""Buildings Department age records — occupation dates and a real use class.

Two things the CSDI permit join cannot give us:

  * 14,116 more buildings with an occupation-permit year, taking 元運 coverage
    from 22.5% to 29.1% of the map. Without a year there is no 元運 and no
    flying star chart at all, so this is the single biggest lever on how much
    of the map can be read properly.

  * An official use classification (住宅/綜合用途 · 寫字樓/商業 · 工業 · 其他)
    for 63,356 buildings. That replaces guessing from names, which was never
    going to be reliable — it is how a theatre and a substation ended up
    graded as places to live.

Every row carries coordinates, so buildings are matched spatially rather than
by name. Against the permit join the two agree on 47,113 of 47,693 shared
buildings (98.8%), which is also a useful check that the join is sound.

Source: data.gov.hk, Buildings Department, free for commercial re-use.
Output: data/bd_age.json -> {"<lat>,<lon>": {"year": 1984, "use": "住宅/綜合用途"}}
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import SSL_CTX, UA  # noqa: E402

URL = "https://static.csdi.gov.hk/csdi-webpage/download/0e55c533715b5da3ae0ca6e6024e90b4/csv"
OUT = pathlib.Path(__file__).parent.parent / "data" / "bd_age.json"

# The file is named .csv but is served as a zip archive.
def load_rows() -> list[dict]:
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as r:
        blob = r.read()
    print(f"downloaded {len(blob)/1e6:.1f} MB")

    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            text = z.read(name).decode("utf-8-sig", errors="replace")
    else:
        text = blob.decode("utf-8-sig", errors="replace")

    return list(csv.DictReader(io.StringIO(text)))


def main() -> None:
    rows = load_rows()
    print(f"{len(rows):,} rows")

    out: dict[str, dict] = {}
    for r in rows:
        try:
            lat = round(float(r["LATITUDE"]), 5)
            lon = round(float(r["LONGITUDE"]), 5)
        except (TypeError, ValueError, KeyError):
            continue

        raw = (r.get("NSEARCH3_E") or "").strip()          # yyyy-mm-dd
        year = int(raw[:4]) if len(raw) >= 4 and raw[:4].isdigit() else None
        if year and not (1864 <= year <= 2043):
            year = None

        use = (r.get("NSEARCH5_C") or "").strip() or None
        if year is None and use is None:
            continue

        key = f"{lat},{lon}"
        prev = out.get(key)
        # Several records can share a point (blocks of one development). Keep
        # the earliest year, for the same reason as the permit join: later
        # entries are alterations, and 元運 follows original completion.
        if prev is None:
            out[key] = {"year": year, "use": use}
        else:
            if year and (prev["year"] is None or year < prev["year"]):
                prev["year"] = year
            if use and not prev["use"]:
                prev["use"] = use

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

    import collections
    uses = collections.Counter(v["use"] for v in out.values() if v["use"])
    print(f"\n{len(out):,} distinct points")
    print(f"  with a year : {sum(1 for v in out.values() if v['year']):,}")
    print("  use classes :")
    for u, n in uses.most_common():
        print(f"    {u:<22} {n:>7,}")
    print(f"\nwrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
