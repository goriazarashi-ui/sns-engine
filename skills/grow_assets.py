#!/usr/bin/env python3
"""
アセット画像自動拡充スキル（新規・既存スキルに非依存）
前日の投稿テキストを元にClaude が画像生成プロンプトを作成し、
SDXL-Turbo でカテゴリごとに1枚ずつ生成・蓄積する。

Usage:
  ~/.claude/sns/flux-env/bin/python3 grow_assets.py --client 天弥堂
"""

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from client_manager import get_client_dir

CACHE_DIR = Path.home() / ".claude/outputs"
CLAUDE_BIN = Path.home() / ".local/bin/claude"

# カテゴリごとのフォールバックプロンプト（キャッシュがない日用）
FALLBACK_PROMPTS = {
    "香り": "Japanese incense sticks, aromatic dried flowers, soft candlelight, zen atmosphere, dark moody background, fine art still life photography, no people",
    "占い・手相": "mystical tarot cards, crystal ball, candles, dried herbs, dark wooden table, moody atmospheric lighting, spiritual objects still life, no people",
    "陶芸": "hand-built Japanese pottery, pinch pot ceramic bowls, irregular organic shapes, fingerprint textures on clay, earthy tones, wabi-sabi aesthetic, studio light, minimalist still life, no people",
    "Webデザイン・ブランディング": "Japanese minimal design objects, elegant stationery, clean desk composition, modern aesthetic, professional still life, no people",
    "心理学・交流分析": "open psychology journal, fountain pen, soft reading light, wooden desk, calm introspective atmosphere, minimal Japanese aesthetic, no people",
}

NEGATIVE_PROMPT = "person, people, human, face, body, hand, finger, portrait, selfie, ugly, blurry, low quality"


def load_recent_cache(client_name: str) -> dict | None:
    """昨日または今日のキャッシュを読む（夕→朝の順で優先）"""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    for slot in ["evening", "morning"]:
        for target_date in [yesterday, today]:
            cp = CACHE_DIR / f"daily_cache_{client_name}_{slot}.json"
            if not cp.exists():
                continue
            data = json.loads(cp.read_text(encoding="utf-8"))
            if data.get("date") == target_date:
                print(f"📦 キャッシュ使用: {slot} ({target_date})", file=sys.stderr)
                return data
    return None


def build_image_prompt(image_text: str, activity: str) -> str:
    """Claude CLI を使って日本語テキストを英語画像生成プロンプトに変換する"""
    prompt = f"""以下の日本語テキストと活動テーマを元に、Stable Diffusion 用の英語画像生成プロンプトを1行で作成してください。
条件:
- 人物・顔・手は含めない（no people）
- スティルライフ・情景・オブジェクト中心
- 天弥堂（香り・占い・陶芸のサロン）の世界観
- 30ワード以内の英語

活動テーマ: {activity}
テキスト: {image_text}

プロンプトのみ出力してください。説明不要。"""

    result = subprocess.run(
        [str(CLAUDE_BIN), "-p", prompt],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def generate_one_image(prompt: str, out_path: Path, device: str, pipe) -> bool:
    """SDXL-Turbo で1枚生成して保存する"""
    import torch
    image = pipe(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=4,
        guidance_scale=0.0,
    ).images[0]
    image.save(str(out_path), quality=95)
    return True


def get_categories(client_name: str) -> list[str]:
    """sns_config.json からカテゴリ一覧を取得する"""
    config_path = get_client_dir(client_name) / "sns_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return list(config.get("assets", {}).get("images", {}).keys())


def main():
    parser = argparse.ArgumentParser(description="アセット画像を毎晩1枚ずつ自動拡充")
    parser.add_argument("--client", required=True)
    args = parser.parse_args()

    try:
        import torch
        from diffusers import AutoPipelineForText2Image
    except ImportError:
        print("ERROR: flux-env の diffusers が見つかりません。flux-env の python で実行してください。")
        sys.exit(1)

    client_dir = get_client_dir(args.client)
    categories = get_categories(args.client)

    # キャッシュから昨日のテキストを取得
    cache = load_recent_cache(args.client)
    image_text = cache.get("image_text", "") if cache else ""
    activity = cache.get("activity", "") if cache else ""

    # Claude でプロンプト生成
    ai_prompt = None
    if image_text:
        print(f"🤖 Claudeがプロンプト生成中（ベース: {activity}）...", file=sys.stderr)
        ai_prompt = build_image_prompt(image_text, activity)
        if ai_prompt:
            print(f"   → {ai_prompt}", file=sys.stderr)

    # モデル読み込み（1回だけ）
    print("📦 SDXL-Turbo 読み込み中...", file=sys.stderr)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    pipe = AutoPipelineForText2Image.from_pretrained(
        "stabilityai/sdxl-turbo",
        torch_dtype=torch.float32,
    )
    pipe = pipe.to(device)
    pipe.enable_attention_slicing()

    # カテゴリごとに1枚生成
    for category in categories:
        out_dir = client_dir / "assets/images" / category
        out_dir.mkdir(parents=True, exist_ok=True)

        existing = list(out_dir.glob("*.jpg")) + list(out_dir.glob("*.png"))
        next_idx = len(existing) + 1
        out_path = out_dir / f"ai_{date.today().isoformat()}_{next_idx:03d}.jpg"

        # activityが一致するカテゴリはAIプロンプト、それ以外はフォールバック
        if ai_prompt and activity == category:
            prompt = ai_prompt
        else:
            prompt = FALLBACK_PROMPTS.get(category, f"{category}, Japanese aesthetic, still life, no people")

        print(f"🎨 [{category}] 生成中...", file=sys.stderr)
        generate_one_image(prompt, out_path, device, pipe)
        print(f"   ✅ 保存: {out_path}", file=sys.stderr)

    print(f"\n✅ 完了: {len(categories)}枚を各フォルダに追加しました", file=sys.stderr)


if __name__ == "__main__":
    main()
