#!/usr/bin/env python3
"""
Claude CLIを使ってSNS投稿テキストを動的生成するスクリプト。
APIキー不要。`claude` コマンドをサブプロセスで呼び出す。

Usage:
  python3 generate_post.py --client 天弥堂 --sns x
  python3 generate_post.py --client 天弥堂 --sns instagram
  python3 generate_post.py --client 天弥堂 --sns threads
  python3 generate_post.py --client 天弥堂 --sns instagram --image-text  # 画像用テキストも生成
"""

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client_manager import get_client_dir


def load_content_profile(client_name: str) -> dict:
    path = get_client_dir(client_name) / "content_profile.json"
    if not path.exists():
        print(f"ERROR: content_profile.json が見つかりません: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_prompt(profile: dict, sns: str, include_image_text: bool = False) -> str:
    activity = random.choice(profile["activities"])
    fmt = profile["sns_formats"].get(sns, {})
    brand_tags = " ".join(profile["hashtags"]["brand"])
    activity_tags = " ".join(profile["hashtags"].get(activity["name"], []))
    hashtags = f"{brand_tags} {activity_tags}"

    prompt = f"""あなたは「{profile['brand_name']}」というブランドのSNS担当者です。

【ブランドの核心哲学】
{profile['core_philosophy']}

【今回のテーマ】
活動: {activity['name']}
内容: {activity['description']}

【トーン】
{profile['tone']}

【投稿先】{sns.upper()}
{fmt.get('style', '')}

【ハッシュタグ（必ず末尾に付ける）】
{hashtags}

以下の形式で出力してください。余計な説明は不要です。
"""

    if sns == "instagram" and include_image_text:
        prompt += """
---CAPTION---
（Instagramのキャプション本文をここに書く）
---IMAGE_TEXT---
（画像に載せる短いテキスト、2〜3行）
---END---
"""
    else:
        prompt += """
---POST---
（投稿本文をここに書く）
---END---
"""
    return prompt


def call_claude(prompt: str) -> str:
    import shutil
    from pathlib import Path
    claude_bin = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    result = subprocess.run(
        [claude_bin, "-p", prompt],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        print(f"ERROR: claude コマンド失敗:\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def parse_output(raw: str, sns: str, include_image_text: bool = False) -> dict:
    """Claudeの出力からキャプション・画像テキストを抽出する"""
    if include_image_text and "---CAPTION---" in raw:
        caption = raw.split("---CAPTION---")[1].split("---IMAGE_TEXT---")[0].strip()
        image_text = raw.split("---IMAGE_TEXT---")[1].split("---END---")[0].strip()
        return {"caption": caption, "image_text": image_text}
    elif "---POST---" in raw:
        post = raw.split("---POST---")[1].split("---END---")[0].strip()
        return {"text": post}
    else:
        # フォールバック: そのまま使う
        return {"text": raw}


def generate(client_name: str, sns: str, include_image_text: bool = False) -> dict:
    profile = load_content_profile(client_name)
    prompt = build_prompt(profile, sns, include_image_text)
    raw = call_claude(prompt)
    return parse_output(raw, sns, include_image_text)


def main():
    parser = argparse.ArgumentParser(description="Claude CLIでSNS投稿テキストを生成")
    parser.add_argument("--client", required=True)
    parser.add_argument("--sns", required=True, choices=["x", "instagram", "threads"])
    parser.add_argument("--image-text", action="store_true", help="Instagram画像用テキストも生成")
    args = parser.parse_args()

    result = generate(args.client, args.sns, args.image_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
