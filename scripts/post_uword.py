#!/usr/bin/env python3
"""
U-Word（ユーワード）投稿スクリプト
https://u-word.com/horby/myPage/realTimePost への自動投稿。

Usage:
  # 初回のみ: 専用プロファイルを作成して U-Word にログイン
  python3 post_uword.py --client 天弥堂 --setup

  # 投稿
  python3 post_uword.py --client 天弥堂 --title "タイトル" --body "本文"
  python3 post_uword.py --client 天弥堂 --title "タイトル" --body "本文" --category "お得情報"
"""

import argparse
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: pip3 install playwright --break-system-packages")
    sys.exit(1)

_SNS_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = _SNS_ROOT / "outputs/images"
AUTOMATION_PROFILES_DIR = _SNS_ROOT / "chrome-profiles"

POST_URL = "https://u-word.com/horby/myPage/realTimePost"
LOGIN_URL = "https://u-word.com/horby/login"

# 文字数上限
TITLE_MAX = 50
BODY_MAX = 500
DEFAULT_CATEGORY = "お得情報"


def automation_profile(client_name: str) -> Path:
    return AUTOMATION_PROFILES_DIR / f"{client_name}_uword"


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
    print("🌐 Chromeを開きます。U-Wordにログインして3分以内に完了してください。")

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
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

        print("⏳ ログイン待機中...")
        for _ in range(180):
            time.sleep(1)
            url = page.url
            # ログインページから別ページへ遷移したらログイン成功とみなす
            if "u-word.com" in url and "login" not in url:
                time.sleep(2)
                break
        else:
            print("❌ タイムアウト: 3分以内にログインが完了しませんでした")
            context.close()
            sys.exit(1)

        print("✅ ログイン完了。セットアップ終了します。")
        context.close()


def _try_fill(page, candidates, value):
    """複数のセレクタ候補で順に試して入力する"""
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible(timeout=1000):
                el.click()
                el.fill("")
                el.type(value, delay=10)
                return True
        except Exception:
            continue
    return False


def _try_select(page, candidates, value):
    """複数のセレクタ候補で順にセレクトボックス選択を試す"""
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                # select要素として試す
                try:
                    el.select_option(label=value)
                    return True
                except Exception:
                    pass
                # クリック → 候補選択
                try:
                    el.click()
                    time.sleep(0.5)
                    page.get_by_text(value, exact=True).first.click()
                    return True
                except Exception:
                    pass
        except Exception:
            continue
    return False


