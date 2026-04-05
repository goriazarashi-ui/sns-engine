#!/usr/bin/env python3
"""
AI画像アセット生成スキル（新規・既存スキルに非依存）
SDXL-Turbo を使ってローカルで高品質な画像を生成し、
clients/{client}/assets/images/{category}/ に保存する。

Usage:
  python3 generate_assets.py --client 天弥堂 --category 香り --count 5
  python3 generate_assets.py --client 天弥堂 --category 陶芸 --count 3 --prompt-extra "白磁, ミニマル"
"""

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from client_manager import get_client_dir

SDXL_MODEL = "stabilityai/sdxl-turbo"
PYTHON = Path(__file__).parent.parent / "flux-env/bin/python3"

# カテゴリ別のデフォルトプロンプト（人物なし）
CATEGORY_PROMPTS = {
    "香り": "Japanese incense sticks, aromatic herbs and dried flowers, soft candlelight, zen atmosphere, dark moody background, fine art still life photography, no people",
    "占い・手相": "mystical tarot cards, crystal ball, candles, dried herbs, dark wooden table, moody atmospheric lighting, spiritual objects still life, no people",
    "陶芸": "hand-built Japanese pottery, pinch pot ceramic bowls, irregular organic shapes, fingerprint textures on clay, earthy tones, wabi-sabi aesthetic, studio light, minimalist still life, no people",
    "Webデザイン・ブランディング": "Japanese minimal design objects, elegant stationery, clean desk composition, modern aesthetic, professional still life, no people",
    "心理学・交流分析": "open psychology journal, fountain pen, soft reading light, wooden desk, calm introspective atmosphere, minimal Japanese aesthetic, no people",
}

NEGATIVE_PROMPT = "person, people, human, face, body, hand, finger, portrait, selfie, ugly, blurry, low quality"


def generate(client_name: str, category: str, count: int, prompt_extra: str = ""):
    try:
        import torch
        from diffusers import AutoPipelineForText2Image
    except ImportError:
        print("ERROR: flux-env の diffusers が見つかりません")
        print(f"  {PYTHON} を使って実行してください")
        sys.exit(1)

    client_dir = get_client_dir(client_name)
    out_dir = client_dir / "assets/images" / category.replace("・", "_").replace("/", "_")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 既存ファイル数を確認
    existing = list(out_dir.glob("*.jpg")) + list(out_dir.glob("*.png"))
    start_idx = len(existing) + 1

    base_prompt = CATEGORY_PROMPTS.get(category, f"{category}, Japanese aesthetic, high quality photography")
    if prompt_extra:
        base_prompt = f"{base_prompt}, {prompt_extra}"

    print(f"📦 モデル読み込み中: {SDXL_MODEL}", file=sys.stderr)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    pipe = AutoPipelineForText2Image.from_pretrained(
        SDXL_MODEL,
        torch_dtype=torch.float32,
    )
    pipe = pipe.to(device)
    pipe.enable_attention_slicing()

    print(f"🎨 生成開始: {category} × {count}枚", file=sys.stderr)
    print(f"   プロンプト: {base_prompt}", file=sys.stderr)

    generated = []
    for i in range(count):
        idx = start_idx + i
        out_path = out_dir / f"{category[:3]}_{idx:02d}.jpg"

        print(f"   [{i+1}/{count}] 生成中...", file=sys.stderr)
        image = pipe(
            prompt=base_prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=4,   # SDXL-Turbo は4ステップで十分
            guidance_scale=0.0,      # Turbo は CFG不要
        ).images[0]

        image.save(str(out_path), quality=95)
        generated.append(str(out_path))
        print(f"   ✅ 保存: {out_path}", file=sys.stderr)

    print(f"\n✅ 完了: {len(generated)}枚を {out_dir} に保存しました", file=sys.stderr)
    return generated


def main():
    parser = argparse.ArgumentParser(description="SDXL-Turboでアセット画像をAI生成")
    parser.add_argument("--client", required=True, help="クライアント名")
    parser.add_argument("--category", required=True,
                        choices=list(CATEGORY_PROMPTS.keys()) + ["custom"],
                        help="カテゴリ（香り/占い・手相/陶芸/Webデザイン・ブランディング/custom）")
    parser.add_argument("--count", type=int, default=3, help="生成枚数（デフォルト: 3）")
    parser.add_argument("--prompt-extra", default="", help="プロンプトへの追加指示")
    args = parser.parse_args()

    generate(args.client, args.category, args.count, args.prompt_extra)


if __name__ == "__main__":
    main()
