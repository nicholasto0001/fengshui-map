"""將樓宇配落人口普查嘅主要屋苑 —— 用座標點對面，唔係撞名。

撞名唔夠好：409 個公營屋苑入面淨係 266 個對得返人口普查（65%），而
「翠湖別墅」「怡景花園」呢啲名喺全港唔止一個地方有。點對面冇呢個問題,
而且順手解決咗私樓 —— 私樓根本冇一個 register 可以撞。

冇用 shapely。成條 pipeline 跑喺淨 python3 上面（GitHub Actions、任何
一部 Mac，唔使裝嘢），所以射線法自己寫，四十行。540 個多邊形 × 56,841
幢樓硬碰係三千萬次，所以先用格網索引篩 —— 實際每幢樓只需要試一兩個。
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
CENSUS = ROOT / "data" / "census.json"

CELL = 0.005          # 約 500 米。格太大就篩唔走嘢，太細就索引本身大過數據。


def _bbox(rings):
    """rings 係一個屋苑嘅全部多邊形：[多邊形][環][點]。"""
    xs = [pt[0] for poly in rings for ring in poly for pt in ring]
    ys = [pt[1] for poly in rings for ring in poly for pt in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _in_ring(x, y, ring):
    """射線法。由 (x,y) 向右射，數過幾多條邊 —— 單數即係喺入面。"""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _in_poly(x, y, poly):
    """poly[0] 係外框，之後嘅係窿（例如屋苑中間嘅公園唔算）。"""
    if not _in_ring(x, y, poly[0]):
        return False
    return not any(_in_ring(x, y, hole) for hole in poly[1:])


class Estates:
    def __init__(self, rows):
        self.rows = rows
        self.grid = {}
        for i, e in enumerate(rows):
            x0, y0, x1, y1 = _bbox(e["rings"])
            e["bbox"] = (x0, y0, x1, y1)
            for cx in range(int(x0 / CELL), int(x1 / CELL) + 1):
                for cy in range(int(y0 / CELL), int(y1 / CELL) + 1):
                    self.grid.setdefault((cx, cy), []).append(i)

    def at(self, lon: float, lat: float):
        """邊個屋苑覆蓋呢一點？冇就 None。"""
        for i in self.grid.get((int(lon / CELL), int(lat / CELL)), ()):
            e = self.rows[i]
            x0, y0, x1, y1 = e["bbox"]
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            if any(_in_poly(lon, lat, poly) for poly in e["rings"]):
                return e
        return None


def load() -> Estates:
    if not CENSUS.exists():
        raise SystemExit("冇 data/census.json —— 先行 pipeline/fetch_census.py")
    return Estates(json.loads(CENSUS.read_text()))
