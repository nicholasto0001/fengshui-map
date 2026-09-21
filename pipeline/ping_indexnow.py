"""出版之後即刻通知 Bing、Yandex 佢哋，唔使等佢哋自己爬過嚟。

點解要有呢樣
------------
Google 有 Search Console 可以逐條 URL 撳「Request indexing」，但撳唔晒
683 版，而且有每日限額。其餘嘅搜尋引擎連個掣都冇。

IndexNow 係 Bing 同 Yandex 2021 年一齊搞嘅開放協議：你 POST 一批 URL
上去，佢哋就插隊去爬，通常 2–24 小時入索引。Naver、Seznam、Yep 都收。
Google 唔支援，佢自己一套。

對我哋嘅意義唔止係 Bing 本身 —— ChatGPT search 用緊 Bing 個索引，所以
入咗 Bing，等於多咗一條路俾 AI 引用。

點運作
------
個 key 係公開嘅，唔係秘密：佢擺喺 <key>.txt 就係用嚟證明你控制住呢個
網域。所以入 git 冇問題。

只喺真正上線嗰陣先 ping。Staging 係 `Disallow: /`，叫人哋去爬一個叫
人哋唔好爬嘅網站，係自相矛盾。

跑法：python3 pipeline/ping_indexnow.py https://hkfengshuimap.com
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).parent.parent
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10_000          # 協議上限


def key_file() -> tuple[str, str] | None:
    """個 key 就係檔名本身 —— <key>.txt，入面亦都係同一串。"""
    for f in ROOT.glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{8,128}", f.stem):
            return f.stem, f.name
    return None


def urls_from_sitemap() -> list[str]:
    sm = ROOT / "sitemap.xml"
    if not sm.exists():
        return []
    return re.findall(r"<loc>([^<]+)</loc>", sm.read_text("utf8"))


def main() -> int:
    host_url = sys.argv[1] if len(sys.argv) > 1 else "https://hkfengshuimap.com"
    host = host_url.split("//", 1)[-1].strip("/")

    got = key_file()
    if not got:
        print("冇搵到 IndexNow key 檔（根目錄嘅 <key>.txt）—— 跳過")
        return 0
    key, fname = got

    urls = [u for u in urls_from_sitemap() if host in u]
    if not urls:
        print("sitemap 度攞唔到 URL —— 跳過")
        return 0

    sent = 0
    for i in range(0, len(urls), BATCH):
        chunk = urls[i:i + BATCH]
        body = json.dumps({
            "host": host,
            "key": key,
            "keyLocation": f"{host_url.rstrip('/')}/{fname}",
            "urlList": chunk,
        }).encode()
        req = urllib.request.Request(
            ENDPOINT, data=body,
            headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                # 200 收咗、202 收咗但 key 未驗；兩個都算成功
                print(f"  {len(chunk):,} 條 → HTTP {r.status}")
                sent += len(chunk)
        except Exception as e:                      # noqa: BLE001
            # 通知唔到唔應該搞冧個 deploy —— 佢係加速，唔係必需品。
            print(f"::warning::IndexNow ping 失敗（{e}）—— 唔影響上線")
            return 0
    print(f"IndexNow：通知咗 {sent:,} 條 URL（Bing、Yandex、Naver、Seznam、Yep）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
