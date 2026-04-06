#!/bin/bash
# SNS自動投稿 リモート更新スクリプト
# クライアントPCで実行: bash ~/.claude/sns/update.sh
# clients/ や chrome-profiles/ は上書きされない

set -e

SNS_DIR="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="$HOME"
LAUNCH_AGENTS="$HOME_DIR/Library/LaunchAgents"
LOG_DIR="$HOME_DIR/.claude/outputs"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
info() { echo -e "${YELLOW}▶ $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

echo "======================================"
echo " SNS自動投稿 アップデート"
echo "======================================"
echo ""

# ────────────────────────────────────────
# 0. 事前チェック
# ────────────────────────────────────────
if [ ! -d "$SNS_DIR/.git" ]; then
    err "Gitリポジトリが見つかりません: $SNS_DIR"
    exit 1
fi

# アクティブクライアントを取得
if [ -f "$SNS_DIR/current_client" ]; then
    source "$SNS_DIR/current_client"
fi
if [ -z "$SNS_CLIENT" ]; then
    err "current_client が見つかりません。先に setup.sh を実行してください。"
    exit 1
fi
ok "クライアント: $SNS_CLIENT"

# ────────────────────────────────────────
# 1. git pull でコードを更新
# ────────────────────────────────────────
info "最新コードを取得中..."
cd "$SNS_DIR"

# 未コミットの変更がないか確認
if ! git diff --quiet 2>/dev/null; then
    err "ローカルに未コミットの変更があります。先に確認してください。"
    git status --short
    exit 1
fi

BEFORE=$(git rev-parse HEAD)
git pull --ff-only origin main
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
    ok "すでに最新です（$BEFORE）"
else
    echo ""
    info "更新内容:"
    git log --oneline "${BEFORE}..${AFTER}"
    echo ""
    ok "コード更新完了（$BEFORE → $AFTER）"
fi

# ────────────────────────────────────────
# 2. Python依存パッケージの更新
# ────────────────────────────────────────
info "Python パッケージを確認中..."
pip3 install --break-system-packages --upgrade playwright numpy requests Pillow 2>/dev/null \
  || pip3 install --upgrade playwright numpy requests Pillow
ok "Python パッケージ更新完了"

# Playwright Chrome の更新
info "Playwright Chrome を確認中..."
python3 -m playwright install chrome
ok "Playwright Chrome 更新完了"

# Flux venv の確認（存在すれば更新）
FLUX_ENV="$SNS_DIR/flux-env"
if [ -f "$FLUX_ENV/bin/python3" ]; then
    info "Flux venv のパッケージを更新中..."
    "$FLUX_ENV/bin/pip" install --upgrade torch torchvision diffusers transformers accelerate 2>/dev/null || true
    ok "Flux venv 更新完了"
fi

# ────────────────────────────────────────
# 3. LaunchAgent の再登録
# ────────────────────────────────────────
info "LaunchAgent を再登録中..."

PYTHON_BIN="$(command -v python3)"
HOMEBREW_BIN="$(brew --prefix)/bin"

# 既存のGIST_TOKENをplistから取得（上書きしないように）
GIST_TOKEN=""
MORNING_PLIST="$LAUNCH_AGENTS/com.imamuramaki.sns.morning.plist"
if [ -f "$MORNING_PLIST" ]; then
    GIST_TOKEN=$(/usr/libexec/PlistBuddy -c "Print :EnvironmentVariables:GITHUB_GIST_TOKEN" "$MORNING_PLIST" 2>/dev/null || echo "")
fi

generate_plist() {
    local label="$1"
    local script="$2"
    local log="$3"
    local hour="$4"
    local minute="$5"

    cat > "$LAUNCH_AGENTS/${label}.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${script}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${hour}</integer>
        <key>Minute</key>
        <integer>${minute}</integer>
    </dict>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>${HOME_DIR}</string>
        <key>PATH</key>
        <string>${HOMEBREW_BIN}:/usr/local/bin:/usr/bin:/bin:${HOME_DIR}/.local/bin</string>
        <key>GITHUB_GIST_TOKEN</key>
        <string>${GIST_TOKEN}</string>
        <key>SNS_CLIENT</key>
        <string>${SNS_CLIENT}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>${log}</string>
    <key>StandardErrorPath</key>
    <string>${log}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST
}

generate_plist_weekly() {
    local label="$1"
    local python="$2"
    local script="$3"
    local log="$4"
    local weekday="$5"
    local hour="$6"
    local minute="$7"
    shift 7
    local extra_args=("$@")

    local args_xml="        <string>${python}</string>"$'\n'"        <string>${script}</string>"
    for arg in "${extra_args[@]}"; do
        args_xml+=$'\n'"        <string>${arg}</string>"
    done

    cat > "$LAUNCH_AGENTS/${label}.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
${args_xml}
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>${weekday}</integer>
        <key>Hour</key>
        <integer>${hour}</integer>
        <key>Minute</key>
        <integer>${minute}</integer>
    </dict>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>${HOME_DIR}</string>
        <key>PATH</key>
        <string>${HOMEBREW_BIN}:/usr/local/bin:/usr/bin:/bin:${HOME_DIR}/.local/bin</string>
        <key>GITHUB_GIST_TOKEN</key>
        <string>${GIST_TOKEN}</string>
        <key>SNS_CLIENT</key>
        <string>${SNS_CLIENT}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>${log}</string>
    <key>StandardErrorPath</key>
    <string>${log}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST
}

# 全LaunchAgentをアンロード
for label in morning evening fetch_trends grow_assets check_sessions; do
    launchctl unload "$LAUNCH_AGENTS/com.imamuramaki.sns.${label}.plist" 2>/dev/null || true
done

# plistを再生成
generate_plist \
    "com.imamuramaki.sns.morning" \
    "$SNS_DIR/scripts/sns_morning.sh" \
    "$LOG_DIR/launchagent_morning.log" \
    7 58

generate_plist \
    "com.imamuramaki.sns.evening" \
    "$SNS_DIR/scripts/sns_evening.sh" \
    "$LOG_DIR/launchagent_evening.log" \
    17 58

generate_plist \
    "com.imamuramaki.sns.fetch_trends" \
    "$SNS_DIR/scripts/fetch_trends.sh" \
    "$LOG_DIR/launchagent_fetch_trends.log" \
    1 0

generate_plist \
    "com.imamuramaki.sns.grow_assets" \
    "$SNS_DIR/scripts/grow_assets.sh" \
    "$LOG_DIR/launchagent_grow_assets.log" \
    2 0

generate_plist_weekly \
    "com.imamuramaki.sns.check_sessions" \
    "$PYTHON_BIN" \
    "$SNS_DIR/scripts/check_sessions.py" \
    "$LOG_DIR/launchagent_check_sessions.log" \
    1 9 0 \
    "--client" "$SNS_CLIENT"

# 全LaunchAgentをロード
for label in morning evening fetch_trends grow_assets check_sessions; do
    launchctl load "$LAUNCH_AGENTS/com.imamuramaki.sns.${label}.plist"
done
ok "LaunchAgent 再登録完了"

# ────────────────────────────────────────
# 4. 動作確認
# ────────────────────────────────────────
echo ""
info "動作確認..."

# LaunchAgent状態
AGENT_COUNT=$(launchctl list 2>/dev/null | grep -c "com.imamuramaki.sns" || echo "0")
if [ "$AGENT_COUNT" -eq 5 ]; then
    ok "LaunchAgent: $AGENT_COUNT 件稼働中"
else
    err "LaunchAgent: $AGENT_COUNT / 5 件（不足あり）"
    launchctl list | grep sns
fi

# クライアント設定の存在確認
CLIENT_DIR="$SNS_DIR/clients/$SNS_CLIENT"
CHECKS=0
TOTAL=4
[ -f "$CLIENT_DIR/profile.json" ]        && CHECKS=$((CHECKS+1)) || err "profile.json が見つかりません"
[ -f "$CLIENT_DIR/content_profile.json" ] && CHECKS=$((CHECKS+1)) || err "content_profile.json が見つかりません"
[ -f "$CLIENT_DIR/sns_config.json" ]      && CHECKS=$((CHECKS+1)) || err "sns_config.json が見つかりません"
[ -f "$CLIENT_DIR/.env" ]                 && CHECKS=$((CHECKS+1)) || err ".env が見つかりません"

if [ "$CHECKS" -eq "$TOTAL" ]; then
    ok "クライアント設定: $CHECKS / $TOTAL 件OK"
else
    err "クライアント設定: $CHECKS / $TOTAL 件（不足あり）"
fi

# Chromeプロファイル確認
PROFILES=$(ls -d "$SNS_DIR/chrome-profiles/${SNS_CLIENT}"* 2>/dev/null | wc -l | tr -d ' ')
ok "Chromeプロファイル: ${PROFILES} 件"

echo ""
echo "======================================"
echo " アップデート完了！"
echo "======================================"
echo ""
echo "  コード: $(git rev-parse --short HEAD)"
echo "  クライアント: $SNS_CLIENT"
echo "  LaunchAgent: ${AGENT_COUNT} 件"
echo ""
