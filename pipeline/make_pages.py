"""屋苑頁同區頁 —— 俾 Google 睇嘅版本。

我哋計咗 84,720 幢樓，但全部收喺一個 JavaScript 地圖入面。有人 search
「長安邨 風水」，我哋根本冇一版嘢畀佢搵到。呢個檔案就係將已經有嘅數據
印出嚟。

刻意唔逐幢樓開版。84,720 版套同一個模係 Google 2026 年 scaled content
abuse 嘅教科書定義，會全站降權。18 區 + 540 個屋苑 = 558 版，每版嘅表、
數字、排名都完全唔同 —— 呢個係「資料庫出頁」，同天文台逐區一版同一性質。

一個字都唔係寫出嚟嘅。每個數要嘛喺 scores.json，要嘛喺人口普查。

Output: pages/district/*.html, pages/estate/*.html
"""
from __future__ import annotations

import collections
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import census                                    # noqa: E402
from build_tiles import is_dwelling, keep        # noqa: E402

OUT = ROOT / "pages"
SITE = "https://hkfengshuimap.com"


def side(path, default):
    """額外數據唔應該搞冧主要內容。攞唔到就當冇，照出頁。"""
    f = ROOT / path
    if not f.exists():
        print(f"  （冇 {path}，呢部分跳過）")
        return default
    return json.loads(f.read_text())

BREAKS = [41, 46, 52, 58]
LABELS = ["差", "欠佳", "平穩", "吉", "大吉"]
TONE = ["s1", "s2", "s3", "s4", "s5"]

# 每個代碼都用數據本身驗證過，唔係靠估：
#   t_pop = age_1..5 之和（540/540 完全一致）
#   adhz  = t_pop / dh（528/540 喺四捨五入誤差內）
#   dhz_1..6 之和 = dh（490/490）
#   年齡分佈同 2021 全港吻合；fa_m 由寶田邨 12㎡ 到康樂園 148㎡
AGES = [("age_1", "0–14 歲"), ("age_2", "15–24 歲"), ("age_3", "25–44 歲"),
        ("age_4", "45–64 歲"), ("age_5", "65 歲以上")]
SIZES = [("dhz_1", "1 人"), ("dhz_2", "2 人"), ("dhz_3", "3 人"),
         ("dhz_4", "4 人"), ("dhz_5", "5 人"), ("dhz_6", "6 人或以上")]

e = lambda s: html.escape(str(s if s is not None else ""))
n = lambda v: f"{v:,.0f}"


def band(v):
    i = next((i for i, b in enumerate(BREAKS) if v < b), len(BREAKS))
    return LABELS[i], TONE[i]


