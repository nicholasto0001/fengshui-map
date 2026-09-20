# SEO 完整計劃

寫於 2026-09-20。基於實測 + 2026 年最新研究（來源見底）。

---

## 一、現況實測

```
Google 見到嘅可見文字            270 個字元
可以被索引嘅頁面                 1 版
sitemap.xml                      404
robots.txt                       Cloudflare 預設，冇指向 sitemap
JSON-LD 結構化資料               冇
<html lang="zh-Hant-HK">         ✓ 有
<link rel="canonical">           ✓ 有
<h1>香港風水地圖</h1>            ✓ 有
手機體驗                         ✓ 好
```

基本功做咗，但**內容層面近乎空白**。

---

## 二、研究：2026 年嘅三個關鍵事實

### 1. Google 識行 JavaScript，但唔可以靠佢

Google 係**兩階段索引**：先攞原始 HTML，之後先排隊行 JavaScript —— **第二階段可以
遲幾個鐘到幾日**。2026 年 3 月 Search Console 數據顯示，**80% 嘅單頁應用（SPA）有
爬取預算浪費**：頁面排咗隊等渲染，但最終從來冇渲染過。

> **對我哋嘅意思：** 唔可以靠「反正 Google 識行 JS」。SEO 要用嘅內容必須喺原始
> HTML 入面就有。好彩嘅係 —— 我哋已經有個 Worker 喺 edge 改寫緊 OG tag，
> **同一個機制可以直接輸出真 HTML，唔使改架構、唔使加 build step。**

### 2. ⚠️ 大量薄內容頁而家會拖低成個網站

呢個係 2026 年最大變化。Google 嘅「scaled content abuse」政策：

- 判斷標準係**意圖同價值**，唔理你係人寫、AI 寫定程式生成
- **薄內容頁而家唔止係自己排唔到 —— 佢會拖低成個域名嘅權重（sitewide demotion）**

> **對我哋嘅意思：** 我原本話「出 20,000 版樓宇頁」係**太急**。一次過出一大批
> 每版得幾行字嘅頁，會反而害死首頁同屋苑頁。要**分批出、量度、先再加**。

### 3. 但有數據支撐嘅程式生成頁，完全冇問題

研究明確指出，**每版有獨家數據、有真實用途嘅頁面，就算去到百萬版都係容許嘅**。
能夠站得住腳嘅模式係：

| 條件 | 我哋有冇 |
|---|---|
| 每版有獨家數據 | ✅ 分數、飛星盤、山水方位、入伙年份 —— 冇人有 |
| 人手寫嘅模板引言／結語 | ⬜ 要寫 |
| 明確服務一個用戶任務 | ✅「我想知呢個盤風水點」 |
| 連去一版人手寫嘅主幹文章 | ⬜ 要寫（方法論頁） |
| 控制爬取預算 | ⬜ 要做（分批 + sitemap 分檔） |

**四樣入面我哋有兩樣，另外兩樣要補。補咗就安全。**

---

## 三、第一階段：搵「香港風水地圖」要搵到我哋

呢個目標**唔難**，因為佢近乎係品牌字，競爭極低。但要做齊六步。

### Step 1 — Google Search Console（最重要，要你做）

Google 唔知你個網站存在，就乜都免問。

1. 去 **https://search.google.com/search-console**
2. 左上揀 **Add property** → 揀左邊嗰個 **Domain**（唔係右邊 URL prefix）
3. 輸入 `hkfengshuimap.com`
4. 佢會俾你一段 **TXT record**，樣似 `google-site-verification=xxxxx`
5. 去 **Cloudflare → 你個域名 → DNS → Add record**
   - Type：`TXT`
   - Name：`@`
   - Content：貼嗰段
   - Save
6. 返 Search Console 撳 **Verify**

> 用 DNS TXT 係 Google 建議嘅方法，唔會觸發任何重新評估。DNS 生效通常幾分鐘，
> Search Console 最多要 24 小時確認。

### Step 2 — 自己嘅 robots.txt

