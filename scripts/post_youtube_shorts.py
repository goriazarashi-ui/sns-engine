#!/usr/bin/env python3
"""
YouTube Shorts投稿スクリプト
JSONテンプレートから動画を自動生成してYouTube Studioにアップロードする。
TikTokと同じ動画テンプレートを共用する。
メインのChromeを閉じる必要はない。

Usage:
  # 初回のみ: 専用プロファイルを作成してGoogleアカウントにログイン
  python3 post_youtube_shorts.py --client 天弥堂 --setup

  # 以降: テンプレートローテーションで動画生成→投稿
  python3 post_youtube_shorts.py --client 天弥堂 --template

  # 動画ファイルを直接指定
  python3 post_youtube_shorts.py --client 天弥堂 --video /path/to/video.mp4 --title "タイトル" --description "説明"
"""

import argparse
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
SCREENSHOT_DIR = _SNS_ROOT / "outputs/images"
VIDEO_DIR = _SNS_ROOT / "outputs/videos"
AUTOMATION_PROFILES_DIR = _SNS_ROOT / "chrome-profiles"
GENERATE_VIDEO_SCRIPT = Path.home() / ".claude/scripts/generate_video.py"
SKILLS_DIR = _SNS_ROOT / "skills"


def automation_profile(client_name: str) -> Path:
    return AUTOMATION_PROFILES_DIR / f"{client_name}_youtube"


def remove_singleton_lock(profile_dir: Path):
    for name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock = profile_dir / name
        if lock.exists() or lock.is_symlink():
            lock.unlink()


def setup_profile(client_name: str):
    """自動化専用プロファイルを作成し、Googleアカウントにログインさせる"""
    profile_dir = automation_profile(client_name)
    profile_dir.mkdir(parents=True, exist_ok=True)
    remove_singleton_lock(profile_dir)
    print(f"🔧 専用プロファイル: {profile_dir}")
    print("🌐 Chromeを開きます。YouTubeのGoogleアカウントにログインして3分以内に完了してください。")

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
        page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60000)

        print("⏳ ログイン待機中...")
        for _ in range(180):
            time.sleep(1)
            url = page.url
            if "studio.youtube.com" in url and "accounts.google.com" not in url:
                time.sleep(2)
                break
        else:
            print("❌ タイムアウト: 3分以内にログインが完了しませんでした")
            context.close()
            sys.exit(1)

        print("✅ ログイン完了。セットアップ終了します。")
        context.close()


def get_next_tiktok_template(client_name: str) -> tuple[dict, int]:
    """TikTokテンプレートJSONをローテーションで返す（YouTube Shortsで共用）"""
    tmpl_dir = get_client_dir(client_name) / "templates" / "tiktok"
    templates = sorted(tmpl_dir.glob("*.json"))
    if not templates:
        print(f"ERROR: テンプレートが見つかりません: {tmpl_dir}")
        sys.exit(1)

    state_path = get_client_dir(client_name) / ".template_index_youtube_shorts"
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
    out_path = out_dir / f"{seq:03d}_youtube_shorts.mp4"

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