def num(s, k):
    v = s.get(k)
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------- 版面 ---
CSS = """
:root{color-scheme:light;
 --bg:#f4f3f0;--card:#fff;--line:#e3e2dd;--ink:#0b0b0b;--ink2:#55534e;--ink3:#86847d;
 --brand:#1b4f8f;--s1:#a01f1f;--s2:#d76f6f;--s3:#b4ad97;--s4:#4da79a;--s5:#0f6354}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang HK",
 "Hiragino Sans CNS","Microsoft JhengHei",sans-serif;-webkit-text-size-adjust:100%}
.wrap{max-width:820px;margin:0 auto;padding:0 16px 64px}
header.bar{position:sticky;top:0;z-index:5;background:rgba(244,243,240,.92);
 backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--line)}
header.bar .wrap{display:flex;align-items:center;gap:10px;padding:10px 16px;min-height:52px}
header.bar a.home{display:flex;align-items:center;gap:8px;color:var(--ink);
 text-decoration:none;font-weight:650;font-size:16px;white-space:nowrap;flex:none}
header.bar img{width:26px;height:26px;border-radius:6px}
header.bar .go{margin-inline-start:auto;background:var(--brand);color:#fff;
 text-decoration:none;font-size:14.5px;font-weight:650;padding:9px 15px;
 border-radius:999px;white-space:nowrap;flex:none}
nav.crumb{font-size:13.5px;color:var(--ink3);margin:18px 0 6px}
nav.crumb a{color:var(--ink3)}
h1{font-size:30px;line-height:1.25;letter-spacing:-.022em;margin:0 0 6px}
.sub{color:var(--ink2);font-size:16px;margin:0 0 22px}
.hero{display:flex;align-items:center;gap:18px;background:var(--card);
 border:1px solid var(--line);border-radius:16px;padding:18px 20px;margin:0 0 26px}
.big{font-size:44px;font-weight:700;letter-spacing:-.03em;line-height:1;font-variant-numeric:tabular-nums}
.pill{display:inline-block;color:#fff;font-size:13px;font-weight:700;
 padding:3px 11px;border-radius:999px;margin-bottom:5px}
.hero .rk{color:var(--ink2);font-size:15px;line-height:1.5}
h2{font-size:21px;letter-spacing:-.015em;margin:34px 0 4px}
h2+p.note{color:var(--ink3);font-size:14px;margin:0 0 14px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;
 background:var(--card);border:1px solid var(--line);border-radius:16px}
table{border-collapse:collapse;width:100%;font-size:15px}
th,td{padding:11px 13px;text-align:start;white-space:nowrap;border-bottom:1px solid var(--line)}
th{font-size:12.5px;font-weight:650;color:var(--ink3);letter-spacing:.03em;
 background:var(--card);position:sticky;top:0}
tr:last-child td{border-bottom:0}
td.sc{font-weight:700;font-variant-numeric:tabular-nums}
td.nm{font-weight:600}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-inline-end:7px;vertical-align:-1px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kv{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:13px 15px}
.kv b{display:block;font-size:21px;font-weight:700;letter-spacing:-.02em;
 font-variant-numeric:tabular-nums;line-height:1.3}
.kv span{font-size:13px;color:var(--ink3)}
.bars{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.bar{display:grid;grid-template-columns:86px 1fr 62px;align-items:center;gap:10px;margin:0 0 9px;font-size:14.5px}
.bar:last-child{margin:0}
.bar i{display:block;height:9px;border-radius:5px;background:var(--brand);opacity:.82}
.bar em{font-style:normal;color:var(--ink3);text-align:end;font-variant-numeric:tabular-nums}
.bar u{text-decoration:none;color:var(--ink2)}
.track{background:var(--line);border-radius:5px}
ul.links{list-style:none;padding:0;margin:0;display:grid;
 grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px}
ul.links a{display:flex;justify-content:space-between;gap:10px;align-items:baseline;
 background:var(--card);border:1px solid var(--line);border-radius:12px;
 padding:11px 14px;text-decoration:none;color:var(--ink);font-size:15px;font-weight:550}
ul.links a b{font-variant-numeric:tabular-nums;font-size:15px}
figure.plan{margin:22px 0 0}
.pw{position:relative;border-radius:16px;overflow:hidden;border:1px solid var(--line);
 background:#dfddd6;line-height:0}
.pw img{width:100%;height:auto;display:block}
.pl{position:absolute;transform:translate(-50%,-50%);white-space:nowrap;
 background:rgba(0,0,0,.62);color:#fff;font-size:12px;font-weight:600;
 padding:3px 7px;border-radius:6px;line-height:1.4;letter-spacing:.01em}
.pl b{margin-inline-start:5px;font-variant-numeric:tabular-nums}
.sc-m{position:absolute;left:18px;bottom:44px;color:#fff;font-size:11.5px;
 font-weight:600;text-shadow:0 1px 3px rgba(0,0,0,.9)}
.nn{position:absolute;right:26px;top:56px;color:#fff;font-size:11px;
 font-weight:700;text-shadow:0 1px 3px rgba(0,0,0,.9);transform:translateX(50%)}
figure.plan figcaption{font-size:13px;color:var(--ink3);margin:9px 2px 0;line-height:1.6}
figure.plan i{display:inline-block;width:10px;height:10px;border-radius:3px;
 vertical-align:-1px;margin:0 2px}
table.kvt th{width:36%;color:var(--ink3);font-weight:600;background:transparent;position:static}
table.kvt td{white-space:normal;font-weight:550}
.mkt{display:flex;align-items:flex-end;gap:3px;height:74px;margin:6px 0 0}
.mkt span{flex:1;background:var(--brand);opacity:.72;border-radius:3px 3px 0 0;min-height:2px}
.mkt span:last-child{opacity:1}
.cta{display:block;background:var(--brand);color:#fff;text-align:center;
 text-decoration:none;font-weight:650;font-size:17px;padding:16px;border-radius:14px;margin:30px 0 0}
.src{font-size:13px;color:var(--ink3);margin:10px 0 0;line-height:1.6}
footer{margin:40px 0 0;padding:20px 0 0;border-top:1px solid var(--line);
 font-size:13px;color:var(--ink3);line-height:1.7}
footer a{color:var(--ink2)}
.warn{background:#fff8ec;border:1px solid #f0dfbe;border-radius:14px;
 padding:14px 16px;font-size:14px;color:#6b5626;line-height:1.65;margin:26px 0 0}
@media(max-width:560px){h1{font-size:25px}.big{font-size:38px}.wrap{padding:0 14px 48px}}
"""


