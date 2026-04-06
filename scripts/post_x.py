#!/usr/bin/env python3
"""
X（旧Twitter）投稿スクリプト
自動化専用Chromeプロファイルを使って投稿する。
メインのChromeを閉じる必要はない。

Usage:
  # 初回のみ: 専用プロファイルを作成してXにログイン
  python3 post_x.py --client 天弥堂 --setup

  # 以降: メインChromeを開いたまま投稿できる
  python3 post_x.py --client 天弥堂 --text "投稿内容"
  python3 post_x.py --client 天弥堂 --text "投稿内容" --image /path/to/image.jpg
  python3 post_x.py --client 天弥堂 --template
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client_manager import get_next_template

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: pip3 install playwright --break-system-packages")
    sys.exit(1)

SCREENSHOT_DIR = Path.home() / ".claude/outputs/images"
AUTOMATION_PROFILES_DIR = Path.home() / ".claude/sns/chrome-profiles"
SKILLS_DIR = Path.home() / ".claude/sns/skills"


def automation_profile(client_name: str) -> Path:
    return AUTOMATION_PROFILES_DIR / client_name


def setup_profile(client_name: str):
    """自動化専用プロファイルを作成し、手動ログインさせる"""
    profile_dir = automation_profile(client_name)
    profile_dir.mkdir(parents=True, exist_ok=True)
    remove_singleton_lock(profile_dir)
    print(f"🔧 専用プロファイル: {profile_dir}")
    print("🌐 Chromeを開きます。Xにログインして3分以内に完了してください。")

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
        page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=60000)

        print("⏳ ログイン待機中...")
        for _ in range(180):
            time.sleep(1)
            if "x.com/home" in page.url or ("x.com" in page.url and "login" not in page.url and "i/flow" not in page.url):
                time.sleep(2)
                break
        else:
            print("❌ タイムアウト: 3分以内にログインが完了しませんでした")
            context.close()
            sys.exit(1)

        print("✅ ログイン完了。セットアップ終了します。")
        context.close()


def remove_singleton_lock(profile_dir: Path):
    """残留しているSingletonLockを削除する"""
    for name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock = profile_dir / name
        if lock.exists() or lock.is_symlink():
            lock.unlink()


def post_to_x(client_name: str, text: str, image_path: str = None, video_path: str = None):
    """自動化専用プロファイルのChromeでXに投稿する"""
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_x.py --client {client_name} --setup")
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
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "login" in page.url or "i/flow/login" in page.url:
                print("❌ ログインしていません。Chromeで x.com にログインしてから再実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")

            # 投稿ボックスをクリック
            print("📝 投稿中...")
            compose = page.locator('[data-testid="tweetTextarea_0"]')
            compose.wait_for(timeout=15000)
            compose.click()
            time.sleep(1)

            # テキスト入力（fill だと一部環境で日本語が化けるので type を使う）
            compose.type(text, delay=30)
            time.sleep(1)

            # 動画 or 画像添付（動画が優先）
            attach_path = None
            if video_path and Path(video_path).exists():
                print("🎬 動画添付中...")
                attach_path = video_path
            elif video_path:
                print(f"⚠️  動画が見つかりません（スキップ）: {video_path}")
            elif image_path and Path(image_path).exists():
                print("🖼️  画像添付中...")
                attach_path = image_path
            elif image_path:
                print(f"⚠️  画像が見つかりません（スキップ）: {image_path}")

            if attach_path:
                file_input = page.locator('input[data-testid="fileInput"]')
                file_input.set_input_files(attach_path)
                is_video = str(attach_path).lower().endswith('.mp4')
                if is_video:
                    print("  ⏳ 動画アップロード処理待機中...")
                    # アップロード中のプログレスバーが消えるまで待つ（最大60秒）
                    for _ in range(60):
                        time.sleep(1)
                        # progressbar が消えたら完了
                        progress = page.locator('[data-testid="attachments"] [role="progressbar"]')
                        if progress.count() == 0:
                            break
                    time.sleep(2)
                else:
                    time.sleep(3)

            # 投稿ボタン — ネイティブクリックを試み、失敗したらJS経由
            tweet_btn = page.locator('[data-testid="tweetButtonInline"]')
            tweet_btn.wait_for(timeout=10000)
            try:
                tweet_btn.click(timeout=5000)
            except Exception:
                tweet_btn.evaluate("el => el.click()")

            # 投稿後20秒間、ダイアログ監視 & 成否確認
            posted = False
            for _ in range(20):
                time.sleep(1)

                # 成功①：投稿完了トーストが出た
                try:
                    toast = page.locator('[data-testid="toast"]')
                    if toast.count() > 0 and toast.first.is_visible(timeout=200):
                        posted = True
                        break
                except Exception:
                    pass

                # 成功②：投稿ボタンが非表示になった（モーダルが閉じた）
                try:
                    btn_inline = page.locator('[data-testid="tweetButtonInline"]').first
                    if not btn_inline.is_visible(timeout=200):
                        posted = True
                        break
                except Exception:
                    pass

                # ダイアログが出ていたら承認（app-bar-closeはキャンセルなので除外）
                for confirm_sel in [
                    '[data-testid="confirmationSheetConfirm"]',
                    'button:has-text("投稿する")',
                    'button:has-text("Post")',
                    'button:has-text("はい")',
                    'button:has-text("OK")',
                    'button:has-text("続ける")',
                    'button:has-text("Continue")',
                ]:
                    try:
                        btn = page.locator(confirm_sel).first
                        if btn.is_visible(timeout=200):
                            _save_screenshot(page, f"{client_name}_dialog")
                            btn.click()
                            print(f"  → ダイアログを承認 ({confirm_sel})")
                            time.sleep(1)
                            break
                    except Exception:
                        continue

            _save_screenshot(page, f"{client_name}_after_post")

            if posted:
                print("✅ 投稿完了!")
            else:
                print("❌ 投稿が確認できませんでした（スクリーンショットを確認してください）")
                raise Exception("投稿未確認")

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
        from datetime import date
        today = date.today().isoformat()
        out_dir = SCREENSHOT_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"x_error_{label}.png"
        page.screenshot(path=str(path))
        print(f"📸 スクリーンショット保存: {path}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Xへの自動投稿（Chrome実プロファイル使用）")
    parser.add_argument("--client", required=True, help="クライアント名（例: 天弥堂）")
    parser.add_argument("--setup", action="store_true", help="初回セットアップ（専用プロファイルを作成してログイン）")
    parser.add_argument("--text", help="投稿テキスト")
    parser.add_argument("--template", action="store_true", help="テンプレートローテーション使用")
    parser.add_argument("--generate", action="store_true", help="Claude CLIで投稿テキストを自動生成")
    parser.add_argument("--image", help="添付画像パス")
    parser.add_argument("--video", help="添付動画パス（画像より優先）")
    args = parser.parse_args()

    if args.setup:
        setup_profile(args.client)
        return

    # テキスト・画像・動画決定
    image_path = args.image
    video_path = args.video
    if args.generate:
        import json as _json
        r = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_daily.py"), "--client", args.client],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            print(f"ERROR: generate_daily.py 失敗:\n{r.stderr}"); sys.exit(1)
        data = _json.loads(r.stdout)
        text = data["x_text"]
        image_path = data.get("image_path") or args.image
        print(f"🤖 生成テキスト:\n{text}\n")
    elif args.template:
        text = get_next_template(args.client, "x")
        if not text:
            print("ERROR: テンプレートが見つかりません")
            sys.exit(1)
        print(f"📋 テンプレート:\n{text}\n")
    elif args.text:
        text = args.text
    else:
        print("ERROR: --text / --template / --generate のいずれかを指定してください")
        sys.exit(1)

    post_to_x(client_name=args.client, text=text, image_path=image_path, video_path=video_path)


if __name__ == "__main__":
    main()
