#!/usr/bin/env python3
"""
Instagram投稿スクリプト
テンプレートから画像を自動生成してInstagramに投稿する。
メインのChromeを閉じる必要はない。

Usage:
  # 初回のみ: 専用プロファイルを作成してInstagramにログイン
  python3 post_instagram.py --client 天弥堂 --setup

  # 以降: テンプレートから画像生成して投稿
  python3 post_instagram.py --client 天弥堂 --template

  # 画像・キャプションを直接指定
  python3 post_instagram.py --client 天弥堂 --image /path/to/image.jpg --caption "キャプション"
"""

import argparse
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client_manager import get_client_dir, load_templates, get_next_template

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: pip3 install playwright --break-system-packages")
    sys.exit(1)

_SNS_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = _SNS_ROOT / "outputs/images"
AUTOMATION_PROFILES_DIR = _SNS_ROOT / "chrome-profiles"
INSTA_IMAGE_SCRIPT = Path.home() / ".claude/scripts/insta_image.py"
SKILLS_DIR = _SNS_ROOT / "skills"


def automation_profile(client_name: str) -> Path:
    return AUTOMATION_PROFILES_DIR / f"{client_name}_instagram"


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
    print("🌐 Chromeを開きます。Instagramにログインして3分以内に完了してください。")

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
        page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=60000)

        print("⏳ ログイン待機中...")
        for _ in range(180):
            time.sleep(1)
            url = page.url
            if "instagram.com" in url and "login" not in url and "accounts" not in url:
                time.sleep(2)
                break
        else:
            print("❌ タイムアウト: 3分以内にログインが完了しませんでした")
            context.close()
            sys.exit(1)

        print("✅ ログイン完了。セットアップ終了します。")
        context.close()


def parse_instagram_template(template_str: str) -> tuple[str, str]:
    """
    テンプレート文字列から caption と text を分離する。
    caption: ... / text: ... の形式でなければ全文をキャプションとして扱う。
    戻り値: (caption, image_text)
    """
    caption = ""
    image_text = ""
    current_key = None
    current_lines = []

    for line in template_str.splitlines():
        if line.startswith("caption:"):
            if current_key == "text":
                image_text = "\n".join(current_lines).strip()
            current_key = "caption"
            rest = line[len("caption:"):].strip()
            current_lines = [rest] if rest else []
        elif line.startswith("text:"):
            if current_key == "caption":
                caption = "\n".join(current_lines).strip()
            current_key = "text"
            rest = line[len("text:"):].strip()
            current_lines = [rest] if rest else []
        else:
            current_lines.append(line)

    if current_key == "caption":
        caption = "\n".join(current_lines).strip()
    elif current_key == "text":
        image_text = "\n".join(current_lines).strip()

    # caption/text 記法がなければ全文をキャプションに
    if not caption and not image_text:
        caption = template_str.strip()

    return caption, image_text


