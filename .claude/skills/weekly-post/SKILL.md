---
name: weekly-post
description: 出今個星期嘅 Facebook 群組貼文同第一個留言。用嚟每週推 hkfengshuimap.com 落 165K 人嗰個群組。用戶打 /weekly-post 就跟呢套做。
---

# 每週群組貼文

用戶每個星期撳一次。你要做嘅嘢全部喺下面，唔使問佢。

## 規則

1. 行 `python3 pipeline/weekly.py`。佢會自己由 `docs/post-log.json` 數到
   今個星期係第幾週，揀返題目同版本（A 定 B），出齊貼文同第一個留言。
2. **原文照搬俾用戶**，貼文同留言各自入一個 code block，等佢一撳就 copy 到。
   唔好改字、唔好「執靚啲」、唔好刪 disclaimer——嗰句 disclaimer 係佢嘅保護。
3. 提返佢嗰個版本點做：
   - **A**（link 喺正文）：排得期。群組 → 三點 → 群組設定 → Admin Assist →
     Publish a custom post。留言遲幾個鐘補都得，而且**唔再貼 link**。
   - **B**（link 喺留言）：**排唔到期**。排期出嘅貼文唔識自己留言，所以佢要
     喺場，出街即刻貼第一個留言。
4. 叫佢貼完打 `python3 pipeline/weekly.py --done`，或者叫你幫佢行。
5. 出咗一日之後，佢會俾三個數（觸及 / 撳 link / 留言）。行
   `python3 pipeline/weekly.py --log <觸及> <撳link> <留言>`，跟住行 `--score`
   報返 A 同 B 邊個贏緊。**夠六篇先好落結論**，唔夠就照講「仲未夠數」。

## 落結論嗰陣要記住

比嘅係**撳入嚟嘅人數**，唔係觸及。版本 B 就算觸及高，冇人撳落留言撳 link 一樣係輸。
`--score` 已經係咁計，唔好自己另外解讀個觸及數。

## 一定唔好做

- **唔好寫程式幫佢出 post。** Facebook 2024 年 4 月 22 日由所有 API 版本移除咗
  Groups API，連 `publish_to_groups` permission 都刪埋，就係為咗截停自動出文。
  用瀏覽器自動化繞過去，賭嘅係佢個 165K 群組同個account。撳掣嗰下留返俾佢。
- **唔好自己作數字。** 篇文入面每個數都係 `data/scores.json` 計出嚟。要新數字
  就加個題目落 `pipeline/make_posts.py` 嘅 `TOPICS`，由數據計，唔好喺文字度寫死。
- **唔好將啱啱 rebuild 嘅數當咗已經出咗嗰篇嘅數。** `docs/posts.md` 會被重寫，
  `docs/post-log.json` 唔會——成績只記喺 log 嗰邊。

## 用戶問「今個星期出咩？」以外嘅嘢

- 想睇齊十二個星期：`docs/posts.md`
- 想加題目 / 改文案：`pipeline/make_posts.py`（`TOPICS` 同 `REPLIES`）
- 數據 rebuild 咗想更新啲榜：`python3 pipeline/make_posts.py`
