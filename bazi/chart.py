"""四柱八字排盤。

冇一步係判斷，全部都係算術 —— 所以寫得出程式就一定計得啱，問題只係
邊個慣例。慣例有幾處唔同門派有唔同做法，全部喺下面寫明，而且做成選項,
唔好靜靜雞揀一個當係標準。

要小心嗰四處：
  1. 年柱喺立春轉，唔係年初一，亦唔係一月一日
  2. 月柱喺十二個「節」轉，唔係初一
  3. 真太陽時 —— 香港喺東經 114.17°，用緊東經 120° 嘅時區，差 23 分鐘
  4. 夜晚 11 點到 12 點（晚子時）—— 呢個係門派分歧，冇「啱」嘅答案
"""
from __future__ import annotations

import math
import pathlib
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from astro import (RAD, cal_from, delta_t, jd_from,  # noqa: E402
                   solar_longitude, term_hkt, term_jd_hkt)

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_WUXING = "木木火火土土金金水水"
ZHI_WUXING = "水土木木土火火土金金土水"
GAN_YINYANG = "陽陰陽陰陽陰陽陰陽陰"

# 月支由寅起（立春後係寅月），對應十二個「節」。
JIE_INDEX = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]   # 喺 astro.TERMS 入面
JIE_NAME = ["立春", "驚蟄", "清明", "立夏", "芒種", "小暑",
            "立秋", "白露", "寒露", "立冬", "大雪", "小寒"]

HK_LON = 114.1694          # 香港天文台


def gz(i: int) -> str:
    return GAN[i % 10] + ZHI[i % 12]


def equation_of_time(jde: float) -> float:
    """均時差（分鐘）。真太陽時同平太陽時嘅差，一年入面由 -14 到 +16 分鐘。"""
    t = (jde - 2451545.0) / 36525.0
    l0 = (280.46646 + 36000.76983 * t + 0.0003032 * t * t) % 360
    m = (357.52911 + 35999.05029 * t - 0.0001537 * t * t) * RAD
    e = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t
    eps = 23.439291 - 0.0130042 * t
    y = math.tan(eps / 2 * RAD) ** 2
    eot = (y * math.sin(2 * l0 * RAD)
           - 2 * e * math.sin(m)
           + 4 * e * y * math.sin(m) * math.cos(2 * l0 * RAD)
           - 0.5 * y * y * math.sin(4 * l0 * RAD)
           - 1.25 * e * e * math.sin(2 * m))
    return math.degrees(eot) * 4.0


@dataclass
class Chart:
    year: str
    month: str
    day: str
    hour: str
    solar: str          # 用嚟排盤嗰個時刻（可能已經校正過真太陽時）
    notes: list
    bazi_year: int      # 立春為界嘅年份 —— 命卦要用呢個，唔係公曆年

    @property
    def pillars(self):
        return [self.year, self.month, self.day, self.hour]

    def __str__(self):
        return " ".join(self.pillars)


# 夜晚 11 點到 12 點（晚子時）點算，三個實作三個答案。呢個唔係邊個計錯,
# 係門派分歧，而各家軟件靜靜雞揀咗一個都唔講。實測：
#
#   ZI_NEW_DAY  日柱轉下一日、時柱跟下一日   —— 大陸多數排盤軟件
#   ZI_SAME     日柱留當日、時柱跟當日       —— bz.superd.org
#   ZI_HOUR_NEW 日柱留當日、時柱跟下一日     —— lunar-python
#
# 影響嘅人：出生時間喺 23:00–23:59 嗰啲，即係二十四分一。
ZI_NEW_DAY = "next_day"
ZI_SAME = "same_day"
ZI_HOUR_NEW = "hour_next"