def generate_image(text: str) -> Path:
    """insta_image.py を使って画像を生成し、パスを返す"""
    today = date.today().isoformat()
    out_dir = SCREENSHOT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = list(out_dir.glob("*.jpg")) + list(out_dir.glob("*.png"))
    seq = len(existing) + 1
    out_path = out_dir / f"{seq:03d}_instagram.jpg"

    cmd = [
        sys.executable,
        str(INSTA_IMAGE_SCRIPT),
        "--text", text,
        "--output", str(out_path),
        "--size", "square",
        "--font", "hiragino-w5",
        "--font-size", "64",
        "--color", "#ffffff",
        "--bg-fill", "#1a1a2e",
        "--shadow",
        "--overlay-opacity", "0.3",
    ]
    print(f"🎨 画像生成中...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ 画像生成失敗:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout.strip())
    return out_path


def post_reel_to_instagram(client_name: str, video_path: Path, caption: str = ""):
    """Instagramリールに動画を投稿する。
    フィード「投稿」フローで動画をアップロードするとInstagramが自動的にリールとして扱う。
    """
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に --setup を実行してください。")
        sys.exit(1)

    remove_singleton_lock(profile_dir)
    print("🌐 Chrome起動中（リール投稿）...")

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
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            if "login" in page.url or "accounts" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                sys.exit(1)

            print("✅ ログイン確認OK")
            print("📝 リール投稿フロー開始...")

            # 「作成」ボタンをクリック
            create_clicked = False
            for selector in [
                '[aria-label="新しい投稿"]',
                '[aria-label="新しい投稿を作成"]',
                '[aria-label="Create"]',
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        create_clicked = True
                        print(f"  → 作成ボタンクリック: {selector}")
                        break
                except Exception:
                    continue

            if not create_clicked:
                raise Exception("作成ボタンが見つかりません")

            time.sleep(2)

            # サブメニューの「投稿」をクリック（動画をアップするとリールになる）
            for text in ["投稿", "Post"]:
                try:
                    btn = page.get_by_text(text, exact=True).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        print(f"  → 「{text}」クリック")
                        break
                except Exception:
                    continue

            time.sleep(2)

            # 動画ファイルをアップロード
            print("🎬 動画をアップロード中...")
            with page.expect_file_chooser(timeout=15000) as fc_info:
                for selector in [
                    'button:has-text("コンピューターから選択")',
                    'button:has-text("Select from computer")',
                    'button:has-text("パソコンから選択")',
                    'input[type="file"]',
                ]:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=3000):
                            el.click()
                            print(f"  → ファイル選択: {selector}")
                            break
                    except Exception:
                        continue
            fc_info.value.set_files(str(video_path))
            time.sleep(5)

            # 「動画投稿はリール動画としてシェアされるようになりました」ダイアログの「OK」
            try:
                ok_btn = page.get_by_text("OK", exact=True).first
                if ok_btn.is_visible(timeout=5000):
                    ok_btn.click()
                    print("  → リール通知ダイアログ OK")
                    time.sleep(2)
            except Exception:
                pass

            # 「次へ」を2回クリック（切り抜き → フィルター）
            for step_name in ["切り抜き", "フィルター"]:
                for selector in [
                    '[role="button"]:has-text("次へ")',
                    '[role="button"]:has-text("Next")',
                    'button:has-text("次へ")',
                ]:
                    try:
                        btn = page.locator(selector).last
                        btn.wait_for(state="visible", timeout=10000)
                        btn.evaluate("el => el.click()")
                        print(f"  → {step_name}をスキップ")
                        time.sleep(3)
                        break
                    except Exception:
                        continue

            # キャプション入力
            if caption:
                print("📝 キャプション入力中...")
                for selector in [
                    '[aria-label="キャプションを書く..."]',
                    '[aria-label="Write a caption..."]',
                    'div[contenteditable="true"]',
                ]:
                    try:
                        cap_field = page.locator(selector).first
                        if cap_field.is_visible(timeout=5000):
                            cap_field.click()
                            time.sleep(0.5)
                            cap_field.type(caption, delay=20)
                            time.sleep(1)
                            page.keyboard.press("Tab")
                            time.sleep(1)
                            break
                    except Exception:
                        continue

                # 「破棄」ダイアログが出ていたらキャンセル
                try:
                    cancel_btn = page.get_by_text("キャンセル", exact=True).first
                    if cancel_btn.is_visible(timeout=2000):
                        cancel_btn.click()
                        print("  → 破棄ダイアログをキャンセル")
                        time.sleep(1)
                except Exception:
                    pass

            # 「シェア」ボタンをクリック
            print("🚀 シェア中...")
            share_clicked = False
            for selector in [
                'div[role="dialog"] [role="button"]:has-text("シェア"):not(:has-text("シェア先"))',
                '[role="button"]:has-text("シェア")',
                '[role="button"]:has-text("Share")',
                'button:has-text("シェア")',
            ]:
                try:
                    btn = page.locator(selector).first
                    btn.wait_for(state="visible", timeout=15000)
                    btn.evaluate("el => el.click()")
                    share_clicked = True
                    print(f"  → シェアボタンクリック ({selector})")
                    break
                except Exception:
                    continue

            if not share_clicked:
                _save_screenshot(page, f"{client_name}_reel_share")
                raise Exception("リールシェアボタンが見つかりません")

            # 完了確認
            for success_selector in [
                'text="リールがシェアされました"',
                'text="Your reel has been shared"',
                'text="投稿がシェアされました"',
                'text="Your post has been shared"',
            ]:
                try:
                    page.locator(success_selector).first.wait_for(timeout=20000)
                    print("✅ リール投稿確認OK")
                    break
                except Exception:
                    continue

            print("✅ リール投稿完了!")
            time.sleep(2)

        except PlaywrightTimeout as e:
            print(f"❌ タイムアウト: {e}")
            _save_screenshot(page, f"{client_name}_reel_error")
            raise
        except Exception as e:
            print(f"❌ エラー: {e}")
            _save_screenshot(page, f"{client_name}_reel_error")
            raise
        finally:
            try:
                page.close()
            except Exception:
                pass
            time.sleep(1)
            context.close()


def post_to_instagram(client_name: str, image_path: Path, caption: str):
    """自動化専用プロファイルのChromeでInstagramに投稿する"""
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_instagram.py --client {client_name} --setup")
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
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "login" in page.url or "accounts" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")
            print("📝 投稿フロー開始...")

            # 「作成」ボタンをクリック
            print("  → 作成ボタンを探しています...")
            create_clicked = False
            create_selectors = [
                '[aria-label="新しい投稿"]',
                '[aria-label="新しい投稿を作成"]',
                '[aria-label="新規投稿"]',
                '[aria-label="投稿を作成"]',
                '[aria-label="Create"]',
                '[aria-label="New post"]',
                '[aria-label="作成"]',
                'a[href="/create/style/"]',
                'svg[aria-label="新しい投稿"]',
                'svg[aria-label="新しい投稿を作成"]',
                'svg[aria-label="新規投稿"]',
            ]
            for selector in create_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        create_clicked = True
                        print(f"  → 作成ボタンクリック: {selector}")
                        break
                except Exception:
                    continue

            if not create_clicked:
                # テキスト「作成」または「Create」のリンク/ボタンを探す
                for text in ["作成", "Create", "新規投稿"]:
                    try:
                        btn = page.get_by_text(text, exact=True).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            create_clicked = True
                            print(f"  → テキストで作成ボタンクリック: {text}")
                            break
                    except Exception:
                        continue

            if not create_clicked:
                print("⚠️  作成ボタンが見つかりません。スクリーンショットを確認してください。")
                _save_screenshot(page, f"{client_name}_create_btn")
                raise Exception("作成ボタンが見つかりません")

            time.sleep(2)

            # サブメニューの「投稿」をクリック
            for text in ["投稿", "Post"]:
                try:
                    btn = page.get_by_text(text, exact=True).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        print(f"  → 「{text}」クリック")
                        break
                except Exception:
                    continue

            time.sleep(2)

            # ファイル選択（ファイルチューザー経由）
            print("🖼️  画像をアップロード中...")
            with page.expect_file_chooser(timeout=15000) as fc_info:
                for selector in [
                    'button:has-text("コンピューターから選択")',
                    'button:has-text("Select from computer")',
                    'button:has-text("パソコンから選択")',
                    'input[type="file"]',
                ]:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=3000):
                            el.click()
                            print(f"  → ファイル選択ボタンクリック: {selector}")
                            break
                    except Exception:
                        continue
            file_chooser = fc_info.value
            file_chooser.set_files(str(image_path))
            time.sleep(3)

            # 「次へ」を2回クリック（切り抜き → フィルター）
            for step_name in ["切り抜き", "フィルター"]:
                clicked = False
                # DIV[role="button"] を優先（Instagramの実際のボタン構造）
                for selector in [
                    '[role="button"]:has-text("次へ")',
                    '[role="button"]:has-text("Next")',
                    'button:has-text("次へ")',
                    'button:has-text("Next")',
                    '[aria-label="次へ"]',
                ]:
                    try:
                        btn = page.locator(selector).last  # 最後の要素（ヘッダーの右端）
                        btn.wait_for(state="visible", timeout=10000)
                        time.sleep(0.5)
                        btn.evaluate("el => el.click()")
                        print(f"  → {step_name}をスキップ ({selector})")
                        time.sleep(3)
                        clicked = True
                        break
                    except Exception:
                        continue
                if not clicked:
                    print(f"  ⚠️ {step_name}の「次へ」が見つかりません（スキップして続行）")

            # キャプション入力
            print("📝 キャプション入力中...")
            for selector in [
                '[aria-label="キャプションを書く..."]',
                '[aria-label="Write a caption..."]',
                'div[contenteditable="true"]',
                'textarea[aria-label*="caption"]',
            ]:
                try:
                    cap_field = page.locator(selector).first
                    if cap_field.is_visible(timeout=5000):
                        cap_field.click()
                        time.sleep(0.5)
                        cap_field.type(caption, delay=20)
                        time.sleep(1)
                        # ハッシュタグ補完ドロップダウンをTabキーで閉じる（Escはモーダルを閉じてしまう）
                        page.keyboard.press("Tab")
                        time.sleep(1)
                        break
                except Exception:
                    continue

            # 「破棄」ダイアログが出ていたらキャンセル
            try:
                cancel_btn = page.get_by_text("キャンセル", exact=True).first
                if cancel_btn.is_visible(timeout=2000):
                    cancel_btn.click()
                    print("  → 破棄ダイアログをキャンセル")
                    time.sleep(1)
            except Exception:
                pass

            # 「シェア」ボタンをクリック（ヘッダー右上の青いテキスト）
            print("🚀 シェア中...")
            share_clicked = False
            # ヘッダー内のシェアボタンを特定（「シェア先」と区別するため最初の要素）
            for selector in [
                'div[role="dialog"] [role="button"]:has-text("シェア"):not(:has-text("シェア先"))',
                '[role="button"]:has-text("シェア")',
                '[role="button"]:has-text("Share")',
                'button:has-text("シェア")',
                'button:has-text("Share")',
                '[aria-label="シェア"]',
            ]:
                try:
                    btns = page.locator(selector)
                    count = btns.count()
                    # 最初のボタン（ヘッダーの「シェア」）を使う
                    share_btn = btns.first
                    share_btn.wait_for(state="visible", timeout=10000)
                    share_btn.evaluate("el => el.click()")
                    share_clicked = True
                    print(f"  → シェアボタンクリック ({selector}, count={count})")
                    break
                except Exception:
                    continue

            if not share_clicked:
                _save_screenshot(page, f"{client_name}_share_btn")
                raise Exception("シェアボタンが見つかりません")

            # 投稿完了を確認（ダイアログが閉じてフィードに戻るのを待つ）
            posted = False
            for success_selector in [
                'text="投稿がシェアされました"',
                'text="Your post has been shared"',
                'text="投稿しました"',
                'text="シェアされました"',
            ]:
                try:
                    page.locator(success_selector).first.wait_for(timeout=20000)
                    posted = True
                    break
                except Exception:
                    continue

            if not posted:
                # ダイアログが消えたかで判断（投稿フォームが消えたら成功とみなす）
                try:
                    page.locator('[aria-label="新しい投稿を作成"], [aria-label="新しい投稿"]').first.wait_for(
                        state="visible", timeout=10000
                    )
                    posted = True  # フォームが消えてサイドバーが戻った
                except Exception:
                    pass

            if not posted:
                _save_screenshot(page, f"{client_name}_after_share")
                print("⚠️ 投稿完了ダイアログ未確認（投稿された可能性あり）")
            else:
                print("✅ 投稿確認OK")

            print("✅ 投稿完了!")
            time.sleep(2)

        except PlaywrightTimeout as e:
            print(f"❌ タイムアウト: {e}")
            _save_screenshot(page, client_name)
            raise
        except Exception as e:
            print(f"❌ エラー: {e}")
            _save_screenshot(page, client_name)
            raise
        finally:
            try:
                page.close()
            except Exception:
                pass
            time.sleep(1)
            context.close()


