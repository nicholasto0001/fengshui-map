"""玄空飛星 — Xuan Kong Flying Star chart construction.

This is the "理氣" half that the 2023 reference layer left out entirely
(see docs/fengshui-logic.md). Given a building's construction period and its
facing direction in degrees, it builds the full three-layer chart:

    運盤 period chart  → 山星 mountain stars + 向星 facing stars

and classifies the result into the four classical outcomes.

Everything here is the deterministic classical algorithm. No judgement calls
except one documented ambiguity (the 5 star, see YIN_YANG_FOR_5 below).

Self-test: `python3 pipeline/flyingstar.py`
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# The nine palaces, in Luoshu flight order starting from the centre.
#   中 → 乾NW → 兌W → 艮NE → 離S → 坎N → 坤SW → 震E → 巽SE
# ---------------------------------------------------------------------------
FLIGHT_ORDER = ["C", "NW", "W", "NE", "S", "N", "SW", "E", "SE"]

# Each star's home palace in the Luoshu square.
STAR_HOME = {1: "N", 2: "SW", 3: "E", 4: "SE", 5: "C", 6: "NW", 7: "W", 8: "NE", 9: "S"}

PALACE_TC = {"C": "中宮", "N": "坎北", "NE": "艮東北", "E": "震東", "SE": "巽東南",
             "S": "離南", "SW": "坤西南", "W": "兌西", "NW": "乾西北"}

# ---------------------------------------------------------------------------
# 二十四山. 24 sectors of 15°, 子 centred on due north (0°).
# Each entry: (name, palace, 元龍 index 0=地元 1=天元 2=人元, yang?)
# 陽 → 順飛 (forward), 陰 → 逆飛 (reverse).
# ---------------------------------------------------------------------------
MOUNTAINS = [
    ("壬", "N",  0, True),  ("子", "N",  1, False), ("癸", "N",  2, False),
    ("丑", "NE", 0, False), ("艮", "NE", 1, True),  ("寅", "NE", 2, True),
    ("甲", "E",  0, True),  ("卯", "E",  1, False), ("乙", "E",  2, False),
    ("辰", "SE", 0, False), ("巽", "SE", 1, True),  ("巳", "SE", 2, True),
    ("丙", "S",  0, True),  ("午", "S",  1, False), ("丁", "S",  2, False),
    ("未", "SW", 0, False), ("坤", "SW", 1, True),  ("申", "SW", 2, True),
    ("庚", "W",  0, True),  ("酉", "W",  1, False), ("辛", "W",  2, False),
    ("戌", "NW", 0, False), ("乾", "NW", 1, True),  ("亥", "NW", 2, True),
]

# palace -> its three mountains, indexed by 元龍
BY_PALACE: dict[str, list[tuple]] = {}
for m in MOUNTAINS:
    BY_PALACE.setdefault(m[1], []).append(m)
for v in BY_PALACE.values():
    v.sort(key=lambda t: t[2])

OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E",
            "NE": "SW", "SW": "NE", "SE": "NW", "NW": "SE"}

# 三元九運 periods
PERIODS = [(1864, 1883, 1), (1884, 1903, 2), (1904, 1923, 3), (1924, 1943, 4),
           (1944, 1963, 5), (1964, 1983, 6), (1984, 2003, 7), (2004, 2023, 8),
           (2024, 2043, 9)]

# The 5 star has no palace of its own, so it has no 元龍 and no intrinsic
# yin/yang. Schools disagree on what to substitute. We use the most common
# practical rule: 5 borrows the yin/yang of the actual 坐山 / 向首 mountain.
# Documented here rather than buried, because it does change some charts.
YIN_YANG_FOR_5 = "use_sitting_or_facing_mountain"


def period_for_year(year: int) -> int:
    for lo, hi, p in PERIODS:
        if lo <= year <= hi:
            return p
    raise ValueError(f"year {year} outside the 1864-2043 三元九運 table")


def mountain_for_degrees(deg: float) -> tuple[str, str, int, bool]:
    """Compass bearing (0 = north, clockwise) -> the 24-mountain sector it falls in.

    子 is centred on due north, so the list's first entry 壬 is centred on 345°.
    """
    idx = int(((deg + 22.5) % 360) // 15) % 24
    return MOUNTAINS[idx]


def _fly(center: int, forward: bool) -> dict[str, int]:
    """Place `center` in the middle and fly through the nine palaces."""
    chart = {}
    for step, palace in enumerate(FLIGHT_ORDER):
        n = center + step if forward else center - step
        chart[palace] = (n - 1) % 9 + 1
    return chart


def _direction_for_star(star: int, yuan: int, fallback_yang: bool) -> bool:
    """Is this star's flight forward? Decided by the yin/yang of the mountain
    occupying the same 元龍 slot in the star's own home palace."""
    home = STAR_HOME[star]
    if home == "C":                      # star 5 — see YIN_YANG_FOR_5
        return fallback_yang
    return BY_PALACE[home][yuan][3]