而家 serve 緊 Cloudflare 預設嗰個，冇指向 sitemap。要換成自己嘅：

```
User-agent: *
Allow: /

Sitemap: https://hkfengshuimap.com/sitemap.xml
```

### Step 3 — sitemap.xml

由 pipeline 生成。第一階段只需要放幾版：首頁、方法論頁、私隱政策。

### Step 4 — 首頁要有真內容

而家得 270 字。要加一段**真正解釋呢個網站係乜**嘅文字，喺原始 HTML 入面就存在。

唔係塞關鍵字 —— 係真係寫清楚：呢個地圖係乜、數據嚟自邊個政府部門、分數點計、
覆蓋幾多幢樓、限制係乜。呢啲本來就應該有，而家只係散落喺 app 入面。

### Step 5 — JSON-LD 結構化資料

加 `WebSite` + `Organization`，令 Google 明白「香港風水地圖」係一個實體名，
唔係四個中文字咁簡單。

### Step 6 — 出 post（你已經計劃緊）

**呢步對 SEO 嘅作用比你想像中大：**

- Facebook 條 link 本身係 nofollow，唔傳權重
- **但 165,000 人入面有人會直接 Google「香港風水地圖」** —— 品牌搜尋量本身就係
  Google 用嚟判斷「呢個名對應呢個網站」嘅最強信號
- 有人分享去 blog、討論區、WhatsApp 之後，自然會出現真正嘅外部連結

### Step 7 — 主動叫 Google 收錄

Search Console → **URL Inspection** → 貼首頁網址 → **Request Indexing**

> 每日有軟性上限（約 10–12 條），所以唔好一次過貼幾十條。首頁優先。

**第一階段預期：1–2 星期內，搜「香港風水地圖」應該搵到。**

---

## 四、第二階段：攻長尾

### 策略：唔好追「風水」，要攻「屋苑名 + 風水」

| 關鍵字 | 競爭 | 獨家內容 | 意圖 | 追唔追 |
|---|---|---|---|---|
| 「風水」 | 極高（麥玲玲、蘇民峰、媒體） | ❌ | 模糊 | **❌ 唔好** |
| 「香港風水地圖」 | 極低 | ✅ | 高 | ✅ 第一階段 |
| **「XX屋苑 風水」** | **極低** | ✅ 409 個 | **極高** | **✅ 主攻** |
| 「XX區 風水」 | 中 | ✅ 18 區 | 高 | ✅ |
| 「九運 旺 樓盤」 | 中 | ✅ | 高 | ✅ |

**實測佐證：** 搜「日出康城 風水」，排頭位係 Facebook post、YouTube 片、個別師傅
blog、e-zone 文章。**連全香港最出名嗰個樓盤都冇一個結構化頁面**，其餘幾百個屋苑
更加空白。

### 順序（一定要照呢個次序，唔好跳）

#### 2A. 先寫一版人手寫嘅「方法論」主幹頁

```
/method  — 呢個分數點計出嚟？
```

內容：逆向工程 2023 官方圖層、三元九運點定、坐向點推算、五個常見錯誤、
覆蓋率同限制。**呢版係人手寫嘅，唔係生成嘅。**

呢版嘅作用：所有程式生成嘅頁都連去呢度。研究明確指出，「連去一版人手寫嘅主幹
文章」係令程式生成頁站得住腳嘅其中一個條件。

#### 2B. 18 個分區頁

```
/d/大埔區
```

每版：該區平均分、樓宇數、等級分佈、頭 50 名樓宇（連結）、該區山水地理特點
（人手寫嘅一段）、連去方法論頁。

**18 版，每版都有實質內容，零風險。**

#### 2C. 409 個屋苑頁 ← 最值錢

```
/e/日出康城
```

每版：屋苑名、座數、單位數、入伙年份、管理公司、**每一座嘅分數同飛星格局**、
同區排名、連去分區頁同方法論頁。

**409 版，每版有獨家數據（成座座數同飛星），完全符合「可辯護」嘅標準。**

