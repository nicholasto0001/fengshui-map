/**
 * 分享卡 —— 喺部機度即場畫，然後分享張圖本身。
 *
 * 點解唔用 OG 卡：OG 卡係逐個分數預先整定（og/s21.png … og/s89.png），
 * 全港所有 80 分嘅樓共用一張，所以入面冇可能有樓名。收到嘅人第一眼望
 * 個圖，見到「80 大吉」但唔知講緊邊幢樓 —— 而人係望圖唔係望字嘅。
 *
 * 逐幢樓生成又唔得：84,720 幢預先整唔晒，喺 Cloudflare Worker 即場畫
 * 又要成套中文字體（5–15 MB，放唔落）。
 *
 * 但瀏覽器本身就有中文字體。所以喺 canvas 畫完，用 navigator.share 分享
 * 張圖 —— 收到嘅人見到一張大圖，唔使靠 WhatsApp unfurl。唔支援就跌返
 * 落原本嗰個連結分享，OG 卡照樣做後備。
 *
 * 刻意冇畫「交通」分：全港每一幢都係 50，畫一條人人一樣嘅 bar 落去，
 * 等於當住人講緊一樣我哋根本冇量過嘅嘢。改為畫最近山水嘅距離同方向,
 * 嗰啲係逐幢樓真係計過嘅。
 */
const W = 1080, H = 1080;
const IVORY = "#faf9f6", INK = "#141414", INK2 = "#57544d", INK3 = "#8b8880";
const RED = "#a7161e", GOLD = "#e1b370", LINE = "#e6e3dc";
const RAMP = ["#a01f1f", "#d76f6f", "#cfcabb", "#4da79a", "#0f6354"];
const BREAKS = [41, 46, 52, 58];
// 方位要用中文。收到張卡嘅人唔會由 "SE" 諗到「東南」—— 而張卡由頭到尾
// 都係中文，剩返兩個英文縮寫喺度好突兀。
const DIR_TC = {N:"北", NE:"東北", E:"東", SE:"東南",
                S:"南", SW:"西南", W:"西", NW:"西北"};

const band = v => RAMP[BREAKS.findIndex(b => v < b) === -1 ? 4 : BREAKS.findIndex(b => v < b)];
const FONT = '-apple-system,BlinkMacSystemFont,"PingFang HK","Hiragino Sans CNS",'
           + '"Microsoft JhengHei","Noto Sans CJK TC",sans-serif';

function rr(c, x, y, w, h, r){
  c.beginPath();
  c.moveTo(x + r, y);
  c.arcTo(x + w, y, x + w, y + h, r);
  c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r);
  c.arcTo(x, y, x + w, y, r);
  c.closePath();
}

/** 字太長就縮細，縮到最細都仲長就斬。名係主角，唔可以出界。 */
function fitText(c, text, max, size, weight = "700"){
  let s = size;
  for(; s > size * 0.55; s -= 2){
    c.font = `${weight} ${s}px ${FONT}`;
    if(c.measureText(text).width <= max) return {text, size: s};
  }
  c.font = `${weight} ${s}px ${FONT}`;
  let t = text;
  while(t.length > 2 && c.measureText(t + "…").width > max) t = t.slice(0, -1);
  return {text: t + "…", size: s};
}

