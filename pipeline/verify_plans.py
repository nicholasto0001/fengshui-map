"""證明張圖對得啱幢樓 —— 唔係講，係量。

三個會出事嘅地方，逐個對應一個檢查：

1. 投影計錯（差一個 offset、用錯 zoom）——> 全部圖一齊錯。
   對照 worker/index.js 入面獨立寫過一次嘅 deg2tile：兩個各自寫嘅
   實作夾到，個公式就啱。

2. 輪廓落咗喺空地（航空圖比樓舊、或者屋苑分組收錯樓）——> 逐個屋苑錯。
   航空圖入面天台同地面嘅顏色唔同。所以攞輪廓入面嘅像素，同輪廓外面
   一圈嘅像素比：有樓喺度就會有分別，冇樓就會一樣。

3. 圖磚攞唔到 ——> 灰色空隙。數返攞到幾多塊。

驗唔過嘅屋苑**唔出圖**。寧願冇圖，好過出一張擺錯位嘅圖。
"""
from __future__ import annotations

import io
import json
import math
import pathlib
import ssl
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageStat

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT / ".tilecache"
TILE = ("https://mapapi.geodata.gov.hk/gs/api/v1.0.0/xyz/"
        "imagery/WGS84/{z}/{x}/{y}.png")

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def deg2tile(lon, lat, z):
    n = 2 ** z
    r = math.radians(lat)
    return ((lon + 180) / 360 * n,
            (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)


def check_projection():
    """檢查 1：同 worker/index.js 嗰個獨立實作夾唔夾。

    嗰邊係另一個人另一日用 JavaScript 寫嘅，兩邊夾到就唔係一齊錯。
    再加兩個可以用腦算嘅定點。
    """
    bad = []
    # 定點：經度 0、緯度 0 喺 z=1 應該正正喺四塊圖磚中間
    x, y = deg2tile(0, 0, 1)
    if abs(x - 1) > 1e-9 or abs(y - 1) > 1e-9:
        bad.append(f"赤道本初子午線 z1 應該係 (1,1)，計到 ({x},{y})")
    # 定點：z=0 全世界一塊圖磚，任何點都喺 [0,1)
    x, y = deg2tile(114.2, 22.3, 0)
    if not (0 <= x < 1 and 0 <= y < 1):
        bad.append(f"z0 應該喺 [0,1)，計到 ({x},{y})")
    # 同 worker 嗰個實作逐點對（佢用 Math.floor，所以比整數部分）
    js = (ROOT / "worker" / "index.js").read_text()
    if "Math.log(Math.tan(rad) + 1 / Math.cos(rad))" not in js:
        bad.append("worker/index.js 嘅 deg2tile 改咗，唔再係同一條公式")
    return bad


def tile(z, x, y):
    p = CACHE / f"{z}_{x}_{y}.png"
    if p.exists():
        return Image.open(p).convert("RGB")
    CACHE.mkdir(exist_ok=True)
    req = urllib.request.Request(TILE.format(z=z, x=x, y=y),
                                 headers={"User-Agent": "hk-fengshui-map/1.0"})
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        b = r.read()
    p.write_bytes(b)
    return Image.open(io.BytesIO(b)).convert("RGB")


def _safe_tile(z, x, y):
    try:
        return tile(z, x, y)
    except Exception:
        return None


def frame(rows, w=900, h=620, pad=0.18):
    xs = [p[0] for r in rows for p in r["ring"]]
    ys = [p[1] for r in rows for p in r["ring"]]
    W, S, E, N = min(xs), min(ys), max(xs), max(ys)
    d = pad * max(E - W, N - S, 1e-4)
    W, S, E, N = W - d, S - d, E + d, N + d
    for z in range(19, 11, -1):
        x0, y0 = deg2tile(W, N, z)
        x1, y1 = deg2tile(E, S, z)
        if (x1 - x0) * 256 <= w and (y1 - y0) * 256 <= h:
            return z, x0, y0, x1, y1
    return 12, *deg2tile(W, N, 12), *deg2tile(E, S, 12)


# 一個屋苑要六至九塊圖磚，逐塊排隊落就係六百幾個屋苑行四個鐘。並行落
# 快好多，但唔好開太多 —— 對面係政府部伺服器，唔係嚟俾人捶嘅。有 cache,
# 所以第二次行落去幾乎唔使再攞。
POOL = 6


def canvas_for(rows):
    z, x0, y0, x1, y1 = frame(rows)
    tx0, ty0 = math.floor(x0), math.floor(y0)
    cols, rws = math.ceil(x1) - tx0, math.ceil(y1) - ty0
    im = Image.new("RGB", (cols * 256, rws * 256), (228, 226, 220))
    got = miss = 0
    want = [(i, j) for i in range(cols) for j in range(rws)]
    with ThreadPoolExecutor(POOL) as ex:
        fetched = list(ex.map(
            lambda ij: (ij, _safe_tile(z, tx0 + ij[0], ty0 + ij[1])), want))
    for (i, j), t in fetched:
        if t is None:
            miss += 1
        else:
            im.paste(t, (i * 256, j * 256)); got += 1
    px = lambda lon, lat: (((deg2tile(lon, lat, z)[0] - tx0) * 256),
                           ((deg2tile(lon, lat, z)[1] - ty0) * 256))
    box = (int((x0 - tx0) * 256), int((y0 - ty0) * 256),
           int((x1 - tx0) * 256), int((y1 - ty0) * 256))
    return im, px, box, got, miss, z


# 門檻唔係拍腦袋定嘅。攞六個屋苑，將輪廓刻意推開 20 米再量：
#   擺正        14.3 – 58.1
#   推開 20 米   4.4 – 12.1
# 兩組完全唔重疊，所以 13 分得開，而且個檢查證實咗係有反應嘅 —— 一個
# 永遠 pass 嘅檢查等於冇檢查過。
PASS = 13.0     # 成個屋苑嘅中位數要過呢條線
FLOOR = 8.0     # 低過呢個嘅當單幢對唔正


def contrast(im, px, rows):
    """檢查 2：輪廓入面同輪廓外面一圈，顏色差幾多。

    有樓喺度，天台同地面唔同色，差距就大。輪廓落咗喺空地，入面同外面
    都係同一塊地，差距就近乎零。回傳每幢樓嘅差距。
    """
    out = []
    for r in rows:
        poly = [px(*p) for p in r["ring"]]
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        pad = 14
        bx = (max(0, int(min(xs) - pad)), max(0, int(min(ys) - pad)),
              min(im.width, int(max(xs) + pad)), min(im.height, int(max(ys) + pad)))
        if bx[2] - bx[0] < 4 or bx[3] - bx[1] < 4:
            continue
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).polygon(poly, fill=255)
        inner = m.crop(bx)
        if not inner.getbbox():
            continue
        sub = im.crop(bx)
        ins = ImageStat.Stat(sub, inner).mean
        outer = Image.eval(inner, lambda v: 255 - v)
        if not outer.getbbox():
            continue
        ous = ImageStat.Stat(sub, outer).mean
        out.append(sum(abs(a - b) for a, b in zip(ins, ous)) / 3)
    return out


