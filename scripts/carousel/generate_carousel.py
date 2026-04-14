#!/usr/bin/env python3
"""
教育コンテンツ → Instagramカルーセル画像生成スクリプト v2

HTML/CSS + Playwright screenshot + SDXL Turbo イラスト生成
APIキー不要。すべてローカルで完結。

Usage:
  python3 generate_carousel.py --id 53
  python3 generate_carousel.py --id 53 --no-illustrations
"""

import argparse
import asyncio
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
IECJUKU_DIR = Path.home() / ".claude" / "iecjuku"
CONTENTS_JSON = IECJUKU_DIR / "site" / "data" / "mo-contents.json"
CLAUDE_BIN = Path.home() / ".local" / "bin" / "claude"

# スライドごとの絵文字アイコン（イラスト未生成時のフォールバック）
FALLBACK_ICONS = ["💡", "🧠", "🎯", "📊", "🔑", "💬", "🌟", "📱", "🤝", "✨"]

# スライドごとのアイコン背景グラデーション
ICON_GRADIENTS = [
    ("E3F2FD", "BBDEFB"),  # ブルー
    ("FFF3E0", "FFE0B2"),  # オレンジ
    ("E8F5E9", "C8E6C9"),  # グリーン
    ("F3E5F5", "E1BEE7"),  # パープル
    ("FCE4EC", "F8BBD0"),  # ピンク
    ("E0F7FA", "B2EBF2"),  # シアン
    ("FFF8E1", "FFECB3"),  # イエロー
]


# ─── SDXL Turbo イラスト生成 ───

def generate_illustration(prompt: str, output_path: Path, width=512, height=512):
    """SDXL Turboでイラストを生成"""
    import torch
    from diffusers import AutoPipelineForText2Image

    # パイプラインをキャッシュ（関数属性に保持）
    if not hasattr(generate_illustration, "_pipe"):
        print("  🔧 SDXL Turbo をロード中...")
        pipe = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float16,
            variant="fp16",
        )
        pipe = pipe.to("mps")
        generate_illustration._pipe = pipe

    pipe = generate_illustration._pipe

    full_prompt = (
        "cute kawaii illustration, simple hand-drawn style, "
        "soft pastel colors, white background, minimal clean design, "
        f"{prompt}"
    )

    image = pipe(
        full_prompt,
        num_inference_steps=4,
        guidance_scale=0.0,
        width=width,
        height=height,
    ).images[0]

    image.save(output_path)
    return output_path


# ─── スライド構成生成 ───

