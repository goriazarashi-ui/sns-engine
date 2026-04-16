#!/bin/bash
# =============================================================
# install_insta.sh — Instagram カルーセル機能インストーラー
#
# 【上書きルール】
#   ✅ 上書きする : スクリプト・Claude スキル（コードの更新が目的）
#   🚫 触らない  : ~/.claude/insta/templates/ 配下（各PCのクライアントデータ）
#
# 使い方:
#   初回インストール : bash install_insta.sh
#   アップデート     : bash install_insta.sh        （テンプレートは保護される）
# =============================================================

set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "======================================"
echo "  Instagram カルーセル機能インストール"
echo "======================================"
echo ""

# -------------------------------------------------------
# 1. スクリプト（常に上書き）
# -------------------------------------------------------
echo "📦 スクリプトをインストール中..."
mkdir -p "$CLAUDE_DIR/scripts"
cp "$REPO_DIR/scripts/insta_image.py"    "$CLAUDE_DIR/scripts/insta_image.py"
cp "$REPO_DIR/scripts/insta_generate.py" "$CLAUDE_DIR/scripts/insta_generate.py"
echo "  ✅ insta_image.py"
echo "  ✅ insta_generate.py"

# -------------------------------------------------------
# 2. Claude スキル（常に上書き）
# -------------------------------------------------------
echo ""
echo "🧠 Claude スキルをインストール中..."
mkdir -p "$CLAUDE_DIR/skills/insta-layout"
mkdir -p "$CLAUDE_DIR/skills/insta-set"
cp "$REPO_DIR/claude-skills/insta-layout/SKILL.md" "$CLAUDE_DIR/skills/insta-layout/SKILL.md"
cp "$REPO_DIR/claude-skills/insta-set/SKILL.md"    "$CLAUDE_DIR/skills/insta-set/SKILL.md"
echo "  ✅ insta-layout スキル"
echo "  ✅ insta-set スキル"

# -------------------------------------------------------
# 3. ディレクトリ構造（存在しなければ作るだけ・削除しない）
# -------------------------------------------------------
echo ""
echo "📂 ディレクトリ構造を確認中..."
TEMPLATES_DIR="$CLAUDE_DIR/insta/templates"
OUTPUTS_DIR="$CLAUDE_DIR/insta/outputs"
LAYOUTS_DIR="$CLAUDE_DIR/layouts"

if [ -d "$TEMPLATES_DIR" ]; then
    echo "  ✅ ~/.claude/insta/templates/ — 既存データを保護（スキップ）"
else
    mkdir -p "$TEMPLATES_DIR"
    echo "  ✅ ~/.claude/insta/templates/ — 新規作成"
fi

if [ -d "$OUTPUTS_DIR" ]; then
    echo "  ✅ ~/.claude/insta/outputs/ — 既存データを保護（スキップ）"
else
    mkdir -p "$OUTPUTS_DIR"
    echo "  ✅ ~/.claude/insta/outputs/ — 新規作成"
fi

if [ -d "$LAYOUTS_DIR" ]; then
    echo "  ✅ ~/.claude/layouts/ — 既存データを保護（スキップ）"
else
    mkdir -p "$LAYOUTS_DIR"
    echo "  ✅ ~/.claude/layouts/ — 新規作成"
fi

# -------------------------------------------------------
# 4. Python依存チェック
# -------------------------------------------------------
echo ""
echo "🐍 Python 依存パッケージを確認中..."
if python3 -c "from PIL import Image" 2>/dev/null; then
    echo "  ✅ Pillow — インストール済み"
else
    echo "  ⚠️  Pillow が見つかりません。インストールします..."
    pip3 install pillow
    echo "  ✅ Pillow — インストール完了"
fi

# -------------------------------------------------------
# 5. 完了メッセージ
# -------------------------------------------------------
echo ""
echo "======================================"
echo "  ✅ インストール完了"
echo "======================================"
echo ""
echo "【次のステップ — 新しいクライアントをセットアップする場合】"
echo ""
echo "  1. ベース画像とサンプル画像を用意する"
echo "     - トップページ用 × 2枚（ベース・サンプル）"
echo "     - コンテンツページ用 × 2枚（ベース・サンプル）"
echo "     - CTA固定画像 × 1枚"
echo ""
echo "  2. テンプレートディレクトリを作成する"
echo "     mkdir -p ~/.claude/insta/templates/{クライアント名}/{layouts,base}"
echo ""
echo "  3. Claude Code で /insta-layout を2回実行"
echo "     /insta-layout  → top.json 生成"
echo "     /insta-layout  → content.json 生成"
echo ""
echo "  4. CTA画像を配置"
echo "     cp {CTA画像} ~/.claude/insta/templates/{クライアント名}/cta.png"
echo ""
echo "  5. /insta-set {クライアント名} で動作確認"
echo ""
