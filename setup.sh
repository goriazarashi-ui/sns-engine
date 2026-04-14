#!/bin/bash
# SNS自動投稿セットアップスクリプト
# macOS (Apple Silicon / Intel) 対応
# 実行: bash setup.sh

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
echo " SNS自動投稿セットアップ"
echo "======================================"
echo ""

# ────────────────────────────────────────
# 0. クライアント設定
# ────────────────────────────────────────
echo ""
info "クライアント設定"
read -p "  クライアント名を入力してください: " CLIENT
if [ -z "$CLIENT" ]; then
    err "クライアント名は必須です。"
    exit 1
fi

CLIENT_DIR="$SNS_DIR/clients/$CLIENT"
if [ ! -d "$CLIENT_DIR" ]; then
    info "新規クライアントを作成します: $CLIENT"
    mkdir -p "$CLIENT_DIR/templates" "$CLIENT_DIR/assets/images" "$CLIENT_DIR/assets/bgm"

    cat > "$CLIENT_DIR/profile.json" <<EOF
{
  "name": "$CLIENT",
  "owner": "",
  "industry": "",
  "description": "",
  "tone": "",
  "keywords": [],
  "url": "",
  "sns": {
    "x":             {"enabled": true,  "content_type": "auto"},
    "instagram":     {"enabled": true,  "content_type": "auto"},
    "threads":       {"enabled": true,  "content_type": "auto"},
    "tiktok":        {"enabled": true,  "content_type": "auto"},
    "youtube_shorts":{"enabled": true,  "content_type": "auto"},
    "facebook":      {"enabled": false, "content_type": "auto"}
  }
}
EOF

    echo ""
    info "SNSアカウント情報を入力してください"
    echo "  （後から ~/.claude/sns/clients/$CLIENT/.env を直接編集しても構いません）"
    echo ""
    read -p "  X ユーザー名: "                               X_USER
    read -p "  X パスワード: "                               X_PASS
    read -p "  Instagram / Threads / Facebook メール: "      IG_EMAIL
    read -p "  Instagram / Threads / Facebook パスワード: "  IG_PASS

    cat > "$CLIENT_DIR/.env" <<EOF
# $CLIENT SNSアカウント情報
# このファイルは絶対にGitにコミットしないこと

X_USERNAME=$X_USER
X_PASSWORD=$X_PASS

INSTAGRAM_USERNAME=$IG_EMAIL
INSTAGRAM_PASSWORD=$IG_PASS

THREADS_USERNAME=$IG_EMAIL
THREADS_PASSWORD=$IG_PASS

TIKTOK_USERNAME=
TIKTOK_PASSWORD=

YOUTUBE_EMAIL=
YOUTUBE_PASSWORD=

FACEBOOK_EMAIL=$IG_EMAIL
FACEBOOK_PASSWORD=$IG_PASS
EOF

    ok "クライアント設定を作成しました: $CLIENT_DIR"
else
    ok "クライアント設定確認済み: $CLIENT"
fi

# アクティブクライアントを記録（shell scripts が参照）
echo "SNS_CLIENT=\"$CLIENT\"" > "$SNS_DIR/current_client"
ok "アクティブクライアント: $CLIENT"

# ────────────────────────────────────────
# 1. Homebrew
# ────────────────────────────────────────
info "Homebrew を確認中..."
if ! command -v brew &>/dev/null; then
    info "Homebrewをインストールします..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Siliconのパス設定
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    ok "Homebrew インストール済み"
fi

# ────────────────────────────────────────
# 2. Python3 / ffmpeg / Google Chrome
# ────────────────────────────────────────
info "Python3 を確認中..."
if ! command -v python3 &>/dev/null; then
    brew install python
else
    ok "Python3 インストール済み ($(python3 --version))"
fi

info "ffmpeg を確認中..."
if ! command -v ffmpeg &>/dev/null; then
    brew install ffmpeg
else
    ok "ffmpeg インストール済み"
fi

info "Google Chrome を確認中..."
if [ ! -d "/Applications/Google Chrome.app" ]; then
    info "Google Chromeをインストールします..."
    brew install --cask google-chrome
else
    ok "Google Chrome インストール済み"
fi

# ────────────────────────────────────────
# 3. Python パッケージ
# ────────────────────────────────────────
info "Python パッケージをインストール中..."
pip3 install --break-system-packages playwright numpy requests Pillow 2>/dev/null \
  || pip3 install playwright numpy requests Pillow
ok "Python パッケージ完了"

info "Playwright用 Chrome をインストール中..."
python3 -m playwright install chrome
ok "Playwright Chrome 完了"

# ────────────────────────────────────────
# 3b. Flux venv（grow_assets用）
# ────────────────────────────────────────
FLUX_ENV="$SNS_DIR/flux-env"
info "Flux venv を確認中..."
if [ ! -f "$FLUX_ENV/bin/python3" ]; then
    info "Flux venv を作成中（初回のみ時間がかかります）..."
    python3 -m venv "$FLUX_ENV"
    "$FLUX_ENV/bin/pip" install --upgrade pip
    "$FLUX_ENV/bin/pip" install torch torchvision
    "$FLUX_ENV/bin/pip" install diffusers transformers accelerate
    ok "Flux venv 作成完了"
else
    ok "Flux venv インストール済み"
fi

# ────────────────────────────────────────
# 3c. SDXL Turbo 事前ダウンロード（カルーセル用、約5GB）
# ────────────────────────────────────────
info "SDXL Turbo モデルを確認中..."
SDXL_CACHE="$HOME_DIR/.cache/huggingface/hub/models--stabilityai--sdxl-turbo"
if [ ! -d "$SDXL_CACHE" ]; then
    echo ""
    read -p "  SDXL Turbo（約5GB）を事前DLしますか？（初回カルーセル生成時にDLされるので、スキップも可） [y/N]: " DL_SDXL
    if [[ "$DL_SDXL" =~ ^[Yy]$ ]]; then
        info "SDXL Turbo をダウンロード中（数分かかります）..."
        "$FLUX_ENV/bin/python3" -c "
