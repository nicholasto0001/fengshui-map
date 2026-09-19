# 香港風水地圖 · 九運

逐棟樓宇嘅九運風水評分地圖。全部用香港政府免費公開數據，零 API key。

## 即刻試

雙擊 **`開啟風水地圖.command`**，瀏覽器會自動開。
（或者喺呢個資料夾行 `python3 -m http.server 4180`，再開 http://localhost:4180）

`index.html` 係單一檔案、冇 build step，直接雙擊都開到。

## 現況

| 部分 | 狀態 |
|---|---|
| 地圖介面 | ✅ 做好，手機／電腦都用得 |
| 分區概覽 + 逐棟樓評分 | ✅ |
| 地址／屋苑搜尋 | ✅ 政府 ALS + 圖層樓名搜尋 |
| 評分數據 | ⚠️ **仍然用 2023 年現成圖層**（62,751 棟，唔包新盤） |
| 自建評分 pipeline | 🔧 已寫好，未跑過完整一次 |
| 每日自動更新 | 🔧 workflow 已寫，未部署 |
| 風水 logic | ⚠️ 只有外巒頭，冇坐向飛星盤 — 詳見 `docs/fengshui-logic.md` |

## 資料來源（全部免費、免 key）

| 用途 | 來源 |
|---|---|
| 地形圖 / 衛星圖 / 中文標籤 tile | 地政總署 `mapapi.geodata.gov.hk` |
| 地址定位 | 數字政策辦公室 ALS `als.gov.hk` |
| 樓宇資料（live，含新盤） | CSDI `portal.csdi.gov.hk` |
| 現行評分（2023 快照） | ArcGIS `HKFengShui_WFL1` |

地圖須標示「Map from Lands Department」同地政總署標誌 — 正式發佈前要加埋 logo。

Google 地圖係可選底圖，撳右上角圖層掣輸入你自己嘅 API key（需要 Google Cloud 帳戶同啟用付費）。
唔輸入都用得，政府底圖有齊中文樓名同地形等高線。

## Pipeline

```bash
pip install -r pipeline/requirements.txt

python3 pipeline/reconstruct_terrain.py   # 山／水邊界參考點（月更）
python3 pipeline/fetch_buildings.py       # CSDI 現役樓宇（日更）
python3 pipeline/fetch_facilities.py      # 負面設施（日更）
python3 pipeline/score.py                 # 計分 -> data/scores.json
```

純標準庫 + certifi，冇 geopandas / shapely 依賴，GitHub Actions 直接跑得。

**點樣搵到山同水**：`reconstruct_terrain.py` 用返 2023 圖層入面每棟樓「最近山／水嘅距離同角度」，
由樓宇位置按距離同角度推算返出去，就還原到山邊同海岸線嘅點雲。62,751 個樣本足夠覆蓋全港。
長遠應該改用地政總署 DTM 原始柵格重做一次。

## 自動更新

`.github/workflows/daily.yml` — 每日香港時間早上 5 點重新抓數據、計分、部署上 GitHub Pages。
部署後會有一條公開 link，WhatsApp send 得，唔使裝嘢。

## 文件

- `docs/fengshui-logic.md` — 風水計算方法完整拆解、驗證、同缺陷（**先睇呢份**）
- `docs/research-notes.md` — 所有政府 API endpoint、dataset ID、實測結果
- `docs/mwds-scoring-table.png` / `weighting-flow.png` — 原始方法論圖

## 免責

外巒頭地理分析，唔包括坐向飛星盤、元運、樓層同室內佈局。僅供參考，不構成置業建議。