def chart(year: int, facing_deg: float) -> dict:
    """Build the full flying star chart.

    year        建成年份 (occupation permit year)
    facing_deg  向 — the direction the building faces, degrees from north
    """
    period = period_for_year(year)

    face_m = mountain_for_degrees(facing_deg)
    sit_m = mountain_for_degrees(facing_deg + 180)
    face_palace, sit_palace = face_m[1], sit_m[1]
    yuan = face_m[2]                      # 坐 and 向 always share the same 元龍

    period_chart = _fly(period, True)

    sit_star = period_chart[sit_palace]
    face_star = period_chart[face_palace]

    mountain_chart = _fly(sit_star, _direction_for_star(sit_star, yuan, sit_m[3]))
    facing_chart = _fly(face_star, _direction_for_star(face_star, yuan, face_m[3]))

    return {
        "period": period,
        "sitting": sit_m[0], "facing": face_m[0],
        "sit_palace": sit_palace, "face_palace": face_palace,
        "yuan": ["地元", "天元", "人元"][yuan],
        "period_chart": period_chart,
        "mountain_chart": mountain_chart,
        "facing_chart": facing_chart,
        "pattern": classify(period, sit_palace, face_palace, mountain_chart, facing_chart),
    }


def classify(period: int, sit_palace: str, face_palace: str,
             mountain_chart: dict, facing_chart: dict) -> dict:
    """The four classical outcomes, judged on where the current period's star lands."""
    m_at_sit = mountain_chart[sit_palace] == period
    m_at_face = mountain_chart[face_palace] == period
    f_at_face = facing_chart[face_palace] == period
    f_at_sit = facing_chart[sit_palace] == period

    if m_at_sit and f_at_face:
        return {"code": "旺山旺向", "meaning": "丁財兩旺", "rank": 1}
    if m_at_face and f_at_sit:
        return {"code": "上山下水", "meaning": "損丁破財", "rank": 4}
    if m_at_face and f_at_face:
        return {"code": "雙星到向", "meaning": "旺財不旺丁", "rank": 2}
    if m_at_sit and f_at_sit:
        return {"code": "雙星到坐", "meaning": "旺丁不旺財", "rank": 3}
    return {"code": "其他", "meaning": "非四大格局", "rank": 3}


def render(c: dict) -> str:
    """Print the chart as a 3x3 grid, south at top (Chinese convention)."""
    grid = [["SE", "S", "SW"], ["E", "C", "W"], ["NE", "N", "NW"]]
    lines = [f"{c['period']}運 {c['sitting']}山{c['facing']}向 ({c['yuan']}龍) — "
             f"{c['pattern']['code']}・{c['pattern']['meaning']}"]
    for row in grid:
        cells = []
        for p in row:
            m = c["mountain_chart"][p]
            f = c["facing_chart"][p]
            r = c["period_chart"][p]
            cells.append(f"{m} {f}\n {r} ".center(9))
        top = " | ".join(x.split("\n")[0].center(9) for x in cells)
        bot = " | ".join(x.split("\n")[1].center(9) for x in cells)
        lines += [top, bot, "-" * 33]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test against charts that are documented in the standard literature.
# ---------------------------------------------------------------------------
def _selftest() -> None:
    # Expectations below are the charts published in the standard literature.
    # The 八運 and 七運 旺山旺向 / 上山下水 sets are the strongest check available:
    # both reproduce exactly (八運 丑未·未丑·巽乾·乾巽·巳亥·亥巳;
    # 七運 卯酉·酉卯·乙辛·辛乙·辰戌·戌辰).
    cases = [
        # (year, facing degrees, 坐, 向, expected pattern)
        (2010, 180.0, "子", "午", "雙星到向"),   # 八運 子山午向 — 雙星會向
        (2010, 210.0, "丑", "未", "旺山旺向"),   # 八運 丑山未向
        (2010, 225.0, "艮", "坤", "上山下水"),   # 八運 艮山坤向
        (1995, 270.0, "卯", "酉", "旺山旺向"),   # 七運 卯山酉向
        (2030, 180.0, "子", "午", "雙星到坐"),   # 九運 子山午向
    ]
    failures = 0
    for year, deg, sit, face, expected in cases:
        c = chart(year, deg)
        ok = (c["sitting"] == sit and c["facing"] == face
              and c["pattern"]["code"] == expected)
        print(("PASS " if ok else "FAIL ") +
              f"{c['period']}運 {c['sitting']}山{c['facing']}向 -> "
              f"{c['pattern']['code']} (expected {expected})")
        if not ok:
            failures += 1
    print()
    print(render(chart(2030, 180.0)))
    print()
    print(render(chart(2010, 180.0)))
    if failures:
        raise SystemExit(f"{failures} case(s) failed")


if __name__ == "__main__":
    _selftest()