def generate_slide_content(title: str, content: str) -> dict:
    """Claude CLIでスライド構成をJSON生成"""
    prompt = f"""以下の教育コンテンツをInstagramカルーセル投稿（7枚）のスライド構成に変換してください。

タイトル: {title}

本文:
{content[:3000]}

以下のJSON形式のみを出力（他のテキストは一切不要）:
{{
  "cover_title": "表紙の大見出し（8文字以内）",
  "cover_subtitle": "問いかけ形式（20文字以内）",
  "slides": [
    {{
      "header": "見出し（12文字以内）",
      "main_text": "吹き出しポイント（25文字以内）",
      "body_lines": ["補足1行目（18文字以内）", "補足2行目", "補足3行目"],
      "highlight_words": ["強調ワード1"],
      "illustration_prompt": "英語10語以内のイラスト説明"
    }}
  ],
  "cta_text": "CTAメッセージ（15文字以内）",
  "caption": "Instagramキャプション（ハッシュタグ3個含む。200字以内）"
}}"""

    result = subprocess.run(
        [str(CLAUDE_BIN), "-p", "--output-format", "text", prompt],
        capture_output=True, text=True, timeout=120,
    )
    text = result.stdout.strip().replace("```json", "").replace("```", "")
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("JSON解析失敗")
    json_str = text[start:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        return json.loads(json_str)


# ─── HTMLテンプレート ───

def _common_head():
    return """<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;700;900&family=Noto+Sans+JP:wght@300;400;700;900&display=swap" rel="stylesheet">"""


def cover_html(data: dict, ill_b64: str = None) -> str:
    title = data["cover_title"]
    subtitle = data["cover_subtitle"]

    # タイトルを適切な位置で改行
    if len(title) > 5:
        mid = len(title) // 2
        title_html = f"{title[:mid]}<br>{title[mid:]}"
    else:
        title_html = title

    ill_section = ""
    if ill_b64:
        ill_section = f"""
        <div class="illustration">
          <img src="data:image/png;base64,{ill_b64}" alt="">
        </div>"""
    else:
        ill_section = """
        <div class="deco-group">
          <div class="deco-item" style="background:linear-gradient(135deg,#FFE4B5,#FFD180)">💡</div>
          <div class="deco-item" style="background:linear-gradient(135deg,#B5EAD7,#8FD5A6)">🤝</div>
          <div class="deco-item" style="background:linear-gradient(135deg,#D4B5FF,#B794F6)">📱</div>
        </div>"""

    return f"""<!DOCTYPE html><html><head>{_common_head()}
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; font-family:'Noto Sans JP',sans-serif; background:#FFFAF6; position:relative; overflow:hidden; }}
.blob {{ position:absolute; border-radius:50%; filter:blur(8px); }}
.b1 {{ width:200px; height:200px; background:rgba(245,166,35,0.25); top:-60px; left:-60px; }}
.b2 {{ width:170px; height:170px; background:rgba(125,198,122,0.2); top:-40px; right:-50px; }}
.b3 {{ width:190px; height:190px; background:rgba(155,127,212,0.2); bottom:-50px; left:-40px; }}
.b4 {{ width:160px; height:160px; background:rgba(91,164,207,0.2); bottom:-40px; right:-50px; }}
.content {{ position:relative; z-index:1; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; padding:80px; }}
.subtitle {{ font-size:34px; color:#3D3D4D; margin-bottom:30px; letter-spacing:0.08em; }}
.title {{ font-family:'Zen Maru Gothic',sans-serif; font-size:110px; font-weight:900; color:#E84088; line-height:1.3; text-align:center; margin-bottom:20px; }}
.question {{ font-family:'Zen Maru Gothic',sans-serif; font-size:72px; font-weight:700; color:#2C3E50; }}
.illustration {{ margin-top:40px; }}
.illustration img {{ width:460px; height:460px; object-fit:cover; border-radius:40px; box-shadow:0 16px 48px rgba(0,0,0,0.1); }}
.deco-group {{ display:flex; gap:40px; margin-top:60px; }}
.deco-item {{ width:100px; height:100px; border-radius:24px; display:flex; align-items:center; justify-content:center; font-size:48px; box-shadow:0 8px 24px rgba(0,0,0,0.06); }}
.swipe {{ position:absolute; bottom:50px; right:60px; font-size:24px; color:#AAAABC; letter-spacing:0.1em; }}
</style></head><body>
<div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div>
<div class="content">
  <div class="subtitle">＼ {subtitle} ／</div>
  <div class="title">{title_html}</div>
  <div class="question">って？</div>
  {ill_section}
</div>
<div class="swipe">Swipe →</div>
</body></html>"""


def content_html(slide: dict, page: int, total: int, ill_b64: str = None, slide_idx: int = 0) -> str:
    header = slide.get("header", "")
    main_text = slide.get("main_text", "")
    body_lines = slide.get("body_lines", [])
    highlights = slide.get("highlight_words", [])
    icon = FALLBACK_ICONS[slide_idx % len(FALLBACK_ICONS)]
    g1, g2 = ICON_GRADIENTS[slide_idx % len(ICON_GRADIENTS)]

    # 吹き出しテキスト（改行対応）
    main_html = main_text.replace("\n", "<br>")

    # 本文（ハイライト付き）
    body_html = ""
    for line in body_lines:
        processed = line
        for hw in sorted(highlights, key=len, reverse=True):
            if hw in processed:
                processed = processed.replace(hw, f'<span class="hl">{hw}</span>', 1)
        body_html += f'<div class="body-line">{processed}</div>\n'

    # イラストまたはアイコン
    if ill_b64:
        visual = f'<div class="visual"><img src="data:image/png;base64,{ill_b64}" alt=""></div>'
    else:
        visual = f'<div class="icon-card" style="background:linear-gradient(135deg,#{g1},#{g2})">{icon}</div>'

    return f"""<!DOCTYPE html><html><head>{_common_head()}
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; font-family:'Noto Sans JP',sans-serif; background:#FAFBFD; overflow:hidden; display:flex; flex-direction:column; }}
.header {{ background:linear-gradient(135deg,#2C3E50,#34495E); padding:28px 60px; display:flex; justify-content:space-between; align-items:center; flex-shrink:0; }}
.header-title {{ font-size:30px; font-weight:700; color:white; letter-spacing:0.06em; }}
.header-page {{ font-size:22px; color:rgba(255,255,255,0.5); }}
.slide-body-wrap {{ flex:1; display:flex; flex-direction:column; justify-content:space-evenly; align-items:center; padding:30px 60px 180px; gap:20px; }}
.bubble {{ background:white; border:2px solid #E8ECF0; border-radius:24px; padding:28px 40px; font-family:'Zen Maru Gothic',sans-serif; font-size:34px; font-weight:700; color:#2C3E50; line-height:1.5; box-shadow:0 4px 20px rgba(0,0,0,0.04); position:relative; text-align:center; width:90%; }}
.bubble::after {{ content:''; position:absolute; bottom:-18px; left:50%; transform:translateX(-50%); border-left:16px solid transparent; border-right:16px solid transparent; border-top:18px solid white; filter:drop-shadow(0 2px 2px rgba(0,0,0,0.04)); }}
.visual img {{ width:560px; height:560px; object-fit:cover; border-radius:40px; box-shadow:0 20px 60px rgba(0,0,0,0.1); display:block; }}
.icon-card {{ width:360px; height:360px; border-radius:44px; display:flex; align-items:center; justify-content:center; font-size:140px; box-shadow:0 16px 48px rgba(0,0,0,0.08); }}
.body-area {{ display:flex; flex-direction:column; align-items:center; gap:12px; width:100%; }}
.body-line {{ font-size:30px; line-height:1.7; color:#4A4A5A; text-align:center; }}
.hl {{ color:#E84088; font-weight:700; position:relative; }}
.hl::after {{ content:''; position:absolute; bottom:-2px; left:0; width:100%; height:8px; background:rgba(232,64,136,0.1); border-radius:4px; }}
.footer {{ position:absolute; bottom:80px; right:60px; font-size:22px; color:#AAAABC; }}
</style></head><body>
<div class="header">
  <div class="header-title">{header}</div>
  <div class="header-page">{page}/{total}</div>
</div>
<div class="slide-body-wrap">
  <div class="bubble">{main_html}</div>
  {visual}
  <div class="body-area">{body_html}</div>
</div>
<div class="footer">Next: →</div>
</body></html>"""


def cta_html(data: dict) -> str:
    cta = data.get("cta_text", "学びを続けよう")
    return f"""<!DOCTYPE html><html><head>{_common_head()}
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; font-family:'Noto Sans JP',sans-serif; background:#FFFAF6; overflow:hidden; position:relative; }}
.blob {{ position:absolute; border-radius:50%; filter:blur(10px); }}
.b1 {{ width:220px; height:220px; background:rgba(232,64,136,0.15); top:-70px; left:-70px; }}
.b2 {{ width:180px; height:180px; background:rgba(245,166,35,0.18); top:-50px; right:-60px; }}
.b3 {{ width:200px; height:200px; background:rgba(125,198,122,0.15); bottom:-60px; left:-50px; }}
.b4 {{ width:170px; height:170px; background:rgba(91,164,207,0.18); bottom:-50px; right:-60px; }}
.content {{ position:relative; z-index:1; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:30px; padding:80px; }}
.cta-title {{ font-family:'Zen Maru Gothic',sans-serif; font-size:52px; font-weight:900; color:#2C3E50; text-align:center; line-height:1.5; }}
.account {{ font-size:28px; color:#8A8A9A; letter-spacing:0.06em; }}
.gold-line {{ width:80px; height:2px; background:linear-gradient(90deg,transparent,#C9A254,transparent); }}
.follow {{ font-size:30px; color:#5BA4CF; font-weight:500; }}
.like {{ margin-top:80px; font-family:'Zen Maru Gothic',sans-serif; font-size:36px; font-weight:700; color:#E84088; }}
.save {{ font-size:26px; color:#C9A254; }}
</style></head><body>
<div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div>
<div class="content">
  <div class="cta-title">{cta}</div>
  <div class="account">天弥堂 ｜ IEC塾 教育コンテンツ</div>
  <div class="gold-line"></div>
  <div class="follow">Follow で学びを受け取る</div>
  <div class="like">❤️ いいね・コメント歓迎！</div>
  <div class="save">🔖 後から見返す</div>
</div>
</body></html>"""


# ─── レンダリング ───

async def render_html_to_png(html: str, output_path: Path):
    """HTML → PNG（Playwright）"""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1350})
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_timeout(1500)  # Webフォント読み込み待ち
        await page.screenshot(path=str(output_path), type="png")
        await page.close()
        await browser.close()


