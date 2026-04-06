#!/usr/bin/env python3
"""
TikTok投稿スクリプト
JSONテンプレートから動画を自動生成してTikTokに投稿する。
メインのChromeを閉じる必要はない。

Usage:
  # 初回のみ: 専用プロファイルを作成してTikTokにログイン
  python3 post_tiktok.py --client 天弥堂 --setup

  # 以降: テンプレートローテーションで動画生成→投稿
  python3 post_tiktok.py --client 天弥堂 --template

  # 動画ファイルを直接指定
  python3 post_tiktok.py --client 天弥堂 --video /path/to/video.mp4 --caption "キャプション"
"""

import argparse
import glob
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client_manager import get_client_dir

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: pip3 install playwright --break-system-packages")
    sys.exit(1)

_SNS_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = Path.home() / ".claude/outputs/images"
VIDEO_DIR = Path.home() / ".claude/outputs/videos"
AUTOMATION_PROFILES_DIR = _SNS_ROOT / "chrome-profiles"
GENERATE_VIDEO_SCRIPT = Path.home() / ".claude/scripts/generate_video.py"
SKILLS_DIR = _SNS_ROOT / "skills"


def automation_profile(client_name: str) -> Path:
    return AUTOMATION_PROFILES_DIR / f"{client_name}_tiktok"


def remove_singleton_lock(profile_dir: Path):
    for name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock = profile_dir / name
        if lock.exists() or lock.is_symlink():
            lock.unlink()


def setup_profile(client_name: str):
    """自動化専用プロファイルを作成し、手動ログインさせる"""
    profile_dir = automation_profile(client_name)
    profile_dir.mkdir(parents=True, exist_ok=True)
    remove_singleton_lock(profile_dir)
    print(f"🔧 専用プロファイル: {profile_dir}")
    print("🌐 Chromeを開きます。TikTokにログインして3分以内に完了してください。")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation", "--no-sandbox"],
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=60000)

        print("⏳ ログイン待機中...")
        for _ in range(180):
            time.sleep(1)
            url = page.url
            if "tiktok.com" in url and "login" not in url:
                time.sleep(2)
                break
        else:
            print("❌ タイムアウト: 3分以内にログインが完了しませんでした")
            context.close()
            sys.exit(1)

        print("✅ ログイン完了。セットアップ終了します。")
        context.close()


def get_next_tiktok_template(client_name: str) -> tuple[dict, int]:
    """テンプレートJSONをローテーションで返す。(template_dict, index)"""
    tmpl_dir = get_client_dir(client_name) / "templates" / "tiktok"
    templates = sorted(tmpl_dir.glob("*.json"))
    if not templates:
        print(f"ERROR: TikTokテンプレートが見つかりません: {tmpl_dir}")
        sys.exit(1)

    state_path = get_client_dir(client_name) / ".template_index_tiktok"
    idx = 0
    if state_path.exists():
        try:
            idx = int(state_path.read_text().strip())
        except ValueError:
            idx = 0

    tmpl_path = templates[idx % len(templates)]
    state_path.write_text(str((idx + 1) % len(templates)))

    with open(tmpl_path, encoding="utf-8") as f:
        return json.load(f), idx


def generate_video(slides: list, client_name: str) -> Path:
    """generate_video.py を使って動画を生成しパスを返す"""
    import tempfile
    today = date.today().isoformat()
    out_dir = VIDEO_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = list(out_dir.glob("*.mp4"))
    seq = len(existing) + 1
    out_path = out_dir / f"{seq:03d}_tiktok.mp4"

    # スライドJSONを一時ファイルに書き出す
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(slides, f, ensure_ascii=False)
        tmp_json = f.name

    cmd = [sys.executable, str(GENERATE_VIDEO_SCRIPT), "--slides", tmp_json, "-o", str(out_path)]
    print("🎬 動画生成中...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(tmp_json).unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"❌ 動画生成失敗:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout.strip())
    return out_path


