#!/usr/bin/env python3
"""
Threads投稿スクリプト
自動化専用Chromeプロファイルを使って投稿する。
メインのChromeを閉じる必要はない。

Usage:
  # 初回のみ: 専用プロファイルを作成してThreadsにログイン
  python3 post_threads.py --client 天弥堂 --setup

  # 以降: テンプレートローテーションで投稿
  python3 post_threads.py --client 天弥堂 --template
  python3 post_threads.py --client 天弥堂 --text "投稿内容"
  python3 post_threads.py --client 天弥堂 --text "投稿内容" --image /path/to/image.jpg
"""

import argparse
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


def automation_profile(client_name: str) -> Path:
    return AUTOMATION_PROFILES_DIR / f"{client_name}_threads"


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
    print("🌐 Chromeを開きます。Threadsにログインして3分以内に完了してください。")

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
        page.goto("https://www.threads.net/login", wait_until="domcontentloaded", timeout=60000)

        print("⏳ ログイン待機中...")
        for _ in range(180):
            time.sleep(1)
            url = page.url
            if "threads.net" in url and "login" not in url:
                time.sleep(2)
                break
        else:
            print("❌ タイムアウト: 3分以内にログインが完了しませんでした")
            context.close()
            sys.exit(1)

        print("✅ ログイン完了。セットアップ終了します。")
        context.close()


def post_to_threads(client_name: str, text: str, image_path: str = None):
    """自動化専用プロファイルのChromeでThreadsに投稿する"""
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_threads.py --client {client_name} --setup")
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
            page.goto("https://www.threads.com/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "login" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")
            print("📝 投稿中...")

            # 「なにしてる？」をクリックしてモーダルを開く
            for trigger in ["なにしてる？", "今なにしてる？", "What's new?", "Start a thread..."]:
                try:
                    page.get_by_text(trigger).first.click()
                    time.sleep(2)
                    break
                except Exception:
                    continue

            # モーダル内のtextboxに入力
            compose_el = page.locator('div[role="textbox"]').first
            compose_el.wait_for(state="visible", timeout=10000)
            compose_el.click()
            time.sleep(0.5)
            compose_el.type(text, delay=20)
            time.sleep(1)

            # 投稿ボタン（モーダル内の「投稿」DIV要素）
            post_btn = page.get_by_text("投稿", exact=True).last
            post_btn.wait_for(timeout=10000)
            post_btn.evaluate("el => el.click()")

            time.sleep(3)
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
        path = out_dir / f"threads_error_{label}.png"
        page.screenshot(path=str(path))
        print(f"📸 スクリーンショット保存: {path}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Threadsへの自動投稿")
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

    if args.generate:
        import subprocess, json as _json
        skills_dir = Path(__file__).parent.parent / "skills"
        # generate_daily.pyのキャッシュを使う（Xと同じコンテンツ）
        result = subprocess.run(
            [sys.executable, str(skills_dir / "generate_daily.py"), "--client", args.client],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            print(f"ERROR: generate_daily.py 失敗:\n{result.stderr}"); sys.exit(1)
        data = _json.loads(result.stdout)
        text = data.get("x_text", "")
        print(f"🤖 生成テキスト:\n{text}\n")
    elif args.template:
        text = get_next_template(args.client, "threads")
        if not text:
            print("ERROR: threads テンプレートが見つかりません")
            sys.exit(1)
        print(f"📋 テンプレート:\n{text}\n")
    elif args.text:
        text = args.text
    else:
        print("ERROR: --text / --template / --generate のいずれかを指定してください")
        sys.exit(1)

    post_to_threads(client_name=args.client, text=text, image_path=args.image)


if __name__ == "__main__":
    main()
