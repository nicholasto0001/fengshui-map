/**
 * 八字排盤同八宅配樓。
 *
 * 節氣唔喺呢度計 —— VSOP87 嗰條級數已經對住天文台 4,800 個節氣日期同
 * 220 個時刻驗過，搬嚟 JavaScript 重寫一次等於重新開一次打錯數字嘅機會。
 * 所以由 pipeline/make_bazi_data.py 出表，呢度淨係查表。
 *
 * 剩返嘅全部係算術：六十甲子、五虎遁、五鼠遁、本命卦、變爻。冇一步
 * 需要判斷，所以寫得啱就一定計得啱。
 */
const GAN = "甲乙丙丁戊己庚辛壬癸";
const ZHI = "子丑寅卯辰巳午未申酉戌亥";
const JIE_NAME = ["立春","驚蟄","清明","立夏","芒種","小暑",
                  "立秋","白露","寒露","立冬","大雪","小寒"];
const HK_LON = 114.1694;

/* 晚子時三個門派，見 docs/bazi-verification.md。預設跟大陸多數排盤軟件。 */
const ZI_NEW_DAY = "next_day", ZI_SAME = "same_day", ZI_HOUR_NEW = "hour_next";

const DAY_MS = 86400000;
const EPOCH_DAY = Date.UTC(1900, 0, 1) / DAY_MS;     // 表嘅原點
const JDN_1970 = 2440588;

let TERMS = null;                                     // {y0, y1, n, abs[]}

/** 個表擺喺 data/ 度（同 district_stats.json、estates.json 一齊），
    唔係 data/tiles/ —— tiles 嗰個資料夾係圖磚，每日重出。 */
export async function ready(url = "data/solar_terms.json"){
  if(TERMS) return TERMS;
  const d = await fetch(url).then(r => r.json());
  const abs = new Array(d.d.length);
  let run = 0;
  for(let i = 0; i < d.d.length; i++){ run += d.d[i]; abs[i] = run; }
  TERMS = {y0: d.y0, y1: d.y1, n: d.n, abs};
  return TERMS;
}

const gz = i => GAN[((i % 10) + 10) % 10] + ZHI[((i % 12) + 12) % 12];
const dayNum = (y, m, d) => Date.UTC(y, m - 1, d) / DAY_MS;
/** 由 1900-01-01 00:00 香港時間起計嘅分鐘數 —— 同節氣表同一個尺度。 */
const minutesOf = (y, m, d, hh, mi) => (dayNum(y, m, d) - EPOCH_DAY) * 1440 + hh * 60 + mi;
const termAt = (baziYear, k) => TERMS.abs[(baziYear - TERMS.y0) * TERMS.n + k];

/** 均時差（分鐘）。 */
function equationOfTime(y, m, d){
  const t = (dayNum(y, m, d) + JDN_1970 - 2451545) / 36525;
  const R = Math.PI / 180;
  const l0 = (280.46646 + 36000.76983 * t) % 360;
  const M = (357.52911 + 35999.05029 * t) * R;
  const e = 0.016708634 - 0.000042037 * t;
  const eps = 23.439291 - 0.0130042 * t;
  const yy = Math.tan(eps / 2 * R) ** 2;
  const eot = yy * Math.sin(2 * l0 * R) - 2 * e * Math.sin(M)
            + 4 * e * yy * Math.sin(M) * Math.cos(2 * l0 * R)
            - 0.5 * yy * yy * Math.sin(4 * l0 * R) - 1.25 * e * e * Math.sin(2 * M);
  return eot / R * 4;
}

/**
 * 排盤。
 * @param {boolean} trueSolar  真太陽時。預設唔校正 —— 我哋核對過嘅排盤網
 *                             同 lunar-python 全部都冇校正。
 */