def shell(title, desc, canon, crumbs, body):
    trail = " › ".join(
        f'<a href="{u}">{e(t)}</a>' if u else e(t) for t, u in crumbs)
    ld = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": t,
             **({"item": SITE + u} if u else {})}
            for i, (t, u) in enumerate(crumbs)],
    }
    return f"""<!doctype html>
<html lang="zh-HK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{canon}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}{canon}">
<meta property="og:image" content="{SITE}/og.png">
<link rel="icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
</head>
<body>
<header class="bar"><div class="wrap">
  <a class="home" href="/"><img src="/icon-192.png" alt="">香港風水地圖</a>
  <a class="go" href="/">開地圖</a>
</div></header>
<div class="wrap">
<nav class="crumb">{trail}</nav>
{body}
<footer>
  <p>評分由電腦計算，數據嚟自政府公開資料。<a href="/method">計算方法同數據限制</a> ·
     <a href="/privacy.html">私隱政策</a> · <a href="/">返地圖</a></p>
  <p>人口統計數字：政府統計處《2021 年人口普查》，經「空間數據共享平台」發佈。
     樓宇資料：地政總署、屋宇署、香港房屋委員會。以上數據版權歸香港特別行政區政府所有。</p>
</footer>
</div>
</body>
</html>
"""


DISCLAIM = """<div class="warn">呢版嘅評分係<b>電腦計算</b>嘅結果，唔係風水師傅睇過。
坐向由樓宇外形推算，誤差大約 ±10–20°，唔係羅盤實測；分數只計得到山水方位、
坐向同周邊環境，計唔到單位入面嘅間隔、門口、爐灶、床位，亦冇夾你嘅八字。
認真睇樓請搵專業風水師傅。</div>"""


def plan_figure(name, rep):
    """屋苑平面圖。標籤係真 HTML 字，唔係燒落張圖 —— 揀得、放大唔矇、
    Google 讀得到，而且 CI 嗰邊唔使有中文字體。"""
    if not rep:
        return ""
    lab = "".join(
        f'<span class="pl" style="left:{l["x"]}%;top:{l["y"]}%">'
        f'{e(l["t"])}<b>{l["s"]:.0f}</b></span>' for l in rep.get("labels", []))
    alt = (f"{name}航空影像，{rep['blocks']} 座樓宇輪廓按風水評分上色，"
           f"綠色分高、紅色分低")
    return f"""<figure class="plan">
  <div class="pw"><img src="/plan/{e(name)}.jpg" alt="{e(alt)}"
       width="880" height="600" loading="lazy" decoding="async">{lab}
    <span class="sc-m">{rep.get('scale_m', 0)} 米</span><span class="nn">北</span></div>
  <figcaption>{e(name)} {rep['blocks']} 座嘅位置同座向。
    顏色係風水評分：<i style="background:var(--s5)"></i> 高 →
    <i style="background:var(--s1)"></i> 低。
    航空影像：地政總署。</figcaption>
</figure>"""


def meta_panel(m):
    """發展商、地址、落成 —— 中原同 28Hse 自己喺 data.gov.hk 出嘅開放數據。"""
    if not m:
        return ""
    kv = []
    if m.get("dev"):
        kv.append(("發展商", "、".join(m["dev"])))
    if m.get("dev_alt"):
        kv.append(("發展商（另一說法）", "、".join(m["dev_alt"])))
    if m.get("addr"):
        kv.append(("地址", m["addr"]))
    if m.get("year"):
        kv.append(("落成", f"{m['year']}–{m['year_to']}" if m.get("year_to")
                   else str(m["year"])))
    if m.get("blocks"):
        kv.append(("座數", f"{m['blocks']} 座"))
    if m.get("flats"):
        kv.append(("單位總數", f"{m['flats']:,} 伙"))
    if not kv:
        return ""
    rows = "".join(f'<tr><th>{e(a)}</th><td>{e(b)}</td></tr>' for a, b in kv)
    src = "、".join(m.get("src") or [])
    note = ("兩個來源講嘅發展商唔同，所以兩個都列出嚟。"
            if m.get("dev_alt") else "")
    return (f'<h2>屋苑資料</h2><p class="note">{e(src)}喺 data.gov.hk 發佈嘅'
            f'開放數據。{e(note)}</p>'
            f'<div class="tw"><table class="kvt"><tbody>{rows}</tbody></table></div>')