def post_to_tiktok(client_name: str, video_path: Path, caption: str):
    """自動化専用プロファイルのChromeでTikTokに投稿する"""
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_tiktok.py --client {client_name} --setup")
        sys.exit(1)

    remove_singleton_lock(profile_dir)
    print("🌐 Chromeを起動中（専用プロファイル）...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation", "--no-sandbox"],
        )
        page = context.new_page()

        try:
            page.goto("https://www.tiktok.com/creator-center/upload", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "login" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")
            print("📤 動画アップロード中...")

            # ファイル入力を探してアップロード
            with page.expect_file_chooser(timeout=20000) as fc_info:
                for selector in [
                    'input[type="file"]',
                    'button:has-text("ファイルを選択")',
                    'button:has-text("Select file")',
                    'button:has-text("Upload")',
                    '[class*="upload"]',
                ]:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=3000):
                            el.click()
                            break
                    except Exception:
                        continue

            file_chooser = fc_info.value
            file_chooser.set_files(str(video_path))
            print("  → ファイルセット完了。処理待機中...")
            time.sleep(10)  # TikTokの動画処理に時間がかかる

            # キャプション入力
            print("📝 キャプション入力中...")
            for selector in [
                '[contenteditable="true"]',
                'div[data-contents="true"]',
                '[aria-label*="キャプション"]',
                '[aria-label*="caption"]',
                '[placeholder*="キャプション"]',
            ]:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=5000):
                        el.click()
                        time.sleep(0.5)
                        # 既存テキストを全選択して削除してから入力
                        el.evaluate("el => { el.focus(); document.execCommand('selectAll'); document.execCommand('delete'); }")
                        time.sleep(0.3)
                        el.type(caption, delay=20)
                        break
                except Exception:
                    continue

            time.sleep(2)

            # 投稿ボタン
            print("🚀 投稿中...")
            for selector in [
                'button:has-text("投稿")',
                'button:has-text("Post")',
                '[data-e2e="post_video_button"]',
            ]:
                try:
                    btn = page.locator(selector).last  # 「投稿」ボタンは複数あるので最後
                    btn.wait_for(timeout=10000)
                    btn.evaluate("el => el.click()")
                    break
                except Exception:
                    continue

            time.sleep(5)
            print("✅ 投稿完了!")

        except PlaywrightTimeout as e:
            print(f"❌ タイムアウト: {e}")
            _save_screenshot(page, client_name)
            raise
        except Exception as e:
            print(f"❌ エラー: {e}")
            _save_screenshot(page, client_name)
            raise
        finally:
            context.close()


def _save_screenshot(page, label: str = "error"):
    try:
        today = date.today().isoformat()
        out_dir = SCREENSHOT_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"tiktok_error_{label}.png"
        page.screenshot(path=str(path))
        print(f"📸 スクリーンショット保存: {path}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="TikTokへの自動投稿")
    parser.add_argument("--client", required=True, help="クライアント名（例: 天弥堂）")
    parser.add_argument("--setup", action="store_true", help="初回セットアップ（専用プロファイル作成・ログイン）")
    parser.add_argument("--template", action="store_true", help="テンプレートローテーション使用（動画自動生成）")
    parser.add_argument("--generate", action="store_true", help="Claude CLIでテキスト生成＋アセット画像で動画生成")
    parser.add_argument("--video", help="投稿する動画パス（省略時はテンプレートから自動生成）")
    parser.add_argument("--caption", help="キャプション")
    args = parser.parse_args()

    if args.setup:
        setup_profile(args.client)
        return

    if args.generate:
        import json as _json
        result = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_post.py"), "--client", args.client, "--sns", "tiktok"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"ERROR: generate_post.py 失敗:\n{result.stderr}"); sys.exit(1)
        data = _json.loads(result.stdout)
        activity = data.get("activity", "")
        caption = data.get("caption", "")
        slide_texts = data.get("slide_texts", [caption])
        print(f"🤖 生成キャプション:\n{caption}\n")

        today = date.today().isoformat()
        out_dir = VIDEO_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)
        existing = list(out_dir.glob("*.mp4"))
        out_path = out_dir / f"{len(existing)+1:03d}_tiktok.mp4"

        result2 = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_video.py"),
             "--client", args.client, "--activity", activity,
             "--text", "\\n".join(slide_texts), "--output", str(out_path), "--sns", "tiktok"],
            capture_output=True, text=True, timeout=120
        )
        if result2.returncode != 0:
            print(f"ERROR: generate_video.py 失敗:\n{result2.stderr}"); sys.exit(1)
        print(result2.stdout.strip())
        video_path = out_path
    elif args.template:
        tmpl, idx = get_next_tiktok_template(args.client)
        caption = tmpl.get("caption", "")
        slides = tmpl.get("slides", [])
        print(f"📋 テンプレート #{idx + 1}\nキャプション: {caption[:50]}...\n")
        video_path = generate_video(slides, args.client)
    elif args.video:
        video_path = Path(args.video)
        caption = args.caption or ""
        if not video_path.exists():
            print(f"ERROR: 動画が見つかりません: {args.video}")
            sys.exit(1)
    else:
        print("ERROR: --template または --video を指定してください")
        sys.exit(1)

    post_to_tiktok(client_name=args.client, video_path=video_path, caption=caption)


if __name__ == "__main__":
    main()