export function chart(y, m, d, hh, mi = 0,
                      {lon = HK_LON, trueSolar = false, zi = ZI_NEW_DAY} = {}){
  if(!TERMS) throw new Error("要先 await ready()");
  const notes = [];

  let sy = y, sm = m, sd = d, sh = hh, smi = mi;
  if(trueSolar){
    const shift = (lon - 120) * 4 + equationOfTime(y, m, d);
    let t = hh * 60 + mi + shift, off = 0;
    while(t < 0){ t += 1440; off--; }
    while(t >= 1440){ t -= 1440; off++; }
    const dt = new Date((dayNum(y, m, d) + off) * DAY_MS);
    sy = dt.getUTCFullYear(); sm = dt.getUTCMonth() + 1; sd = dt.getUTCDate();
    sh = Math.floor(t / 60); smi = Math.round(t % 60);
    notes.push(`真太陽時校正 ${shift >= 0 ? "+" : ""}${shift.toFixed(0)} 分鐘`);
  }

  const now = minutesOf(sy, sm, sd, sh, smi);
  // 我哋嘅節氣準到大約一分鐘，所以界線兩分鐘之內唔可以扮肯定。
  const UNSURE = 2;

  /* 年柱：立春為界 */
  if(sy < TERMS.y0 + 1 || sy > TERMS.y1) return null;
  const liChun = termAt(sy, 0);
  const baziYear = now >= liChun ? sy : sy - 1;
  if(Math.abs(now - liChun) <= UNSURE)
    notes.push("⚠ 出生時間喺立春前後兩分鐘之內，年柱唔夠肯定");
  const ypil = ((baziYear - 4) % 60 + 60) % 60;

  /* 月柱：十二個節為界，五虎遁定天干 */
  let mi_ = 11;
  for(let k = 0; k < 12; k++){
    if(termAt(baziYear, k) <= now) mi_ = k; else break;
  }
  for(let k = 0; k < 12; k++){
    if(Math.abs(now - termAt(baziYear, k)) <= UNSURE){
      notes.push(`⚠ 出生時間喺${JIE_NAME[k]}前後兩分鐘之內，月柱唔夠肯定`);
      break;
    }
  }
  const zhiM = (2 + mi_) % 12;
  const ganM = ((((baziYear - 4) % 10 + 10) % 10) % 5 * 2 + 2 + mi_) % 10;
  let mpil = 0;
  for(let i = 0; i < 60; i++) if(i % 10 === ganM && i % 12 === zhiM){ mpil = i; break; }

  /* 日柱：連續六十日循環 */
  const jdn = dayNum(sy, sm, sd) + JDN_1970;
  let dayI = ((jdn + 49) % 60 + 60) % 60;
  let stemDay = dayI;
  if(sh === 23){
    if(zi === ZI_NEW_DAY){ dayI = stemDay = (dayI + 1) % 60;
      notes.push("晚子時：日柱同時柱都算下一日"); }
    else if(zi === ZI_HOUR_NEW){ stemDay = (dayI + 1) % 60;
      notes.push("晚子時：日柱留當日，時柱天干跟下一日"); }
    else notes.push("晚子時：日柱同時柱都留當日");
    notes.push("⚠ 23:00–23:59 出世，三個門派三個答案");
  }

  /* 時柱：五鼠遁 */
  const zhiH = Math.floor((sh + 1) / 2) % 12;
  const ganH = (stemDay % 10 % 5 * 2 + zhiH) % 10;
  let hpil = 0;
  for(let i = 0; i < 60; i++) if(i % 10 === ganH && i % 12 === zhiH){ hpil = i; break; }

  return {year: gz(ypil), month: gz(mpil), day: gz(dayI), hour: gz(hpil),
          baziYear, notes,
          solar: `${sy}-${String(sm).padStart(2,"0")}-${String(sd).padStart(2,"0")} `
               + `${String(sh).padStart(2,"0")}:${String(smi).padStart(2,"0")}`};
}

/* ---------------------------------------------------------------- 八宅 --- */

const GUA_N = {1:"坎",2:"坤",3:"震",4:"巽",6:"乾",7:"兌",8:"艮",9:"離"};
const GUA_DIR = {坎:"北", 離:"南", 震:"東", 巽:"東南",
                 乾:"西北", 坤:"西南", 艮:"東北", 兌:"西"};
const EAST = new Set(["坎","離","震","巽"]);
export const SHAN_DIR = {
  壬:"北", 子:"北", 癸:"北", 丑:"東北", 艮:"東北", 寅:"東北",
  甲:"東", 卯:"東", 乙:"東", 辰:"東南", 巽:"東南", 巳:"東南",
  丙:"南", 午:"南", 丁:"南", 未:"西南", 坤:"西南", 申:"西南",
  庚:"西", 酉:"西", 辛:"西", 戌:"西北", 乾:"西北", 亥:"西北",
};

/* 遊年唔打表，由變爻推。8 × 8 = 64 格，打錯一格冇人睇得出，而嗰格會
   令一個人以為自己間屋喺吉方 —— Python 嗰邊第一次手打就錯咗 15 格。
   爻由下數上，1 陽 0 陰。 */
const TRI = {"111":"乾","110":"兌","101":"離","100":"震",
             "011":"巽","010":"坎","001":"艮","000":"坤"};
const BITS = Object.fromEntries(Object.entries(TRI).map(([k,v]) => [v, k]));
const CHANGE = [[[], "伏位"], [[2], "生氣"], [[1], "絕命"], [[0], "禍害"],
                [[0,1], "天醫"], [[1,2], "五鬼"], [[0,2], "六煞"], [[0,1,2], "延年"]];
export const GOOD = ["生氣", "天醫", "延年", "伏位"];

export const LUCK = (() => {
  const out = {};
  for(const [gua, bits] of Object.entries(BITS)){
    const t = {};
    for(const [flips, star] of CHANGE){
      const b = bits.split("");
      for(const f of flips) b[f] = b[f] === "1" ? "0" : "1";
      t[GUA_DIR[TRI[b.join("")]]] = star;
    }
    out[gua] = t;
  }
  return out;
})();

/** 本命卦。年份要用八字年（立春為界），唔係公曆年。 */
export function mingGua(baziYear, male){
  let s = baziYear;
  while(s > 9) s = String(s).split("").reduce((a, c) => a + +c, 0);
  let n = male ? 11 - s : 4 + s;
  while(n > 9) n -= 9;
  if(n === 5) n = male ? 2 : 8;
  return GUA_N[n];
}

export const guaGroup = g => EAST.has(g) ? "東四" : "西四";

/** 四個吉方，由最吉排落去。 */
export function goodDirs(gua){
  const order = {生氣:0, 天醫:1, 延年:2, 伏位:3};
  return Object.keys(LUCK[gua]).filter(d => GOOD.includes(LUCK[gua][d]))
              .sort((a, b) => order[LUCK[gua][a]] - order[LUCK[gua][b]]);
}