def post_carousel_to_instagram(client_name: str, image_dir: Path, caption: str):
    """カルーセル（複数画像）をInstagramに投稿する"""
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_instagram.py --client {client_name} --setup")
        sys.exit(1)

    # 画像ファイルを収集（slide_01, slide_02...の順）
    image_files = sorted(image_dir.glob("slide_*.png"))
    if not image_files:
        print(f"❌ {image_dir} にスライド画像が見つかりません")
        sys.exit(1)
    print(f"📸 カルーセル: {len(image_files)}枚の画像")

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
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "login" in page.url or "accounts" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")
            print("📝 カルーセル投稿フロー開始...")

            # 「作成」ボタンをクリック
            print("  → 作成ボタンを探しています...")
            create_clicked = False
            create_selectors = [
                '[aria-label="新しい投稿"]',
                '[aria-label="新しい投稿を作成"]',
                '[aria-label="新規投稿"]',
                '[aria-label="投稿を作成"]',
                '[aria-label="Create"]',
                '[aria-label="New post"]',
                '[aria-label="作成"]',
                'a[href="/create/style/"]',
                'svg[aria-label="新しい投稿"]',
                'svg[aria-label="新しい投稿を作成"]',
                'svg[aria-label="新規投稿"]',
            ]
            for selector in create_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        create_clicked = True
                        print(f"  → 作成ボタンクリック: {selector}")
                        break
                except Exception:
                    continue

            if not create_clicked:
                for text in ["作成", "Create", "新規投稿"]:
                    try:
                        btn = page.get_by_text(text, exact=True).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            create_clicked = True
                            print(f"  → テキストで作成ボタンクリック: {text}")
                            break
                    except Exception:
                        continue

            if not create_clicked:
                _save_screenshot(page, f"{client_name}_carousel_create_btn")
                raise Exception("作成ボタンが見つかりません")

            time.sleep(2)

            # サブメニューの「投稿」をクリック
            for text in ["投稿", "Post"]:
                try:
                    btn = page.get_by_text(text, exact=True).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        print(f"  → 「{text}」クリック")
                        break
                except Exception:
                    continue

            time.sleep(2)

            # ファイル選択（複数画像を一度に選択）
            print(f"🖼️  {len(image_files)}枚の画像をアップロード中...")
            with page.expect_file_chooser(timeout=15000) as fc_info:
                for selector in [
                    'button:has-text("コンピューターから選択")',
                    'button:has-text("Select from computer")',
                    'button:has-text("パソコンから選択")',
                    'input[type="file"]',
                ]:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=3000):
                            el.click()
                            print(f"  → ファイル選択ボタンクリック: {selector}")
                            break
                    except Exception:
                        continue
            file_chooser = fc_info.value
            # 複数画像を同時選択
            file_chooser.set_files([str(f) for f in image_files])
            print(f"  → {len(image_files)}枚を選択完了")
            time.sleep(4)

            # 「次へ」を2回クリック（切り抜き → フィルター）
            for step_name in ["切り抜き", "フィルター"]:
                clicked = False
                for selector in [
                    '[role="button"]:has-text("次へ")',
                    '[role="button"]:has-text("Next")',
                    'button:has-text("次へ")',
                    'button:has-text("Next")',
                    '[aria-label="次へ"]',
                ]:
                    try:
                        btn = page.locator(selector).last
                        btn.wait_for(state="visible", timeout=10000)
                        time.sleep(0.5)
                        btn.evaluate("el => el.click()")
                        print(f"  → {step_name}をスキップ ({selector})")
                        time.sleep(3)
                        clicked = True
                        break
                    except Exception:
                        continue
                if not clicked:
                    print(f"  ⚠️ {step_name}の「次へ」が見つかりません（スキップして続行）")

            # キャプション入力
            print("📝 キャプション入力中...")
            for selector in [
                '[aria-label="キャプションを書く..."]',
                '[aria-label="Write a caption..."]',
                'div[contenteditable="true"]',
                'textarea[aria-label*="caption"]',
            ]:
                try:
                    cap_field = page.locator(selector).first
                    if cap_field.is_visible(timeout=5000):
                        cap_field.click()
                        time.sleep(0.5)
                        cap_field.type(caption, delay=20)
                        time.sleep(1)
                        page.keyboard.press("Tab")
                        time.sleep(1)
                        break
                except Exception:
                    continue

            # 「破棄」ダイアログが出ていたらキャンセル
            try:
                cancel_btn = page.get_by_text("キャンセル", exact=True).first
                if cancel_btn.is_visible(timeout=2000):
                    cancel_btn.click()
                    print("  → 破棄ダイアログをキャンセル")
                    time.sleep(1)
            except Exception:
                pass

            # 「シェア」ボタンをクリック
            print("🚀 シェア中...")
            share_clicked = False
            for selector in [
                'div[role="dialog"] [role="button"]:has-text("シェア"):not(:has-text("シェア先"))',
                '[role="button"]:has-text("シェア")',
                '[role="button"]:has-text("Share")',
                'button:has-text("シェア")',
                'button:has-text("Share")',
                '[aria-label="シェア"]',
            ]:
                try:
                    btns = page.locator(selector)
                    share_btn = btns.first
                    share_btn.wait_for(state="visible", timeout=10000)
                    share_btn.evaluate("el => el.click()")
                    share_clicked = True
                    print(f"  → シェアボタンクリック ({selector})")
                    break
                except Exception:
                    continue

            if not share_clicked:
                _save_screenshot(page, f"{client_name}_carousel_share_btn")
                raise Exception("シェアボタンが見つかりません")

            # 投稿完了を確認
            posted = False
            for success_selector in [
                'text="投稿がシェアされました"',
                'text="Your post has been shared"',
                'text="投稿しました"',
                'text="シェアされました"',
            ]:
                try:
                    page.locator(success_selector).first.wait_for(timeout=30000)
                    posted = True
                    break
                except Exception:
                    continue

            if not posted:
                try:
                    page.locator('[aria-label="新しい投稿を作成"], [aria-label="新しい投稿"]').first.wait_for(
                        state="visible", timeout=15000
                    )
                    posted = True
                except Exception:
                    pass

            if not posted:
                _save_screenshot(page, f"{client_name}_carousel_after_share")
                print("⚠️ 投稿完了ダイアログ未確認（投稿された可能性あり）")
            else:
                print("✅ 投稿確認OK")

            print(f"✅ カルーセル投稿完了！（{len(image_files)}枚）")
            time.sleep(2)

        except PlaywrightTimeout as e:
            print(f"❌ タイムアウト: {e}")
            _save_screenshot(page, client_name)
            raise
        except Exception as e:
            print(f"❌ エラー: {e}")
            _save_screenshot(page, client_name)
            raise
        finally:
            try:
                page.close()
            except Exception:
                pass
            time.sleep(1)
            context.close()


