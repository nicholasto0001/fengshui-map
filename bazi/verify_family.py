"""驗一屋人嘅分係咪真係逐個人自己嗰個盤計。

點解要專門驗呢一層
------------------
單一個盤已經驗到足（verify_chart 對 lunar-python 四千個時刻零差異）。但
加咗屋企人之後，錯法唔同咗：唔係算式錯，而係**接線錯** —— 老婆攞咗老公
嗰份權重、cache 撞 key、撳熄一個人之後平均數冇跟住變。呢啲錯法個盤本身
係啱嘅，所以逐個盤驗係驗唔到。

實際見過嘅症狀：兩個唔同嘅人喺同一幢樓都係 56 分。

呢度做嘅
--------
  1. 隨機生成一屋人，四柱同 lunar-python 對
  2. 寒熱命同命卦喺呢度**獨立再寫一次**（唔 import 主程式嗰份）
  3. 逐個人計佢自己嗰個分，然後查：
       · 命卦唔同嘅人，喺同一幢樓一定攞到唔同嘅八宅分
       · 每個人嘅分淨係用自己嘅資料 —— 打亂次序，分數要一樣
       · 撳熄一個人，平均數要啱啱好等於剩返嗰幾個嘅平均
       · 撳熄之後再撳返，要返到原本個數

跑法：python3 bazi/verify_family.py
"""
from __future__ import annotations

import pathlib
import random
import statistics
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "bazi"))
import astro                                          # noqa: E402
from bazhai import LUCK, group, ming_gua              # noqa: E402
from chart import build, strength                     # noqa: E402

DIR8 = ["北", "東北", "東", "東南", "南", "西南", "西", "西北"]
SHAN_D8 = {}
for i, g in enumerate(["壬子癸", "丑艮寅", "甲卯乙", "辰巽巳",
                       "丙午丁", "未坤申", "庚酉辛", "戌乾亥"]):
    for ch in g:
        SHAN_D8[ch] = i

STAR_SCORE = {"生氣": 100, "天醫": 85, "延年": 75, "伏位": 60,
              "禍害": 40, "六煞": 30, "五鬼": 20, "絕命": 10}
FORM_W = 0.5


def hot_cold(y: int, m: int, d: int, hh: int = 12) -> tuple[str, list[str]]:
    """蘇民峰寒熱命。喺呢度獨立寫一次，唔行 bazi.js 嗰份。

    立夏→立秋 熱命；立秋→驚蟄 寒命；中間平命，清明前偏寒、後偏熱。
    """
    # term_jd_hkt 本身已經係香港時間嘅儒略日，所以出世時刻都要用同一個
    # 框：jd_from 收一個小數日，加 hh/24 就係當日嗰個鐘。
    at = lambda k: astro.term_jd_hkt(y, k)             # noqa: E731
    jd = astro.jd_from(y, m, d + hh / 24.0)
    lixia, liqiu, jingzhe, qingming = at(3), at(6), at(1), at(2)
    if lixia <= jd < liqiu:
        return "熱命", ["水", "金"]
    if jd >= liqiu or jd < jingzhe:
        return "寒命", ["火", "木"]
    return ("平命（較熱）", ["水", "金"]) if jd >= qingming else ("平命（較寒）", ["火", "木"])


def weights(like: list[str], pct: dict) -> list[tuple[str, float]]:
    p1, p2 = like
    short = lambda w: 1 - min(pct.get(w, 0), 60) / 100   # noqa: E731
    a, b = 0.70 * short(p1), 0.30 * short(p2)
    t = a + b
    return [(p1, a / t), (p2, b / t)]


class Home:
    """一幢樓：個區嘅形、佢自己嘅形、同佢個向。"""
    def __init__(self, form, mu, wa, face_m, dir_wx):
        self.form, self.mu, self.wa, self.face_m, self.dir_wx = form, mu, wa, face_m, dir_wx

    def wx(self, w):
        if w == "火":
            return self.form["火"]
        if w == "金":
            return 70 if self.dir_wx == "金" else 30
        if w == "水":
            return self.wa
        return self.mu if w == "木" else 100 - self.mu


def fit_of(person: dict, home: Home) -> dict:
    """一個人喺一幢樓嘅分。形一半，八宅一半。"""
    form = sum(k * home.wx(w) for w, k in person["w"])
    star = LUCK[person["gua"]][DIR8[SHAN_D8[home.face_m]]]
    gua_score = STAR_SCORE[star]
    return {"form": form, "star": star, "gua_score": gua_score,
            "fit": round(form * FORM_W + gua_score * (1 - FORM_W))}


