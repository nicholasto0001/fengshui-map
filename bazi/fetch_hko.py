"""攞天文台嘅曆法數據落嚟做對照。

兩批：
  T<year>c.txt  —— 公曆農曆對照表，1901–2100，逐日標節氣「日期」
  24SolarTerms_<year>.xml —— 節氣「時刻」，只得近年

兩批都係為咗驗我哋自己計嘅嘢，唔係攞嚟行時用 —— 行時要計得到 1901 到
2100 任何一日，唔可以靠兩百個檔案。
"""
from __future__ import annotations

import pathlib
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CACHE = pathlib.Path(__file__).parent / ".hko"
CAL = "https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T{y}c.txt"
XML = "https://www.hko.gov.hk/tc/gts/astronomy/data/files/24SolarTerms_{y}.xml"

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def get(url: str, name: str) -> bytes | None:
    f = CACHE / name
    if f.exists():
        return f.read_bytes()
    CACHE.mkdir(exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hk-fengshui-map/1.0"})
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            b = r.read()
    except Exception:
        return None
    if b"<html" in b[:200].lower():        # 天文台冇嘅年份會回一版 HTML
        return None
    f.write_bytes(b)
    return b


def main() -> None:
    years = range(1901, 2101)
    with ThreadPoolExecutor(8) as ex:
        cal = list(ex.map(lambda y: (y, get(CAL.format(y=y), f"cal{y}.txt")), years))
        xml = list(ex.map(lambda y: (y, get(XML.format(y=y), f"st{y}.xml")), years))
    print(f"對照表 {sum(1 for _, b in cal if b)}/200 年")
    got = [y for y, b in xml if b]
    print(f"節氣時刻 {len(got)} 年" + (f"（{min(got)}–{max(got)}）" if got else ""))


if __name__ == "__main__":
    main()
