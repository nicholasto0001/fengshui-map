"""成交數據 —— 源頭唔喺地產代理度，喺政府度。

中原、28Hse 啲逐個單位嘅二手成交，源頭係**土地註冊處**。但土地註冊處
免費公開嘅只係**每月總數**；逐個單位嗰啲喺佢個 IRIS 查冊系統入面，
**要畀錢**，代理買緊批量餵送。所以呢一忽我哋複製唔到，亦都唔應該扮有。

免費而且逐個單位嘅成交有一批：**房委會嘅居屋同綠置居銷售**。呢啲係真
成交價、真單位、真面積，而且啱啱好就係我哋覆蓋得最好嗰批樓。

所以呢度攞兩樣：
  1. 土地註冊處每月買賣合約宗數（全港 + 佢自己嗰 10 個分區）
  2. 房委會居屋／綠置居逐個單位成交

Output: data/market.json
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import ssl
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "data" / "market.json"
LR = "https://www.landreg.gov.hk/datagovhk/{ym}_data.json"
HA = "https://data.housingauthority.gov.hk/dataset/ssfs/ssfs-sale-transactions-{k}_tc.json"

# 土地註冊處自己嗰 10 個分區，對唔正 18 區議會分區。對得正嘅先放落區頁,
# 對唔正嘅（港島、九龍、荃灣）只擺喺市場頁，用返佢自己個名 ——
# 夾硬砌一個對應出嚟就係講咗一樣數據本身冇講過嘅嘢。
LR_TO_DISTRICT = {
    "Island": "離島區", "North": "北區", "Sai Kung": "西貢區",
    "Shatin": "沙田區", "Tai Po": "大埔區", "Tuen Mun": "屯門區",
    "Yuen Long": "元朗區",
}
LR_REGION_TC = {
    "Hong Kong": "港島", "Kowloon": "九龍", "Island": "離島", "North": "北區",
    "Sai Kung": "西貢", "Shatin": "沙田", "Tai Po": "大埔",
    "Tsuen Wan": "荃灣", "Tuen Mun": "屯門", "Yuen Long": "元朗",
}
HOS_SETS = ["018", "019", "020", "022", "023", "024",
            "g18", "g19", "g20", "g22", "g23", "g24", "e22", "e23"]

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def grab(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "hk-fengshui-map/1.0"})
    with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def rows_of(d):
    return d if isinstance(d, list) else next(
        (v for v in d.values() if isinstance(v, list)), [])


def to_int(v):
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def land_registry(months: int = 36) -> list:
    """由最近嗰個月倒行。政府出數有滯後，所以由上個月開始試，
    連續兩個月 404 就當到咗盡頭。"""
    out, miss = [], 0
    cur = dt.date.today().replace(day=1)
    for _ in range(months + 3):
        cur = (cur - dt.timedelta(days=1)).replace(day=1)
        try:
            rows = rows_of(grab(LR.format(ym=cur.strftime("%Y%m"))))
        except urllib.error.HTTPError:
            miss += 1
            if miss >= 2 and out:
                break
            continue
        except Exception:
            continue
        miss = 0
        rec = {"ym": cur.strftime("%Y-%m"), "regions": {}}
        for r in rows:
            d, u = r.get("Description", ""), to_int(r.get("Units"))
            if u is None:
                continue
            for en, tc in LR_REGION_TC.items():
                if d == f"Number of {en} transactions for ASP building units":
                    rec["regions"][tc] = u
            if d == "Number of ASP for Residential Building Units":
                rec["resi"] = u
            elif d == "Number of Primary Sales for ASP Residential Building Units":
                rec["primary"] = u
            elif d == "Number of Secondary Sales for ASP Residential Building Units":
                rec["secondary"] = u
        if rec.get("resi"):
            out.append(rec)
        if len(out) >= months:
            break
    return sorted(out, key=lambda r: r["ym"])


def hos() -> list:
    out = []
    for k in HOS_SETS:
        try:
            rows = rows_of(grab(HA.format(k=k)))
        except Exception:
            continue
        for r in rows:
            est = (r.get("Court/Estate") or "").strip()
            price = to_int(r.get("Transaction Price"))
            area = r.get("Saleable Area of Flats (sq. m.)")
            if not est or not price:
                continue
            out.append({"estate": est, "block": (r.get("Block") or "").strip(),
                        "floor": (r.get("Floor") or "").strip(),
                        "area": area, "price": price,
                        "date": (r.get("Date of Agreement for Sale and Purchase (ASP)")
                                 or "").strip(),
                        "scheme": (r.get("Scheme Type") or "").strip()})
    return out


def main() -> None:
    lr = land_registry()
    print(f"土地註冊處：{len(lr)} 個月"
          + (f"（{lr[0]['ym']} 至 {lr[-1]['ym']}）" if lr else ""))
    tx = hos()
    ests = {t["estate"] for t in tx}
    print(f"居屋／綠置居成交：{len(tx):,} 宗 · {len(ests)} 個屋苑")
    if not lr and not tx:
        raise SystemExit("兩邊都攞唔到，唔覆蓋原本份檔案。")
    OUT.write_text(json.dumps(
        {"landreg": lr, "lr_district": LR_TO_DISTRICT, "hos": tx},
        ensure_ascii=False, separators=(",", ":")))
    print(f"-> {OUT}  ({OUT.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
