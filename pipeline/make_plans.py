"""屋苑平面圖 —— 政府航空影像，加上我哋自己算出嚟嗰啲樓宇輪廓。

點解要自己畫：地產網嗰啲屋苑相係佢哋嘅內容，攞唔得。但航空影像係地政
總署嘅開放數據（我哋個地圖已經用緊同已經註明），而輪廓同分數係我哋自己
計嘅。兩樣夾埋就係一張人哋冇、而且真係答到問題嘅圖 —— 邊一座喺邊，邊
一座分高，邊面向山邊面向水。

每一張出之前都要過 verify_plans 入面嗰兩個檢查。過唔到就唔出。一張擺錯
位嘅圖係對住人哋間屋講咗錯嘢，冇圖只係蝕少少。

Output: pages/plan/*.jpg
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import census                                        # noqa: E402
from build_tiles import is_dwelling, keep            # noqa: E402
from verify_plans import FLOOR, PASS, canvas_for, check_projection, contrast  # noqa: E402

OUT = ROOT / "pages" / "plan"
REPORT = ROOT / "pages" / "plan-report.json"
W, H = 880, 600

BREAKS = [41, 46, 52, 58]
COLOR = [(160, 31, 31), (215, 111, 111), (176, 169, 148), (77, 167, 154), (15, 99, 84)]
INK = (24, 24, 24)
PAPER = (255, 255, 255)




def tone(v):
    return COLOR[next((i for i, b in enumerate(BREAKS) if v < b), 4)]




def scale_bar(d, im, z, lat):
    """比例尺，只畫條線 —— 個數字由 HTML 嗰邊寫，回傳返俾佢。"""
    mpp = 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)
    for m in (500, 200, 100, 50, 25):
        px = m / mpp
        if 70 <= px <= 190:
            break
    x, y = 18, im.height - 26
    d.rounded_rectangle((x - 8, y - 22, x + px + 10, y + 12), 6, fill=(0, 0, 0, 140))
    d.line((x, y, x + px, y), fill=PAPER, width=2)
    d.line((x, y - 4, x, y + 4), fill=PAPER, width=2)
    d.line((x + px, y - 4, x + px, y + 4), fill=PAPER, width=2)
    return m


def north(d, im):
    x, y = im.width - 34, 34
    d.ellipse((x - 19, y - 19, x + 19, y + 19), fill=(0, 0, 0, 140))
    # 唔寫個 N 字 —— 上面嗰支針已經指住北，而字係 HTML 嗰邊加返。
    d.polygon([(x, y - 13), (x - 7, y + 8), (x, y + 3), (x + 7, y + 8)], fill=PAPER)


def draw(rows, im, px, box):
    im = im.convert("RGBA")
    d = ImageDraw.Draw(im, "RGBA")
    for r in rows:
        poly = [px(*p) for p in r["ring"]]
        if len(poly) < 3:
            continue
        d.polygon(poly, fill=tone(r["total"]) + (200,), outline=(255, 255, 255, 235))
    im = im.crop(box).convert("RGB")
    # 標籤唔燒落張圖，回傳百分比位置，等 HTML 疊返上去 —— 咁啲字係
    # 真字，揀得、放大唔矇、Google 讀得到，而且唔使 CI 有中文字體。
    w, h = box[2] - box[0], box[3] - box[1]
    labels = []
    if len(rows) <= 14:
        for r in rows:
            poly = [px(*p) for p in r["ring"]]
            cx = sum(p[0] for p in poly) / len(poly) - box[0]
            cy = sum(p[1] for p in poly) / len(poly) - box[1]
            if 0 < cx < w and 0 < cy < h:
                labels.append({"t": (r.get("tc") or r.get("en") or "")[:8],
                               "s": round(r["total"], 1),
                               "x": round(100 * cx / w, 2),
                               "y": round(100 * cy / h, 2)})
    return im, labels


def main() -> None:
    bad = check_projection()
    if bad:
        raise SystemExit("投影檢查唔過：" + "; ".join(bad))

    # 同 make_pages 收一樣嘅樓：要有名。唔要名嘅話，長安邨會多咗一幢
    # 冇名嘅樓，張圖寫「11 座」但個表列 10 座，而且會有個淨係得分數、
    # 冇名嘅標籤浮喺度。
    home = [r for r in json.loads((ROOT / "data" / "scores.json").read_text())
            if keep(r) and is_dwelling(r) and r.get("ring")
            and (r.get("tc") or r.get("en"))]
    # 同 make_pages 用同一個分組同同一個顯示名，所以檔名一定對得返版名。
    g = {k: v["rows"] for k, v in census.group(home).items()}

    only = set(sys.argv[1:]) or None
    OUT.mkdir(parents=True, exist_ok=True)
    made, skipped, report = 0, [], {}
    # 淨係跑幾個屋苑嘅時候要合併，唔可以覆寫 —— 之前跑三個屋苑就冚咗
    # 六百幾個嘅記錄，跟住出頁嗰陣一張圖都搵唔返。
    prev = {"ok": {}, "skipped": {}}
    if only and REPORT.exists():
        prev = json.loads(REPORT.read_text())
        report = dict(prev.get("ok", {}))
    names = sorted(g)
    for i, k in enumerate(names):
        if only and k not in only:
            continue
        rows = g[k]
        try:
            im, px, box, got, miss, z = canvas_for(rows)
        except Exception as exc:
            skipped.append((k, f"攞圖磚失敗 {exc}")); continue
        if miss:
            skipped.append((k, f"{miss} 塊圖磚攞唔到")); continue
        cs = contrast(im, px, rows)
        if not cs:
            skipped.append((k, "量唔到對比")); continue
        med = sorted(cs)[len(cs) // 2]
        weak = sum(1 for c in cs if c < FLOOR)
        if med < PASS:
            skipped.append((k, f"中位對比度 {med:.1f} < {PASS}")); continue
        if weak > len(cs) * 0.34:
            skipped.append((k, f"{weak}/{len(cs)} 幢對唔正（中位 {med:.1f} 過到）"))
            continue

        lat = sum(r["lat"] for r in rows) / len(rows)
        out, labels = draw(rows, im, px, box)
        d = ImageDraw.Draw(out, "RGBA")
        metres = scale_bar(d, out, z, lat)
        north(d, out)
        out.thumbnail((W, H), Image.LANCZOS)
        out.save(OUT / f"{k}.jpg", "JPEG", quality=72, optimize=True, progressive=True)
        # 記低真尺寸。thumbnail() 保持比例，所以出嚟好少係 880×600 ——
        # 喺 HTML 寫死 880×600 嘅話，載入之前個框比例就錯，啲絕對定位
        # 嘅標籤會喺圖載入嗰刻跳一跳。
        report[k] = {"contrast": round(med, 1), "blocks": len(rows),
                     "scale_m": metres, "w": out.width, "h": out.height,
                     "labels": labels}
        made += 1
        if made % 50 == 0:
            print(f"  … {made} 張", flush=True)

    # 改咗屋苑顯示名之後，舊名嗰啲檔仲會留喺度 —— 冇任何一版指住佢哋,
    # 但會跟住 deploy 上線。全量跑嘅時候清走佢。
    if not only:
        stale = [f for f in OUT.glob("*.jpg") if f.stem not in report]
        for f in stale:
            f.unlink()
        if stale:
            print(f"清走 {len(stale)} 個舊名留低嘅檔")

    tot = sum((OUT / f"{k}.jpg").stat().st_size for k in report)
    print(f"\n出咗 {made} 張 · 平均 {tot/max(made,1)/1024:.0f} KB · 共 {tot/1024/1024:.1f} MB")
    print(f"唔出圖 {len(skipped)} 個（驗唔過）：")
    for k, why in skipped[:15]:
        print(f"   {k} — {why}")
    drop = dict(prev.get("skipped", {}))
    drop.update(dict(skipped))
    for k in report:
        drop.pop(k, None)          # 今次出到圖嘅，唔應該仲留喺唔合格名單
    REPORT.write_text(json.dumps({"ok": report, "skipped": drop},
                                 ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