export async function buildingCard(o, {name, en, district, level, rank, mark}){
  await (document.fonts ? document.fonts.ready : Promise.resolve());
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const c = cv.getContext("2d");
  const col = band(o.total);

  c.fillStyle = IVORY; c.fillRect(0, 0, W, H);

  /* 頂：品牌條 */
  c.fillStyle = RED; c.fillRect(0, 0, W, 132);
  if(mark){
    c.save(); rr(c, 48, 26, 80, 80, 20); c.clip();
    c.drawImage(mark, 48, 26, 80, 80); c.restore();
  }
  c.fillStyle = "#fff"; c.font = `700 40px ${FONT}`; c.textBaseline = "alphabetic";
  c.fillText("香港風水地圖", 148, 62);
  c.fillStyle = GOLD; c.font = `500 25px ${FONT}`;
  c.fillText("三元九運 · 第九運 2024–2043", 148, 100);

  /* 主卡 */
  c.save();
  c.shadowColor = "rgba(0,0,0,.09)"; c.shadowBlur = 34; c.shadowOffsetY = 10;
  c.fillStyle = "#fff"; rr(c, 48, 186, W - 96, 706, 36); c.fill();
  c.restore();

  /* 樓名 —— 張卡嘅主角，所以字最大、位最好 */
  const nm = fitText(c, name, W - 200, 78);
  c.fillStyle = INK; c.font = `700 ${nm.size}px ${FONT}`;
  c.textAlign = "center";
  c.fillText(nm.text, W / 2, 300);

  const sub = [en && en !== name ? en : null, district].filter(Boolean).join("   ·   ");
  if(sub){
    const st = fitText(c, sub, W - 220, 32, "500");
    c.fillStyle = INK3; c.font = `500 ${st.size}px ${FONT}`;
    c.fillText(st.text, W / 2, 348);
  }

  /* 分數環 */
  const cx = W / 2, cy = 512, R = 108;
  c.beginPath(); c.arc(cx, cy, R, 0, Math.PI * 2);
  c.fillStyle = col; c.fill();
  c.fillStyle = "#fff"; c.font = `700 104px ${FONT}`; c.textBaseline = "middle";
  c.fillText(String(Math.round(o.total)), cx, cy + 4);
  c.textBaseline = "alphabetic";

  c.fillStyle = col; c.font = `700 46px ${FONT}`;
  c.fillText(level, cx, cy + R + 76);
  if(rank){
    c.fillStyle = INK2; c.font = `500 30px ${FONT}`;
    c.fillText(rank, cx, cy + R + 122);
  }

  /* 山水 —— 逐幢樓真係計過嘅嘢 */
  c.textAlign = "left";
  const dir = d => DIR_TC[d] || d || "";
  const facts = [];
  if(o.mt_d != null) facts.push(["最近山", `${o.mt_d} 米`, dir(o.mt_dir)]);
  if(o.wt_d != null) facts.push(["最近水", `${o.wt_d} 米`, dir(o.wt_dir)]);
  if(o.sit_m && o.face_m) facts.push(["坐向", `坐${o.sit_m}向${o.face_m}`, ""]);
  if(o.now) facts.push(["九運", o.now, ""]);

  const TOP = 762, PAD = 80;
  c.strokeStyle = LINE; c.lineWidth = 1;
  c.beginPath(); c.moveTo(PAD, TOP); c.lineTo(W - PAD, TOP); c.stroke();

  const bw = (W - PAD * 2) / Math.max(facts.length, 1);
  facts.forEach(([k, v, d], i) => {
    const x = PAD + i * bw;
    c.fillStyle = INK3; c.font = `500 24px ${FONT}`;
    c.fillText(k, x, TOP + 46);
    const val = fitText(c, v, bw - 26, 31, "650");
    c.fillStyle = INK; c.font = `650 ${val.size}px ${FONT}`;
    c.fillText(val.text, x, TOP + 88);
    if(d){ c.fillStyle = INK2; c.font = `500 24px ${FONT}`; c.fillText(d, x, TOP + 124); }
    if(i){ c.strokeStyle = LINE; c.lineWidth = 1;
      c.beginPath(); c.moveTo(x - 22, TOP + 18); c.lineTo(x - 22, TOP + 134); c.stroke(); }
  });

  /* 底 */
  c.textAlign = "center";
  c.fillStyle = INK; c.font = `650 34px ${FONT}`;
  c.fillText("撳入嚟睇飛星盤、坐向同評分拆解", W / 2, 956);
  c.fillStyle = INK3; c.font = `500 27px ${FONT}`;
  c.fillText("hkfengshuimap.com   ·   政府公開數據   ·   免安裝免登記", W / 2, 1002);
  c.fillStyle = "#a9a59c"; c.font = `500 22px ${FONT}`;
  c.fillText("電腦計算，僅供參考。認真睇樓請搵專業風水師傅。", W / 2, 1042);

  return new Promise(res => cv.toBlob(res, "image/png"));
}
