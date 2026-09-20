"""2021 人口普查 —— 主要屋苑統計數字及分界。

點解要佢：

房委會個登記冊得公屋居屋，所以我哋而家淨係公營房屋有「屋苑」呢個概念 ——
409 個。打「太古城」落搜尋，出嚟係一堆散裝樓宇，因為我哋根本唔知邊幾幢
係太古城。

呢個數據集有 540 個主要屋苑，公私營都有，而且**連邊界圖形**。用座標點
對面，私樓第一次 group 得到。撞名唔得：409 個入面淨係 266 個對得返
（65%），而「翠湖別墅」呢類名喺全港唔止一個。點對面唔會撞錯。

129 個統計欄位一併攞埋，因為同一個 request 拎得晒，遲啲要用唔使再問人。

來源：政府統計處，經 CSDI Portal 發佈（data.gov.hk）。
授權：商業用途免費，要註明來源，唔可以轉售數據本身。

Output: data/census.json
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import get_json  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "data" / "census.json"

LAYER = ("https://portal.csdi.gov.hk/server/rest/services/common/"
         "censtatd_rcd_1695182015782_79001/MapServer/0/query")

# 政府一個 request 出唔晒 540 個連圖形嘅話會截short，所以分兩次攞:
# 一次淨係統計數字，一次淨係圖形。兩次都用 OBJECTID 做鎖匙。
STATS = dict(where="1=1", outFields="*", returnGeometry="false", f="json")
SHAPE = dict(where="1=1", outFields="OBJECTID,estate_chi", returnGeometry="true",
             outSR="4326", f="geojson")


def main() -> None:
    print("攞緊統計數字 …")
    stats = get_json(LAYER, STATS)
    rows = {f["attributes"]["OBJECTID"]: f["attributes"]
            for f in stats.get("features", [])}
    print(f"  {len(rows)} 個屋苑 · {len(next(iter(rows.values())))} 個欄位")

    print("攞緊邊界 …")
    geo = get_json(LAYER, SHAPE)
    feats = geo.get("features", [])
    print(f"  {len(feats)} 個圖形")

    out = []
    for f in feats:
        oid = f["properties"].get("OBJECTID")
        a = rows.get(oid)
        if not a:
            continue
        g = f["geometry"]
        # GeoJSON 嘅 Polygon 同 MultiPolygon 攤平做同一個形狀，
        # 落面嘅點對面就唔使分兩種 case。
        rings = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        a = {k: v for k, v in a.items() if v not in (None, "", "-")}
        a.pop("SHAPE", None); a.pop("SHAPE_Length", None); a.pop("SHAPE_Area", None)
        out.append({"name": a.get("estate_chi"), "en": a.get("estate_eng"),
                    "stats": a, "rings": rings})

    missing = len(feats) - len(out)
    if missing:
        print(f"  ⚠ {missing} 個有圖形但冇統計數字，跳咗")
    if len(out) < 400:
        raise SystemExit(f"淨係得 {len(out)} 個屋苑，明顯唔對路 —— 唔覆蓋原本份檔案。")

    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"-> {OUT}  ({OUT.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
