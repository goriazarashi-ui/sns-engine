#!/usr/bin/env python3
"""
投稿テキスト生成スキル（Claude CLI使用）
動画投稿向け: activity + caption + slide_texts を生成する。

Usage:
  python3 generate_post.py --client 天弥堂 --sns tiktok
  python3 generate_post.py --client 天弥堂 --sns youtube_shorts
  # 出力: JSON {"activity": "香り", "caption": "...", "slide_texts": ["...", "..."]}
"""

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from client_manager import get_client_dir


def load_content_profile(client_name: str) -> dict:
    path = get_client_dir(client_name) / "content_profile.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_video_prompt(profile: dict, sns: str) -> tuple[str, str]:
    """プロンプトと選択したactivity名を返す"""
    act = random.choice(profile["activities"])
    fmt = profile["sns_formats"].get(sns.replace("youtube_shorts", "tiktok") if sns == "youtube_shorts" else sns, {})
    brand_tags = " ".join(profile["hashtags"]["brand"])
    activity_tags = " ".join(profile["hashtags"].get(act["name"], []))
    hashtags = f"{brand_tags} {activity_tags}"

    prompt = f"""あなたは「{profile['brand_name']}」というブランドのSNS担当者です。

【ブランドの核心哲学】
{profile['core_philosophy']}

【今回のテーマ】
活動: {act['name']}
内容: {act['description']}

【トーン】
{profile['tone']}

【投稿先】{sns.upper()}（縦型スライド動画・約30秒）
6枚のスライドに分けて表示します。各スライドに1〜2行のテキストを表示します。

【スライド構成の指示】
- SLIDE_1（Hook）: 最初の3秒で視聴者を止める一言。疑問・驚き・共感を誘う短い問いかけや断言。
- SLIDE_2〜5: テーマの世界観を詩的に展開。余白を大切に。
- SLIDE_6: ブランド名「{profile['brand_name']}」または短いキャッチコピー。

【キャプションの指示】
- 最初の1文に検索キーワード（{act['name']}に関連する自然なワード）を含める
- 2〜3行の本文
- 最後に「保存してね」「コメントで教えて」等の一言CTA
- ハッシュタグ3〜5個（末尾）

【ハッシュタグ候補（この中から3〜5個選ぶ）】
{hashtags}

以下の形式で出力してください。余計な説明は不要です。

---ACTIVITY---
{act['name']}
---CAPTION---
（キャプション本文＋CTA＋ハッシュタグ3〜5個）
---SLIDE_1---
（Hook: 視聴者を止める一言。1〜2行）
---SLIDE_2---
（世界観展開。1〜2行）
---SLIDE_3---
（世界観展開。1〜2行）
---SLIDE_4---
（世界観展開。1〜2行）
---SLIDE_5---
（世界観展開。1〜2行）
---SLIDE_6---
（ブランド名またはキャッチコピー）
---END---
"""
    return prompt, act["name"]


def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["/Users/imamuramaki/.local/bin/claude", "-p", prompt],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"ERROR: claude コマンド失敗:\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def parse_video_output(raw: str, activity: str) -> dict:
    """スライドテキストとキャプションを抽出"""
    lines_between = lambda marker_start, marker_end: (
        raw.split(marker_start)[1].split(marker_end)[0].strip()
        if marker_start in raw and marker_end in raw else ""
    )

    caption = lines_between("---CAPTION---", "---SLIDE_1---") or lines_between("---CAPTION---", "---END---")

    slide_texts = []
    for i in range(1, 8):
        marker = f"---SLIDE_{i}---"
        next_marker = f"---SLIDE_{i+1}---" if f"---SLIDE_{i+1}---" in raw else "---END---"
        if marker in raw:
            t = lines_between(marker, next_marker)
            if t:
                slide_texts.append(t)

    # スライドが取れなかった場合はキャプションを分割して使う
    if not slide_texts and caption:
        parts = [p.strip() for p in caption.split("\n") if p.strip() and not p.startswith("#")]
        slide_texts = parts[:4] if parts else [caption]

    return {
        "activity": activity,
        "caption": caption,
        "slide_texts": slide_texts,
    }


def generate(client_name: str, sns: str) -> dict:
    profile = load_content_profile(client_name)
    prompt, activity = build_video_prompt(profile, sns)
    raw = call_claude(prompt)
    return parse_video_output(raw, activity)


def main():
    parser = argparse.ArgumentParser(description="動画投稿テキスト生成（Claude CLI）")
    parser.add_argument("--client", required=True)
    parser.add_argument("--sns", required=True, choices=["tiktok", "youtube_shorts"])
    args = parser.parse_args()

    result = generate(args.client, args.sns)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