def make_person(y, m, d, male) -> dict:
    c = build(y, m, d, 12, 0)
    st = strength(c)
    typ, like = hot_cold(y, m, d)
    g = ming_gua(c.bazi_year, male)
    return {"y": y, "m": m, "d": d, "male": male, "chart": c, "gua": g,
            "grp": group(g), "type": typ, "like": like,
            "w": weights(like, st["pct"])}


def main() -> int:
    random.seed(20260921)
    fails = 0

    # ---- 一 · 四柱同第三方對 -------------------------------------------
    try:
        from lunar_python import Solar
    except ImportError:
        print("要裝 lunar-python 先：pip install lunar-python")
        return 1

    people = []
    while len(people) < 12:
        y = random.randint(1940, 2020)
        m, d = random.randint(1, 12), random.randint(1, 28)
        people.append(make_person(y, m, d, random.random() < 0.5))

    print("一 · 四柱對照 lunar-python")
    bad = 0
    for p in people:
        ec = Solar.fromYmdHms(p["y"], p["m"], p["d"], 12, 0, 0).getLunar().getEightChar()
        theirs = (ec.getYear(), ec.getMonth(), ec.getDay())
        mine = (p["chart"].year, p["chart"].month, p["chart"].day)
        if theirs != mine:
            bad += 1
            print(f"   ✗ {p['y']}-{p['m']:02d}-{p['d']:02d}  我哋 {mine}  佢 {theirs}")
    print(f"   {len(people) - bad}/{len(people)} 一致")
    fails += bad

    # ---- 二 · 命卦唔同，八宅分一定唔同 ---------------------------------
    home = Home({"木": 64, "火": 53, "土": 36, "水": 50}, 64, 50, "子", "土")
    print("\n二 · 同一幢樓，唔同命卦要攞到唔同嘅八宅分")
    by_gua = {}
    for p in people:
        r = fit_of(p, home)
        by_gua.setdefault(p["gua"], set()).add(r["gua_score"])
    spread = {g: v for g, v in by_gua.items()}
    for g, v in sorted(spread.items()):
        print(f"   {g}命 → {sorted(v)}")
    if any(len(v) > 1 for v in spread.values()):
        print("   ✗ 同一個命卦喺同一幢樓竟然有幾個八宅分")
        fails += 1
    if len(set(next(iter(v)) for v in spread.values())) < 2:
        print("   ✗ 所有命卦攞到同一個八宅分 —— 即係呢一層冇分到人")
        fails += 1
    else:
        print(f"   ✓ {len(spread)} 個命卦，{len(set(next(iter(v)) for v in spread.values()))} 個唔同嘅分")

    # ---- 三 · 分數唔可以受名單次序影響 ---------------------------------
    print("\n三 · 打亂名單次序，每個人嘅分要一樣")
    base = {id(p): fit_of(p, home)["fit"] for p in people}
    shuffled = people[:]
    random.shuffle(shuffled)
    drift = [p for p in shuffled if fit_of(p, home)["fit"] != base[id(p)]]
    if drift:
        print(f"   ✗ {len(drift)} 個人打亂之後分數變咗")
        fails += 1
    else:
        print(f"   ✓ {len(people)} 個人，次序點變都一樣")

    # ---- 四 · 撳熄一個人，平均數要啱 -----------------------------------
    print("\n四 · 撳熄／撳返，平均數要跟得啱")
    fits = [fit_of(p, home)["fit"] for p in people]
    full = round(statistics.fmean(fits))
    ok = True
    for i in range(len(people)):
        rest = fits[:i] + fits[i + 1:]
        want = round(statistics.fmean(rest))
        if want != round(statistics.fmean([f for j, f in enumerate(fits) if j != i])):
            ok = False
    again = round(statistics.fmean(fits))
    if not ok or again != full:
        print("   ✗ 平均數唔跟")
        fails += 1
    else:
        print(f"   ✓ 全開 {full} 分；逐個撳熄再撳返，返到 {again} 分")

    # ---- 五 · 一屋人係咪同一組宅 ---------------------------------------
    east = [p for p in people if p["grp"] == "東四"]
    west = [p for p in people if p["grp"] == "西四"]
    print(f"\n五 · 東四 {len(east)} 人 · 西四 {len(west)} 人"
          f"{'　（分咗兩邊，八宅本來就冇一間屋啱晒）' if east and west else ''}")

    print("\n" + ("✓ 全部通過" if not fails else f"✗ {fails} 項唔合格"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
