#!/usr/bin/env python3
"""
日次コンテンツ生成スキル
1回の実行でX・Instagram用のキャプションと共有画像を生成・キャッシュする。
XとInstagramが同じactivity・画像を使い、キャプションだけ最適化される。

Usage:
  python3 generate_daily.py --client 天弥堂
  # 出力: ~/.claude/outputs/daily_cache_{朝|夜}.json + 画像ファイル
"""

import argparse
import json
import subprocess
import sys
import random
from datetime import date, datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from client_manager import get_client_dir

_SNS_ROOT = Path(__file__).resolve().parent.parent
INSTA_IMAGE_SCRIPT = Path.home() / ".claude/scripts/insta_image.py"
IMAGE_OUT_DIR = _SNS_ROOT / "outputs/images"
CACHE_DIR = _SNS_ROOT / "outputs"
TRENDS_CACHE = _SNS_ROOT / "outputs/trends_cache.json"


def load_trends() -> dict:
    """トレンドキャッシュを読み込む（なければ空を返す）"""
    if not TRENDS_CACHE.exists():
        return {}
    try:
        return json.loads(TRENDS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_content_profile(client_name: str) -> dict:
    path = get_client_dir(client_name) / "content_profile.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_sns_config(client_name: str) -> dict:
    path = get_client_dir(client_name) / "sns_config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_prompt(profile: dict, activity: dict) -> str:
    brand_tags = " ".join(profile["hashtags"]["brand"])
    activity_tags = " ".join(profile["hashtags"].get(activity["name"], []))

    x_fmt = profile["sns_formats"]["x"]
    ig_fmt = profile["sns_formats"]["instagram"]
    fb_fmt = profile["sns_formats"].get("facebook", {})
    th_fmt = profile["sns_formats"].get("threads", {})
    tt_fmt = profile["sns_formats"].get("tiktok", {})
    yt_fmt = profile["sns_formats"].get("youtube_shorts", {})

    # トレンド情報を取得
    trends = load_trends()
    trends_section = ""
    if trends:
        keywords = "、".join(trends.get("weekly_keywords", [])[:6])
        hints = "\n".join(f"・{h}" for h in trends.get("content_hints", [])[:5])

        # 今回のテーマに関連するTA分析を優先抽出（activity名との部分一致）
        all_ta = trends.get("ta_analysis", [])
        activity_name = activity["name"]
        related_ta = [t for t in all_ta if activity_name in t.get("trend", "") or activity_name in t.get("post_angle", "")]
        other_ta = [t for t in all_ta if t not in related_ta]
        ta_items = (related_ta + other_ta)[:3]

        ta_text = ""
        for t in ta_items:
            ta_text += f"\n  トレンド「{t['trend']}」\n  TA視点: {t['ta_perspective'][:120]}…\n  推奨投稿角度: {t['post_angle'][:120]}…\n"

        trends_section = f"""
【今週のトレンド】
キーワード: {keywords}
投稿ネタヒント（今回のテーマと連動しやすいものを選んで使う）:
{hints}

【交流分析（TA）視点のトレンド読み解き】
以下のうち最もテーマ「{activity['name']}」と結びつく視点を1つ以上、投稿に自然に織り込むこと。
無理に全部入れず、読み手に違和感を与えない範囲で活用すること。
{ta_text}"""

    return f"""あなたは「{profile['brand_name']}」のSNS担当者です。

【ブランドの核心哲学】
{profile['core_philosophy']}

【今回のテーマ】
活動: {activity['name']}
内容: {activity['description']}

【トーン】
{profile['tone']}

【ブランドハッシュタグ】{brand_tags}
【テーマハッシュタグ】{activity_tags}
{trends_section}
以下の形式で出力してください。余計な説明は不要です。
トレンド・TA視点は必ず1つ以上取り入れること。ただし不自然に押し込まず、読んだ人が気づかないくらい自然に溶け込ませること。

---X_POST---
（X用: {x_fmt['style']} 最大{x_fmt['max_chars']}字）
---INSTAGRAM_CAPTION---
（Instagram用: {ig_fmt['style']}）
---FACEBOOK_POST---
（Facebook用: {fb_fmt.get('style', '3〜5行の体験談＋問いかけ。ハッシュタグ1個。')}）
---THREADS_POST---
（Threads用: {th_fmt.get('style', '200字以内、会話誘発、ハッシュタグ1個')}）
---TIKTOK_CAPTION---
（TikTok用: {tt_fmt.get('style', 'Hook→世界観→CTA、ハッシュタグ3〜5個')}）
---YOUTUBE_CAPTION---
（YouTube Shorts用: {yt_fmt.get('style', 'SEOキーワード重視、ハッシュタグ3〜5個')}）
---IMAGE_TEXT---
（画像に重ねる短いテキスト。2〜3行。詩的に。）
---END---
"""


def call_claude(prompt: str) -> str:
    import shutil
    claude_bin = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    result = subprocess.run(
        [claude_bin, "-p", prompt],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"ERROR: claude失敗:\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def parse_output(raw: str) -> dict:
    def extract(start, end):
        if start in raw and end in raw:
            return raw.split(start)[1].split(end)[0].strip()
        return ""

    return {
        "x_text":             extract("---X_POST---",         "---INSTAGRAM_CAPTION---"),
        "instagram_caption":  extract("---INSTAGRAM_CAPTION---", "---FACEBOOK_POST---"),
        "facebook_text":      extract("---FACEBOOK_POST---",  "---THREADS_POST---"),
        "threads_text":       extract("---THREADS_POST---",   "---TIKTOK_CAPTION---"),
        "tiktok_caption":     extract("---TIKTOK_CAPTION---", "---YOUTUBE_CAPTION---"),
        "youtube_caption":    extract("---YOUTUBE_CAPTION---","---IMAGE_TEXT---"),
        "image_text":         extract("---IMAGE_TEXT---",     "---END---"),
    }


def get_random_asset_image(client_name: str, activity: str):
    """activityに対応するアセット画像をランダムに返す"""
    config = load_sns_config(client_name)
    client_dir = get_client_dir(client_name)
    images = config.get("assets", {}).get("images", {}).get(activity, [])
    candidates = [str(client_dir / p) for p in images if (client_dir / p).exists()]
    return random.choice(candidates) if candidates else None


def generate_image(image_text: str, client_name: str, activity: str = "") -> Path:
    today = date.today().isoformat()
    out_dir = IMAGE_OUT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = list(out_dir.glob("*.jpg")) + list(out_dir.glob("*.png"))
    seq = len(existing) + 1
    out_path = out_dir / f"{seq:03d}_daily.jpg"

    bg_image = get_random_asset_image(client_name, activity) if activity else None

    cmd = [
        sys.executable, str(INSTA_IMAGE_SCRIPT),
        "--text", image_text,
        "--output", str(out_path),
        "--size", "portrait",
        "--font", "hiragino-w5",
        "--font-size", "64",
        "--color", "#ffffff",
        "--shadow",
        "--overlay-opacity", "0.45",
    ]
    if bg_image:
        cmd += ["--image", bg_image]
    else:
        cmd += ["--bg-fill", "#1a1a2e"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: 画像生成失敗:\n{result.stderr}")
        sys.exit(1)
    return out_path


def get_slot() -> str:
    """実行時間帯を返す: morning / evening"""
    hour = datetime.now().hour
    return "morning" if hour < 14 else "evening"


def cache_path(client_name: str, slot: str) -> Path:
    return CACHE_DIR / f"daily_cache_{client_name}_{slot}.json"


def generate(client_name: str) -> dict:
    profile = load_content_profile(client_name)
    activity = random.choice(profile["activities"])
    slot = get_slot()

    print(f"🎲 activity: {activity['name']} ({slot})", file=sys.stderr)
    print("🤖 Claude生成中...", file=sys.stderr)

    prompt = build_prompt(profile, activity)
    raw = call_claude(prompt)
    texts = parse_output(raw)

    print("🎨 画像生成中...", file=sys.stderr)
    image_path = generate_image(texts["image_text"] or texts["instagram_caption"], client_name, activity["name"])

    result = {
        "client": client_name,
        "slot": slot,
        "date": date.today().isoformat(),
        "activity": activity["name"],
        "image_path": str(image_path),
        "x_text":            texts["x_text"],
        "instagram_caption": texts["instagram_caption"],
        "facebook_text":     texts["facebook_text"],
        "threads_text":      texts["threads_text"],
        "tiktok_caption":    texts["tiktok_caption"],
        "youtube_caption":   texts["youtube_caption"],
        "image_text":        texts["image_text"],
    }

    # キャッシュ保存
    cp = cache_path(client_name, slot)
    cp.parent.mkdir(parents=True, exist_ok=True)
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ キャッシュ保存: {cp}", file=sys.stderr)
    return result


def load_cache(client_name: str, slot: str = None):
    if slot is None:
        slot = get_slot()
    cp = cache_path(client_name, slot)
    if not cp.exists():
        return None
    data = json.loads(cp.read_text(encoding="utf-8"))
    # 今日のキャッシュか確認
    if data.get("date") != date.today().isoformat():
        return None
    return data


def main():
    parser = argparse.ArgumentParser(description="日次コンテンツ一括生成")
    parser.add_argument("--client", required=True)
    parser.add_argument("--force", action="store_true", help="キャッシュを無視して再生成")
    args = parser.parse_args()

    if not args.force:
        cached = load_cache(args.client)
        if cached:
            print(f"📦 キャッシュ使用 (activity={cached['activity']})", file=sys.stderr)
            print(json.dumps(cached, ensure_ascii=False, indent=2))
            return

    result = generate(args.client)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
