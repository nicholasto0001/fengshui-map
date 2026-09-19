"""Stamp the deployed page with its build id, and publish that id separately.

Browsers cache HTML. Without a way to tell which build it is running, a visitor
who came yesterday can keep seeing yesterday's page indefinitely and there is
nothing in the interface to reveal it. The page compares the id baked into it
against version.json (always fetched uncached) and offers to reload when they
differ.

Run at deploy time:  python3 pipeline/stamp_build.py <build-id> [site-dir]
"""
import json
import pathlib
import sys
import datetime

build = (sys.argv[1] if len(sys.argv) > 1 else "dev").strip()
root = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else
                    pathlib.Path(__file__).parent.parent)

page = root / "index.html"
s = page.read_text()
marker = 'const BUILD_ID = "'
i = s.index(marker) + len(marker)
j = s.index('"', i)
page.write_text(s[:i] + build + s[j:])

(root / "version.json").write_text(json.dumps({
    "build": build,
    "at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"),
}, separators=(",", ":")))
print(f"stamped build {build}")
