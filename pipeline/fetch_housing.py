"""Housing Authority estates — the completion years nothing else carries.

The Rating and Valuation Department states outright that public rental housing
is excluded from its completion years, and the occupation-permit join does not
reach it either. So the blocks where roughly a third of Hong Kong lives had no
元運 and no flying star chart at all — not because the record is missing, but
because it is published somewhere else.

The Housing Authority publishes it itself, per estate, with the name of every
block. Matching on BLOCK names rather than estate names is what makes this
work: a block is called 德璋樓, not 德朗邨, so estate-name matching found 477
buildings where block-name matching finds 2,499 — 88% of every block in the
index.

It also carries what a buyer actually asks about: how many blocks, how many
flats, who manages it.

Source: data.gov.hk, Hong Kong Housing Authority.
Output: data/housing.json -> {"<normalised block name>": {...}}
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import unicodedata
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import SSL_CTX, UA  # noqa: E402

SOURCES = [
    ("https://www.housingauthority.gov.hk/datagovhk/prh-estates.json",
     "Year of Intake", "No. of Rental Flats", "公共租住屋邨"),
    ("https://www.housingauthority.gov.hk/datagovhk/hos-courts.json",
     "Year of Completion", "No. of Flats", "資助出售房屋"),
]
OUT = pathlib.Path(__file__).parent.parent / "data" / "housing.json"


def pick(v, lang: str = "zh-Hant") -> str:
    if isinstance(v, dict):
        return (v.get(lang) or v.get("en") or "").strip()
    return str(v).strip() if v is not None else ""


def norm(s: str) -> str:
    """Fold to a comparable key: width, case and punctuation all vary between
    the Housing Authority's spelling and CSDI's."""
    s = unicodedata.normalize("NFKC", s or "").upper()
    return re.sub(r"[\s·・,，.。\-–—()（）'’\"]", "", s)


def company(v) -> str | None:
    """The Property Management field is the managing agent's name, its full
    postal address, a phone and a fax in one newline-separated blob — and for
    an estate managed in parts, a bracketed list of which blocks each agent
    covers ahead of each name. 115 subsidised courts carry no agent at all,
    only the note that the owners' corporation appoints one; that is worth
    saying plainly rather than printing angle brackets at people.
    """
    lines = [ln.strip() for ln in pick(v).split("\n") if ln.strip()]
    for ln in lines:
        if ln[0] in "(（<＜":          # a scope qualifier, not a name
            continue
        return ln
    if any("業主立案法團" in ln for ln in lines):
        return "業主立案法團委派"
    return None


def count(v) -> int | None:
    """Flat counts read '3 900 as at 30.6.2026' — a space as the thousands
    separator and a currency date glued on. Take the leading number only, or
    the date's digits come along and an estate reports 39,003 flats."""
    txt = pick(v, "en")
    digits = ""
    for c in txt:
        if c.isdigit():
            digits += c
        elif c in " \u00a0,":
            if digits and txt[txt.index(c):].lstrip(" \u00a0,")[:1].isdigit():
                continue        # a thousands separator, keep reading
            break
        else:
            break
    return int(digits) if digits else None


def fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    out: dict[str, dict] = {}
    for url, year_key, flats_key, kind in SOURCES:
        rows = fetch(url)
        print(f"{kind}: {len(rows)} 個")
        for r in rows:
            year = "".join(c for c in pick(r.get(year_key), "en") if c.isdigit())[:4]
            if not (year.isdigit() and 1950 <= int(year) <= 2043):
                continue
            meta = {
                "year": int(year),
                "estate": pick(r.get("Estate Name")),
                "kind": kind,
                "mgmt": company(r.get("Property Management")),
                "flats": count(r.get(flats_key)),
                "nblocks": count(r.get("No. of Blocks")),
            }
            for lang, minlen in (("zh-Hant", 2), ("en", 4)):
                raw = pick(r.get("Name of Block(s)"), lang)
                for b in re.split(r"[\n,、/]+", raw):
                    key = norm(b)
                    if len(key) >= minlen:
                        out.setdefault(key, meta)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(f"\n{len(out):,} block names -> {OUT} ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