SCHEME = {"HOS": "居屋", "GSH": "綠置居", "EFAS": "白居二"}


def tx_panel(name, tx):
    """資助房屋成交。呢啲係土地註冊處以外唯一一批免費而且逐個單位嘅真
    成交價 —— 二手嗰啲要向土地註冊處買，我哋冇。

    居屋同綠置居唔可以溝埋計一個中位數：綠置居折扣深好多，長安邨嗰 53 宗
    入面 29 宗綠置居、24 宗居屋，溝埋出嚟嗰個數邊種都唔代表到。
    """
    if not tx:
        return ""
    # 房委會啲日期係 DD/MM/YYYY。照字串排就變咗先排「日」——
    # 出嚟個範圍會係「01/02/2023 至 31/01/2023」，開始遲過結束。
    def when(t):
        d = (t.get("date") or "").split("/")
        return (d[2], d[1], d[0]) if len(d) == 3 else ("", "", "")
    tx = sorted(tx, key=when, reverse=True)

    by = collections.defaultdict(list)
    for t in tx:
        by[t.get("scheme") or "—"].append(t)

    mid = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    rows = []
    for sc, g in sorted(by.items(), key=lambda kv: -len(kv[1])):
        ps = [t["price"] for t in g]
        per = [t["price"] / t["area"] for t in g if t.get("area")]
        rows.append(
            f'<tr><td class="nm">{e(SCHEME.get(sc, sc))}</td>'
            f'<td>{len(g):,} 宗</td>'
            f'<td class="sc">HK${mid(ps):,.0f}</td>'
            f'<td>HK${min(ps):,.0f} – {max(ps):,.0f}</td>'
            f'<td>{f"HK${mid(per):,.0f}" if per else "—"}</td></tr>')

    recent = "".join(
        f'<tr><td class="nm">{e(t["block"])}</td><td>{e(t["floor"])} 樓</td>'
        f'<td>{t["area"]:.1f} ㎡</td><td class="sc">HK${t["price"]:,.0f}</td>'
        f'<td>{e(SCHEME.get(t.get("scheme"), t.get("scheme") or "—"))}</td>'
        f'<td>{e(t["date"])}</td></tr>'
        for t in tx[:12] if t.get("area"))

    kinds = "、".join(SCHEME.get(k, k) for k in by)
    return (f'<h2>資助房屋成交紀錄</h2>'
            f'<p class="note">房屋委員會公開嘅銷售成交（{e(kinds)}），'
            f'{e(tx[-1].get("date",""))} 至 {e(tx[0].get("date",""))}。'
            f'呢啲係政府首次銷售價，唔係二手市價 —— 綠置居同居屋嘅折扣唔同，'
            f'所以分開列。</p>'
            f'<div class="tw"><table><thead><tr><th>計劃</th><th>宗數</th>'
            f'<th>成交價中位</th><th>最低 – 最高</th><th>每㎡中位</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            + (f'<div class="tw" style="margin-top:12px"><table><thead><tr>'
               f'<th>座</th><th>樓層</th><th>實用面積</th><th>成交價</th>'
               f'<th>計劃</th><th>日期</th></tr></thead><tbody>{recent}</tbody>'
               f'</table></div>' if recent else ""))


def blocks_table(rows):
    tr = []
    for r in rows:
        lbl, tone = band(r["total"])
        sit = (f'坐{r["sit_m"]}向{r["face_m"]}' if r.get("sit_m") else "—")
        tr.append(
            f'<tr><td class="nm">{e(r["tc"] or r["en"])}</td>'
            f'<td class="sc"><span class="dot" style="background:var(--{tone})"></span>'
            f'{r["total"]:.1f}</td><td>{lbl}</td><td>{sit}</td>'
            f'<td>{e(r.get("pattern") or "—")}</td><td>{e(r.get("now") or "—")}</td>'
            f'<td>{r["mt_d"]}m {e(r["mt_dir"])}</td><td>{r["wt_d"]}m {e(r["wt_dir"])}</td>'
            f'<td>{r.get("storeys") or "—"}</td></tr>')
    return ('<div class="tw"><table><thead><tr>'
            '<th>座</th><th>評分</th><th>等級</th><th>坐向</th><th>格局</th>'
            '<th>九運</th><th>最近山</th><th>最近水</th><th>層</th>'
            '</tr></thead><tbody>' + "".join(tr) + "</tbody></table></div>")


