#!/bin/bash
# SNS夕方投稿スクリプト（LaunchAgent用）
# 17:58に実行される

SNS="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(command -v python3)"
LOG="$SNS/outputs"
mkdir -p "$LOG"

# アクティブクライアントを読み込む（setup.sh が生成）
# plistの環境変数 SNS_CLIENT が優先、なければ current_client、なければ天弥堂
if [ -z "$SNS_CLIENT" ] && [ -f "$SNS/current_client" ]; then
    source "$SNS/current_client"
fi
SNS_CLIENT="${SNS_CLIENT:-天弥堂}"

RETRY_CMD="$PYTHON $SNS/scripts/run_with_retry.py --retries 3 --delay 60 --"
REPORT_CMD="$PYTHON $SNS/scripts/report.py --client $SNS_CLIENT"
NOTIFY="bash $SNS/scripts/notify_error.sh"

exec >> "$LOG/launchagent_evening.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 夜の投稿開始 ==="

# 投稿時刻にランダム揺らぎ（0〜4分）
JITTER=$((RANDOM % 240))
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Jitter: ${JITTER}秒待機"
sleep $JITTER

# 1. コンテンツ生成（キャッシュがなければAPIを呼ぶ）
$PYTHON "$SNS/skills/generate_daily.py" --client $SNS_CLIENT >> "$LOG/cron_daily.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] generate_daily 完了"

# 2. Facebook
$NOTIFY "Facebook" $RETRY_CMD $PYTHON "$SNS/scripts/post_facebook.py" --client $SNS_CLIENT --generate >> "$LOG/cron_facebook.log" 2>&1
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Facebook 完了"

# 3. Instagram フィード
$NOTIFY "Instagram" $RETRY_CMD $PYTHON "$SNS/scripts/post_instagram.py" --client $SNS_CLIENT --generate >> "$LOG/cron_instagram.log" 2>&1
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Instagram(フィード) 完了"

# 4. Threads
$NOTIFY "Threads" $RETRY_CMD $PYTHON "$SNS/scripts/post_threads.py" --client $SNS_CLIENT --generate >> "$LOG/cron_threads.log" 2>&1
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Threads 完了"

# 5. TikTok（動画生成 → 投稿。生成した動画パスを取得してXでも使う）
$NOTIFY "TikTok" $RETRY_CMD $PYTHON "$SNS/scripts/post_tiktok.py" --client $SNS_CLIENT --generate >> "$LOG/cron_tiktok.log" 2>&1
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] TikTok 完了"

# TikTokが生成した動画をXで使い回す
SHARED_VIDEO=$(ls -t "$SNS/outputs/videos/$(date '+%Y-%m-%d')"/*_tiktok.mp4 2>/dev/null | head -1)

# 6. X（TikTokと同じ動画を使用）
if [ -n "$SHARED_VIDEO" ]; then
    $NOTIFY "X" $RETRY_CMD $PYTHON "$SNS/scripts/post_x.py" --client $SNS_CLIENT --generate --video "$SHARED_VIDEO" >> "$LOG/cron_x.log" 2>&1
else
    $NOTIFY "X" $RETRY_CMD $PYTHON "$SNS/scripts/post_x.py" --client $SNS_CLIENT --generate >> "$LOG/cron_x.log" 2>&1
fi
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] X 完了"

# 7. YouTube Shorts
$NOTIFY "YouTube Shorts" $RETRY_CMD $PYTHON "$SNS/scripts/post_youtube_shorts.py" --client $SNS_CLIENT --generate >> "$LOG/cron_youtube.log" 2>&1
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] YouTube Shorts 完了"

# 8. Instagram リール
$NOTIFY "Instagram Reel" $RETRY_CMD $PYTHON "$SNS/scripts/post_instagram.py" --client $SNS_CLIENT --reel-generate >> "$LOG/cron_instagram_reel.log" 2>&1
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Instagram Reel 完了"

# 9. U-Word
$NOTIFY "U-Word" $RETRY_CMD $PYTHON "$SNS/scripts/post_uword.py" --client $SNS_CLIENT --generate >> "$LOG/cron_uword.log" 2>&1
$REPORT_CMD >> "$LOG/cron_report.log" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] U-Word 完了"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 夜の投稿すべて完了 ==="
