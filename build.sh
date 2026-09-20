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

cp index.html manifest.webmanifest public/
cp og.png favicon.ico apple-touch-icon.png icon-192.png icon-512.png public/
cp -R og public/og          # one preview card per score, chosen by the Worker
# An allowlist, not a delete list. Every new pipeline stage drops another
# intermediate into data/, and a delete list publishes each one until someone
# notices — bd_age.json (2.9 MB) and the housing register were being served to
# the public internet despite nothing on the page ever fetching them. These
# tiles/ (which is also where build.json, index.json and search.json land)
# plus these two are exactly what index.html asks for.
mkdir -p public/data
cp -R data/tiles public/data/tiles
for f in district_stats.json estates.json; do
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
