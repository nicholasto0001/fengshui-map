"""同一個獨立實作對幾千個盤。

六個個案對得上，證明唔到乜 —— 錯得啱啱好避開嗰六個係好容易嘅事。所以
攞 lunar-python（中文世界用得最多嗰個曆法庫，同我哋完全獨立寫）嚟對,
隨機抽幾千個出生時刻，逐個柱比。

對唔上嗰啲要逐個解釋得到係咩原因，唔可以當「差不多」。
"""
from __future__ import annotations

import collections
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from chart import ZI_HOUR_NEW, build          # noqa: E402

try:
    from lunar_python import Solar
except ImportError:
    raise SystemExit("要裝 lunar-python 先：pip install lunar-python")


def ref(y, m, d, hh, mm):
    e = Solar.fromYmdHms(y, m, d, hh, mm, 0).getLunar().getEightChar()
    return f"{e.getYear()} {e.getMonth()} {e.getDay()} {e.getTime()}"


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    rng = random.Random(20260921)
    bad = collections.Counter()
    samples = collections.defaultdict(list)
    checked = 0

    for _ in range(n):
        y = rng.randint(1901, 2100)
        m = rng.randint(1, 12)
        d = rng.randint(1, 28)
        hh = rng.randint(0, 23)
        mm = rng.randint(0, 59)
        # 唔校正真太陽時：lunar-python 係照鐘面時間排，要比就要同一個基準。
        # 用 lunar-python 嗰個門派嚟比，先至比得到計算本身 —— 用唔同門派
        # 去比，得出嚟嘅只係「門派唔同」，證明唔到邊度計錯。
        mine = build(y, m, d, hh, mm, true_solar=False, zi=ZI_HOUR_NEW)
        r = ref(y, m, d, hh, mm)
        checked += 1
        a, b = mine.pillars, r.split()
        for k, name in enumerate(("年", "月", "日", "時")):
            if a[k] != b[k]:
                bad[name] += 1
                if len(samples[name]) < 6:
                    samples[name].append(
                        f"{y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}  "
                        f"我哋 {' '.join(a)}  |  lunar-python {r}")

    print(f"對照 {checked:,} 個出生時刻（1901–2100，隨機）")
    print(f"{'柱':<4}{'唔同':>8}{'比例':>10}")
    print("─" * 24)
    for name in ("年", "月", "日", "時"):
        print(f"{name}柱{bad[name]:>8}{100*bad[name]/checked:>9.2f}%")
    for name in ("年", "月", "日", "時"):
        if samples[name]:
            print(f"\n{name}柱唔同嘅例子：")
            for s in samples[name]:
                print("   ", s)
    total = sum(bad.values())
    print("\n" + ("✓ 全部一致" if total == 0 else f"✗ 共 {total} 個柱唔同"))
    return 0 if total == 0 else 1


if __name__ == "__main__" and "--edges" not in sys.argv:
    sys.exit(main())


def edges() -> int:
    """節氣界線前後一分鐘。

    隨機抽樣撞唔中呢啲位：一年得十二個換月柱嘅時刻，每個得一分鐘闊。
    但生喺嗰一刻嘅人係真實存在嘅，而且佢哋先係最易排錯嗰批。
    """
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from astro import TERMS, term_hkt
    from chart import JIE_INDEX, ZI_HOUR_NEW

    bad, warned, checked = [], [], 0
    for year in range(1901, 2101):
        for k in JIE_INDEX:
            ty, tm, td, tmin = term_hkt(year, k)
            for delta in (-1, 0, +1):
                t = tmin + delta
                if not 0 <= t < 1440:          # 跨日嘅留返俾隨機抽樣
                    continue
                hh, mm = divmod(t, 60)
                mine = build(ty, tm, td, hh, mm,
                             true_solar=False, zi=ZI_HOUR_NEW)
                r = ref(ty, tm, td, hh, mm)
                checked += 1
                if " ".join(mine.pillars) != r:
                    flagged = any("⚠" in n for n in mine.notes)
                    (warned if flagged else bad).append(
                        f"{ty}-{tm:02d}-{td:02d} {hh:02d}:{mm:02d} "
                        f"({TERMS[k]}{delta:+d}分) 我哋 {mine} | 參考 {r}")

    # 合格線唔係「同 lunar-python 一模一樣」。喺節氣嗰一分鐘，兩邊都冇
    # 權威性 —— 我哋嘅節氣準到大約一分鐘，人哋嗰個都係計出嚟。真正要求
    # 係：有分歧嘅個案，我哋一定要自己講咗「呢個位唔肯定」。
    print(f"\n節氣界線：{checked:,} 個時刻（每個節前後一分鐘）")
    print(f"   同參考唔同 {len(warned) + len(bad)} 個")
    print(f"   其中我哋有標示「唔肯定」 {len(warned)} 個")
    print(f"   冇標示就唔同咗 {len(bad)} 個  ← 呢個先係唔合格")
    for b in bad[:8]:
        print("   ", b)
    return len(bad)


if __name__ == "__main__" and "--edges" in sys.argv:
    sys.exit(1 if edges() else 0)
