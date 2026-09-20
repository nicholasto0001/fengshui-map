"""每週貼文同第一個留言，由我哋自己嘅數據生成。

點解要寫呢個：Meta 喺 2024 年 4 月 22 日由所有 API 版本移除咗 Groups API，
所以冇任何程式出得到群組貼文 —— Zapier、Buffer、佢自己個 Business Suite 都
唔得。可以自動化嘅係另一半：諗題目、計數、寫成一篇有人想睇嘅嘢。

每篇都由真數據生成，冇一句係砌出嚟。撳掣嗰下留返俾人 —— 嗰下 Facebook 唔准
自動化，而佢只係三十秒。

每個題目出兩個版本：
  A  連結放喺正文
  B  正文唔放連結，連結留喺第一個留言
兩個版本係要攞嚟做 A/B 嘅 —— 「連結會壓低觸及」呢個講法流傳好廣，但我哋
自己冇證據，所以用自己條群組度出嚟嘅數字去決定。

Output: docs/posts.md
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from build_tiles import is_dwelling, keep  # noqa: E402

SITE = "https://hkfengshuimap.com"
OUT = ROOT / "docs" / "posts.md"

# 每篇都以同一句收尾。唔係口號，係我哋真係咁做。
FOOT = ("⚠️ 電腦計算，唔係師傅睇。坐向由樓宇外形推算，誤差 ±10–20°，"
        "唔係羅盤實測。認真睇樓請搵專業風水師傅。")

CTA = "👉 打你住緊嗰幢樓個名落去，即刻睇到幾多分"


def load():
    sc = [r for r in json.loads((ROOT / "data" / "scores.json").read_text()) if keep(r)]
    home = [r for r in sc if is_dwelling(r)]
    ds = json.loads((ROOT / "data" / "district_stats.json").read_text())
    return sc, home, ds


def n(x):
    return f"{x:,}"


def dedupe(rows, key=lambda r: r.get("tc")):
    """同一個名喺數據入面可以出現幾次（同名唔同幢）。榜入面淨係留第一個 ——
    一張榜出兩次「銀池道」睇落似出錯，唔似係事實。"""
    seen, out = set(), []
    for r in rows:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


# ------------------------------------------------------------------ 題目 ---
def top_buildings(sc, home, ds):
    rows = dedupe(sorted((r for r in home if r.get("tc")),
                         key=lambda r: -r["total"]))[:10]
    lines = [f"{i+1}. {r['tc']}（{r['district']}）{r['total']:.1f} 分"
             for i, r in enumerate(rows)]
    where = collections.Counter(r["district"] for r in rows).most_common(1)[0]
    return {
        "name": "全港十大旺宅",
        "hook": f"全港最高分嘅十幢住宅，{where[1]} 幢喺同一個區。",
        "body": "\n".join([
            f"我哋計咗全港 {n(len(home))} 幢住宅樓宇嘅九運風水評分，",
            "山水方位、坐向、飛星盤全部用政府公開數據計。",
            "",
            "分數最高嘅十幢係：",
            "",
            *lines,
            "",
            f"十個入面有 {where[1]} 個喺{where[0]}。",
            "背山面海、樓不高、明堂開闊 —— 呢個組合喺九運特別食糊。",
        ]),
        "ask": "你嗰區最高分嘅係邊幢？打個屋苑名落去就睇到。",
        "com": ["榜上全部都係低密度、背山、前面開揚。",
                "但高分唔等於貴 —— 分數同樓價完全冇關係，我哋根本冇攞過樓價數據。"],
    }


def district_rank(sc, home, ds):
    rows = sorted(ds, key=lambda a: -a["avg"])
    lines = [f"{i+1}. {a['tc']}　{a['avg']:.1f} 分　（{n(a['n'])} 幢）"
             for i, a in enumerate(rows)]
    return {
        "name": "18 區風水評分排名",
        "hook": "18 區邊區風水分最高？答案同樓價排名唔同。",
        "body": "\n".join([
            f"全港 {n(len(sc))} 幢樓宇，按區計平均分：",
            "",
            *lines,
            "",
            f"最高同最低差 {rows[0]['avg'] - rows[-1]['avg']:.1f} 分。",
            "分數計嘅係山水距離、方位配對同周邊配套 —— 唔係樓價。",
        ]),
        "ask": "你住嗰區排第幾？睇完打落 comment。",
        "com": ["留意：呢個係全區平均。區內每一幢都有自己個分，",
                "同區可以爭三十幾分，所以睇自己嗰幢先準。"],
    }


def trapped(sc, home, ds):
    got = [r for r in home if r["now"]]
    c = collections.Counter(r["district"] for r in got if r["now"] == "入囚")
    tot = collections.Counter(r["district"] for r in got)
    by_pct = sorted(((d, k, tot[d], 100 * k / tot[d]) for d, k in c.items() if tot[d] >= 500),
                    key=lambda x: -x[3])[:8]
    lines = [f"{i+1}. {d}　{p:.1f}%　（{n(k)} / {n(t)} 幢）"
             for i, (d, k, t, p) in enumerate(by_pct)]
    total = sum(c.values())
    return {
        "name": "邊個區「入囚」最多",
        "hook": "九運「入囚」—— 向星入中宮，氣被困。全港有幾多幢？",
        "body": "\n".join([
            f"我哋為 {n(len(got))} 幢住宅排咗玄空飛星盤，",
            f"其中 {n(total)} 幢喺九運屬於「入囚」。",
            "",
            "按比例計，入囚最多嘅區：",
            "",
            *lines,
            "",
            "入囚唔等於間屋唔住得 —— 佢講嘅係呢廿年嘅氣運格局，",
            "同樓價、間隔、樓層完全冇關係。",
        ]),
        "ask": "想知你嗰幢係唔係？打個名落去，有入伙年份就排得到盤。",
        "com": ["入囚係九運（2024–2043）嘅事，唔係永久。",
                "到十運會再翻盤，所以睇嘅係你打算住幾耐。"],
    }


def estates(sc, home, ds):
    by = collections.defaultdict(list)
    for r in home:
        e = r.get("estate") or {}
        if e.get("estate"):
            by[e["estate"]].append(r)
    rank = sorted(((k, sum(x["total"] for x in v) / len(v), len(v))
                   for k, v in by.items() if len(v) >= 3), key=lambda x: -x[1])[:10]
    lines = [f"{i+1}. {k}　{a:.1f} 分　（{c} 座）" for i, (k, a, c) in enumerate(rank)]
    return {
        "name": "公屋居屋屋苑排行榜",
        "hook": f"房委會 {n(len(by))} 個屋邨同居屋，邊個平均分最高？",
        "body": "\n".join([
            "差餉物業估價署唔收錄公屋落成年份，所以好多風水分析都跳過公屋。",
            "我哋改為用房屋委員會自己公開嘅登記冊，逐座配返年份 ——",
            f"補返 {n(sum(len(v) for v in by.values()))} 座，覆蓋 {n(len(by))} 個屋苑。",
            "",
            "平均分最高嘅十個（三座或以上）：",
            "",
            *lines,
        ]),
        "ask": "你住嗰個屋邨幾多分？打個邨名就查到，連每一座都有得睇。",
        "com": ["同一個邨，每一座嘅分都唔同 —— 座向、望山定望樓都唔一樣。",
                "撳個邨入去就逐座列晒出嚟。"],
    }


def patterns(sc, home, ds):
    c = collections.Counter(r["pattern"] for r in home if r["pattern"])
    total = sum(c.values())
    order = ["旺山旺向", "上山下水", "雙星到向", "雙星到坐"]
    note = {"旺山旺向": "丁財兩旺，四大格局之首",
            "上山下水": "山水顛倒，主損丁破財",
            "雙星到向": "旺財不旺丁",
            "雙星到坐": "旺丁不旺財"}
    lines = [f"・{k}　{n(c[k])} 幢（{100*c[k]/total:.0f}%）—— {note[k]}"
             for k in order if c[k]]
    return {
        "name": "四大格局全港分佈",
        "hook": f"全港 {n(total)} 幢住宅排得出飛星盤。四大格局點分佈？",
        "body": "\n".join([
            "玄空飛星入面，坐山同向首嘅山向星組合分四大格局：",
            "",
            *lines,
            "",
            "格局由入伙年份（元運）同坐向決定。",
            "我哋用屋宇署嘅入伙紙年份定元運，坐向由樓宇外形同明堂開闊度推算。",
        ]),
        "ask": "你嗰幢係邊個格局？打個名落去就見到。",
        "com": ["四個格局個分佈幾平均，因為坐向喺香港基本上係隨機嘅。",
                "所以「旺山旺向」唔算罕有 —— 四幢就有一幢。"],
    }


def coverage(sc, home, ds):
    withy = sum(1 for r in home if r["period"])
    return {
        "name": "點解有啲樓查唔到",
        "hook": "有人問：點解我幢樓冇飛星盤？答案唔係我哋偷懶。",
        "body": "\n".join([
            "起飛星盤要兩樣嘢：入伙年份（定元運）同坐向。",
            "",
            f"住宅樓宇入面，{100*withy/len(home):.0f}% 查到入伙年份 —— 呢個數唔算低。",
            "但起到盤仲要坐向可靠，而坐向係由樓宇外形推算：",
            "外形太接近正方形，長軸就定唔準，坐向就唔可靠。",
            "",
            "嗰陣我哋會寫「未能起盤」，唔會夾硬砌一個。",
            "",
            "順帶一提，差餉物業估價署喺佢自己份刊物講明：",
            "村屋、政府物業、公屋嘅落成年份佢都唔收錄。",
            "公屋嗰部分我哋用房委會嘅登記冊補返，逐座配 —— 配「座名」唔係",
            "「屋邨名」，因為一座叫德璋樓，唔叫德朗邨。配錯個名就成座樓冇年份。",
        ]),
        "ask": "你幢樓起唔起到盤？打個名落去試下。",
        "com": ["查唔到嘅話，喺下面打個樓名，我睇下係年份問題定坐向問題。",
                "有啲真係政府數據入面都冇。"],
    }


TOPICS = [top_buildings, district_rank, trapped, estates, patterns, coverage]


# ------------------------------------------------------------------ 輸出 ---
# 回覆先係真正推高觸及嗰樣嘢：Facebook 排嘅係互動，而一條有人回嘅留言串
# 會令成篇文喺其他人嘅 feed 入面再浮返上去。下面呢啲係我哋一定會收到嘅
# 問題，預先寫好答案，唔使每次即場諗。
REPLIES = [
    ("準唔準？／電腦點識睇風水",
     "準唔準要睇你攞嚟做乜。我哋計嘅係客觀嗰部分 —— 同山幾遠、同水幾遠、"
     "邊個方位、入伙年份配坐向出咩飛星盤。呢啲數係查得到、覆得到嘅。\n"
     "師傅睇嘅嘢我哋做唔到：入屋、羅盤實測、睇門口爐灶床位、夾你八字。\n"
     "所以當佢係篩樓嘅第一步，唔係結論。"),

    ("我幢樓查唔到／冇分",
     "多數係兩個原因：一係政府數據冇你幢樓嘅入伙年份（村屋、政府物業好常見），"
     "一係樓形太接近正方形，推唔準長軸，坐向就唔可靠。\n"
     "夾硬砌一個分出嚟好易呃到人，所以我哋寧願寫「未能起盤」。"),

    ("收唔收錢／要唔要登記",
     "免費，唔使登記，唔使裝 App，手機瀏覽器開條 link 就用得。"),

    ("你哋係咪賣緊樓／收地產商錢",
     "唔係。冇地產商、冇代理、冇贊助。分數同樓價完全冇關係 —— "
     "我哋根本冇攞過樓價數據入嚟計。"),

    ("我嘅資料會唔會俾人",
     "唔會賣、唔會轉俾第三方。唔登記就乜都唔會留低。"),

    ("坐向計錯咗／我間屋明明係坐北向南",
     "好可能你啱。我哋係由樓宇嘅外形同邊面開揚推坐向，冇入過屋、冇羅盤，"
     "誤差大概 ±10–20°。逐幢改唔切八萬幾幢，但你講返個樓名，我記低。"),

    ("邊個做㗎？",
     "一個人做嘅。數據全部嚟自政府公開資料（屋宇署、地政總署、房委會），"
     "計法喺網站「計算方法」嗰版寫晒，邊個數點嚟都寫明。"),
]


def plan(i: int) -> tuple:
    """第 i 個星期（由 0 數起）出邊個題目、邊個版本。

    兩輪：第一輪 ABABAB，第二輪反過嚟 BABABA，咁每個題目都試齊兩個版本，
    而同一個版本又唔會全部撞喺同一個月 —— 群組本身嘅活躍度會浮動，
    唔間開就分唔清係版本嘅分別定係嗰個月嘅分別。

    呢度係排期嘅唯一出處。docs/posts.md 同 weekly.py 都問呢個 function，
    所以冇可能出現兩邊各數各嘅情況。
    """
    n_t = len(TOPICS)
    flip = (i // n_t) % 2 == 1
    ver = "A" if ((i % 2 == 0) != flip) else "B"
    return TOPICS[i % n_t], ver


def pieces(t: dict) -> dict:
    """篇文嘅四舊字。render() 攞去砌 markdown，weekly.py 攞去單獨出一篇。"""
    body = f"{t['hook']}\n\n{t['body']}\n\n{t['ask']}"
    topic = "\n".join(t["com"])
    return {
        "A": "\n\n".join([body, f"{CTA}\n{SITE}",
                           "免費、免登記、免裝 App。", FOOT]),
        "B": "\n\n".join([body, "連結喺第一個 comment 👇",
                           "免費、免登記、免裝 App。", FOOT]),
        # A 篇正文已經有 link，留言唔好再貼多次 —— 重覆貼 link 睇落似 spam，
        # 而且會冚咗留言本身嘅作用。佢淨係負責開個話題。
        "com_A": topic + "\n\n有邊幢查完覺得唔對路？喺下面打個樓名。",
        # B 篇靠留言帶 link，所以 link 要擺第一行 —— Facebook 淨係顯示頭一兩行。
        "com_B": "\n".join([SITE, "", topic, "",
                            "手機瀏覽器直接開，免裝 App、免登記。"]),
    }


def render(t: dict) -> str:
    pc = pieces(t)
    with_link, no_link = pc["A"], pc["B"]
    com_a, com_b = pc["com_A"], pc["com_B"]

    return "\n".join([
        f"## {t['name']}", "",
        "### 版本 A — 連結放正文", "```", with_link, "```", "",
        "**第一個 comment（A 用，唔再貼 link）**", "```", com_a, "```", "",
        "### 版本 B — 連結留喺第一個 comment", "```", no_link, "```", "",
        "**第一個 comment（B 用，link 擺第一行）**", "```", com_b, "```", "",
        "---", "",
    ])


def main() -> None:
    sc, home, ds = load()
    topics = [fn(sc, home, ds) for fn in TOPICS]
    weeks = len(TOPICS) * 2
    named = "\n".join(f"| 第 {i+1} 週 | {topics[TOPICS.index(plan(i)[0])]['name']}"
                      f" | {plan(i)[1]} |" for i in range(weeks))

    parts = [
        "# 每週貼文（自動生成）\n",
        "由 `pipeline/make_posts.py` 生成，數據跟住最新一次 build 走。",
        f"全港 {n(len(sc))} 幢上圖 · {n(len(home))} 幢當住宅顯示。\n",
        "⚠️ Facebook 喺 2024 年 4 月 22 日由所有 API 版本移除咗 Groups API，",
        "所以**冇任何程式出得到群組貼文** —— Zapier、Buffer、佢自己個 Business",
        "Suite 都唔得。呢度生成嘅係內容；撳掣嗰下用 Admin Assist 的",
        "「Publish a custom post」排期，一次過排幾個星期，每次三十秒。\n",
        "## 點解一個題目兩個版本\n",
        "「正文放 link 會被壓低觸及」呢個講法流傳好廣，但我哋自己冇證據。",
        "第一篇（link 喺正文）觸及 1,300，佔群組 165,100 人嘅 0.8% —— ",
        "冇對照組，就唔知 0.8% 係因為條 link，定係因為篇文本身。\n",
        "所以每個題目出齊兩個版本，梅花間竹咁出，出夠六篇之後比較觸及。",
        "夠數之後就一直用贏嗰個。\n",
        "## 排期\n",
        "| 週 | 題目 | 版本 |", "|---|---|---|", named, "",
        "同一個題目第二次出（第 7–12 週）換另一個版本，所以每個題目都試齊兩次。\n",
        "## 成績（自己填）\n",
        "出完之後入 Facebook 個 post 撳「查看成效」抄低。冇呢個表個 A/B 就等於冇做過。\n",
        "| 週 | 版本 | 觸及 | 撳 link | 留言 | 出街時間 |",
        "|---|---|---|---|---|---|",
        *[f"| 第 {i+1} 週 | {plan(i)[1]} |  |  |  |  |" for i in range(weeks)],
        "",
        "六篇之後就算得出邊個版本贏。留意「撳 link」先係重點 —— ",
        "版本 B 就算觸及高，如果冇人撳落留言撳 link，一樣係輸。\n",
        "---\n",
    ]
    parts += [render(t) for t in topics]

    parts += ["## 回覆模板\n",
              "貼完之後最重要嘅一步：有人留言就要回。Facebook 排嘅係互動，",
              "一條有人回嘅留言串會令成篇文喺其他人個 feed 度再浮返上去。",
              "下面係一定會收到嘅問題，答案預先寫好。\n"]
    for q, a in REPLIES:
        parts.append(f"**{q}**\n```\n{a}\n```\n")

    OUT.write_text("\n".join(parts))
    print(f"{len(TOPICS)} 個題目 × 2 個版本 + 留言 + {len(REPLIES)} 個回覆模板")
    print(f"  -> {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
