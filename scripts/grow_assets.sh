#!/bin/bash
# アセット画像自動拡充スクリプト（LaunchAgent用）
# 毎晩2:00に実行される

SNS="$(cd "$(dirname "$0")/.." && pwd)"
FLUX_PYTHON="$SNS/flux-env/bin/python3"
LOG="$HOME/.claude/outputs/launchagent_grow_assets.log"

# アクティブクライアントを読み込む
if [ -z "$SNS_CLIENT" ] && [ -f "$SNS/current_client" ]; then
    source "$SNS/current_client"
fi
SNS_CLIENT="${SNS_CLIENT:-天弥堂}"

exec >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === アセット拡充開始 ==="

$FLUX_PYTHON "$SNS/skills/grow_assets.py" --client $SNS_CLIENT

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === アセット拡充完了 ==="