async def render_all(html_list: list[tuple[str, Path]]):
    """複数HTMLを一括レンダリング（ブラウザ共有で高速化）"""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for html, path in html_list:
            page = await browser.new_page(viewport={"width": 1080, "height": 1350})
            await page.set_content(html, wait_until="networkidle")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(path), type="png")
            await page.close()
            print(f"  ✅ {path.name}")
        await browser.close()


def img_to_b64(path: Path) -> str:
    """画像をbase64文字列に変換"""
    return base64.b64encode(path.read_bytes()).decode()


# ─── メイン ───

def main():
    parser = argparse.ArgumentParser(description="教育コンテンツ → Instagramカルーセル v2")
    parser.add_argument("--id", type=int, required=True, help="教育コンテンツID")
    parser.add_argument("--no-illustrations", action="store_true", help="イラスト生成スキップ")
    args = parser.parse_args()

    # コンテンツ読み込み
    with open(CONTENTS_JSON) as f:
        contents = json.load(f)
    item = next((c for c in contents if c["id"] == args.id), None)
    if not item:
        print(f"❌ ID {args.id} が見つかりません")
        sys.exit(1)

    print(f"📄 コンテンツ: {item['title']}")

    out_dir = OUTPUT_DIR / f"carousel_{args.id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ill_dir = out_dir / "illustrations"
    ill_dir.mkdir(exist_ok=True)

    # 1. スライド構成生成
    print("🧠 スライド構成を生成中...")
    data = generate_slide_content(item["title"], item["content"])
    with open(out_dir / "slide_data.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    slides = data["slides"]
    total = len(slides) + 2
    print(f"  ✅ {len(slides)}枚の記事スライド（計{total}枚）")

    # 2. イラスト生成
    illustrations = {}
    if not args.no_illustrations:
        print("🎨 イラスト生成中（SDXL Turbo）...")
        # 表紙用
        cover_prompt = slides[0].get("illustration_prompt", "people learning together")
        p = ill_dir / "cover.png"
        generate_illustration(cover_prompt, p)
        illustrations["cover"] = img_to_b64(p)
        print(f"  ✅ 表紙イラスト（{cover_prompt}）")

        # 各スライド用
        for i, s in enumerate(slides):
            prompt = s.get("illustration_prompt", "person thinking")
            p = ill_dir / f"slide_{i}.png"
            generate_illustration(prompt, p)
            illustrations[f"slide_{i}"] = img_to_b64(p)
            print(f"  ✅ スライド{i+2}イラスト（{prompt}）")
    else:
        print("⏭️ イラスト生成スキップ")

    # 3. HTML生成 → PNG レンダリング
    print("🖼️ スライド画像を生成中...")
    render_jobs = []

    # 表紙
    html = cover_html(data, illustrations.get("cover"))
    p = out_dir / "slide_01_cover.png"
    render_jobs.append((html, p))

    # 記事スライド
    for i, s in enumerate(slides):
        html = content_html(s, i + 2, total, illustrations.get(f"slide_{i}"), i)
        p = out_dir / f"slide_{i+2:02d}.png"
        render_jobs.append((html, p))

    # CTA
    html = cta_html(data)
    p = out_dir / f"slide_{total:02d}_cta.png"
    render_jobs.append((html, p))

    asyncio.run(render_all(render_jobs))

    # キャプション保存
    caption = data.get("caption", "")
    (out_dir / "caption.txt").write_text(caption)

    print(f"\n✅ カルーセル生成完了！")
    print(f"   出力: {out_dir}")
    print(f"   スライド: {total}枚")
    print(f"   イラスト: {'あり' if not args.no_illustrations else 'なし'}")
    print(f"   キャプション: caption.txt")

    return str(out_dir)


if __name__ == "__main__":
    main()
