# SEO 同 AI 曝光：查到啲乜，做緊乜

---

## 一、香港人用邊啲 AI（Statcounter，2026 年 8 月）

| | 香港市佔 |
|---|---|
| ChatGPT | 48.1% |
| **Gemini** | **30.4%** |
| **Perplexity** | **13.6%** |
| Copilot | 7.1% |
| Claude | 0.57% |
| DeepSeek | 0.28% |

**最重要嘅一個結論：兩份工係同一份。**

- **Gemini（30%）讀 Google 自己個索引。** 做好 Google SEO ＝ 做緊 Gemini。
- **Perplexity ＋ ChatGPT search（約 62%）即時爬網。** 佢哋睇嘅係伺服器
  直接出嘅 HTML。
- Claude 喺香港得 0.57%，唔值得為佢做嘢。

所以唔使分兩條路。**一條路：靜態 HTML ＋ 結構清晰 ＋ 答案行先。**

---

## 二、做唔到嘅嘢，要講明

**冇任何方法令 Gemini 或者 ChatGPT「推薦」我哋。**冇 API、冇付費位、
冇注入點。任何聲稱做得到嘅人係喺度呃你。

真正有效嘅只有一樣：當有人問嗰條問題嗰陣，我哋係網上**最值得引用嗰個
答案**。AI 揀引用邊個，睇嘅係：

1. **爬蟲入唔入到**（robots.txt 已經明文放行回答型 bot）
2. **伺服器直接出嘅文字** —— AI 爬蟲唔行 JavaScript
3. **答案行先嘅結構** —— 問題做標題，第一句就答
4. **Schema 標記**
5. **第三方佐證** —— 有其他網站講過你

第 2 點係我哋最大嘅洞：八字功能全部係 JS 跑出嚟，喺 AI 眼中唔存在。
`/bazi-guide` 係靜態 HTML，所以佢先係我哋喺 AI 度嘅門面，唔係首頁。

---

## 三、llms.txt

有，但唔好當佢係策略。實測 5.15 億次 bot 請求，GPTBot／ClaudeBot／
PerplexityBot 掂 `/llms.txt` 嘅比例統計上等於零；截至 2026 Q1 冇一間
大廠公開承諾會讀。**成本五分鐘，所以照放，但唔好指望。**

---

## 四、robots.txt 嘅決定

分兩種 AI bot，兩種都放行：

- **回答型**（OAI-SearchBot、Claude-SearchBot、PerplexityBot、
  ChatGPT-User、Claude-User）—— 人問問題嗰陣去攞內容返嚟引用。
  **擋咗就完全唔會出現喺 AI 答案入面。**
- **訓練型**（GPTBot、ClaudeBot、Google-Extended）—— 攞去訓練模型。
  我哋內容本身係政府公開數據加自己計算，畀模型見到多啲冇壞。

寫出嚟唔係因為 `*` 唔夠，係因為呢個係一個決定，要有得追溯。

---

## 五、已經修好嘅缺陷（2026-09-21）

| 問題 | 影響 |
|---|---|
| Canonical 冇編碼（`/estate/Grand YOHO` 有個真空格） | 無效 URL，而且同 sitemap 嗰條唔同字串 —— canonical 訊號自己打自己 |
| 678 版 SEO 頁零個字提八字 | 最大功能喺最多人入到嘅頁面度唔存在 |
| `/district/` 同 `/district/index` 都喺 sitemap | 同一版兩條 URL |
| privacy.html 有 noindex 但又喺 sitemap | 自相矛盾嘅訊號 |
| 結構化資料只講九運評分 | 加咗 `WebApplication` 描述八字工具 |

---

## 六、「大包圍」實際點做

用戶要求：人哋講算命、八字、風水、搵師傅，都要搵到我哋。

呢個方向啱，但機制係**內容覆蓋**，唔係技巧。每一條問題要有一版靜態
HTML，問題做標題，第一句就答。

已經有嘅：

- `/bazi-guide` — 八字揀樓點計
- `/method` — 九運評分點計
- `/district/`（18 版）— 每區風水評分排名
- `/estate/`（658 版）— 每個屋苑逐座

缺口（按價值排）：

1. **各區風水** — 「觀塘風水好唔好」呢類問題而家答唔到。區頁有數據但
   冇答呢條問題
2. **凶宅點查** — 見 `docs/haunted-houses.md`。做教學唔做名單，零法律風險
3. **八字基礎** — 「點樣睇自己八字」「寒熱命係咩」。呢啲係最大流量嘅
   入口，而我哋真係答得到
4. **師傅背景** — ⚠ 小心。評論在世人士有誹謗風險，只可以引用佢哋自己
   公開發表過嘅嘢（已經喺 `docs/district-research.md` 做緊）

每一版都要：靜態 HTML、問題做 `<h2>`、第一句答、`FAQPage` schema、
互相連結。

---

## 七、量度

Google Search Console 睇 impressions 同 position。AI 曝光暫時冇官方
工具，只可以靠伺服器 log 睇 `OAI-SearchBot`／`PerplexityBot` 嘅
user-agent 有冇嚟過、嚟得幾密。