def post_to_youtube_shorts(client_name: str, video_path: Path, title: str, description: str = ""):
    """YouTube Studioで動画をアップロードしてShortsとして投稿する"""
    profile_dir = automation_profile(client_name)
    if not profile_dir.exists():
        print(f"❌ 専用プロファイルが未作成です。先に以下を実行してください:")
        print(f"   python3 post_youtube_shorts.py --client {client_name} --setup")
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
            page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # ログイン確認
            if "accounts.google.com" in page.url:
                print("❌ ログインしていません。先に --setup を実行してください。")
                context.close()
                sys.exit(1)

            print("✅ ログイン確認OK")
            print("📤 動画アップロード中...")

            # 「作成」ボタン → 「動画をアップロード」
            create_btn = page.locator('#create-icon, [aria-label="作成"], [aria-label="Create"]').first
            create_btn.wait_for(timeout=15000)
            create_btn.click()
            time.sleep(2)

            upload_btn = page.locator('tp-yt-paper-item:has-text("動画をアップロード"), tp-yt-paper-item:has-text("Upload video")').first
            upload_btn.wait_for(timeout=10000)
            upload_btn.click()
            time.sleep(2)

            # ファイル選択
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator('input[type="file"]').first.evaluate("el => el.click()")
            file_chooser = fc_info.value
            file_chooser.set_files(str(video_path))
            print("  → ファイルセット完了。処理待機中...")
            time.sleep(8)

            # タイトル入力（デフォルトでファイル名が入っているのでクリアして入力）
            print("📝 タイトル・説明入力中...")
            title_field = page.locator('#title-textarea #textbox, [aria-label="タイトルを追加（必須）"]').first
            title_field.wait_for(timeout=15000)
            title_field.click(click_count=3)
            title_field.type(title, delay=20)
            time.sleep(1)

            # 説明欄
            if description:
                desc_field = page.locator('#description-textarea #textbox, [aria-label="視聴者に動画の内容を伝えましょう"]').first
                try:
                    if desc_field.is_visible(timeout=3000):
                        desc_field.click()
                        desc_field.type(description, delay=20)
                        time.sleep(1)
                        # ハッシュタグのオートコンプリートドロップダウンを閉じる
                        page.keyboard.press("Escape")
                        time.sleep(0.5)
                        # タイトル欄をクリックしてフォーカスを移しドロップダウンを確実に消す
                        title_field.click()
                        time.sleep(0.5)
                except Exception:
                    pass

            # 視聴者層はチャンネルデフォルト（子ども向けでない）に任せる — 触らない
            print("  → 視聴者層: チャンネルデフォルト使用（子ども向けでない）")

            # 「次へ」を3回クリック（詳細 → 動画の要素 → チェック → 公開設定）
            for step in ["動画の要素", "チェック", "公開設定"]:
                try:
                    btn = page.locator('ytcp-button#next-button').first
                    btn.wait_for(timeout=10000)
                    btn.evaluate("el => el.click()")
                    print(f"  → {step}へ")
                    time.sleep(3)
                except Exception:
                    continue

            # 公開設定: 「公開」ラジオボタンを選択
            print("  → 公開設定: 「公開」を選択")
            for selector in [
                'ytcp-radio-button:has-text("公開")',
                'tp-yt-paper-radio-button:has-text("公開")',
            ]:
                try:
                    btn = page.locator(selector).last  # 「公開」が最後（非公開・限定公開・公開の順）
                    if btn.is_visible(timeout=5000):
                        btn.evaluate("el => el.click()")
                        time.sleep(1)
                        break
                except Exception:
                    continue

            # 「保存」ボタンをクリック（公開選択後は即時公開される）
            print("🚀 公開中...")
            done_btn = page.locator('ytcp-button#done-button').first
            done_btn.wait_for(timeout=15000)
            done_btn.evaluate("el => el.click()")

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
        path = out_dir / f"youtube_error_{label}.png"
        page.screenshot(path=str(path))
        print(f"📸 スクリーンショット保存: {path}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="YouTube Shortsへの自動投稿")
    parser.add_argument("--client", required=True, help="クライアント名（例: 天弥堂）")
    parser.add_argument("--setup", action="store_true", help="初回セットアップ（専用プロファイル作成・ログイン）")
    parser.add_argument("--template", action="store_true", help="テンプレートローテーション使用（動画自動生成）")
    parser.add_argument("--generate", action="store_true", help="Claude CLIでテキスト生成＋アセット画像で動画生成")
    parser.add_argument("--video", help="投稿する動画パス（省略時はテンプレートから自動生成）")
    parser.add_argument("--title", help="動画タイトル")
    parser.add_argument("--description", help="動画説明")
    args = parser.parse_args()

    if args.setup:
        setup_profile(args.client)
        return

    if args.generate:
        import json as _json
        result = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_post.py"), "--client", args.client, "--sns", "youtube_shorts"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"ERROR: generate_post.py 失敗:\n{result.stderr}"); sys.exit(1)
        data = _json.loads(result.stdout)
        activity = data.get("activity", "")
        caption = data.get("caption", "")
        slide_texts = data.get("slide_texts", [caption])
        title = caption.splitlines()[0][:100] if caption else "天弥堂"
        description = caption
        print(f"🤖 生成テキスト:\n{caption}\n")

        today = date.today().isoformat()
        out_dir = VIDEO_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)
        existing = list(out_dir.glob("*.mp4"))
        out_path = out_dir / f"{len(existing)+1:03d}_youtube.mp4"

        result2 = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "generate_video.py"),
             "--client", args.client, "--activity", activity,
             "--text", "\\n".join(slide_texts), "--output", str(out_path), "--sns", "youtube_shorts"],
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
        # キャプション1行目をタイトルに、全文を説明に
        title = caption.splitlines()[0][:100] if caption else "天弥堂"
        description = caption
        print(f"📋 テンプレート #{idx + 1}\nタイトル: {title}\n")
        video_path = generate_video(slides, args.client)
    elif args.video:
        video_path = Path(args.video)
        title = args.title or video_path.stem
        description = args.description or ""
        if not video_path.exists():
            print(f"ERROR: 動画が見つかりません: {args.video}")
            sys.exit(1)
    else:
        print("ERROR: --template または --video を指定してください")
        sys.exit(1)

    post_to_youtube_shorts(client_name=args.client, video_path=video_path, title=title, description=description)


if __name__ == "__main__":
    main()
