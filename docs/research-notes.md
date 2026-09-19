# 風水地圖 — 研究筆記（2026-09-19 實測）

## A. 你貼嗰個網站係咩
- StoryMap: https://storymaps.arcgis.com/stories/e67f149fbed143c9a00ae4d25a47ad62
- 題目：GIS Application in Feng Shui — Rating the Feng Shui of Residential
  Buildings in Hong Kong during Nine Luck Period（署名 YSA2023_02）
- ArcGIS item metadata：created 2023-02-20 / modified 2023-03-13，owner `transfer_admin`
- licenseInfo = 空（即係冇授權聲明 → 唔可以假設可以商用）
- Web app（Experience Builder）：
  https://experience.arcgis.com/experience/63fbc80674004691abc063dabd4aeba0/

### 背後嘅公開 FeatureServer（可以直接 query，無 key）
```
https://services4.arcgis.com/jim2f7B8UyqRDApI/arcgis/rest/services/HKFengShui_WFL1/FeatureServer/0
```
- 62,751 個 building polygon，maxRecordCount 2000，SR 3857
- 支援 spatial query（實測：point + 150m buffer → 147 棟）
- 欄位：
  - 識別：OFFICIALBU(EN名) / OFFICIAL_1(中文名) / NAME_TC,NAME_EN(區)
  - 建築：TOPHEIGHT, NUMABOVEGR, NUMBASEMEN, INFODESCRI
  - 山水：Mt_NearDIS, Mt_NearAng, Mt_Dir/_8/_4, Wt_NearDIS, Wt_NearAng, Wt_Dir/_8/_4
  - 分數：MWDir8Scor, MWDir4Scor, MWDir8100, MWDir4100, MtDis100, WtDis100,
          Traffic(AADT), Traffic100, AncilScore, Ancil100, EnvirSco_1, TotalSco_1

範例（最高分）：
```
温莎道 BOULEVARD DU PALAIS 大埔區  Mt:SW Wt:NE  Env 91.6 / Traffic 76.1 / Ancil 90.1 → 90.60
滿湖花園43座 The Riviera Blk43 西貢區  Mt:SW Wt:NE  → 90.18
```
問題：好多 record 嘅名係 "N/A"；亦夾雜商業樓（維寶商業大廈）同變電站 → 「住宅」filter 唔乾淨。

## B. 免費政府 API（全部 2026-09-19 實測通過，除註明外唔需要 key）

### 1. 底圖 tile（標準 XYZ，無 key）— 可以完全取代 Google Maps
```
地形圖 https://mapapi.geodata.gov.hk/gs/api/v1.0.0/xyz/basemap/WGS84/{z}/{x}/{y}.png
航攝圖 https://mapapi.geodata.gov.hk/gs/api/v1.0.0/xyz/imagery/WGS84/{z}/{x}/{y}.png
中文標籤 https://mapapi.geodata.gov.hk/gs/api/v1.0.0/xyz/label/hk/tc/WGS84/{z}/{x}/{y}.png
```
z 10–20，另有 HK80 版。實測 z14/z16 三層都 HTTP 200。
需要：地政總署 logo + "Map from Lands Department" 版權聲明。

### 2. 地址 → 經緯度（ALS，無 key，直接出 WGS84）
```
https://www.als.gov.hk/lookup?q=<address>&n=<count>   (Accept: application/json)
```
出 EngPremisesAddress / ChiPremisesAddress / GeoAddress / Latitude / Longitude / Easting / Northing

### 3. GeoInfo Map API（無 key，座標係 HK80 grid，要轉換）
```
地點搜尋 https://www.map.gov.hk/gs/api/v1.0.0/locationSearch?q=太古城中心
附近設施 https://www.map.gov.hk/gs/api/v1.0.0/searchNearby?x=840383&y=816336&lang=zh
         → 1km 內 532 個設施（有 name/address，但 output 冇 category 欄位，要自己靠名分類）
識別     https://www.map.gov.hk/gs/api/v1.0.0/identify?x=..&y=..
```

