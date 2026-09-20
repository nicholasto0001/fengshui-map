/**
 * Per-link Open Graph cards.
 *
 * WhatsApp, Facebook and every other unfurler reads the HTML and runs no
 * JavaScript, so a page whose meta tags are written at build time produces the
 * same preview for every link it ever emits. Sharing a 大吉 flat and sharing a
 * 差 one looked identical, which is the one moment the share has to do work.
 *
 * So the document is rewritten at the edge: the building behind ?b= is looked
 * up in the very tiles the site already serves, and its name, district, score
 * and 九運 verdict go into the title, the description and the card image.
 * Everything else is passed straight through to static assets.
 */

const SITE = "香港風水地圖";
const BREAKS = [41, 46, 52, 58];
const LABELS = ["差", "欠佳", "平穩", "吉", "大吉"];
const TILE_Z = 14;

const NOW_NOTE = {
  "當運旺山旺向": "九運丁財兩旺",
  "當運旺財": "九運利財",
  "當運旺丁": "九運利人丁",
  "當運平平": "九運當旺星未到坐向",
  "入囚": "向星當運入中宮，氣被困",
};

const levelFor = (v) => {
  const i = BREAKS.findIndex((b) => v < b);
  return LABELS[i === -1 ? LABELS.length - 1 : i];
};

const deg2tile = (lon, lat, z) => {
  const n = 2 ** z;
  const rad = (lat * Math.PI) / 180;
  return [
    Math.floor(((lon + 180) / 360) * n),
    Math.floor(((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n),
  ];
};

const asset = async (env, path) => {
  const r = await env.ASSETS.fetch(new Request(`https://assets.local/${path}`));
  return r.ok ? r.json() : null;
};

/** Which tile file actually covers this point — tiles split where dense. */
async function leafFor(env, lon, lat) {
  const idx = await asset(env, "data/tiles/index.json");
  if (!idx?.leaves) return null;
  let [x, y] = deg2tile(lon, lat, TILE_Z);
  for (let z = TILE_Z; z <= (idx.maxz || 16); z++) {
    if (idx.leaves[`${z}/${x}/${y}`]) return `${z}/${x}/${y}`;
    [x, y] = deg2tile(lon, lat, z + 1);
  }
  return null;
}

/**
 * The shared link carries coordinates rounded to five decimals, the same
 * rounding the tiles are written with, so the match is exact rather than
 * nearest — a near-miss would confidently describe the wrong building.
 */
async function findBuilding(env, lat, lon) {
  const key = await leafFor(env, lon, lat);
  if (!key) return null;
  const t = await asset(env, `data/tiles/${key}.json`);
  if (!t) return null;
  const col = Object.fromEntries(t.c.map((c, i) => [c, i]));
  const want = `${lat.toFixed(5)},${lon.toFixed(5)}`;
  for (const r of t.b) {
    if (`${(+r[col.lat]).toFixed(5)},${(+r[col.lon]).toFixed(5)}` === want) {
      const o = Object.fromEntries(t.c.map((c, i) => [c, r[i]]));
      o.district = t.dn && o.dn != null ? t.dn[o.dn] : null;
      return o;
    }
  }
  return null;
}

const parsePts = (s) =>
  (s || "")
    .split(";")
    .map((p) => p.split(",").map(Number))
    .filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b))
    .map(([lat, lon]) => ({ lat, lon }));

async function cardFor(url, env) {
  const q = url.searchParams;
  const origin = url.origin;

  const one = parsePts(q.get("b"))[0];
  if (one) {
    const o = await findBuilding(env, one.lat, one.lon);
    if (!o) return null;
    const name = o.tc || o.en || "呢棟樓";
    const home = o.res !== 0;
    const score = Math.round(o.total);
    const lvl = levelFor(o.total);
    const where = [o.en && o.en !== name ? o.en : null, o.district]
      .filter(Boolean)
      .join(" · ");
    const now = o.now ? `九運${o.now}` : null;

    return {
      title: home
        ? `${name} · ${score} 分（${lvl}）`
        : `${name} · 非住宅樓宇`,
      // 標題已經講咗樓名同分數，所以描述唔好再講一次。WhatsApp 兩三行
      // 就截斷，長過嗰度嘅字冇人見到 —— 而舊嗰段塞咗六截，包括成句
      // 舊嗰段塞咗六截，結果係一嚿灰色字冇人讀。
      description: [
        where,
        home && now ? `九運${o.now}` : null,
        home ? "撳入嚟睇飛星盤、坐向同評分拆解"
             : "撳入嚟睇山水方位同評分拆解",
      ]
        .filter(Boolean)
        .join(" · "),
      image: home && score >= 21 && score <= 89
        ? `${origin}/og/s${score}.png`
        : `${origin}/og/nonres.png`,
    };
  }

  const many = parsePts(q.get("list"));
  if (many.length) {
    return {
      title: `${many.length} 個樓盤嘅風水評分`,
      description: [
        `有人揀咗 ${many.length} 個樓盤想同你一齊睇`,
        "一次過睇晒每個嘅評分、坐向同飛星盤",
      ].join(" · "),
      image: `${origin}/og/list.png`,
    };
  }

  const d = q.get("d");
  const g = q.get("g");
  if (d || g) {
    const band = g && LABELS.includes(g) ? g : null;
    return {
      title: [d || "全港", band].filter(Boolean).join(" · ") + " 風水評分",
      description: [
        `${d || "全港"}${band ? `評為「${band}」嘅樓宇` : "逐棟樓宇嘅九運風水評分"}`,
        "由高分到低分排好",
      ].join(" · "),
      image: `${origin}/og.png`,
    };
  }
  return null;
}

