#!/usr/bin/env bash
# Put what is on staging onto hkfengshuimap.com.
#
# `git push` only ever reaches staging. This is the one thing that moves the
# live site, and it deliberately takes a typed confirmation: there are more
# than a hundred thousand people on the other side of it.
#
# It promotes the exact commit that staging was built from — it will not ship
# anything that has not been built and looked at first.
set -euo pipefail

BR="production"
say() { printf '%s\n' "$*"; }
die() { printf '\n  ✗ %s\n\n' "$*" >&2; exit 1; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "唔喺 git repo 入面。"

[ -z "$(git status --porcelain)" ] || die \
"仲有改動未 commit。先 commit 同 push 上 staging，睇過冇問題先再 ship。

$(git status --short)"

git fetch --quiet origin

LOCAL=$(git rev-parse main)
REMOTE=$(git rev-parse origin/main 2>/dev/null || echo none)
[ "$LOCAL" = "$REMOTE" ] || die \
"本機 main 同 origin/main 唔同步，即係 staging 上面嗰個版本唔係你手上呢個。
先 git push，等 staging 出到嚟睇過，再 ship。"

LIVE=$(git rev-parse "origin/$BR" 2>/dev/null || echo none)
if [ "$LIVE" = "$LOCAL" ]; then
  say ""
  say "  線上已經係呢個版本，冇嘢要 ship。"
  say ""
  exit 0
fi

say ""
say "  將呢個版本放上 hkfengshuimap.com："
say ""
say "    $(git log -1 --format='%h  %s' main)"
say ""
if [ "$LIVE" != "none" ]; then
  N=$(git rev-list --count "origin/$BR..main")
  say "  線上而家係 $(git log -1 --format='%h  %s' "origin/$BR")"
  say "  今次會上 $N 個 commit："
  git log --format='    · %s' "origin/$BR..main" | head -20
  say ""
fi
# Written once, after the first staging deploy prints the real workers.dev
# address — it is per Cloudflare account, so it cannot be guessed here.
if [ -f .staging-url ]; then
  say "  睇咗 staging 未？ $(cat .staging-url)"
else
  say "  睇咗 staging 未？（URL 喺 GitHub Actions 嘅 deploy step 入面）"
fi
say ""
printf '  打 SHIP 確認（其他任何嘢都會取消）: '
read -r ANSWER
[ "$ANSWER" = "SHIP" ] || die "取消咗，乜都冇改。"

say ""
say "  推緊去 $BR ..."
if [ "$LIVE" = "none" ]; then
  git push origin "main:$BR"                 # first promotion creates it
else
  git push --force-with-lease origin "main:$BR"
fi
say ""
say "  ✓ 上咗。CI 大約兩分鐘後會 deploy 去 hkfengshuimap.com。"
say "    睇進度： https://hkfengshuimap.com/version.json"
say ""
