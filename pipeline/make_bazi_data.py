"""前端要用嘅節氣表。

點解唔喺瀏覽器度計：VSOP87 嗰條級數已經對住天文台 4,800 個節氣日期同
220 個時刻驗過。搬去 JavaScript 重寫一次，等於重新開一次打錯數字嘅機會,
而嗰種錯係睇代碼睇唔出嘅。所以計一次，出表，前端淨係查表。

出嘅係換月柱嗰十二個「節」（立春排頭，佢同時係年柱嘅界線）。
「氣」（雨水、春分嗰啲）唔換柱，所以唔使出。

每個值係「由 1900-01-01 00:00 香港時間起計嘅分鐘數」—— 一個整數，
前端將出生時間轉成同一個尺度就直接比得到，唔使喺瀏覽器度做曆法運算。

Output: data/solar_terms.json
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "bazi"))
from astro import jd_from, term_jd_hkt  # noqa: E402

OUT = ROOT / "data" / "solar_terms.json"
Y0, Y1 = 1900, 2100
JIE = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]   # astro.TERMS 入面嘅節
EPOCH = jd_from(1900, 1, 1.0)                        # 1900-01-01 00:00 香港時間


def main() -> None:
    flat = []
    for y in range(Y0, Y1 + 1):
        for k in JIE:
            # 四捨五入到分鐘：我哋嘅節氣準到大約一分鐘，再細就係虛假精度。
            flat.append(round((term_jd_hkt(y, k) - EPOCH) * 1440.0))

    # 必須遞增 —— 如果有一個位倒退，即係算錯咗，而前端搵月令嗰個迴圈
    # 會靜靜雞畀錯答案。
    bad = [i for i in range(1, len(flat)) if flat[i] <= flat[i - 1]]
    if bad:
        raise SystemExit(f"節氣時刻唔係遞增，第 {bad[:5]} 個位有問題")

    # 差分存，細好多：相鄰兩個節相差大約 44,000 分鐘（五位數），
    # 原值係九位數。
    deltas = [flat[0]] + [flat[i] - flat[i - 1] for i in range(1, len(flat))]
    OUT.write_text(json.dumps({"y0": Y0, "y1": Y1, "n": len(JIE), "d": deltas},
                              separators=(",", ":")))
    span = (flat[-1] - flat[0]) / 1440 / 365.25
    print(f"{len(flat):,} 個節（{Y0}–{Y1}，每年 {len(JIE)} 個）· 橫跨 {span:.0f} 年")
    print(f"-> {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