def build(y: int, m: int, d: int, hh: int, mm: int = 0, *,
          lon: float = HK_LON, true_solar: bool = False,
          zi: str = ZI_NEW_DAY) -> Chart:
    """排一個盤。

    lon                出生地經度（東經為正）。香港 114.17°。
    true_solar         要唔要校正真太陽時。預設唔校正。

                       香港喺東經 114.17°，用緊東經 120° 嘅時區，差 23
                       分鐘；加埋均時差，最多差 39 分鐘。一個時辰兩個鐘,
                       所以呢個夠令生喺時辰頭尾嘅人換咗成個時柱。

                       但我哋核對過嘅排盤網同 lunar-python 全部都冇校正,
                       傳統師傅亦都有人校有人唔校。預設跟返市面做法，令
                       用戶攞去第二度對得返；同時用 alt_hour() 講返「按
                       真太陽時會係另一個時柱」，等佢知道有呢回事。
    zi                 23:00–23:59 點算。見上面三個常數。
    """
    notes = []

    # ---- 真太陽時 ----
    jd_local = jd_from(y, m, d + (hh * 60 + mm) / 1440.0)
    jd_ut = jd_local - 8.0 / 24.0                    # 香港時區
    shift = 0.0
    if true_solar:
        lon_min = (lon - 120.0) * 4.0                # 每度 4 分鐘
        eot = equation_of_time(jd_ut + delta_t(y) / 86400.0)
        shift = lon_min + eot
        notes.append(f"真太陽時校正 {shift:+.1f} 分鐘"
                     f"（經度 {lon_min:+.1f}、均時差 {eot:+.1f}）")
    tmin = hh * 60 + mm + shift
    sday = d
    while tmin < 0:
        tmin += 1440
        sday -= 1
    while tmin >= 1440:
        tmin -= 1440
        sday += 1
    sy, smo, sd = cal_from(jd_from(y, m, sday + 0.5))
    sd = int(math.floor(sd))
    sh, smi = int(tmin // 60), int(tmin % 60)

    # 排盤時刻嘅儒略日（校正後）。界線一律用呢個比，精度到秒。
    now_jd = jd_from(sy, smo, sd + (sh * 60 + smi) / 1440.0)
    # 我哋嘅節氣準到大約一分鐘（對過天文台 220 個時刻，最大差一分鐘）,
    # 所以界線兩分鐘之內唔可以扮肯定。
    UNSURE = 2.0 / 1440.0

    # ---- 年柱：立春為界 ----
    li_jd = term_jd_hkt(sy, 0)                       # 今年嘅立春
    bazi_year = sy if now_jd >= li_jd else sy - 1
    ly, lm, ld, lmin = term_hkt(sy, 0)
    ypil = (bazi_year - 4) % 60
    if (smo, sd) == (lm, ld):
        notes.append(f"生喺立春當日（{lm:02d}-{ld:02d} "
                     f"{lmin//60:02d}:{lmin%60:02d}），年柱按時刻分")
    if abs(now_jd - li_jd) < UNSURE:
        notes.append("⚠ 出生時間喺立春前後兩分鐘之內。我哋嘅節氣準到大約"
                     "一分鐘，所以呢個年柱唔夠肯定，請搵師傅確認")

    # ---- 月柱：十二個節為界 ----
    # 由出生年嘅立春起逐個節比，搵出喺邊個月令。
    mi = None
    for k in range(12):
        if term_jd_hkt(bazi_year, JIE_INDEX[k]) <= now_jd:
            mi = k
        else:
            break
    if mi is None:
        mi = 11
    zhi_m = (2 + mi) % 12                            # 寅 = 2
    # 五虎遁：甲己之年丙作首
    gan_m = ((bazi_year - 4) % 10 % 5 * 2 + 2 + mi) % 10
    mpil = None
    for i in range(60):
        if i % 10 == gan_m and i % 12 == zhi_m:
            mpil = i
            break
    ty, tm, td, tmn = term_hkt(bazi_year, JIE_INDEX[mi])
    if (tm, td) == (smo, sd):
        notes.append(f"生喺{JIE_NAME[mi]}當日（{tm:02d}-{td:02d} "
                     f"{tmn//60:02d}:{tmn%60:02d}），月柱按時刻分")
    for k in range(12):
        if abs(now_jd - term_jd_hkt(bazi_year, JIE_INDEX[k])) < UNSURE:
            notes.append(f"⚠ 出生時間喺{JIE_NAME[k]}前後兩分鐘之內，"
                         f"月柱唔夠肯定，請搵師傅確認")
            break

    # ---- 日柱：連續六十日循環 ----
    # jd_from(y, m, d+0.5) 已經係嗰日中午嘅儒略日，即係 JDN 本身。
    # 之前多加咗個 1，成個日柱早咗一日 —— 而排出嚟個盤照樣似模似樣,
    # 所以淨係睇輸出係睇唔出嚟嘅，要同外面對先知。
    jdn = int(math.floor(jd_from(sy, smo, sd + 0.5)))
    day_i = (jdn + 49) % 60
    zi_late = sh == 23
    hour_stem_day = day_i
    if zi_late:
        if zi == ZI_NEW_DAY:
            day_i = hour_stem_day = (day_i + 1) % 60
            notes.append("晚子時：日柱同時柱都算下一日（子時起新日）")
        elif zi == ZI_HOUR_NEW:
            hour_stem_day = (day_i + 1) % 60
            notes.append("晚子時：日柱留當日，時柱天干跟下一日")
        else:
            notes.append("晚子時：日柱同時柱都留當日")
        notes.append("⚠ 23:00–23:59 出世，三個門派三個答案，呢個盤用咗上面嗰個")

    # ---- 時柱：五鼠遁 ----
    zhi_h = ((sh + 1) // 2) % 12
    gan_h = (hour_stem_day % 10 % 5 * 2 + zhi_h) % 10
    hpil = None
    for i in range(60):
        if i % 10 == gan_h and i % 12 == zhi_h:
            hpil = i
            break

    return Chart(gz(ypil), gz(mpil), gz(day_i), gz(hpil),
                 f"{sy}-{smo:02d}-{sd:02d} {sh:02d}:{smi:02d}", notes, bazi_year)


def alt_hour(y: int, m: int, d: int, hh: int, mm: int = 0, *,
             lon: float = HK_LON, zi: str = ZI_NEW_DAY):
    """按真太陽時會唔會係另一個時柱？係就回傳 (另一個時柱, 校正咗幾多分鐘)。

    預設唔校正，但唔講就等於扮咗呢件事唔存在。生喺時辰頭尾嘅人應該知道
    自己踩喺界線上。
    """
    a = build(y, m, d, hh, mm, lon=lon, true_solar=False, zi=zi)
    b = build(y, m, d, hh, mm, lon=lon, true_solar=True, zi=zi)
    if a.hour == b.hour and a.day == b.day:
        return None
    mins = next((n for n in b.notes if "真太陽時校正" in n), "")
    return b, mins
