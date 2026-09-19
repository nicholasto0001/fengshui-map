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
cp -R data public/data
rm -f public/data/buildings.json public/data/scores.json public/data/op.json

# Stamp the build so a cached page can tell it has fallen behind.
BUILD="${WORKERS_CI_COMMIT_SHA:-${CF_PAGES_COMMIT_SHA:-${GITHUB_SHA:-dev}}}"
BUILD="$(printf '%s' "$BUILD" | cut -c1-7)"
sed -i.bak "s/const BUILD_ID = \"dev\"/const BUILD_ID = \"${BUILD}\"/" public/index.html
rm -f public/index.html.bak
printf '{"build":"%s","at":"%s"}' "$BUILD" "$(date -u +'%Y-%m-%d %H:%M UTC')" > public/version.json

echo "staged build ${BUILD}: $(du -sh public | cut -f1)"
