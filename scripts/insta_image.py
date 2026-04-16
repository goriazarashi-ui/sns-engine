#!/usr/bin/env python3
"""
Instagram Image Text Overlay Generator
Usage: python3 insta_image.py [options]
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
except ImportError:
    print("ERROR: Pillow が必要です。pip3 install Pillow --break-system-packages で インストールしてください。")
    sys.exit(1)


# ===== フォント定義 =====
FONTS = {
    "hiragino-w3":  "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "hiragino-w4":  "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
    "hiragino-w5":  "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc",
    "hiragino-w6":  "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "hiragino-w7":  "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc",
    "hiragino-w8":  "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
    "hiragino-w9":  "/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc",
    "hiragino-maru": "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
    "hiragino-mincho": "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "helvetica":    "/System/Library/Fonts/Helvetica.ttc",
    "avenir":       "/System/Library/Fonts/Avenir.ttc",
}

# ===== Instagram サイズプリセット =====
SIZES = {
    "square":    (1080, 1080),   # 1:1
    "portrait":  (1080, 1350),   # 4:5
    "story":     (1080, 1920),   # 9:16 (Stories/Reels)
    "landscape": (1080, 566),    # 1.91:1
}

# ===== テキスト位置プリセット =====
POSITIONS = {
    "center":        ("center", "center"),
    "top":           ("center", "top"),
    "bottom":        ("center", "bottom"),
    "top-left":      ("left", "top"),
    "top-right":     ("right", "top"),
    "bottom-left":   ("left", "bottom"),
    "bottom-right":  ("right", "bottom"),
}


def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    """#RRGGBB または #RRGGBBAA をRGBAタプルに変換"""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r, g, b, alpha)
    elif len(h) == 8:
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
        return (r, g, b, a)
    raise ValueError(f"無効なカラーコード: {hex_color}")


def load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """フォントを読み込む"""
    font_path = FONTS.get(font_name, FONTS["hiragino-w5"])
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        # フォールバック
        try:
            return ImageFont.truetype(FONTS["hiragino-w4"], size)
        except Exception:
            return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """テキストを最大幅で自動折り返し"""
    lines = []
    # まず改行コードで分割
    paragraphs = text.replace("\\n", "\n").split("\n")
    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue
        words = list(paragraph)  # 日本語は文字単位
        current_line = ""
        for char in paragraph:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
    return lines


def draw_text_with_shadow(
    draw: ImageDraw.Draw,
    xy: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    shadow_color: tuple = None,
    shadow_offset: int = 3,
    stroke_width: int = 0,
    stroke_fill: tuple = None,
):
    """影付き・アウトライン付きテキストを描画"""
    x, y = xy
    if shadow_color:
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text, font=font, fill=shadow_color,
            stroke_width=stroke_width, stroke_fill=shadow_color
        )
    draw.text(
        (x, y), text, font=font, fill=fill,
        stroke_width=stroke_width, stroke_fill=stroke_fill
    )


def calculate_text_block_size(lines: list[str], font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw, line_spacing: float) -> tuple:
    """テキストブロック全体のサイズを計算"""
    max_w = 0
    total_h = 0
    line_height = None
    for line in lines:
        bbox = draw.textbbox((0, 0), line or " ", font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if line_height is None:
            line_height = h
        max_w = max(max_w, w)
        total_h += int(h * line_spacing)
    return max_w, total_h, line_height


def calculate_start_xy(
    canvas_w: int, canvas_h: int,
    block_w: int, block_h: int,
    h_align: str, v_align: str,
    margin: int
) -> tuple:
    """テキストブロックの開始座標を計算"""
    if h_align == "center":
        x = (canvas_w - block_w) // 2
    elif h_align == "left":
        x = margin
    else:  # right
        x = canvas_w - block_w - margin

    if v_align == "center":
        y = (canvas_h - block_h) // 2
    elif v_align == "top":
        y = margin
    else:  # bottom
        y = canvas_h - block_h - margin

    return x, y


def apply_background_overlay(
    canvas: Image.Image,
    x: int, y: int,
    block_w: int, block_h: int,
    bg_color: tuple,
    padding: int,
    radius: int = 16,
    blur: bool = False,
):
    """テキスト背景を描画（角丸対応）"""
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(canvas.width, x + block_w + padding)
    y2 = min(canvas.height, y + block_h + padding)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    if radius > 0:
        overlay_draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=bg_color)
    else:
        overlay_draw.rectangle([x1, y1, x2, y2], fill=bg_color)

    if blur:
        region = canvas.crop((x1, y1, x2, y2)).convert("RGBA")
        region = region.filter(ImageFilter.GaussianBlur(radius=10))
        canvas.paste(region, (x1, y1))

    canvas.alpha_composite(overlay)


