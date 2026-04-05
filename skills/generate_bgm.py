#!/usr/bin/env python3
"""
著作権フリーBGM生成スクリプト
ffmpegを使ってヒーリング系アンビエント音楽をローカル生成する。
完全著作権フリー（自前生成）。

Usage:
  python3 generate_bgm.py --client 天弥堂
  python3 generate_bgm.py --client 天弥堂 --preset meditation
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from client_manager import get_client_dir

# プリセット定義（ブランドのトーンに合わせて選択）
PRESETS = {
    "meditation": {
        "description": "瞑想・ヒーリング系（432Hz倍音、エコーあり）",
        "base_freq": 432,
        "harmonics": [1.0, 1.5, 2.0, 2.5],
        "volumes":   [0.5, 0.25, 0.15, 0.10],
        "echo": "0.6:0.4:40:0.3",
        "duration": 180,
    },
    "nature": {
        "description": "自然・落ち着き系（ブラウンノイズ+低音倍音）",
        "base_freq": 396,
        "harmonics": [1.0, 1.5, 2.0],
        "volumes":   [0.4, 0.2, 0.1],
        "echo": "0.5:0.3:60:0.2",
        "duration": 180,
    },
    "zen": {
        "description": "禅・陶芸系（528Hz倍音、残響長め）",
        "base_freq": 528,
        "harmonics": [1.0, 2.0, 3.0],
        "volumes":   [0.45, 0.20, 0.10],
        "echo": "0.7:0.5:80:0.4",
        "duration": 180,
    },
}


def generate_bgm(output_path: Path, preset: str = "meditation") -> Path:
    cfg = PRESETS[preset]
    base = cfg["base_freq"]
    duration = cfg["duration"]
    fade_out_start = duration - 5

    # 各倍音のsineソースを生成
    inputs = []
    filter_parts = []
    for i, (mult, vol) in enumerate(zip(cfg["harmonics"], cfg["volumes"])):
        freq = base * mult
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={freq:.1f}:duration={duration}"]
        filter_parts.append(f"[{i}]volume={vol}[a{i}]")

    # ミックス
    mix_inputs = "".join(f"[a{i}]" for i in range(len(cfg["harmonics"])))
    n = len(cfg["harmonics"])
    filter_parts.append(
        f"{mix_inputs}amix=inputs={n}:duration=longest,"
        f"afade=t=in:d=5,"
        f"afade=t=out:st={fade_out_start}:d=5,"
        f"aecho={cfg['echo']}"
    )

    filter_complex = ";".join(filter_parts)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = inputs + [
        "-filter_complex", filter_complex,
        "-c:a", "libmp3lame", "-q:a", "2",
        "-y", str(output_path),
    ]
    cmd = ["ffmpeg"] + cmd

    print(f"🎵 BGM生成中... (preset={preset}, {base}Hz, {duration}秒)")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ BGM生成失敗:\n{result.stderr}")
        sys.exit(1)
    print(f"✅ BGM生成完了: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="著作権フリーBGM生成")
    parser.add_argument("--client", required=True)
    parser.add_argument("--preset", default="meditation", choices=list(PRESETS.keys()),
                        help="BGMのプリセット（デフォルト: meditation）")
    parser.add_argument("--output", help="出力パス（省略時はclients/<client>/assets/bgm/に保存）")
    args = parser.parse_args()

    if args.output:
        out_path = Path(args.output)
    else:
        client_dir = get_client_dir(args.client)
        bgm_dir = client_dir / "assets" / "bgm"
        out_path = bgm_dir / f"{args.preset}.mp3"

    generate_bgm(out_path, args.preset)

    # sns_config.jsonのbgmパスを相対パスで表示
    client_dir = get_client_dir(args.client)
    try:
        rel = out_path.relative_to(client_dir)
        print(f'\nsns_config.jsonに設定するパス: "assets/bgm/{out_path.name}"')
    except ValueError:
        pass


if __name__ == "__main__":
    main()