def bars(pairs, total):
    out = []
    top = max((v for _, v in pairs), default=1) or 1
    for lab, v in pairs:
        out.append(f'<div class="bar"><u>{e(lab)}</u>'
                   f'<span class="track"><i style="width:{100*v/top:.1f}%"></i></span>'
                   f'<em>{n(v)}　{100*v/total:.0f}%</em></div>')
    return '<div class="bars">' + "".join(out) + "</div>"


def census_panel(s):
    """人口普查嗰嚿。獨立一格、標明年份同來源，唔同風水評分溝埋一齊。"""
    kv = []
    add = lambda v, lab, f="{:,.0f}": kv.append(
        f'<div class="kv"><b>{f.format(v)}</b><span>{lab}</span></div>') if v else None
    add(num(s, "t_pop"), "人口")
    add(num(s, "dh"), "住戶數目")
    add(num(s, "adhz"), "平均住戶人數", "{:.1f}")
    add(num(s, "fa_m"), "單位面積中位數（㎡）")
    add(num(s, "ma_hh"), "住戶月入中位數（HK$）")
    add(num(s, "dm_r"), "月租中位數（HK$）")
    add(num(s, "dmr_ir"), "租金佔收入（%）", "{:.1f}")
    add(num(s, "dhm_lr"), "供樓佔收入（%）", "{:.1f}")
    if not kv:
        return ""
    out = [f'<h2>2021 年人口普查</h2><p class="note">政府統計處數字，'
           f'統計時點為 2021 年 6 至 8 月 —— 唔係今日嘅數。</p>'
           f'<div class="grid">{"".join(kv)}</div>']

    ages = [(lab, num(s, k)) for k, lab in AGES if num(s, k)]
    if ages:
        out.append('<h2>年齡分佈</h2><p class="note">2021 年人口普查</p>'
                   + bars(ages, sum(v for _, v in ages)))
    sz = [(lab, num(s, k)) for k, lab in SIZES if num(s, k)]
    if sz:
        out.append('<h2>住戶人數分佈</h2><p class="note">2021 年人口普查</p>'
                   + bars(sz, sum(v for _, v in sz)))

    born = [("喺香港出世", num(s, "born_hk")), ("內地／澳門／台灣", num(s, "born_chi")),
            ("其他地方", num(s, "born_else"))]
    born = [(a, b) for a, b in born if b]
    if born:
        out.append('<h2>出生地</h2><p class="note">2021 年人口普查</p>'
                   + bars(born, sum(v for _, v in born)))

    eth = [("華人", num(s, "ethn_chi")), ("菲律賓裔", num(s, "ethn_phi")),
           ("印尼裔", num(s, "ethn_ind")), ("白人", num(s, "ethn_wh")),
           ("其他", num(s, "ethn_oth"))]
    eth = [(a, b) for a, b in eth if b]
    if eth:
        out.append('<h2>族裔分佈</h2><p class="note">2021 年人口普查</p>'
                   + bars(eth, sum(v for _, v in eth)))
    return "".join(out)


# --------------------------------------------------------------- 數據 ---
def gather():
    """每幢樓歸邊個屋苑。分組規則喺 census.group()，只此一份 ——
    出頁同出圖都問佢，所以冇可能出現兩邊各有各叫法嘅情況。"""
    sc = [r for r in json.loads((ROOT / "data" / "scores.json").read_text()) if keep(r)]
    home = [r for r in sc if is_dwelling(r) and (r.get("tc") or r.get("en"))]
    ds = json.loads((ROOT / "data" / "district_stats.json").read_text())

    out = {}
    for name, g in census.group(home).items():
        rows = sorted(g["rows"], key=lambda r: -r["total"])
        cen = g["census"]
        out[name] = {
            "name": name, "stats": cen["stats"] if cen else {},
            "en": cen["en"] if cen else None, "ha": g["ha"],
            "rows": rows,
            "district": collections.Counter(
                r["district"] for r in rows).most_common(1)[0][0],
            "avg": sum(r["total"] for r in rows) / len(rows),
        }
    return sc, home, ds, out


