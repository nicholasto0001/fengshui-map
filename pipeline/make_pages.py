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
import datetime
import html
import json
import re
import urllib.parse
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import census                                    # noqa: E402
from build_tiles import is_dwelling, keep        # noqa: E402

OUT = ROOT / "pages"
SITE = "https://hkfengshuimap.com"


def url(kind: str, name: str) -> str:
    """頁面嘅 URL。一定要同 make_sitemap 嗰邊編碼方式一樣。

    之前 canonical 直接塞原文，出嚟係 /estate/Grand YOHO —— 入面有個真
    空格，本身就唔係一條有效 URL；而 sitemap 嗰邊又編碼咗做 %20。兩邊
    唔同字串，Google 會當成兩條 URL，等於自己拆散自己個 canonical。
    """
    return f"/{kind}/{urllib.parse.quote(name, safe='')}"


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
/* aspect-ratio 由生成器寫落去，令個框喺圖未到之前已經係啱嘅形狀 ——
   否則絕對定位嘅標籤會喺圖載入嗰刻跳位。 */
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
/* 文章入面嘅表同屋苑頁嗰啲唔同：呢度有長句，全站嗰條 th,td 嘅
   white-space:nowrap 會令佢喺電話度撐爆成版（實測 375px 屏幕、
   表寬 429px，第三欄啲字俾切走）。 */
