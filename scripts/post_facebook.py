#!/usr/bin/env python3
"""
Facebook投稿スクリプト
自動化専用Chromeプロファイルを使って投稿する。

Usage:
  # 初回のみ
  python3 post_facebook.py --client 天弥堂 --setup

  # テンプレート投稿
  python3 post_facebook.py --client 天弥堂 --template

  # Claude生成で投稿
  python3 post_facebook.py --client 天弥堂 --generate

  # 画像付き投稿
  python3 post_facebook.py --client 天弥堂 --generate --image /path/to/image.jpg
"""

import argparse
import subprocess
import sys
import time
from datetime import date
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
    return AUTOMATION_PROFILES_DIR / f"{client_name}_facebook"


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
    print("🌐 Chromeを開きます。Facebookにログインして3分以内に完了してください。")

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
        page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=60000)

        print("⏳ ログイン待機中...")
        for _ in range(180):
            time.sleep(1)
            url = page.url
            if "facebook.com" in url and "login" not in url and "checkpoint" not in url:
                time.sleep(2)
                break
        else:
            print("❌ タイムアウト: 3分以内にログインが完了しませんでした")
            context.close()
            sys.exit(1)

        print("✅ ログイン完了。セットアップ終了します。")
        context.close()


def post_to_facebook(client_name: str, text: str, image_path: str = None):
    """自動化専用プロファイルのChromeでFacebookに投稿する"""
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_facebook.py --client {client_name} --setup")
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
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "login" in page.url or "checkpoint" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")
            print("📝 投稿ボックスを開いています...")

            # 「その気持ち、シェアしよう」をクリックしてモーダルを開く
            opened = False
            for selector in [
                'span:has-text("シェアしよう")',
                'span:has-text("その気持ち")',
                '[placeholder*="気持ち"]',
                '[aria-label*="気持ち"]',
                'span:has-text("What\'s on your mind")',
                '[placeholder*="mind"]',
                '[aria-label*="mind"]',
                'div[role="button"]:has-text("シェアしよう")',
            ]:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=3000):
                        el.click()
                        time.sleep(2)
                        opened = True
                        break
                except Exception:
                    continue

            if not opened:
                raise Exception("投稿ボタンが見つかりませんでした。スクリーンショットを確認してください。")

            # テキスト入力エリアを探す
            print("📝 テキスト入力中...")
            compose_el = None
            for selector in [
                'div[role="textbox"][contenteditable="true"]',
                'div[aria-label*="気持ち"][contenteditable]',
                'div[aria-label*="mind"][contenteditable]',
                'div[data-lexical-editor="true"]',
            ]:
                try:
                    el = page.locator(selector).first
                    el.wait_for(state="visible", timeout=8000)
                    compose_el = el
                    break
                except Exception:
                    continue

            if compose_el is None:
                raise Exception("テキスト入力エリアが見つかりませんでした")

            compose_el.click()
            time.sleep(0.5)
            compose_el.type(text, delay=20)
            time.sleep(1)

            # 画像添付
            if image_path and Path(image_path).exists():
                print("🖼️  画像を添付中...")
                for selector in [
                    '[aria-label*="写真"]',
                    '[aria-label*="Photo"]',
                    'input[type="file"]',
                ]:
                    try:
                        if selector == 'input[type="file"]':
                            file_input = page.locator(selector).first
                            file_input.set_input_files(image_path)
                        else:
                            el = page.locator(selector).first
                            if el.is_visible(timeout=3000):
                                el.click()
                                time.sleep(1)
                                file_input = page.locator('input[type="file"]').first
                                file_input.set_input_files(image_path)
                        time.sleep(4)
                        break
                    except Exception:
                        continue
            elif image_path:
                print(f"⚠️  画像が見つかりません（スキップ）: {image_path}")

            # 投稿ボタン
            print("🚀 投稿中...")
            for selector in [
                '[aria-label="投稿"]',
                '[aria-label="Post"]',
                'div[aria-label="投稿"][role="button"]',
                'div[aria-label="Post"][role="button"]',
                'button:has-text("投稿")',
                'button:has-text("Post")',
            ]:
                try:
                    btn = page.locator(selector).last
                    btn.wait_for(state="visible", timeout=8000)
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
        path = out_dir / f"facebook_error_{label}.png"
        page.screenshot(path=str(path))
        print(f"📸 スクリーンショット保存: {path}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Facebookへの自動投稿")
    parser.add_argument("--client", required=True, help="クライアント名（例: 天弥堂）")
    parser.add_argument("--setup", action="store_true", help="初回セットアップ（専用プロファイル作成・ログイン）")
    parser.add_argument("--text", help="投稿テキスト")
    parser.add_argument("--template", action="store_true", help="テンプレートローテーション使用")
    parser.add_argument("--generate", action="store_true", help="Claude CLIで投稿テキストを自動生成")
    parser.add_argument("--image", help="添付画像パス")
    args = parser.parse_args()

    if args.setup:
        setup_profile(args.client)
        return

    image_path = args.image
    if args.generate:
        import json as _json
        r = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_daily.py"), "--client", args.client],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            print(f"ERROR: generate_daily.py 失敗:\n{r.stderr}"); sys.exit(1)
        data = _json.loads(r.stdout)
        text = data.get("facebook_text") or data.get("x_text", "")
        image_path = image_path or data.get("image_path")
        print(f"🤖 生成テキスト:\n{text}\n")
    elif args.template:
        text = get_next_template(args.client, "facebook")
        if not text:
            print("ERROR: facebook テンプレートが見つかりません")
            sys.exit(1)
        print(f"📋 テンプレート:\n{text}\n")
    elif args.text:
        text = args.text
    else:
        print("ERROR: --text / --template / --generate のいずれかを指定してください")
        sys.exit(1)

    post_to_facebook(client_name=args.client, text=text, image_path=image_path)


if __name__ == "__main__":
    main()