def process_image(args) -> Image.Image:
    """メイン処理: 画像にテキストを合成"""

    # === 入力画像の読み込み ===
    if args.image:
        img = Image.open(args.image).convert("RGBA")
    else:
        # 画像なし → 背景色のみのキャンバス
        bg_color = hex_to_rgba(args.bg_fill, 255)
        size = SIZES.get(args.size, (1080, 1080))
        img = Image.new("RGBA", size, bg_color)

    # === リサイズ ===
    if args.size in SIZES:
        target_w, target_h = SIZES[args.size]
    elif args.width and args.height:
        target_w, target_h = args.width, args.height
    else:
        target_w, target_h = img.size

    # クロップ＆リサイズ
    if args.image:
        orig_w, orig_h = img.size
        fit = getattr(args, 'fit', 'cover')
        if fit == 'crop':
            # 縮尺を変えずにアスペクト比でクロップしてからリサイズ
            target_ratio = target_w / target_h
            orig_ratio = orig_w / orig_h
            if orig_ratio > target_ratio:
                # 横長 → 左右をクロップ
                crop_h = orig_h
                crop_w = int(orig_h * target_ratio)
            else:
                # 縦長 → 上下をクロップ
                crop_w = orig_w
                crop_h = int(orig_w / target_ratio)
            left = (orig_w - crop_w) // 2
            top = (orig_h - crop_h) // 2
            img = img.crop((left, top, left + crop_w, top + crop_h))
            img = img.resize((target_w, target_h), Image.LANCZOS)
        else:
            # cover: スケールして中央クロップ（デフォルト）
            scale = max(target_w / orig_w, target_h / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            img = img.crop((left, top, left + target_w, top + target_h))
    else:
        img = img.resize((target_w, target_h), Image.LANCZOS)

    canvas_w, canvas_h = img.size

    # === 全体オーバーレイ（画像を暗くするなど）===
    if args.overlay_opacity > 0:
        overlay_color = hex_to_rgba(args.overlay_color, int(args.overlay_opacity * 255))
        color_overlay = Image.new("RGBA", img.size, overlay_color)
        img.alpha_composite(color_overlay)

    # === テキスト描画 ===
    if args.text:
        draw = ImageDraw.Draw(img)

        font_size = args.font_size
        font = load_font(args.font, font_size)

        margin = args.margin
        max_text_width = canvas_w - margin * 2

        # テキスト折り返し
        lines = wrap_text(args.text, font, max_text_width, draw)

        line_spacing = args.line_spacing
        block_w, block_h, line_height = calculate_text_block_size(lines, font, draw, line_spacing)

        # 位置計算
        pos_key = args.position
        if pos_key in POSITIONS:
            h_align, v_align = POSITIONS[pos_key]
        else:
            h_align, v_align = "center", "center"

        # カスタム座標
        if args.x is not None and args.y is not None:
            start_x, start_y = args.x, args.y
        else:
            start_x, start_y = calculate_start_xy(
                canvas_w, canvas_h, block_w, block_h,
                h_align, v_align, margin
            )

        # テキスト背景
        if args.text_bg:
            bg_rgba = hex_to_rgba(args.text_bg_color, int(args.text_bg_opacity * 255))
            apply_background_overlay(
                img, start_x, start_y, block_w, block_h,
                bg_rgba, args.text_bg_padding, args.text_bg_radius, args.blur_bg
            )
            # alpha_composite後に再描画用のdrawを更新
            draw = ImageDraw.Draw(img)

        # テキスト色・影
        text_rgba = hex_to_rgba(args.color, int(args.opacity * 255))
        shadow_rgba = hex_to_rgba(args.shadow_color, int(args.shadow_opacity * 255)) if args.shadow else None
        stroke_rgba = hex_to_rgba(args.stroke_color, 255) if args.stroke_width > 0 else None

        # 各行を描画
        y = start_y
        for line in lines:
            if not line:
                y += int((line_height or 30) * line_spacing)
                continue

            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]

            # 横方向の揃え
            if h_align == "center":
                x = (canvas_w - line_w) // 2
            elif h_align == "right":
                x = canvas_w - line_w - margin
            else:
                x = start_x

            draw_text_with_shadow(
                draw, (x, y), line, font, text_rgba,
                shadow_color=shadow_rgba,
                shadow_offset=args.shadow_offset,
                stroke_width=args.stroke_width,
                stroke_fill=stroke_rgba,
            )

            h = bbox[3] - bbox[1]
            y += int(h * line_spacing)

    return img