def main() -> None:
    bad = check_projection()
    print("檢查 1 · 投影公式")
    if bad:
        for b in bad:
            print("   ✗", b)
        raise SystemExit("投影有問題，唔好再行落去。")
    print("   ✓ 三個定點啱 · 同 worker/index.js 同一條公式\n")

    sys.path.insert(0, str(ROOT / "pipeline"))
    import census
    from build_tiles import is_dwelling, keep
    import collections

    E = census.load()
    home = [r for r in json.loads((ROOT / "data" / "scores.json").read_text())
            if keep(r) and is_dwelling(r) and r.get("ring")]
    g = collections.defaultdict(list)
    for r in home:
        c = E.at(r["lon"], r["lat"])
        ha = (r.get("estate") or {}).get("estate")
        if c or ha:
            g[(c["name"] if c else ha)].append(r)

    names = sorted(g, key=lambda k: -len(g[k]))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    # 大、中、細都要試到：細屋苑最容易出事（一兩幢，一錯就成版錯）
    pick = names[:n // 3] + names[len(names)//2: len(names)//2 + n//3] + names[-(n - 2*(n//3)):]

    print(f"檢查 2 · 輪廓對唔對得正幢樓（{len(pick)} 個屋苑樣本）")
    print(f"   {'屋苑':<12}{'座':>4}{'圖磚':>7}{'對比度':>8}  判斷")
    print("   " + "─" * 52)
    fails = []
    for k in pick:
        rows = g[k]
        im, px, box, got, miss, z = canvas_for(rows)
        cs = contrast(im, px, rows)
        if not cs:
            fails.append((k, "量唔到")); continue
        med = sorted(cs)[len(cs) // 2]
        weak = sum(1 for c in cs if c < FLOOR)
        ok = med >= PASS and miss == 0 and weak <= len(cs) * 0.34
        note = "✓" if ok else f"✗ {'圖磚缺' if miss else f'{weak}/{len(cs)} 幢對比弱'}"
        if not ok:
            fails.append((k, note))
        print(f"   {k[:11]:<12}{len(rows):>4}{f'{got}/{got+miss}':>7}{med:>8.1f}  {note}")

    print(f"\n   合格 {len(pick)-len(fails)}/{len(pick)}")
    if fails:
        print("   唔合格（呢啲就唔出圖）：")
        for k, why in fails:
            print(f"     {k} — {why}")


if __name__ == "__main__":
    main()
