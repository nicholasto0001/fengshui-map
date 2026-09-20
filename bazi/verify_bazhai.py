"""驗八宅：本命卦同遊年表。

同排盤一樣，唔靠「睇落似啱」。呢度三個對照：

  一  本命卦 vs 坊間公開嘅公式（2000 年前後兩條唔同），1900–2099 × 男女
  二  遊年表對稱 —— 兩卦之間嘅爻變關係係互逆嘅，所以 A 對 B 係生氣,
      B 對 A 就一定要係生氣
  三  東四命嘅四個吉方，要啱啱好等於四個東四卦嘅方位。呢個唔係另外
      定義出嚟嘅規矩，係「東四」「西四」呢兩個名嘅由來 —— 如果推導
      錯咗，呢個性質就唔會成立

第二同第三個檢查特別重要：遊年表係 8 × 8 = 64 格，打錯一格冇人睇得出,
而嗰格會令一個人以為自己間屋喺吉方。第一次係手打嘅，64 格錯咗 15 格。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bazhai import DIR_GUA, EAST, GOOD, GUA_DIR, LUCK, WEST, ming_gua  # noqa: E402

NUM = {1: "坎", 2: "坤", 3: "震", 4: "巽", 6: "乾", 7: "兌", 8: "艮", 9: "離"}


def published(year: int, male: bool) -> str:
    """坊間通行嘅算法，用出生年最後兩位。2000 年前後兩條唔同式。"""
    yy = year % 100
    if year < 2000:
        n = ((100 - yy) if male else (yy - 4)) % 9
    else:
        n = ((99 - yy) if male else (yy + 6)) % 9
    n = n or 9
    if n == 5:
        n = 2 if male else 8
    return NUM[n]


def main() -> int:
    fails = 0

    diff = [f"{y}{'男' if m else '女'}: 我哋 {ming_gua(y, m)} / 坊間 {published(y, m)}"
            for y in range(1900, 2100) for m in (True, False)
            if ming_gua(y, m) != published(y, m)]
    print(f"一 · 本命卦：1900–2099 × 男女 = 400 個 · 唔同 {len(diff)} 個")
    for d in diff[:6]:
        print("   ", d)
    fails += len(diff)

    asym = [f"{a}→{b} {s}，但 {b}→{a} {LUCK[b][GUA_DIR[a]]}"
            for a in LUCK for b, s in
            ((DIR_GUA[d], st) for d, st in LUCK[a].items())
            if LUCK[b][GUA_DIR[a]] != s]
    print(f"二 · 遊年對稱：64 對關係 · 唔對稱 {len(asym)} 個")
    for x in asym[:6]:
        print("   ", x)
    fails += len(asym)

    grp = []
    for g in LUCK:
        got = {d for d, s in LUCK[g].items() if s in GOOD}
        want = {GUA_DIR[x] for x in (EAST if g in EAST else WEST)}
        if got != want:
            grp.append(f"{g}命 吉方 {sorted(got)} ≠ {sorted(want)}")
    print(f"三 · 東四／西四：8 個命卦 · 唔符合 {len(grp)} 個")
    for x in grp:
        print("   ", x)
    fails += len(grp)

    print("\n" + ("✓ 通過" if fails == 0 else f"✗ 唔通過（{fails}）"))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