# --------------------------------------------------------------- 出頁 ---
def estate_page(es, rank, total_est, siblings, extra):
    rows, nm = es["rows"], es["name"]
    lbl, tone = band(es["avg"])
    hi, lo = rows[0], rows[-1]
    spread = (f"同一個屋苑，最高 {hi['total']:.1f} 最低 {lo['total']:.1f}，"
              f"爭 {hi['total']-lo['total']:.1f} 分。"
              if len(rows) > 1 and hi["total"] - lo["total"] >= 1 else "")

    yr = next((r["op_year"] for r in rows if r.get("op_year")), None)
    st = es["stats"]
    facts = " · ".join(x for x in [
        es["district"], f"{yr} 年入伙" if yr else None,
        f"{len(rows)} 座",
        f"{n(num(st,'dh'))} 個住戶" if num(st, "dh") else None] if x)

    title = (f"{nm}風水評分 — {len(rows)} 座逐座坐向、格局、飛星盤｜香港風水地圖")
    desc = (f"{nm}（{es['district']}）風水平均 {es['avg']:.1f} 分，"
            f"{total_est} 個屋苑中排第 {rank}。逐座列出評分、坐向、四大格局、"
            f"九運飛星同最近山水距離"
            + ("、發展商同落成年份" if extra["meta"].get("dev") else "")
            + ("、資助房屋成交價" if extra["tx"] else "")
            + "，另附 2021 年人口普查資料。")

    sib = "".join(
        f'<li><a href="/estate/{e(s["name"])}">{e(s["name"])}<b>{s["avg"]:.1f}</b></a></li>'
        for s in siblings)

    body = f"""
<h1>{e(nm)}風水評分</h1>
<p class="sub">{e(facts)}</p>
{plan_figure(nm, extra["plan"])}

<div class="hero">
  <div><div class="big" style="color:var(--{tone})">{es['avg']:.1f}</div></div>
  <div>
    <span class="pill" style="background:var(--{tone})">{lbl}</span>
    <div class="rk">全港 {total_est} 個屋苑之中排第 <b>{rank}</b><br>
    平均分計，包括公營同私人屋苑</div>
  </div>
</div>

<h2>逐座評分</h2>
<p class="note">按評分由高至低排。{e(spread)}</p>
{blocks_table(rows)}

{meta_panel(extra["meta"])}

{census_panel(st)}

{tx_panel(nm, extra["tx"])}

{'<h2>同區其他屋苑</h2><p class="note">按平均分排</p><ul class="links">' + sib + '</ul>' if sib else ''}

<a class="cta" href="/">喺地圖睇{e(nm)} →</a>
{DISCLAIM}
"""
    crumbs = [("香港風水地圖", "/"), ("屋苑", "/estate/"),
              (es["district"], f"/district/{es['district']}"), (nm, None)]
    return shell(title, desc, f"/estate/{nm}", crumbs, body)


def market_panel(dname, mk):
    """土地註冊處嘅買賣合約宗數。

    佢自己嗰 10 個分區對唔正 18 個區議會分區，所以只有對得正嗰 7 個區
    先出呢一格。夾硬砌個對應出嚟，就係講咗一樣數據本身冇講過嘅嘢。
    """
    if not mk or not mk.get("landreg"):
        return ""
    key = next((tc for en, tc in mk.get("lr_district", {}).items() if tc == dname), None)
    if not key:
        return ""
    short = dname.replace("區", "")
    series = [(m["ym"], m["regions"].get(short)) for m in mk["landreg"]]
    series = [(a, b) for a, b in series if b is not None]
    if len(series) < 6:
        return ""
    top = max(b for _, b in series)
    bars = "".join(f'<span style="height:{100*b/top:.0f}%" '
                   f'title="{a} · {b} 宗"></span>' for a, b in series)
    last, prev = series[-1], series[-13] if len(series) > 13 else series[0]
    delta = (100 * (last[1] - prev[1]) / prev[1]) if prev[1] else 0
    return (f'<h2>{e(dname)}買賣合約宗數</h2>'
            f'<p class="note">土地註冊處每月數字，{e(series[0][0])} 至 {e(last[0])}。'
            f'計嘅係所有樓宇單位，唔分住宅非住宅。</p>'
            f'<div class="bars"><div class="mkt">{bars}</div>'
            f'<div class="bar" style="margin-top:10px"><u>{e(last[0])}</u>'
            f'<span></span><em>{last[1]:,} 宗　'
            f'{"↑" if delta >= 0 else "↓"} {abs(delta):.0f}% 按年</em></div></div>')