def _save_screenshot(page, label: str = "error"):
    try:
        today = date.today().isoformat()
        out_dir = SCREENSHOT_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"instagram_error_{label}.png"
        page.screenshot(path=str(path))
        print(f"📸 スクリーンショット保存: {path}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Instagramへの自動投稿")
    parser.add_argument("--client", required=True, help="クライアント名（例: 天弥堂）")
    parser.add_argument("--setup", action="store_true", help="初回セットアップ（専用プロファイル作成・ログイン）")
    parser.add_argument("--template", action="store_true", help="テンプレートローテーション使用")
    parser.add_argument("--generate", action="store_true", help="Claude CLIでキャプション・画像テキストを自動生成")
    parser.add_argument("--image", help="投稿する画像パス（省略時は自動生成）")
    parser.add_argument("--caption", help="キャプション")
    parser.add_argument("--carousel", help="カルーセル投稿（スライド画像のディレクトリパス）")
    parser.add_argument("--carousel-caption", help="カルーセル投稿のキャプション（省略時はディレクトリ内のcaption.txtを使用）")
    parser.add_argument("--reel", action="store_true", help="リールに動画を投稿")
    parser.add_argument("--reel-generate", action="store_true", help="動画を自動生成してリール投稿")
    parser.add_argument("--video", help="投稿する動画パス（--reel と併用）")
    args = parser.parse_args()

    if args.setup:
        setup_profile(args.client)
        return

    # カルーセル投稿モード
    if args.carousel:
        carousel_dir = Path(args.carousel)
        if not carousel_dir.exists():
            print(f"❌ ディレクトリが見つかりません: {args.carousel}")
            sys.exit(1)
        # キャプション取得
        carousel_caption = args.carousel_caption or ""
        if not carousel_caption:
            caption_file = carousel_dir / "caption.txt"
            if caption_file.exists():
                carousel_caption = caption_file.read_text().strip()
                print(f"📋 caption.txt からキャプション読み込み")
        post_carousel_to_instagram(client_name=args.client, image_dir=carousel_dir, caption=carousel_caption)
        return

    # リール生成＆投稿モード
    if args.reel_generate:
        import json as _json
        from datetime import date as _date

        # generate_post.py でキャプション＆スライドテキスト生成（TikTokと同じパターン）
        r = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_post.py"), "--client", args.client, "--sns", "tiktok"],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0:
            print(f"ERROR: generate_post.py 失敗:\n{r.stderr}"); sys.exit(1)
        data = _json.loads(r.stdout)
        activity = data.get("activity", "")
        caption = data.get("caption", "")
        slide_texts = data.get("slide_texts", [caption])
        print(f"🤖 生成キャプション:\n{caption}\n")

        today = _date.today().isoformat()
        out_dir = _SNS_ROOT / "outputs/videos" / today
        out_dir.mkdir(parents=True, exist_ok=True)
        existing = list(out_dir.glob("*.mp4"))
        video_path = out_dir / f"{len(existing)+1:03d}_reel.mp4"

        r2 = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_video.py"),
             "--client", args.client, "--activity", activity,
             "--text", "\\n".join(slide_texts), "--output", str(video_path), "--sns", "tiktok"],
            capture_output=True, text=True, timeout=180
        )
        if r2.returncode != 0:
            print(f"ERROR: generate_video.py 失敗:\n{r2.stderr}"); sys.exit(1)
        print(r2.stdout.strip())
        post_reel_to_instagram(client_name=args.client, video_path=video_path, caption=caption)
        return

    # リール投稿モード（動画パス直接指定）
    if args.reel:
        if not args.video:
            print("ERROR: --reel には --video で動画パスを指定してください")
            sys.exit(1)
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"ERROR: 動画が見つかりません: {args.video}")
            sys.exit(1)
        reel_caption = args.caption or ""
        post_reel_to_instagram(client_name=args.client, video_path=video_path, caption=reel_caption)
        return

    # 生成モード
    if args.generate:
        import json as _json
        # generate_daily.pyのキャッシュを使う（Xと同じ画像・同じactivity）
        r = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_daily.py"), "--client", args.client],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            print(f"ERROR: generate_daily.py 失敗:\n{r.stderr}"); sys.exit(1)
        data = _json.loads(r.stdout)
        caption = data.get("instagram_caption", "")
        image_path = Path(data["image_path"])
        print(f"🤖 生成キャプション:\n{caption}\n")
        post_to_instagram(client_name=args.client, image_path=image_path, caption=caption)
        return
    elif args.template:
        template_str = get_next_template(args.client, "instagram")
        if not template_str:
            print("ERROR: instagram テンプレートが見つかりません")
            sys.exit(1)
        caption, image_text = parse_instagram_template(template_str)
        print(f"📋 テンプレート:\n{template_str}\n")
    else:
        caption = args.caption or ""
        image_text = caption

    # 画像の準備
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            print(f"ERROR: 画像が見つかりません: {args.image}")
            sys.exit(1)
    else:
        if not image_text:
            print("ERROR: --template または --image を指定してください")
            sys.exit(1)
        image_path = generate_image(image_text)

    post_to_instagram(client_name=args.client, image_path=image_path, caption=caption)


if __name__ == "__main__":
    main()