/** Stamp a staging response: visible to a reader, and closed to crawlers. */
function mark(res, url) {
  if (!res.headers.get("content-type")?.includes("text/html")) return res;
  const out = new HTMLRewriter()
    .on("body", {
      element(el) { el.prepend(STAGING_RIBBON, {html: true}); },
    })
    .transform(new Response(res.body, res));
  out.headers.set("x-robots-tag", "noindex, nofollow");
  return out;
}

/** Replace the value of the meta tags the card owns; leave the rest alone. */
class Meta {
  constructor(card, url) {
    this.card = card;
    this.url = url;
  }
  element(el) {
    const key = el.getAttribute("property") || el.getAttribute("name");
    const set = (v) => el.setAttribute("content", v);
    switch (key) {
      case "og:title":
      case "twitter:title":
        return set(`${this.card.title} · ${SITE}`);
      case "og:description":
      case "twitter:description":
      case "description":
        return set(this.card.description);
      case "og:image":
      case "og:image:secure_url":
      case "twitter:image":
        return set(this.card.image);
      case "og:image:alt":
        return set(this.card.title);
      case "og:url":
        return set(this.url);
    }
  }
}

class Title {
  constructor(card) {
    this.card = card;
  }
  element(el) {
    el.setInnerContent(`${this.card.title} · ${SITE}`);
  }
}

export default {
  async fetch(request, env, ctx) {
    // "/" is routed through the Worker for every visitor, not just crawlers,
    // so a fault in here would take the whole front page down. Anything that
    // goes wrong falls back to serving the asset exactly as before.
    try {
      return await handle(request, env, ctx);
    } catch {
      return env.ASSETS.fetch(request);
    }
  },
};

const LIVE_HOST = "hkfengshuimap.com";

/* Staging carries the whole site at a different address, which is exactly how
   someone ends up reading it, sharing it, or letting Google index it by
   mistake. So it says so on its face and asks not to be indexed. */
const STAGING_RIBBON = `<div style="position:fixed;z-index:9999;left:0;right:0;top:0;
  background:#b4530f;color:#fff;font:600 12px/1.6 -apple-system,system-ui,sans-serif;
  text-align:center;padding:3px 8px;letter-spacing:.04em">測試版 STAGING · 未上線</div>`;

async function handle(request, env, ctx) {
    const url = new URL(request.url);
    const live = url.hostname === LIVE_HOST;

    // Cloudflare serves a managed robots.txt when a site has none of its own,
    // and that one says nothing about where the sitemap is. Ours does.
    if (url.pathname === "/robots.txt") {
      const body = live
        ? `User-agent: *\nAllow: /\n\nSitemap: https://${LIVE_HOST}/sitemap.xml\n`
        : "User-agent: *\nDisallow: /\n";
      return new Response(body, {
        headers: {"content-type": "text/plain; charset=utf-8",
                  "cache-control": "public, max-age=3600"},
      });
    }
    const shared =
      url.searchParams.has("b") ||
      url.searchParams.has("list") ||
      url.searchParams.has("d") ||
      url.searchParams.has("g");

    if (!shared || request.method !== "GET") {
      const plain = await env.ASSETS.fetch(request);
      return live ? plain : mark(plain, url);
    }

    // Real visitors follow these links too, so the rewritten document is
    // cached: only the first request for a given building pays for the tile
    // lookup, and the crawler and the reader share the result.
    const cache = caches.default;
    const hit = await cache.match(request);
    if (hit) return hit;

    const res = await env.ASSETS.fetch(request);
    if (!res.headers.get("content-type")?.includes("text/html")) return res;

    let card = null;
    try {
      card = await cardFor(url, env);
    } catch {
      card = null;               // never fail the page over a preview
    }
    if (!card) return res;

    const out = new HTMLRewriter()
      .on("meta", new Meta(card, url.toString()))
      .on("title", new Title(card))
      .transform(new Response(res.body, res));

    out.headers.set("cache-control", "public, max-age=300, s-maxage=86400");
    if (!live) return mark(out, url);
    ctx.waitUntil(cache.put(request, out.clone()));
    return out;
}
