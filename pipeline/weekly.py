"""今個星期出邊篇 —— 唔使揭文件，唔使數到第幾週。

docs/posts.md 係十二個星期一次過攤開嚟睇嘅；呢個係每個星期揀返嗰一篇。
排期唔喺呢度重寫，問 make_posts.plan()，所以兩邊冇可能各數各。

進度同成績記喺 docs/post-log.json，佢唔會被 make_posts.py 冚 ——
數據 rebuild 之後啲分會變、榜會變，但你已經出咗嘅嘢同收返嚟嘅數唔應該變。

    python3 pipeline/weekly.py              今個星期出咩，連字
    python3 pipeline/weekly.py --done       記低出咗，下次跳去下一週
    python3 pipeline/weekly.py --log 2100 63 9    補返上一篇嘅 觸及/撳link/留言
    python3 pipeline/weekly.py --score      睇 A 同 B 邊個贏緊
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from make_posts import TOPICS, load, pieces, plan  # noqa: E402

LOG = ROOT / "docs" / "post-log.json"
RULE = "─" * 64


def log_read() -> dict:
    if LOG.exists():
        return json.loads(LOG.read_text())
    return {"weeks": []}


def log_write(d: dict) -> None:
    LOG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def build(i: int) -> tuple[dict, str, dict]:
    fn, ver = plan(i)
    t = fn(*load())
    return t, ver, pieces(t)


def show(i: int) -> None:
    t, ver, pc = build(i)
    n = i + 1
    print(f"\n第 {n} 週 · {t['name']} · 版本 {ver}")
    print(RULE)
    if ver == "A":
        print("link 喺正文，所以可以排期，你唔使喺場。")
        print("群組 → 三點 → 群組設定 → Admin Assist → Publish a custom post")
    else:
        print("link 喺留言，所以唔排得期 —— 排期出嘅文唔識自己留言。")
        print("直接喺群組開個 post 貼，出街之後即刻貼埋下面個留言。")
    print(RULE)
    print(f"\n【貼文】\n\n{pc[ver]}\n")
    print(RULE)
    label = "出街後即刻貼" if ver == "B" else "出街後幾個鐘內貼，唔再貼 link"
    print(f"\n【第一個留言 · {label}】\n\n{pc['com_' + ver]}\n")
    print(RULE)
    print("有人留言就要回 —— 回覆模板喺 docs/posts.md 最底。")
    print("貼完打： python3 pipeline/weekly.py --done\n")


def done(i: int) -> None:
    t, ver, _ = build(i)
    d = log_read()
    d["weeks"].append({"week": i + 1, "name": t["name"], "version": ver,
                       "posted": dt.date.today().isoformat(),
                       "reach": None, "clicks": None, "comments": None})
    log_write(d)
    print(f"記低咗：第 {i+1} 週 · {t['name']} · 版本 {ver} · {dt.date.today()}")
    print("出咗一日之後撳「查看成效」，抄低個數：")
    print("  python3 pipeline/weekly.py --log <觸及> <撳link> <留言>")


def record(vals: list[str]) -> None:
    d = log_read()
    # 補最後一篇仲未有數嗰個 —— 通常係啱啱出咗嗰篇。
    todo = [w for w in d["weeks"] if w["reach"] is None]
    if not todo:
        return print("冇篇文等緊填數。先 --done。")
    w = todo[-1]
    for k, v in zip(("reach", "clicks", "comments"), vals):
        w[k] = int(v)
    log_write(d)
    print(f"第 {w['week']} 週（版本 {w['version']}）：觸及 {w['reach']:,} · "
          f"撳 link {w['clicks']} · 留言 {w['comments']}")


def score() -> None:
    d = log_read()
    got = [w for w in d["weeks"] if w["reach"] is not None]
    if not got:
        return print("仲未有數。")
    print(f"\n{'版本':<4}{'篇數':>4}{'平均觸及':>10}{'平均撳link':>12}{'撳入率':>9}")
    print(RULE)
    for v in ("A", "B"):
        g = [w for w in got if w["version"] == v]
        if not g:
            continue
        r = sum(w["reach"] for w in g) / len(g)
        c = sum(w["clicks"] or 0 for w in g) / len(g)
        print(f"{v:<4}{len(g):>4}{r:>10,.0f}{c:>12,.1f}{100*c/r:>8.2f}%")
    print(RULE)
    if len(got) < 6:
        print(f"得 {len(got)} 篇，夠六篇先好落結論。\n")
    else:
        # 觸及高但冇人撳，等於冇用 —— 所以攞撳入嘅絕對數嚟比，唔係觸及。
        best = max("AB", key=lambda v: sum(
            w["clicks"] or 0 for w in got if w["version"] == v) /
            max(1, len([w for w in got if w["version"] == v])))
        print(f"版本 {best} 帶到入嚟嘅人多啲。之後一直用佢。\n")


def main() -> None:
    a = sys.argv[1:]
    i = len(log_read()["weeks"])          # 出過幾多篇，就輪到下一篇
    if i >= len(TOPICS) * 2:
        print(f"十二個星期出齊。再行落去會由頭循環（第 {i % (len(TOPICS)*2) + 1} 週）。")
        i %= len(TOPICS) * 2
    if not a:
        show(i)
    elif a[0] == "--done":
        done(i)
    elif a[0] == "--log":
        record(a[1:4])
    elif a[0] == "--score":
        score()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