def main():
    parser = argparse.ArgumentParser(
        description="Instagram投稿用 テキストオーバーレイ画像生成ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  # 基本的な使い方
  python3 insta_image.py -i photo.jpg -t "こんにちは" -o output.jpg

  # フォント・サイズ・色を指定
  python3 insta_image.py -i photo.jpg -t "今日も一日" --font hiragino-w7 --font-size 80 --color "#ffffff" -o output.jpg

  # ストーリーサイズ、下部にテキスト背景付き
  python3 insta_image.py -i photo.jpg -t "旅の記録" --size story --position bottom --text-bg --text-bg-color "#000000" --text-bg-opacity 0.6 -o output.jpg

  # 画像なし、背景色のみ
  python3 insta_image.py -t "シンプルな投稿" --bg-fill "#1a1a2e" --color "#e94560" --size square -o output.jpg

利用可能なフォント:
  hiragino-w3, hiragino-w4, hiragino-w5, hiragino-w6, hiragino-w7, hiragino-w8, hiragino-w9
  hiragino-maru, hiragino-mincho, helvetica, avenir

利用可能なサイズ:
  square (1080x1080), portrait (1080x1350), story (1080x1920), landscape (1080x566)

利用可能な位置:
  center, top, bottom, top-left, top-right, bottom-left, bottom-right
        """
    )

    # 入力・出力
    parser.add_argument("-i", "--image", help="入力画像ファイルパス")
    parser.add_argument("-o", "--output", default=None, help="出力ファイルパス (default: 自動管理フォルダ ~/.claude/outputs/images/日付/)")
    parser.add_argument("-t", "--text", help="オーバーレイするテキスト（改行は \\n）")

    # サイズ
    parser.add_argument("--size", default="square", choices=list(SIZES.keys()), help="Instagram サイズプリセット (default: square)")
    parser.add_argument("--fit", default="crop", choices=["cover", "crop"], help="画像フィット方法: cover=拡大して埋める / crop=縮尺変えず中央クロップ (default: crop)")
    parser.add_argument("--width", type=int, help="カスタム幅（px）")
    parser.add_argument("--height", type=int, help="カスタム高さ（px）")

    # フォント・テキスト
    parser.add_argument("--font", default="hiragino-w5", choices=list(FONTS.keys()), help="フォント名 (default: hiragino-w5)")
    parser.add_argument("--font-size", type=int, default=72, help="フォントサイズ (default: 72)")
    parser.add_argument("--color", default="#ffffff", help="テキスト色 HEXコード (default: #ffffff)")
    parser.add_argument("--opacity", type=float, default=1.0, help="テキスト不透明度 0.0〜1.0 (default: 1.0)")
    parser.add_argument("--line-spacing", type=float, default=1.5, help="行間倍率 (default: 1.5)")
    parser.add_argument("--margin", type=int, default=80, help="端からの余白px (default: 80)")

    # テキスト位置
    parser.add_argument("--position", default="center", help="テキスト位置 (default: center)")
    parser.add_argument("--x", type=int, help="テキストX座標（カスタム）")
    parser.add_argument("--y", type=int, help="テキストY座標（カスタム）")

    # テキスト背景
    parser.add_argument("--text-bg", action="store_true", help="テキスト背景を表示")
    parser.add_argument("--text-bg-color", default="#000000", help="テキスト背景色 (default: #000000)")
    parser.add_argument("--text-bg-opacity", type=float, default=0.5, help="テキスト背景不透明度 0.0〜1.0 (default: 0.5)")
    parser.add_argument("--text-bg-padding", type=int, default=20, help="テキスト背景パディングpx (default: 20)")
    parser.add_argument("--text-bg-radius", type=int, default=16, help="テキスト背景角丸px (default: 16)")
    parser.add_argument("--blur-bg", action="store_true", help="テキスト背景をぼかす（すりガラス効果）")

    # 影・アウトライン
    parser.add_argument("--shadow", action="store_true", help="文字影を表示")
    parser.add_argument("--shadow-color", default="#000000", help="影の色 (default: #000000)")
    parser.add_argument("--shadow-opacity", type=float, default=0.6, help="影の不透明度 (default: 0.6)")
    parser.add_argument("--shadow-offset", type=int, default=4, help="影のオフセットpx (default: 4)")
    parser.add_argument("--stroke-width", type=int, default=0, help="文字アウトラインpx (default: 0=なし)")
    parser.add_argument("--stroke-color", default="#000000", help="アウトライン色 (default: #000000)")

    # 全体オーバーレイ
    parser.add_argument("--overlay-color", default="#000000", help="全体オーバーレイ色 (default: #000000)")
    parser.add_argument("--overlay-opacity", type=float, default=0.0, help="全体オーバーレイ不透明度 0.0〜1.0 (default: 0.0=なし)")

    # 背景色（画像なしの場合）
    parser.add_argument("--bg-fill", default="#1a1a2e", help="背景色（画像なし時）(default: #1a1a2e)")

    # 品質
    parser.add_argument("--quality", type=int, default=95, help="JPEG品質 1〜100 (default: 95)")

    args = parser.parse_args()

    # 出力先の解決（未指定なら管理フォルダに自動保存）
    if args.output is None:
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        managed_dir = Path.home() / ".claude" / "outputs" / "images" / today
        managed_dir.mkdir(parents=True, exist_ok=True)
        existing = list(managed_dir.glob("*.jpg")) + list(managed_dir.glob("*.png"))
        seq = len(existing) + 1
        args.output = str(managed_dir / f"{seq:03d}_output.jpg")

    # 処理実行
    result = process_image(args)

    # 出力
    output_path = Path(args.output)
    if output_path.suffix.lower() in (".jpg", ".jpeg"):
        result = result.convert("RGB")
        result.save(str(output_path), "JPEG", quality=args.quality)
    elif output_path.suffix.lower() == ".png":
        result.save(str(output_path), "PNG")
    else:
        result = result.convert("RGB")
        result.save(str(output_path), "JPEG", quality=args.quality)

    print(f"✅ 保存完了: {output_path.resolve()}")
    print(f"   サイズ: {result.size[0]}x{result.size[1]} px")


if __name__ == "__main__":
    main()