def district_page(d, rank, rows, estates, n_est, mk):
    lbl, tone = band(d["avg"])
    top = rows[:20]
    pat = sorted(d["patterns"].items(), key=lambda x: -x[1])
    est = "".join(
        f'<li><a href="/estate/{e(s["name"])}">{e(s["name"])}<b>{s["avg"]:.1f}</b></a></li>'
        for s in estates)

    title = f"{d['tc']}風水評分 — {n(d['n'])} 幢樓宇排名｜香港風水地圖"
    desc = (f"{d['tc']}全部 {n(d['n'])} 幢樓宇嘅九運風水評分，平均 {d['avg']:.1f} 分，"
            f"18 區之中排第 {rank}。列出區內最高分樓宇、四大格局分佈"
            f"同 {n_est} 個屋苑排名。")

    tr = "".join(
        f'<tr><td class="nm">{e(r["tc"] or r["en"])}</td>'
        f'<td class="sc"><span class="dot" style="background:var(--{band(r["total"])[1]})">'
        f'</span>{r["total"]:.1f}</td><td>{band(r["total"])[0]}</td>'
        f'<td>{e(r.get("pattern") or "—")}</td><td>{e(r.get("now") or "—")}</td></tr>'
        for r in top)

    body = f"""
<h1>{e(d['tc'])}風水評分</h1>
<p class="sub">{n(d['n'])} 幢樓宇 · 平均 {d['avg']:.1f} 分 · {len(estates)} 個屋苑</p>

<div class="hero">
  <div><div class="big" style="color:var(--{tone})">{d['avg']:.1f}</div></div>
  <div><span class="pill" style="background:var(--{tone})">{lbl}</span>
  <div class="rk">18 區之中排第 <b>{rank}</b><br>分數計嘅係山水方位、坐向
  同周邊配套 —— 唔係樓價</div></div>
</div>

<h2>區內最高分二十幢</h2>
<p class="note">全區 {n(d['n'])} 幢入面分數最高嗰二十幢</p>
<div class="tw"><table><thead><tr><th>樓宇</th><th>評分</th><th>等級</th>
<th>格局</th><th>九運</th></tr></thead><tbody>{tr}</tbody></table></div>

{market_panel(d["tc"], mk)}

<h2>四大格局分佈</h2>
<p class="note">排得出玄空飛星盤嗰啲樓宇</p>
{bars(pat, sum(v for _, v in pat))}

{f'<h2>區內屋苑</h2><p class="note">按平均分排，列出頭 {len(estates)} 個（共 {n_est} 個）</p><ul class="links">' + est + '</ul>' if est else ''}

<a class="cta" href="/">喺地圖睇{e(d['tc'])} →</a>
{DISCLAIM}
"""
    crumbs = [("香港風水地圖", "/"), ("地區", "/district/"), (d["tc"], None)]
    return shell(title, desc, f"/district/{d['tc']}", crumbs, body)


def hub_estates(ranked):
    """屋苑總目錄。28Hse 排到名嘅機制唔係每版寫得好，係成個網互相扣實 ——
    一版樞紐扣住一百幾十版，爬蟲行一次就見晒。所以呢版唔分頁。"""
    by = collections.defaultdict(list)
    for x in ranked:
        by[x["district"]].append(x)
    secs = []
    for d in sorted(by, key=lambda k: -len(by[k])):
        li = "".join(
            f'<li><a href="/estate/{e(x["name"])}">{e(x["name"])}'
            f'<b>{x["avg"]:.1f}</b></a></li>' for x in by[d])
        secs.append(f'<h2><a href="/district/{e(d)}">{e(d)}</a></h2>'
                    f'<p class="note">{len(by[d])} 個屋苑</p>'
                    f'<ul class="links">{li}</ul>')
    body = (f'<h1>香港屋苑風水評分</h1>'
            f'<p class="sub">{len(ranked)} 個屋苑，逐座計咗九運風水評分</p>'
            + "".join(secs) + f'<a class="cta" href="/">開地圖 →</a>{DISCLAIM}')
    return shell(
        f"香港屋苑風水評分一覽 — {len(ranked)} 個屋苑逐座排名｜香港風水地圖",
        f"全港 {len(ranked)} 個屋苑嘅九運風水評分，按 18 區分類，"
        f"每個屋苑逐座列出評分、坐向、格局同飛星盤。",
        "/estate/", [("香港風水地圖", "/"), ("屋苑", None)], body)


