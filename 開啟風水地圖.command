#!/bin/bash
# 雙擊呢個檔案就會開啟風水地圖。關閉呢個終端機視窗就會停止。
cd "$(dirname "$0")" || exit 1
PORT=4180
while lsof -i :$PORT >/dev/null 2>&1; do PORT=$((PORT+1)); done
echo "風水地圖啟動中… http://localhost:$PORT"
( sleep 1; open "http://localhost:$PORT" ) &
python3 -m http.server $PORT