#### 2D. 樓宇頁 — 分批出，唔好一次過

```
/b/<座標>/頌真閣
```

⚠️ **呢度係唯一有風險嘅一層。** 做法：

| 批次 | 數量 | 條件 | 之後做乜 |
|---|---|---|---|
| 第 1 批 | ~2,000 | 有名 + 住宅 + 起到飛星盤 + 有屋苑資料 | **等 4–8 星期**，睇 Search Console：收錄率？有冇點擊？ |
| 第 2 批 | ~8,000 | 有名 + 住宅 + 起到飛星盤 | 同樣量度 |
| 第 3 批 | 其餘 | 視乎前兩批表現 | 如果第 1 批收錄率低過 50%，**停手，唔好再加** |

**判斷標準：** 如果一批出咗之後，Search Console 顯示大部分頁面係「已檢索但未收錄」
（Crawled – currently not indexed），即係 Google 覺得佢哋唔夠份量 —— 嗰陣應該
**加厚內容**，唔係加更多頁。

---

## 五、唔好做嘅嘢

| 唔好做 | 點解 |
|---|---|
| 一次過出 84,720 版 | 2026 年薄內容頁會**拖低成個域名** |
| 追「風水」兩個字 | 追唔到，意圖亦唔啱 |
| 用 AI 生成「此樓背山面水，主財運亨通」 | 係假嘅，違背成個 app 嘅誠實原則，而且 Google 越嚟越識分 |
| 買連結 / 交換連結 | 可以罰到成個域名 |
| 加 hreflang | 我哋只有中文一個版本，加咗反而出錯。**除非日後真係出英文版** |
| 為咗 SEO 而改到個 app 難用 | 得不償失 |

---

## 六、老實講嘅時間預期

| 時間 | 預期 |
|---|---|
| 第 1–2 星期 | 搜「香港風水地圖」搵到（第一階段完成） |
| 第 1–2 個月 | 分區頁、屋苑頁開始被收錄，零星長尾流量 |
| 第 3–6 個月 | 長尾穩定，「XX屋苑 風水」開始排到 |
| 第 6 個月以後 | 長尾成為穩定流量來源 |

**出 post 帶嚟嘅流量會快好多、亦都大好多。** SEO 係長線資產 —— 佢係唯一唔使每次
靠推廣嘅流量來源，但唔好期望下個禮拜見效。兩樣並行。

---

## 七、下一步

**第一階段（我可以即刻做）：**
- robots.txt、sitemap.xml、首頁真內容、JSON-LD

**第一階段（只有你做得到）：**
- Google Search Console 驗證（DNS TXT）
- 提交 sitemap
- Request Indexing

---

## Sources

- [Vercel — How Google handles JavaScript throughout the indexing process](https://vercel.com/blog/how-google-handles-javascript-throughout-the-indexing-process)
- [JavaScript SEO in 2026: Crawlability, Rendering & Indexing](https://www.w3era.com/blog/seo/javascript-seo-guide/)
- [Google's August 2026 Spam Update — Scaled Content Abuse case studies](https://www.gsqi.com/marketing-blog/august-2026-google-spam-update-case-studies/)
- [Understanding Google's scaled content abuse policy](https://bulkbase.ai/seo/understanding-googles-scaled-content-abuse-policy)
- [Is Programmatic SEO Still Effective? A Data-Driven Analysis for 2026](https://gracker.ai/blog/is-programmatic-seo-still-effective-2026)
- [How to Get a New Site Indexed by Google in 2026](https://dev.to/mrtd/how-to-get-a-new-site-indexed-by-google-in-2026-what-works-whats-a-waste-8do)
- [Sitemaps report — Search Console Help](https://support.google.com/webmasters/answer/7451001?hl=en)
- [Ask Google to recrawl your website](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)
- [Hong Kong SEO for Multilingual English and Chinese — 2026 Guide](https://www.eliteasia.co/hong-kong-seo-agency-for-multilingual-english-and-chinese/)