.terms th,.terms td{white-space:normal;word-break:break-word;line-height:1.6}
.terms tr.now{background:#f3f7fd}
.terms tr.now th{font-weight:700}
@media(max-width:560px){
  .terms{font-size:13.5px}
  .terms th,.terms td{padding:8px 8px}
}
.lede{font-size:17px;line-height:1.8;margin:0 0 20px}
.lede b{font-weight:650}
.faqs{margin:34px 0 0}
.faq{border-top:1px solid var(--line);padding:18px 0 0;margin:18px 0 0}
.faq h2{font-size:19px;margin:0 0 8px}
.faq p{margin:0;font-size:15.5px;line-height:1.75;color:var(--ink2)}
.bzbox{background:linear-gradient(135deg,#3d2f18,#5a4622);color:#fff;border-radius:16px;
 padding:20px 22px;margin:34px 0 0;line-height:1.7}
.bzbox p{margin:0 0 10px;font-size:14.5px;opacity:.9}
.bzbox .bzh2{font-size:18px;font-weight:650;opacity:1;margin-bottom:12px}
.bzbox b{color:#e3c489}
.bzlink{color:#fff;font-weight:650;text-decoration:underline;text-underline-offset:3px}
.warn{background:#fff8ec;border:1px solid #f0dfbe;border-radius:14px;
 padding:14px 16px;font-size:14px;color:#6b5626;line-height:1.65;margin:26px 0 0}
@media(max-width:560px){h1{font-size:25px}.big{font-size:38px}.wrap{padding:0 14px 48px}}
"""


def faq_html(faqs):
    """問題做標題，第一句就答。

    呢個唔淨係俾 Google —— AI 爬蟲唔行 JavaScript，佢哋見到嘅就係呢啲
    靜態文字。一個「答案行先」嘅段落，係佢哋引用得到嘅嘢；一張數據表
    唔係。所以每一版都要用人真係會打嗰句問題做標題。
    """
    if not faqs:
        return ""
    items = "".join(
        f'<div class="faq"><h2>{e(q)}</h2><p>{a}</p></div>' for q, a in faqs)
    return f'<section class="faqs">{items}</section>'


def strip_tags(x):
    return re.sub(r"<[^>]+>", "", x)


def shell(title, desc, canon, crumbs, body, faqs=None):
    trail = " › ".join(
        f'<a href="{u}">{e(t)}</a>' if u else e(t) for t, u in crumbs)
    graph = [{
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": t,
             **({"item": SITE + u} if u else {})}
            for i, (t, u) in enumerate(crumbs)],
    }]
    if faqs:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}}
                for q, a in faqs],
        })
    ld = {"@context": "https://schema.org", "@graph": graph}
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
{faq_html(faqs)}
<div class="bzbox">
  <p class="bzh2">住邊度最旺你？三樣嘢先答到</p>
  <p><b>風水</b>　個地方本身 —— 山喺邊、水喺邊、周圍高定矮、有冇煞。呢啲幾十年唔變。<br>
     <b>大運</b>　而家行緊<b>九運（2024–2043）</b>，二十年轉一次。八運（2004–2023）
     當旺嗰啲樓，今日未必當旺。全港 80.9% 住宅係七運或更早起嘅。<br>
     <b>八字</b>　你自己。上面兩樣<b>邊個睇都一樣</b>，八字先係屬於你嗰層。</p>
  <p>上面每個分係頭兩樣計出嚟嘅。打個出生日期落去，就會排出你嘅四柱、計出你缺
     邊幾樣五行，再用八宅睇你個命卦配唔配呢幢樓個向，逐幢計返一個
     <b>得你一個人有</b>嘅分。屋企人都加得埋，一齊計。</p>
  <p><a class="bzlink" href="/bazi-guide">八字揀樓點計？逐步寫明 →</a><br>
     <a class="bzlink" href="/learn/%E5%AF%92%E7%86%B1%E5%91%BD">寒熱命係咩？點知自己係寒命定熱命 →</a></p>
</div>
<footer>
  <p>評分由電腦計算，數據嚟自政府公開資料。<a href="/method">計算方法同數據限制</a> ·
     <a href="/bazi-guide">八字揀樓</a> ·
     <a href="/learn/">八字基礎</a> ·
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
  <div class="pw" style="aspect-ratio:{rep.get('w',880)}/{rep.get('h',600)}">
    <img src="/plan/{e(name)}.jpg" alt="{e(alt)}"
       width="{rep.get('w',880)}" height="{rep.get('h',600)}"
       loading="lazy" decoding="async">{lab}
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
def estate_faqs(es, rank, total_est):
    """屋苑頁嘅問題 —— 人打嘅係「太古城風水好唔好」，唔係「太古城評分」。"""
    rows, nm = es["rows"], es["name"]
    hi, lo = rows[0], rows[-1]
    lbl = band(es["avg"])[0]
    bn = lambda r: e(r["tc"] or r["en"] or "未命名樓宇")

    out = [(
        f"{nm}風水好唔好？",
        f"{nm}（{e(es['district'])}）{len(rows)} 座嘅九運風水平均分係 "
        f"<b>{es['avg']:.1f} 分</b>，喺全港 {n(total_est)} 個屋苑入面"
        f"<b>排第 {rank}</b>，整體屬「{lbl}」。"
        f"分數計嘅係山水方位、周邊設施同玄空飛星盤，"
        f"唔包括室內間隔、樓層同單位座向。"
    )]

    if len(rows) > 1:
        gap = hi["total"] - lo["total"]
        out.append((
            f"{nm}邊座風水最好？",
            f"最高分係 <b>{bn(hi)}</b>（{hi['total']:.1f} 分），"
            f"最低係 {bn(lo)}（{lo['total']:.1f} 分），"
            f"{'爭 %.1f 分' % gap if gap >= 1 else '差別好細'}。"
            f"同一個屋苑各座嘅坐向同山水方位唔同，所以分數唔會一樣 —— "
            f"上面逐座列晒。"
        ))

    out.append((
        f"{nm}啱唔啱我？",
        f"上面個分答嘅係「{nm}點起」，<b>邊個睇都一樣</b>。"
        f"啱唔啱你係另一條問題：要睇你嘅八字同本命卦。"
        f"同一座樓，向北對乾命嘅人係「六煞」，對巽命嘅人可以係「生氣」。"
        f"打個出生日期落去就計到，屋企人都加得埋一齊計。"
    ))
    return out


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
        f'<li><a href="{url("estate", s["name"])}">{e(s["name"])}<b>{s["avg"]:.1f}</b></a></li>'
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
              (es["district"], url("district", es["district"])), (nm, None)]
    return shell(title, desc, url("estate", nm), crumbs, body,
                 estate_faqs(es, rank, total_est))


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


ELEM = {x["tc"]: x for x in side("data/elements.json", [])}

WX_WHY = {
    "木": lambda x: f"平均樓高 {x['h_med']} 米，高度係地基闊度嘅 {x['slender']} 倍 —— 高而直",
    "土": lambda x: f"平均樓高得 {x['h_med']} 米，矮而闊",
    "火": lambda x: (f"{x['spike']:.0f}% 樓宇高出四周一倍以上，"
                    f"每平方公里 {x['density']} 幢"),
    "水": lambda x: f"{x['shore']:.0f}% 住宅喺離水邊 200 米內",
}


def district_faqs(d, rank, rows, estates):
    """人真係會打嘅問題，唔係我哋想講嘅嘢。

    「觀塘屬咩五行」呢條問題，全網得一篇 2011 年嘅匿名網誌答，而佢自己
    都矛盾。我哋有量出嚟嘅數據，所以答得比全網都好 —— 呢個先係值得
    被引用嘅原因。
    """
    tc, lbl = d["tc"], band(d["avg"])[0]
    out = [(
        f"{tc}風水好唔好？",
        f"{tc}全部 {n(d['n'])} 幢樓宇嘅九運風水平均分係 <b>{d['avg']:.1f} 分</b>，"
        f"喺十八區入面<b>排第 {rank}</b>，整體屬「{lbl}」。"
        f"區內最高分係 {e(rows[0]['tc'] or rows[0]['en'] or '未命名樓宇')}"
        f"（{rows[0]['total']:.1f} 分）。分數計嘅係山水方位、周邊設施同玄空飛星，"
        f"唔包括室內間隔。"
    )]

    x = ELEM.get(tc)
    if x:
        f = x["form"]
        top = max(f, key=f.get)
        out.append((
            f"{tc}屬咩五行？",
            f"按形勢計，{tc}<b>最突出係{top}</b>（全港十八區入面排 {f[top]}／100）。"
            f"{WX_WHY[top](x)}。楊筠松《撼龍經》以形定五行 —— 金圓、木直、水曲、"
            f"火尖、土方 —— 呢度嘅數字係由區內 {n(x['n'])} 幢住宅嘅實際高度、"
            f"地基輪廓同離水距離量出嚟，唔係抄坊間清單。"
            f"（金冇形嘅數據支持，所以唔計；{tc}位處全港{x['zone']}面，"
            f"按方位屬{x['dir_wx']}。）"
        ))

    if estates:
        best = estates[0]
        out.append((
            f"{tc}邊個屋苑風水最好？",
            f"區內平均分最高係 <b>{e(best['name'])}</b>（{best['avg']:.1f} 分）。"
            f"但平均分係成個屋苑嘅，逐座可以差好遠 —— 撳入去睇逐座坐向同飛星盤。"
            f"另外，格局好唔等於啱你：同一幢樓對唔同八字嘅人分數唔同。"
        ))
    return out


def district_page(d, rank, rows, estates, n_est, mk):
    lbl, tone = band(d["avg"])
    top = rows[:20]
    pat = sorted(d["patterns"].items(), key=lambda x: -x[1])
    est = "".join(
        f'<li><a href="{url("estate", s["name"])}">{e(s["name"])}<b>{s["avg"]:.1f}</b></a></li>'
        for s in estates)

    title = f"{d['tc']}風水評分 — {n(d['n'])} 幢樓宇排名｜香港風水地圖"
    desc = (f"{d['tc']}全部 {n(d['n'])} 幢樓宇嘅風水同大運評分，平均 {d['avg']:.1f} 分，"
            f"18 區之中排第 {rank}。九運（2024–2043）山水方位、四大格局分佈、"
            f"區內最高分樓宇同 {n_est} 個屋苑排名。想知邊幢最旺你，再夾埋八字計。")

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
    return shell(title, desc, url("district", d["tc"]), crumbs, body,
                 district_faqs(d, rank, rows, estates))


def hub_estates(ranked):
    """屋苑總目錄。28Hse 排到名嘅機制唔係每版寫得好，係成個網互相扣實 ——
    一版樞紐扣住一百幾十版，爬蟲行一次就見晒。所以呢版唔分頁。"""
    by = collections.defaultdict(list)
    for x in ranked:
        by[x["district"]].append(x)
    secs = []
    for d in sorted(by, key=lambda k: -len(by[k])):
        li = "".join(
            f'<li><a href="{url("estate", x["name"])}">{e(x["name"])}'
            f'<b>{x["avg"]:.1f}</b></a></li>' for x in by[d])
        secs.append(f'<h2><a href="{url("district", d)}">{e(d)}</a></h2>'
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


# ---------------------------------------------------------------- 文章 ---
#
# 點解要有呢一層：AI 爬蟲唔行 JavaScript。八字功能全部係 JS 跑出嚟嘅,
# 所以喺 ChatGPT、Gemini、Perplexity 眼中，我哋個網站就只係一版地圖。
# 呢啲靜態文章係我哋喺 AI 度唯一嘅門面。
#
# 寫嘅規矩（見 docs/content-plan.md）：問題做標題、第一句就答、每個講法
# 有出處、講埋做唔到嘅嘢。追唔到源頭嘅講法唔寫 —— 唔寫「據說」。

sys.path.insert(0, str(ROOT / "bazi"))
import astro                                                  # noqa: E402

# ⚠ astro.py 數 24 個節氣，bazi.js 只數 12 個「節」。兩邊索引唔同,
#   撞過一次（立秋攞成立夏，而且唔會有測試失敗）。呢度係 Python。
T_JINGZHE, T_QINGMING, T_LIXIA, T_LIQIU = 2, 4, 6, 12


def term_rows(index, years):
    out = []
    for y in years:
        _, m, d, mins = astro.term_hkt(y, index)
        out.append((y, m, d, mins // 60, mins % 60))
    return out


def hot_cold_article():
    now = datetime.date.today().year
    years = range(now - 6, now + 6)
    rows = term_rows(T_LIQIU, years)
    off = [r for r in rows if (r[1], r[2]) != (8, 8)]

    tbl = "".join(
        f'<tr{" class=\"now\"" if y == now else ""}>'
        f"<th>{y}</th><td>{m} 月 {d} 日</td><td>{hh:02d}:{mm:02d}</td>"
        f'<td>{"—" if (m, d) == (8, 8) else "唔係 8 月 8 日"}</td></tr>'
        for y, m, d, hh, mm in rows)

    ly, lm, ld, lhh, lmm = next(r for r in rows if r[0] == now)

    body = f"""
<p class="lede"><b>寒熱命係蘇民峰喺 1994 年創立嘅一套命理分法，用出生嗰日
喺邊個節氣之間，將人分做寒命、熱命同平命。</b>
立秋之後至驚蟄之前出世係<b>寒命</b>，喜火，以木生火；立夏之後至立秋之前
出世係<b>熱命</b>，喜水，以金生水；中間嗰段係平命。</p>

<p>佢唔使時辰，淨係要出生日期 —— 呢點同傳統扶抑法好唔同，亦都係佢好用
嘅原因：好多人唔記得自己幾點出世。</p>

<h2>點樣分寒命、熱命、平命</h2>

<table class="terms">
<tr><th>命格</th><th>出生時段</th><th>喜用五行</th></tr>
<tr><td><b>寒命</b></td><td>立秋 → 驚蟄</td><td>喜火，以木生火</td></tr>
<tr><td><b>熱命</b></td><td>立夏 → 立秋</td><td>喜水，以金生水</td></tr>
<tr><td><b>平命</b></td><td>驚蟄 → 立夏</td><td>水火不忌；清明前較寒，清明後較熱</td></tr>
</table>

<p class="src">出處：蘇民峰喺風水雜誌《新玄機》第 53 期自述 ——
「立秋後（西曆八月八日）驚蟄前（西曆三月六日）為寒命。立夏後（西曆五月
六日）立秋前為熱命。驚蟄後，立夏前為平命。」</p>

<h2>但「八月八日」呢個約數，四分三年份都係錯</h2>

<p><b>節氣唔係固定日期。</b>佢係太陽行到黃經某個度數嗰一刻，每年爭幾個
鐘，所以會喺兩日之間游走。蘇民峰自己寫嗰幾個日期係方便記嘅約數，唔係
界線本身。</p>

<p>以立秋為例，{years[0]} 至 {years[-1]} 年入面，<b>{len(off)} 年唔係
8 月 8 日</b>：</p>

<table class="terms">
<tr><th>年</th><th>立秋日期</th><th>時刻（香港時間）</th><th></th></tr>
{tbl}
</table>

<p class="src">節氣時刻用 VSOP87 截斷級數計算太陽視黃經，加 Espenak–Meeus
ΔT 修正。同香港天文台曆書對照過 220 個節氣，1950 年後零差異；戰前有 6 個
踩正午夜，差一分鐘之內。</p>

<h2>差一日，答案可以完全相反</h2>

<p>{ly} 年立秋係 <b>{lm} 月 {ld} 日 {lhh:02d}:{lmm:02d}</b>。假設有人
2020 年 8 月 7 日下午三點出世：</p>

<ul>
  <li><b>用約數</b>（立秋 = 8 月 8 日）：未到立秋 → <b>熱命</b>，喜水、金</li>
  <li><b>用真實節氣</b>（2020 年立秋 = 8 月 7 日 09:06）：已經過咗立秋 →
      <b>寒命</b>，喜火、木</li>
</ul>

<p>一個要水金，一個要火木，<b>完全相反</b>。而由呢一步推落去嘅所有嘢 ——
適合邊個方位、邊個地區、邊種樓 —— 都會跟住反晒。</p>

<p>生喺節氣前後一兩日嘅人，一定要查返嗰年嘅真實時刻。</p>

<h2>知道自己寒定熱，有咩用</h2>

<p>最直接嘅用法係<b>方向</b>。五行對方位係固定嘅：木東、火南、金西、
水北、土中。寒命喜火，火對應南方；熱命喜水，水對應北方。</p>

<p class="src">五行對方位再對香港地理，出處：風水雜誌《新玄機》第 231 期，
區晉豪〈五行方向搵屋〉——「木代表東方。火代表南方。金代表西方。水代表
北方。」</p>

<p>再落一層就係樓宇本身嘅<b>形</b>。楊筠松《撼龍經》以形定五行 ——
金圓、木直、水曲、火尖、土方 —— 而形係量得到嘅：樓幾高、地基幾闊、
離水幾遠。我哋由全港住宅嘅實際數據量出每個區同每幢樓嘅形，所以「你喜火」
可以一路推到「所以呢幢樓夾你幾多分」。</p>

<h2>呢套嘢做唔到啲咩</h2>

<ul>
  <li><b>係一家之言。</b>寒熱命係蘇民峰創立嘅，唔係八字嘅共識。傳統扶抑法
      用完全另一套邏輯，兩者會得出唔同答案。</li>
  <li><b>蘇民峰本人否定扶抑法。</b>佢喺同一篇文寫「根本不用再詳細計算
      命者身旺身弱，以何為用神」。所以唔好將兩套溝埋一齊當成互相印證。</li>
  <li><b>只分三類。</b>全香港人分做寒、熱、平三組，所以單靠佢分唔到人。
      要真係度身訂造，仲要睇埋你自己盤入面五行嘅比例同本命卦。</li>
  <li><b>唔係師傅睇。</b>呢啲係電腦計算嘅參考，唔等同專業風水師傅嘅判斷。</li>
</ul>
"""

    faqs = [
        ("寒熱命係咩？",
         "寒熱命係香港堪輿學家蘇民峰喺 1994 年創立嘅一套命理分法，用出生日期"
         "落喺邊個節氣之間，將人分做寒命、熱命同平命。立秋至驚蟄出世係寒命，"
         "喜火；立夏至立秋出世係熱命，喜水；中間係平命。佢唔使時辰，淨係要"
         "出生日期。"),
        ("點樣知自己係寒命定熱命？",
         f"睇你出生嗰日喺立秋同立夏之間邊個位置。但唔可以用「8 月 8 日」"
         f"呢類約數 —— 節氣每年爭幾個鐘，{years[0]} 至 {years[-1]} 年入面有 "
         f"{len(off)} 年嘅立秋唔係 8 月 8 日。生喺界線前後一兩日嘅人，"
         f"一定要查返嗰年嘅真實節氣時刻。"),
        ("寒命同熱命分別喺邊？",
         "寒命人喜火，以木生火；熱命人喜水，以金生水。推落去，寒命偏向南方"
         "同火形嘅環境，熱命偏向北方同近水嘅環境。五行對方位嘅講法出自"
         "《新玄機》第 231 期區晉豪〈五行方向搵屋〉。"),
        ("寒熱命準唔準？",
         "寒熱命係蘇民峰一家之言，唔係八字嘅共識，而且只分三類，所以單靠佢"
         "分唔到人。蘇民峰本人喺同一篇文否定咗傳統扶抑法，所以兩套唔應該"
         "溝埋當互相印證。要真係因人而異，仲要睇你盤入面五行嘅比例同本命卦。"),
    ]
    title = "寒熱命係咩？點知自己係寒命定熱命｜香港風水地圖"
    desc = (f"寒熱命由蘇民峰 1994 年創立，用出生日期分寒命、熱命、平命。"
            f"但坊間用嘅「8 月 8 日立秋」係約數 —— {years[0]}–{years[-1]} 年入面"
            f"有 {len(off)} 年唔係嗰日，差一日可以令答案完全相反。")
    crumbs = [("香港風水地圖", "/"), ("八字", "/learn/"), ("寒熱命", None)]
    return shell(title, desc, url("learn", "寒熱命"), crumbs, body, faqs)


def learn_hub():
    body = """
<p class="lede">八字同風水嘅基礎概念，逐個講清楚 —— 每個講法寫明出處，
連做唔到啲咩都講埋。</p>
<ul class="links">
  <li><a href="/learn/%E5%AF%92%E7%86%B1%E5%91%BD"><b>寒熱命係咩？</b>
    點知自己係寒命定熱命，同埋點解「8 月 8 日立秋」係錯嘅</a></li>
  <li><a href="/bazi-guide"><b>八字揀樓點計？</b>
    四柱、五行、寒熱命、八宅 —— 連做唔到啲咩都寫明</a></li>
  <li><a href="/method"><b>九運風水評分點計？</b>
    山水方位、玄空飛星、逆向工程自政府圖層</a></li>
</ul>
"""
    return shell("八字同風水基礎｜香港風水地圖",
                 "八字同風水嘅基礎概念，每個講法寫明出處，連做唔到啲咩都講埋。",
                 "/learn/", [("香港風水地圖", "/"), ("八字", None)], body)


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
        write("learn/index.html", learn_hub())
        write("learn/寒熱命.html", hot_cold_article())
        made += 4

    got = sum(1 for x in ranked if plans.get(x["name"]))
    print(f"{made} 版 -> {OUT}")
    print(f"  有平面圖 {got} · 有發展商 "
          f"{sum(1 for x in ranked if (meta.get(x['name']) or {}).get('dev'))} · "
          f"有成交 {sum(1 for x in ranked if tx.get(x['name']))}")
    print(f"  屋苑 {len(ranked)} 個（房委會 {sum(1 for x in ranked if x['ha'])} · "
          f"普查新增 {sum(1 for x in ranked if not x['ha'])}）")


if __name__ == "__main__":
    main()