def hub_districts(ds, drank, by_dist):
    li = "".join(
        f'<li><a href="/district/{e(d["tc"])}">{e(d["tc"])}'
        f'<b>{d["avg"]:.1f}</b></a></li>'
        for d in sorted(ds, key=lambda a: -a["avg"]))
    rows = "".join(
        f'<tr><td class="nm">{drank[d["tc"]]}</td>'
        f'<td class="nm"><a href="/district/{e(d["tc"])}">{e(d["tc"])}</a></td>'
        f'<td class="sc"><span class="dot" style="background:var(--{band(d["avg"])[1]})">'
        f'</span>{d["avg"]:.1f}</td><td>{band(d["avg"])[0]}</td>'
        f'<td>{n(d["n"])}</td><td>{len(by_dist.get(d["tc"], []))}</td></tr>'
        for d in sorted(ds, key=lambda a: -a["avg"]))
    body = (f'<h1>香港 18 區風水評分排名</h1>'
            f'<p class="sub">{n(sum(d["n"] for d in ds))} 幢樓宇，按區計平均分</p>'
            f'<div class="tw"><table><thead><tr><th>排名</th><th>地區</th>'
            f'<th>平均分</th><th>等級</th><th>樓宇</th><th>屋苑</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
            f'<h2>全部地區</h2><ul class="links">{li}</ul>'
            f'<a class="cta" href="/">開地圖 →</a>{DISCLAIM}')
    return shell(
        "香港 18 區風水評分排名｜香港風水地圖",
        f"香港 18 區嘅九運風水評分排名，全港 {n(sum(d['n'] for d in ds))} 幢樓宇，"
        f"列出各區平均分、最高分樓宇同區內屋苑排名。",
        "/district/", [("香港風水地圖", "/"), ("地區", None)], body)


def write(path, text):
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def main() -> None:
    only = sys.argv[1:] or None
    sc, home, ds, est = gather()
    meta = side("data/estate_meta.json", {})
    mk = side("data/market.json", {})
    plans = side("pages/plan-report.json", {}).get("ok", {})
    by_en = {v["en"]: v for v in meta.values() if v.get("en")}
    tx = collections.defaultdict(list)
    for t in mk.get("hos", []):
        tx[t["estate"]].append(t)
    print(f"  平面圖 {len(plans)} · 屋苑資料 {len(meta)} · 居屋成交 {len(tx)} 個屋苑")
    ranked = sorted(est.values(), key=lambda x: -x["avg"])
    for i, x in enumerate(ranked):
        x["rank"] = i + 1
    by_dist = collections.defaultdict(list)
    for x in ranked:
        by_dist[x["district"]].append(x)
    drank = {d["tc"]: i + 1 for i, d in enumerate(sorted(ds, key=lambda a: -a["avg"]))}
    rows_by_dist = collections.defaultdict(list)
    for r in home:
        if r.get("tc") or r.get("en"):
            rows_by_dist[r["district"]].append(r)
    for v in rows_by_dist.values():
        v.sort(key=lambda r: -r["total"])

    made = 0
    for x in ranked:
        if only and x["name"] not in only:
            continue
        sib = [s for s in by_dist[x["district"]] if s["name"] != x["name"]][:12]
        extra = {"plan": plans.get(x["name"]),
                 "meta": meta.get(x["name"]) or by_en.get(x.get("en")) or {},
                 "tx": tx.get(x["name"]) or []}
        write(f"estate/{x['name']}.html",
              estate_page(x, x["rank"], len(ranked), sib, extra))
        made += 1
    for d in ds:
        if only and d["tc"] not in only:
            continue
        write(f"district/{d['tc']}.html",
              district_page(d, drank[d["tc"]], rows_by_dist[d["tc"]],
                            by_dist[d["tc"]][:40], len(by_dist[d["tc"]]), mk))
        made += 1

    if not only:
        write("estate/index.html", hub_estates(ranked))
        write("district/index.html", hub_districts(ds, drank, by_dist))
        made += 2

    got = sum(1 for x in ranked if plans.get(x["name"]))
    print(f"{made} 版 -> {OUT}")
    print(f"  有平面圖 {got} · 有發展商 "
          f"{sum(1 for x in ranked if (meta.get(x['name']) or {}).get('dev'))} · "
          f"有成交 {sum(1 for x in ranked if tx.get(x['name']))}")
    print(f"  屋苑 {len(ranked)} 個（房委會 {sum(1 for x in ranked if x['ha'])} · "
          f"普查新增 {sum(1 for x in ranked if not x['ha'])}）")


if __name__ == "__main__":
    main()
