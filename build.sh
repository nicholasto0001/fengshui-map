#!/usr/bin/env bash
# Assemble the published site.
#
# Deliberately a copy list rather than "publish the repo": pipeline/, docs/ and
# the multi-MB working files (buildings.json, scores.json, op.json) have no
# business on the web, and nothing on the page fetches them.
#
# No Python or Node needed — this runs in any build image.
set -euo pipefail

rm -rf public
mkdir -p public

cp index.html privacy.html admin.html method.html bazi-guide.html sitemap.xml manifest.webmanifest public/
cp bazi.js card.js public/               # 八字引擎同分享卡，用到先載

# Supabase 個 client。由 CDN 載嘅話，廣告攔截器一擋就登入死 —— 同源就冇得擋。
# 攞唔到就唔好整冧成個 build：index.html 會自己跌返去 CDN。
mkdir -p public/vendor
SUPA_JS_URL="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.116.0/dist/umd/supabase.js"
if curl -fsSL --max-time 45 "$SUPA_JS_URL" -o public/vendor/supabase.js \
   && [ -s public/vendor/supabase.js ]; then
  echo "vendored supabase-js ($(wc -c < public/vendor/supabase.js) bytes)"
else
  echo "::warning::could not vendor supabase-js; the page will fall back to the CDN"
  rm -f public/vendor/supabase.js
fi
cp og.png favicon.ico apple-touch-icon.png icon-192.png icon-512.png public/
cp -R og public/og          # one preview card per score, chosen by the Worker
# An allowlist, not a delete list. Every new pipeline stage drops another
# intermediate into data/, and a delete list publishes each one until someone
# notices — bd_age.json (2.9 MB) and the housing register were being served to
# the public internet despite nothing on the page ever fetching them. These
# tiles/ (which is also where build.json, index.json and search.json land)
# plus these two are exactly what index.html asks for.
# 區頁、屋苑頁同佢哋嘅平面圖。由 pipeline/make_pages.py 同 make_plans.py 出,
# 全部係已經計好嘅數據印出嚟 —— Google 淨係讀得到呢啲，讀唔到個地圖入面嘅嘢。
if [ -d pages/district ]; then cp -R pages/district public/district; fi
if [ -d pages/estate ];   then cp -R pages/estate   public/estate;   fi
if [ -d pages/plan ];     then cp -R pages/plan     public/plan;     fi

mkdir -p public/data
cp -R data/tiles public/data/tiles
for f in district_stats.json estates.json solar_terms.json elements.json; do
  cp "data/$f" "public/data/$f"
done

# Stamp the build so a cached page can tell it has fallen behind.
#
# The commit variable differs per platform and Cloudflare's Workers builds did
# not set any of them — the chain fell through to the branch name, giving every
# deploy the id "main" and quietly disabling the whole mechanism. A timestamp is
# appended unconditionally: whatever else resolves, each build is distinct.
SHA="${WORKERS_CI_COMMIT_SHA:-${CF_PAGES_COMMIT_SHA:-${GITHUB_SHA:-${CF_PAGES_COMMIT_SHA:-}}}}"
SHA="$(printf '%s' "$SHA" | cut -c1-7)"
BUILD="${SHA:+$SHA-}$(date -u +%y%m%d%H%M)"
sed -i.bak "s/const BUILD_ID = \"dev\"/const BUILD_ID = \"${BUILD}\"/" public/index.html
rm -f public/index.html.bak
printf '{"build":"%s","at":"%s"}' "$BUILD" "$(date -u +'%Y-%m-%d %H:%M UTC')" > public/version.json

echo "staged build ${BUILD}: $(du -sh public | cut -f1)"
echo "  區頁 $(ls public/district 2>/dev/null | wc -l | tr -d ' ') · 屋苑頁 $(ls public/estate 2>/dev/null | wc -l | tr -d ' ') · 平面圖 $(ls public/plan 2>/dev/null | wc -l | tr -d ' ')"
