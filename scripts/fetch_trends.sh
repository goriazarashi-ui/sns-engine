#!/bin/bash
# トレンド取得スクリプト（LaunchAgent用）
# 毎晩1:00に実行される

PYTHON=/opt/homebrew/bin/python3
SNS="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$HOME/.claude/outputs/launchagent_fetch_trends.log"

exec >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === トレンド取得開始 ==="

$PYTHON "$SNS/skills/fetch_trends.py" --days 7 --verbose

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === トレンド取得完了 ==="
