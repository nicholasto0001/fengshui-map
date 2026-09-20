"""屋苑背景資料 —— 發展商、落成年份、座數、單位數。

呢啲嘢中原同 28Hse 個網都有，但佢哋個網嗰啲係佢哋嘅內容。分別喺於：
兩間公司**自己喺 data.gov.hk 出咗開放數據**，同一批資料，用政府嗰套條款
發佈 —— 商業用途免費，要註明來源，唔可以轉售。所以攞嘅係呢個，唔係佢哋
個網。美聯冇出（成個 3,820 個數據集嘅目錄掃過，冇）。

兩邊有重疊，所以順手做 cross check：同一個屋苑兩邊都講發展商或者落成
年份嘅，夾唔夾到。夾唔到就兩個都寫出嚟，唔好扮知道邊個啱。

Output: data/estate_meta.json
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import ssl
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "data" / "estate_meta.json"

CCI = "http://hk.centanet.com/opendata/CCI%20Estate%20for%20Opendata.csv"
EPI = "https://www.28hse.com/opendata/EPI_constituent_estates.xlsx"

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def grab(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hk-fengshui-map/1.0"})
    with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
        return r.read()


def centaline() -> dict:
    rows = csv.DictReader(io.StringIO(grab(CCI).decode("utf-8-sig")))
    out = {}
    for r in rows:
        name = (r.get("c_estate") or "").strip()
        if not name:
            continue
        lo, hi = r.get("min_opdate"), r.get("max_opdate")
        out[name] = {
            "en": (r.get("e_estate") or "").strip() or None,
            "addr": (r.get("pc_addr") or "").strip() or None,
            "dev": [d.strip() for d in (r.get("pc_dev") or "").split("/") if d.strip()],
            "year": int(lo) if (lo or "").isdigit() else None,
            "year_to": int(hi) if (hi or "").isdigit() and hi != lo else None,
            "blocks": int(r["blgcount"]) if (r.get("blgcount") or "").isdigit() else None,
            "src": "中原地產",
        }
    return out


def hse28() -> dict:
    """xlsx 係一個 zip。用 zipfile 讀 sharedStrings，唔使裝 openpyxl ——
    成條 pipeline 嘅規矩係淨 python3 跑得起。"""
    z = zipfile.ZipFile(io.BytesIO(grab(EPI)))
    ss = re.findall(r"<t[^>]*>([^<]*)</t>", z.read("xl/sharedStrings.xml").decode())
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    out, rows = {}, []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        cells = []
        for c in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
            attrs, inner = c
            v = re.search(r"<v>([^<]*)</v>", inner)
            v = v.group(1) if v else ""
            cells.append(ss[int(v)] if 't="s"' in attrs and v.isdigit() else v)
        rows.append(cells)
    if not rows:
        return out
    head = {h: i for i, h in enumerate(rows[0])}
    need = ("cat_name", "cat_developer", "cat_total_block", "cat_total_flat")
    if not all(k in head for k in need):
        raise SystemExit(f"28Hse 個檔案換咗欄位：{rows[0]}")
    g = lambda r, k: r[head[k]] if head.get(k) is not None and head[k] < len(r) else ""
    for r in rows[1:]:
        name = (g(r, "cat_name") or "").strip()
        if not name:
            continue
        out[name] = {
            "en": (g(r, "cat_name_eng") or "").strip() or None,
            "addr": (g(r, "cat_geoaddr") or "").strip() or None,
            "dev": [d.strip() for d in (g(r, "cat_developer") or "").split("/") if d.strip()],
            "blocks": int(g(r, "cat_total_block")) if str(g(r, "cat_total_block")).isdigit() else None,
            "flats": int(g(r, "cat_total_flat")) if str(g(r, "cat_total_flat")).isdigit() else None,
            "src": "28Hse 香港屋網",
        }
    return out


# 兩邊講同一間公司但寫法唔同：恒基兆業／恒基地產、新鴻基／新鴻基地產、
# 信置／信和集團。而且 28Hse 通常只列牽頭嗰間，中原列齊合作嘅幾間 ——
# 所以 28Hse 嗰個通常係中原嗰個嘅子集，唔係矛盾。
# 正規化之後先比，真係對唔上嗰啲先當有分歧。
SUFFIX = ("集團", "地產", "發展", "置業", "實業", "兆業", "有限公司", "控股")
SYN = {"信置": "信和", "信和集團": "信和", "華置": "華人置業",
       "香港置地": "置地", "九倉": "九龍倉", "長實": "長江實業", "新地": "新鴻基"}


def norm(name: str) -> str:
    n = SYN.get(name, name)
    for suf in SUFFIX:
        if n.endswith(suf) and len(n) > len(suf):
            n = n[: -len(suf)]
    return n[:2]


def main() -> None:
    c, h = centaline(), hse28()
    print(f"中原 {len(c)} 個 · 28Hse {len(h)} 個 · 重疊 {len(set(c) & set(h))} 個")

    out, clash = {}, 0
    for name in set(c) | set(h):
        a, b = c.get(name), h.get(name)
        rec = {"name": name}
        for k in ("en", "addr", "year", "year_to", "blocks", "flats"):
            rec[k] = (a or {}).get(k) or (b or {}).get(k)
        # 發展商：兩邊都有就對一對。夾唔到就兩個都留低，等讀嘅人自己判斷,
        # 唔好扮知道邊個啱。
        da, db = (a or {}).get("dev") or [], (b or {}).get("dev") or []
        na, nb = {norm(x) for x in da}, {norm(x) for x in db}
        if da and db and not (nb <= na or na <= nb):
            rec["dev"], rec["dev_alt"] = da, db
            clash += 1
        else:
            rec["dev"] = da or db
        rec["src"] = [s for s in [(a or {}).get("src"), (b or {}).get("src")] if s]
        out[name] = rec

    print(f"合併後 {len(out)} 個屋苑 · 發展商兩邊講法對唔上嘅 {clash} 個（兩個都保留）")
    print(f"  有發展商 {sum(1 for v in out.values() if v['dev'])} · "
          f"有落成年 {sum(1 for v in out.values() if v['year'])} · "
          f"有單位數 {sum(1 for v in out.values() if v.get('flats'))}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"-> {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