### 4. CSDI 空間數據（無 key）— 500+ datasets，支援 OGC WFS / WMS / ArcGIS REST
注意：舊嘅 Data Query Service (DQS) 2025-09-19 已停用，要用 WFS/WMS/REST。
```
WFS  https://portal.csdi.gov.hk/server/services/common/<datasetId>/MapServer/WFSServer
     ?service=WFS&version=2.0.0&request=GetFeature&typeNames=csdi:<Layer>
     &outputFormat=GeoJSON&srsName=EPSG:4326&bbox=<minLat,minLon,maxLat,maxLon>&count=<n>
REST https://portal.csdi.gov.hk/server/rest/services/common/<datasetId>/MapServer?f=json
```
count 上限 10,000。GetCapabilities 拎 typeNames。

已實測 dataset id：
| 數據 | datasetId | 備註 |
|---|---|---|
| Building 樓宇 | landsd_rcd_1637211194312_35158 | typeNames: csdi:Building（另有 BuildingName / OP / BuildingLotNoInfo） |
| Digital Terrain Model | landsd_rcd_1638158088368_93806 | 山勢分析用 |
| District Boundary | had_rcd_1634523272907_75218 | |
| Road Network | td_rcd_1638949160594_2844 | |
| Traffic Flow Census | td_rcd_1638950691670_3837 | |
| Bridge | hyd_rcd_1632360050986_38630 | |
| Fire Station | hkfsd_rcd_1634798867463_89696 | |
| Police Station | police_rcd_1639562064290_95464 | |

Building 實測 return（銅鑼灣 bbox）：
```
BuildingNameTC 柏寧酒店 / BuildingNameEN The Park Lane
BuildingBlockType Tower, TopHeight 82.9, BaseHeight 3.6, Storeys 22, Status Active
BuildingCSUID 3725815819T20050430, GeoRefNo 3725815819, MultiPolygon
```
→ 即係我哋可以自己用最新數據重做一次評分，唔需要靠 2023 年嗰個 layer。

### 5. 3D 數據（要免費申請 key：3dmap@landsd.gov.hk）
```
https://data.map.gov.hk/api/3d-data/3dsd/WGS84/{building|infrastructure}/tileset.json?key=<key>
```
Cesium 3D Tiles，全港覆蓋，商用/非商用都免費，要標明政府為來源。
限制 5GB/s bandwidth、100 concurrent users。

### 6. 其他 CSDI API（免費，值得留意）
- Streetscape 360（全景圖，類似 Street View）
- 3D Indoor Building Map / 3D Indoor MTR Station Map（室內佈局 → 內巒頭分析）
- 3D Pedestrian Route Search
- Land Parcel & Public Utility Number Search（地段/PRN）
- Lot Index（私人地段 / GLA / STT）
- Vector Map + Vector Map Label（vector tile，可以自己改 style）

## C. Google Maps 現況（2026）
- 2025-03 起取消 $200 統一 credit，改為每個 SKU 獨立免費額：
  Essentials 10,000 / Pro 5,000 / Enterprise 1,000 次每月
- 收費 US$2–40 per 1,000 requests
→ 結論：底圖同 geocoding 用政府 API（無 key、無限額、全中文），
  Google 只有喺需要 Street View / Places 評論 / 全球覆蓋嗰陣才值得用。

## D. 九運資料狀況
- 九運 = 2024–2043，九紫離火，離卦在南
- 主流大環境原則：南見山 / 北見水（「北水南山」），次選東南見水
  → 同 StoryMap 嘅 scoring 方向一致
- 網上九運區域分析（qualitative，可做參考層，非 API）：
  - hokming.com（港島 / 九龍 / 新界離島分區 財丁旺衰）
  - edigest.hk、cosmopolitan.com.hk、hk.ulifestyle.com.hk 等分區推介
- 現有工具全部係「羅盤 / 排盤」類，冇全港逐棟樓地圖：
  - 風水立極尺-玄空飛星（Chrome extension，羅盤疊 Google Maps）
  - 袖裡乾坤·飛星風水（Android 排盤）
  - 風水羅盤（iOS，九宮飛星 + 八宅）
  - mjc-fs.com（人手線上風水服務）
→ 市場空隙：全港 building-level、可搜尋、可篩選嘅風水地圖，未有人做。

## E. 拎唔到嘅數據（要注意）
- 單位級坐向 / 樓層平面圖：屋宇署圖則唔係 machine-readable open data
  → 只可以由 building footprint 長軸 + 路網 frontage 推算「大約」坐向
- 成交價 / 樓盤放盤：唔免費（EPRC、中原、美聯）；差估署只出總指數
- 室內佈局：只有 CSDI 3D Indoor（公共建築 / 港鐵站為主），住宅單位冇
