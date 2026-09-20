"""由一個人嘅出生年同性別，揀出合佢命卦嘅樓。

呢條鏈每一段都有根據：

    出生年（立春為界）+ 性別
        → 本命卦            八宅標準算法，完全確定性
        → 四個吉方          由變爻推導，唔係打表
        → 向首二十四山       我哋 52,383 幢住宅有
        → 樓宇              加埋風水評分排序

刻意冇做嘅：唔會講「你八字啱住沙田」。五行配方位有傳統根據，但「五行
配香港邊個區」冇 —— 嗰個係砌出嚟。呢度講嘅係坐向，而坐向我哋真係逐幢
計過。

坐向可靠度：app 本身用 conf >= 0.6 先肯出飛星盤，呢度用返同一條線。
低過嗰條線嘅樓唔係唔存在，係我哋推唔準佢個長軸，所以唔應該攞佢嚟同
人講「呢幢合你」。
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "bazi"))
from bazhai import GUA_DIR, LUCK, SHAN_DIR, good_dirs, group, ming_gua  # noqa: E402
from build_tiles import is_dwelling, keep                              # noqa: E402

CONF = 0.6          # 同 index.html 出飛星盤嗰條線一樣


def load_homes():
    sc = json.loads((ROOT / "data" / "scores.json").read_text())
    return [r for r in sc if keep(r) and is_dwelling(r)
            and r.get("face_m") and (r.get("tc") or r.get("en"))]


# 八宅只分東四、西四兩組宅。所以同組嘅人，合嘅樓係同一批 —— 分別唔喺
# 「邊幾幢合」，喺「每個方位對你嚟講係邊個遊年星」。乾命嘅「生氣」喺西,
# 艮命嘅「生氣」喺西南，兩者合嘅樓一樣，但最旺嗰批唔同。
#
# 所以排序提供兩種：按風水評分（我哋自己量到嗰樣），或者按遊年再按評分
# （傳統上生氣為首）。唔好靜靜雞揀一個當標準。
STAR_RANK = {"生氣": 0, "天醫": 1, "延年": 2, "伏位": 3}


def for_person(homes, bazi_year: int, male: bool, *,
               district=None, top=10, by="score"):
    gua = ming_gua(bazi_year, male)
    dirs = good_dirs(gua)
    want = set(dirs)

    pool = [r for r in homes if SHAN_DIR.get(r["face_m"]) in want]
    solid = [r for r in pool if (r.get("conf") or 0) >= CONF]
    if district:
        solid = [r for r in solid if r["district"] == district]
    star = lambda r: LUCK[gua][SHAN_DIR[r["face_m"]]]
    if by == "star":
        solid.sort(key=lambda r: (STAR_RANK[star(r)], -r["total"]))
    else:
        solid.sort(key=lambda r: -r["total"])

    by_star = {}
    for r in solid:
        by_star.setdefault(LUCK[gua][SHAN_DIR[r["face_m"]]], []).append(r)

    return {
        "gua": gua, "group": group(gua), "dirs": dirs,
        "matched": len(pool), "reliable": len(solid),
        "by_star": {k: len(v) for k, v in by_star.items()},
        "top": solid[:top],
    }


if __name__ == "__main__":
    homes = load_homes()
    print(f"可以配對嘅住宅：{len(homes):,} 幢（有名、有向首）")
    print(f"其中坐向可靠（conf ≥ {CONF}）：",
          f"{sum(1 for r in homes if (r.get('conf') or 0) >= CONF):,} 幢\n")
    for year, male in ((1985, True), (1990, False), (1972, True)):
        r = for_person(homes, year, male, by="star")
        who = f"{year} 年出世 {'男' if male else '女'}"
        print(f"{who} → {r['gua']}命（{r['group']}）")
        print(f"   宜向：{'、'.join(f'{d}（{LUCK[r['gua']][d]}）' for d in r['dirs'])}")
        print(f"   全港合嘅住宅：{r['matched']:,} 幢，"
              f"其中坐向可靠 {r['reliable']:,} 幢")
        print(f"   按遊年分：{r['by_star']}")
        for b in r["top"][:5]:
            d = SHAN_DIR[b["face_m"]]
            print(f"     {b['total']:5.1f}  {b['tc'] or b['en']:<14}"
                  f"{b['district']:<6} 坐{b['sit_m']}向{b['face_m']}"
                  f"（向{d}·{LUCK[r['gua']][d]}）")
        print()
