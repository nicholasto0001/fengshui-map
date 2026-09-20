"""sitemap.xml — tell Google what exists.

Phase 1 is only the hand-written pages: there is no point listing thousands of
URLs before any of them exist. The generator is shaped so the district, estate
and building pages can be appended as each layer ships, and so that a layer can
be held back — Google's 2026 scaled-content policy demotes a whole domain over a
bloated section of thin pages, so the pages go out in batches that are measured
before the next one follows.

Output: sitemap.xml
"""
from __future__ import annotations

import datetime
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
SITE = "https://hkfengshuimap.com"

# path, change frequency, priority
PAGES = [
    ("/",             "daily",   "1.0"),
    ("/method",       "monthly", "0.8"),
    ("/privacy.html", "yearly",  "0.3"),
]


def main() -> None:
    today = datetime.date.today().isoformat()
    urls = "\n".join(
        f"  <url>\n"
        f"    <loc>{SITE}{path}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{pri}</priority>\n"
        f"  </url>"
        for path, freq, pri in PAGES
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{urls}\n</urlset>\n")
    out = ROOT / "sitemap.xml"
    out.write_text(xml)
    print(f"sitemap.xml: {len(PAGES)} URL -> {out}")


if __name__ == "__main__":
    main()
