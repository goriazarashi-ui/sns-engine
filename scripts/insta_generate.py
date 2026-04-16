#!/usr/bin/env python3
"""
Instagram カルーセル画像生成スクリプト

使い方:
  # 対話モード
  python3 insta_generate.py --template okane-soudan

  # ファイルモード
  python3 insta_generate.py --template okane-soudan --content content.txt

content.txt の形式:
  [top]
  vol: 01
  subtitle: パート収入の壁
  main_copy: それ、税金\nかかるかも？

  [content]
  heading: 103万円の壁とは？
  body: 年収103万円を超えると\n所得税がかかります

  [content]
  ...（コンテンツページの数だけ繰り返し）

出力:
  ~/.claude/insta/outputs/YYYY-MM-DD/{template_id}/p1_top.jpg 〜 p8_cta.jpg
"""

import argparse
import json
import subprocess
import sys
import shutil
from datetime import date
from pathlib import Path

INSTA_DIR = Path.home() / ".claude" / "insta"
SCRIPTS_DIR = Path.home() / ".claude" / "scripts"
INSTA_IMAGE = SCRIPTS_DIR / "insta_image.py"


def load_config(template_id: str) -> dict:
    config_path = INSTA_DIR / "templates" / template_id / "config.json"
    if not config_path.exists():
        print(f"❌ テンプレートが見つかりません: {config_path}")
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_layout(template_dir: Path, layout_path: str) -> dict:
    full = template_dir / layout_path
    if not full.exists():
        print(f"❌ レイアウトJSONが見つかりません: {full}")
        sys.exit(1)
    return json.loads(full.read_text(encoding="utf-8"))


def parse_content_file(content_txt: Path) -> list[dict]:
    """
    content.txtを解析してページごとの辞書リストを返す。
    roleは [top] / [content] / [cta]
    """
    pages = []
    current = None
    for raw_line in content_txt.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            if current is not None:
                pages.append(current)
            role = line[1:-1].strip().lower()
            current = {"role": role}
        elif ":" in line and current is not None:
            key, _, val = line.partition(":")
            # 改行エスケープを実際の改行に変換
            current[key.strip()] = val.strip().replace("\\n", "\n")
    if current is not None:
        pages.append(current)
    return pages


def ask_interactive(role: str, page_num: int, layout: dict) -> dict:
    """対話モードでユーザーからテキストを入力してもらう"""
    print(f"\n── P{page_num} [{role}] ──")
    values = {}
    for zone in layout.get("zones", []):
        template = zone.get("text_template", "")
        # {placeholder} を抽出
        import re
        placeholders = re.findall(r"\{(\w+)\}", template)
        for ph in placeholders:
            if ph not in values:
                raw = input(f"  {zone['id']} / {ph}: ").strip()
                values[ph] = raw.replace("\\n", "\n")
    return values


def apply_zones(base_image: Path, layout: dict, values: dict, output: Path):
    """
    layout の zones を順番に insta_image.py でチェーンして画像を生成する。
    """
    current_input = str(base_image)
    tmp_dir = output.parent / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    zones = layout.get("zones", [])
    for i, zone in enumerate(zones):
        is_last = (i == len(zones) - 1)
        current_output = str(output) if is_last else str(tmp_dir / f"zone_{i}.jpg")

        # text_template に values を当てはめる
        text = zone.get("text_template", "")
        import re
        for ph, val in values.items():
            text = text.replace(f"{{{ph}}}", val)
        # 埋まらなかった placeholder はそのまま（警告のみ）
        remaining = re.findall(r"\{(\w+)\}", text)
        if remaining:
            print(f"  ⚠️  未設定のplaceholder: {remaining} in zone '{zone['id']}'")

        cmd = [
            sys.executable, str(INSTA_IMAGE),
            "-i", current_input,
            "--size", "portrait",
            "-t", text,
            "--x", "0",
            "--y", str(zone.get("y_top", 400)),
            "--font", zone.get("font", "hiragino-w6"),
            "--font-size", str(zone.get("size", 60)),
            "--color", zone.get("color", "#ffffff"),
            "--position", "top",
            "--line-spacing", str(zone.get("line_spacing", 1.4)),
            "-o", current_output,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ❌ zone '{zone['id']}' 生成エラー:")
            print(result.stderr)
            sys.exit(1)
        current_input = current_output

    # 一時ファイルを削除
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"  ✅ 生成: {output.name}")


def main():
    parser = argparse.ArgumentParser(description="Instagram カルーセル画像生成")
    parser.add_argument("--template", required=True, help="テンプレート名（例: okane-soudan）")
    parser.add_argument("--content", help="content.txtのパス（省略時は対話モード）")
    parser.add_argument("--output-dir", help="出力先ディレクトリ（省略時は ~/.claude/insta/outputs/日付/）")
    args = parser.parse_args()

    # テンプレート読み込み
    config = load_config(args.template)
    template_dir = INSTA_DIR / "templates" / args.template

    # 出力ディレクトリ
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = INSTA_DIR / "outputs" / date.today().isoformat() / args.template
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 テンプレート: {args.template}")
    print(f"📂 出力先: {out_dir}")

    # コンテンツ読み込み（ファイル or 対話）
    content_pages = []
    if args.content:
        content_txt = Path(args.content)
        if not content_txt.exists():
            print(f"❌ content.txt が見つかりません: {content_txt}")
            sys.exit(1)
        content_pages = parse_content_file(content_txt)
        print(f"📄 コンテンツ読み込み: {len(content_pages)} ページ分")
    # 対話モードは各ページ処理時に入力

    # 各ページを生成
    content_index = 0  # content_pages のカーソル
    for page_num, page_cfg in enumerate(config["pages"], start=1):
        role = page_cfg["role"]
        output_path = out_dir / f"p{page_num}_{role}.jpg"

        print(f"\n▶ P{page_num} [{role}]")

        if role == "cta":
            # CTAは固定画像をコピー
            cta_src = template_dir / page_cfg["fixed"]
            if not cta_src.exists():
                print(f"  ❌ CTA画像が見つかりません: {cta_src}")
                sys.exit(1)
            shutil.copy(cta_src, output_path)
            print(f"  ✅ コピー: {output_path.name}")
            continue

        # レイアウト読み込み
        layout = load_layout(template_dir, page_cfg["layout"])
        base_image = template_dir / page_cfg["base"]
        if not base_image.exists():
            print(f"  ❌ ベース画像が見つかりません: {base_image}")
            sys.exit(1)

        # コンテンツ取得
        if args.content:
            # ファイルモード: role が一致するページを順番に使う
            matched = [p for p in content_pages if p["role"] == role]
            if content_index >= len(matched) and role == "content":
                print(f"  ⚠️  content.txt にコンテンツページが足りません（P{page_num} をスキップ）")
                continue
            if role == "top":
                values = {k: v for k, v in matched[0].items() if k != "role"} if matched else {}
            else:
                values = {k: v for k, v in matched[content_index].items() if k != "role"}
                content_index += 1
        else:
            # 対話モード
            values = ask_interactive(role, page_num, layout)

        apply_zones(base_image, layout, values, output_path)

    print(f"\n🎉 全ページ生成完了: {out_dir}")
    print("生成ファイル:")
    for f in sorted(out_dir.glob("p*.jpg")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