from diffusers import AutoPipelineForText2Image
import torch
print('モデルDL中...')
AutoPipelineForText2Image.from_pretrained('stabilityai/sdxl-turbo', torch_dtype=torch.float16, variant='fp16')
print('DL完了')
"
        ok "SDXL Turbo DL完了"
    else
        ok "SDXL Turbo DLはスキップ（初回カルーセル生成時に自動DL）"
    fi
else
    ok "SDXL Turbo インストール済み"
fi

# ────────────────────────────────────────
# 4. Claude Code CLI
# ────────────────────────────────────────
info "Claude Code CLI を確認中..."
if ! command -v claude &>/dev/null && [ ! -f "$HOME/.local/bin/claude" ]; then
    info "Claude Code をインストールします..."
    curl -fsSL https://claude.ai/install.sh | sh
    echo ""
    echo -e "${YELLOW}⚠️  Claude Code をインストールしました。"
    echo "   次のステップ: ターミナルを再起動し 'claude' コマンドでログインしてください。"
    echo "   ログイン後、このスクリプトを再実行してください。${NC}"
    echo ""
else
    ok "Claude Code インストール済み"
fi

# claude コマンドのパスを確認
CLAUDE_BIN=""
for p in "$HOME/.local/bin/claude" "/usr/local/bin/claude" "$(command -v claude 2>/dev/null)"; do
    if [ -f "$p" ]; then
        CLAUDE_BIN="$p"
        break
    fi
done

if [ -z "$CLAUDE_BIN" ]; then
    err "claude コマンドが見つかりません。インストール後に再実行してください。"
    exit 1
fi
ok "Claude CLI: $CLAUDE_BIN"

# ────────────────────────────────────────
# 5. 環境変数（GITHUB_GIST_TOKEN）
# ────────────────────────────────────────
echo ""
info "GitHub Gist トークンの設定"
echo "  スマホからレポートを確認するためのトークンです。"
echo "  GitHub → Settings → Developer settings → Personal access tokens → gist スコープで作成"
echo ""
read -p "  GITHUB_GIST_TOKEN を入力してください（スキップ: Enter）: " GIST_TOKEN
if [ -z "$GIST_TOKEN" ]; then
    GIST_TOKEN=""
    echo "  スキップしました（レポート機能は無効）"
fi

# ────────────────────────────────────────
# 6. ログディレクトリ作成
# ────────────────────────────────────────
info "ログディレクトリを作成中..."
mkdir -p "$LOG_DIR"
ok "ログディレクトリ: $LOG_DIR"

# ────────────────────────────────────────
# 7. LaunchAgent の登録
# ────────────────────────────────────────
info "LaunchAgent を設定中..."
mkdir -p "$LAUNCH_AGENTS"

PYTHON_BIN="$(command -v python3)"
HOMEBREW_BIN="$(brew --prefix)/bin"

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
        <string>${CLIENT}</string>
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

# check_sessions用（Weekday指定・python直接呼び出し）
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
        <string>${CLIENT}</string>
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
    "--client" "$CLIENT"

# 既存のLaunchAgentをアンロード（エラー無視）
for label in morning evening fetch_trends grow_assets check_sessions; do
    launchctl unload "$LAUNCH_AGENTS/com.imamuramaki.sns.${label}.plist" 2>/dev/null || true
done

for label in morning evening fetch_trends grow_assets check_sessions; do
    launchctl load "$LAUNCH_AGENTS/com.imamuramaki.sns.${label}.plist"
done
ok "LaunchAgent 登録完了（朝7:58 / 夜17:58 / トレンド1:00 / アセット2:00 / セッション確認月曜9:00）"

# ────────────────────────────────────────
# 8. BGM生成（著作権フリー）
# ────────────────────────────────────────
info "著作権フリーBGMを生成中..."
python3 "$SNS_DIR/skills/generate_bgm.py" --client "$CLIENT" --preset meditation
ok "BGM生成完了"

# ────────────────────────────────────────
# 9. 各SNSのログイン案内
# ────────────────────────────────────────
echo ""
echo "======================================"
echo " 残り作業（手動ログインが必要）"
echo "======================================"
echo ""
echo "以下を1つずつ実行して、ブラウザでログインしてください："
echo ""
echo "  python3 $SNS_DIR/scripts/post_x.py --client \"$CLIENT\" --setup"
echo "  python3 $SNS_DIR/scripts/post_facebook.py --client \"$CLIENT\" --setup"
echo "  python3 $SNS_DIR/scripts/post_threads.py --client \"$CLIENT\" --setup"
echo "  python3 $SNS_DIR/scripts/post_instagram.py --client \"$CLIENT\" --setup"
echo "  python3 $SNS_DIR/scripts/post_tiktok.py --client \"$CLIENT\" --setup"
echo "  python3 $SNS_DIR/scripts/post_youtube_shorts.py --client \"$CLIENT\" --setup"
echo ""
echo "--- カルーセル機能（Instagram複数画像投稿）---"
echo "  $FLUX_ENV/bin/python3 $SNS_DIR/scripts/carousel/generate_carousel.py --id <ID>"
echo "  python3 $SNS_DIR/scripts/post_instagram.py --client \"$CLIENT\" --carousel $SNS_DIR/scripts/carousel/output/carousel_<ID>"
echo ""
echo "======================================"
echo " セットアップ完了！"
echo "======================================"