def post_to_uword(client_name: str, title: str, body: str, category: str = DEFAULT_CATEGORY):
    """U-Word に投稿する"""
    # 文字数チェック
    if len(title) > TITLE_MAX:
        print(f"⚠️  タイトルが{TITLE_MAX}文字を超えています（{len(title)}文字）。切り詰めます。")
        title = title[:TITLE_MAX]
    if len(body) > BODY_MAX:
        print(f"⚠️  本文が{BODY_MAX}文字を超えています（{len(body)}文字）。切り詰めます。")
        body = body[:BODY_MAX]

    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_uword.py --client {client_name} --setup")
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
            page.goto(POST_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "login" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")
            print(f"📝 投稿中... タイトル: {title[:20]}...")

            # タイトル入力（候補セレクタを順に試す）
            title_selectors = [
                'input[name="title"]',
                'input[name="postTitle"]',
                'input[id*="title" i]',
                'input[placeholder*="タイトル"]',
                'input[type="text"]',
            ]
            if not _try_fill(page, title_selectors, title):
                _save_screenshot(page, f"{client_name}_title_failed")
                raise Exception("タイトル入力欄が見つかりませんでした")
            print("  → タイトル入力 OK")

            # 本文入力
            body_selectors = [
                'textarea[name="body"]',
                'textarea[name="content"]',
                'textarea[name="postBody"]',
                'textarea[id*="body" i]',
                'textarea[id*="content" i]',
                'textarea[placeholder*="掲載"]',
                'textarea[placeholder*="本文"]',
                'textarea',
            ]
            if not _try_fill(page, body_selectors, body):
                _save_screenshot(page, f"{client_name}_body_failed")
                raise Exception("本文入力欄が見つかりませんでした")
            print("  → 本文入力 OK")

            # カテゴリー選択（U-Wordはボタン式）
            try:
                page.get_by_text(category, exact=True).first.click()
                print(f"  → カテゴリー: {category}")
            except Exception:
                print(f"  ⚠️  カテゴリー「{category}」が見つかりません（デフォルトで継続）")

            time.sleep(1)
            _save_screenshot(page, f"{client_name}_before_submit")

            # 投稿ボタン（U-Wordは「投稿」テキスト要素・「下書き」ではない方を選ぶ）
            submitted = False
            try:
                # get_by_text で「投稿」を完全一致で取得（下書きを除外）
                post_btn = page.get_by_text("投稿", exact=True).last
                post_btn.wait_for(timeout=5000)
                post_btn.click()
                submitted = True
            except Exception:
                # フォールバック: button要素として
                for sel in [
                    'button:has-text("投稿"):not(:has-text("下書き"))',
                    'button[type="submit"]',
                    'input[type="submit"]',
                ]:
                    try:
                        btn = page.locator(sel).first
                        if btn.count() > 0 and btn.is_visible(timeout=1000):
                            btn.click()
                            submitted = True
                            break
                    except Exception:
                        continue

            if not submitted:
                _save_screenshot(page, f"{client_name}_submit_failed")
                raise Exception("投稿ボタンが見つかりませんでした")

            time.sleep(3)

            # 確認ダイアログがあれば承認
            for confirm_sel in [
                'button:has-text("OK")',
                'button:has-text("はい")',
                'button:has-text("確定")',
                'button:has-text("送信する")',
            ]:
                try:
                    btn = page.locator(confirm_sel).first
                    if btn.count() > 0 and btn.is_visible(timeout=500):
                        btn.click()
                        time.sleep(2)
                        break
                except Exception:
                    continue

            _save_screenshot(page, f"{client_name}_after_submit")
            print("✅ 投稿完了!")

        except PlaywrightTimeout as e:
            print(f"❌ タイムアウト: {e}")
            _save_screenshot(page, f"{client_name}_timeout")
            raise
        except Exception as e:
            print(f"❌ エラー: {e}")
            _save_screenshot(page, f"{client_name}_error")
            raise
        finally:
            context.close()


def _save_screenshot(page, label: str = "error"):
    try:
        today = date.today().isoformat()
        out_dir = SCREENSHOT_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"uword_{label}.png"
        page.screenshot(path=str(path))
        print(f"📸 スクリーンショット保存: {path}")
    except Exception:
        pass


def _load_from_cache(client_name: str):
    """デイリーキャッシュから (title, body) を生成して返す"""
    import json as _json
    from datetime import datetime
    cache_dir = _SNS_ROOT / "outputs"
    # 朝/夕で適切なキャッシュを選ぶ
    hour = datetime.now().hour
    slot = "morning" if hour < 14 else "evening"
    cache_path = cache_dir / f"daily_cache_{client_name}_{slot}.json"
    if not cache_path.exists():
        # フォールバック: もう片方を試す
        slot = "evening" if slot == "morning" else "morning"
        cache_path = cache_dir / f"daily_cache_{client_name}_{slot}.json"
    if not cache_path.exists():
        return None, None
    with open(cache_path, encoding="utf-8") as f:
        data = _json.load(f)
    body = data.get("facebook_text") or data.get("instagram_caption") or data.get("x_text", "")
    if not body:
        return None, None
    # タイトルは本文の最初の1行（句点まで）
    first_line = body.split("\n")[0].split("。")[0]
    if not first_line:
        first_line = body[:TITLE_MAX]
    title = first_line[:TITLE_MAX]
    body = body[:BODY_MAX]
    return title, body


def main():
    parser = argparse.ArgumentParser(description="U-Wordへの自動投稿")
    parser.add_argument("--client", required=True, help="クライアント名（例: 天弥堂）")
    parser.add_argument("--setup", action="store_true", help="初回セットアップ（専用プロファイル作成・ログイン）")
    parser.add_argument("--title", help=f"投稿タイトル（{TITLE_MAX}文字以内）")
    parser.add_argument("--body", help=f"投稿本文（{BODY_MAX}文字以内）")
    parser.add_argument("--category", default=DEFAULT_CATEGORY, help=f"カテゴリー（デフォルト: {DEFAULT_CATEGORY}）")
    parser.add_argument("--generate", action="store_true", help="デイリーキャッシュから自動生成")
    args = parser.parse_args()

    if args.setup:
        setup_profile(args.client)
        return

    if args.generate:
        title, body = _load_from_cache(args.client)
        if not title or not body:
            print("ERROR: デイリーキャッシュが見つかりません。先に generate_daily.py を実行してください")
            sys.exit(1)
        print(f"🤖 生成タイトル: {title}")
        print(f"🤖 生成本文: {body[:80]}...")
    else:
        if not args.title or not args.body:
            print("ERROR: --title と --body の両方、もしくは --generate を指定してください")
            sys.exit(1)
        title, body = args.title, args.body

    post_to_uword(
        client_name=args.client,
        title=title,
        body=body,
        category=args.category,
    )


if __name__ == "__main__":
    main()
