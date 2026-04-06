#!/bin/bash
# トレンド取得スクリプト（LaunchAgent用）
# 毎晩1:00に実行される

SNS="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(command -v python3)"
LOG="$SNS/outputs/launchagent_fetch_trends.log"
mkdir -p "$SNS/outputs"

exec >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === トレンド取得開始 ==="

$PYTHON "$SNS/skills/fetch_trends.py" --days 7 --verbose

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === トレンド取得完了 ==="
