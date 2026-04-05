#!/usr/bin/env python3
"""
動画生成スキル
sns_config.json + content_profile.json + アセット画像を組み合わせてスライド動画を生成する。

Usage:
  python3 generate_video.py --client 天弥堂 --activity 香り --text "香りの詩" --output /path/to/out.mp4
  python3 generate_video.py --client 天弥堂 --auto  # activityをランダム選択、テキストもランダム
"""

import argparse
import json
import random
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from client_manager import get_client_dir

GENERATE_VIDEO_SCRIPT = Path.home() / ".claude/scripts/generate_video.py"
VIDEO_OUT_DIR = Path.home() / ".claude/outputs/videos"


def load_config(client_name: str) -> dict:
    path = get_client_dir(client_name) / "sns_config.json"
    if not path.exists():
        print(f"ERROR: sns_config.json が見つかりません: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_content_profile(client_name: str) -> dict:
    path = get_client_dir(client_name) / "content_profile.json"
    if not path.exists():
        print(f"ERROR: content_profile.json が見つかりません: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_asset_images(client_name: str, activity: str, config: dict) -> list[str]:
    """アクティビティに対応するアセット画像パスリストを返す（絶対パス）"""
    client_dir = get_client_dir(client_name)
    images = config.get("assets", {}).get("images", {}).get(activity, [])
    abs_paths = []
    for rel in images:
        abs_path = client_dir / rel
        if abs_path.exists():
            abs_paths.append(str(abs_path))
    return abs_paths


def build_slides(text_lines: list[str], image_paths: list[str], video_cfg: dict) -> list[dict]:
    """
    テキスト行数分のスライドを組み立てる。
    画像がある場合は各スライドにランダムに割り当て。
    最後のスライドはブランド名。
    """
    font = video_cfg.get("font", "hiragino-w3")
    font_size = video_cfg.get("font_size", 80)
    color = video_cfg.get("color", "#ffffff")
    overlay_op = video_cfg.get("overlay_opacity", 0.45)
    shadow = video_cfg.get("shadow", True)

    slides = []
    shuffled_imgs = image_paths.copy()
    random.shuffle(shuffled_imgs)

    for i, line in enumerate(text_lines):
        slide = {
            "text": line,
            "font": font,
            "font_size": font_size,
            "color": color,
            "overlay_opacity": overlay_op,
            "shadow": shadow,
            "position": "center",
        }
        if shuffled_imgs:
            slide["image"] = shuffled_imgs[i % len(shuffled_imgs)]
        else:
            slide["bg_color"] = "#1a1a2e"
        slides.append(slide)

    return slides


def generate(
    client_name: str,
    activity: str,
    text_lines: list[str],
    output_path: Path,
    sns: str = "tiktok",
) -> Path:
    config = load_config(client_name)
    video_cfg = config.get("sns", {}).get(sns, {}).get("video_config", {})
    image_paths = get_asset_images(client_name, activity, config)
    # SNS別video_configに"bgm"があればそれを優先。nullなら無音。なければグローバル設定を使用
    if "bgm" in video_cfg:
        bgm_raw = video_cfg["bgm"] or ""
    else:
        bgm_raw = config.get("assets", {}).get("bgm", "")
    if bgm_raw:
        bgm_p = Path(bgm_raw)
        if not bgm_p.is_absolute():
            bgm_p = get_client_dir(client_name) / bgm_p
        bgm_path = str(bgm_p)
    else:
        bgm_path = ""

    slides = build_slides(text_lines, image_paths, video_cfg)

    # スライドJSONを一時ファイルに書き出す
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(slides, f, ensure_ascii=False)
        tmp_json = f.name

    cmd = [sys.executable, str(GENERATE_VIDEO_SCRIPT), "--slides", tmp_json, "-o", str(output_path)]
    if bgm_path and Path(bgm_path).exists():
        cmd += ["--bgm", bgm_path, "--bgm-volume", "0.3"]
    print(f"🎬 動画生成中... ({len(slides)}スライド, activity={activity})")
    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(tmp_json).unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"❌ 動画生成失敗:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout.strip())
    return output_path


def main():
    parser = argparse.ArgumentParser(description="アセット画像を使ったスライド動画生成")
    parser.add_argument("--client", required=True)
    parser.add_argument("--activity", help="アクティビティ名（省略時はランダム）")
    parser.add_argument("--text", help="動画に表示するテキスト（改行区切りでスライド分割）")
    parser.add_argument("--output", required=True, help="出力MP4パス")
    parser.add_argument("--sns", default="tiktok", choices=["tiktok", "youtube_shorts"])
    parser.add_argument("--auto", action="store_true", help="activityとテキストをランダム生成")
    args = parser.parse_args()

    if args.auto or not args.activity:
        profile = load_content_profile(args.client)
        act = random.choice(profile["activities"])
        activity = act["name"]
        print(f"🎲 ランダムアクティビティ: {activity}")
    else:
        activity = args.activity

    if args.text:
        text_lines = [l.strip() for l in args.text.split("\\n") if l.strip()]
    else:
        # デフォルト: ブランドの哲学を1スライド
        profile = load_content_profile(args.client)
        text_lines = [profile["core_philosophy"]]

    out_path = generate(
        client_name=args.client,
        activity=activity,
        text_lines=text_lines,
        output_path=Path(args.output),
        sns=args.sns,
    )
    print(f"✅ 動画生成完了: {out_path}")


if __name__ == "__main__":
    main()
