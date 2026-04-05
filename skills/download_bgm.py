#!/usr/bin/env python3
"""
著作権フリーBGM自動ダウンロードスクリプト
Internet Archive (archive.org) のCC0 Public Domain 音楽を自動取得する。
ダウンロードごとに異なる曲が当たるようランダム選択。

Usage:
  python3 download_bgm.py --client 天弥堂
  python3 download_bgm.py --client 天弥堂 --keyword "zen piano"
"""

import argparse
import random
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from client_manager import get_client_dir

try:
    import requests
except ImportError:
    print("requestsをインストール中...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "requests", "--break-system-packages"],
        check=True,
    )
    import requests

DURATION = 180  # 秒

# 検索クエリ（天弥堂ブランドに合うもの順）
DEFAULT_QUERIES = [
    "healing meditation ambient",
    "zen relaxation instrumental",
    "peaceful nature meditation",
    "spiritual ambient music",
    "lofi healing ambient",
]


def search_archive(query: str) -> list:
    """Internet Archive で CC0/Public Domain 音楽を検索"""
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": f"({query}) AND mediatype:audio AND licenseurl:(*publicdomain* OR *cc0*)",
        "fl[]": ["identifier", "title"],
        "rows": 30,
        "output": "json",
        "sort[]": "downloads desc",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json().get("response", {}).get("docs", [])
    except Exception as e:
        print(f"  検索エラー: {e}")
        return []


def get_mp3_url(identifier: str) -> tuple | None:
    """アイテムから適切なMP3を選ぶ（5KB〜50MB）"""
    url = f"https://archive.org/metadata/{identifier}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        files = r.json().get("files", [])
        mp3s = [f for f in files if f.get("name", "").lower().endswith(".mp3")]
        if not mp3s:
            return None
        # サイズフィルタ（小さすぎ・大きすぎを除外）
        candidates = [f for f in mp3s if 500_000 < int(f.get("size", 0)) < 60_000_000]
        if not candidates:
            candidates = mp3s
        f = random.choice(candidates)
        return identifier, f["name"]
    except Exception:
        return None


def download_file(identifier: str, filename: str, tmp_path: Path) -> bool:
    url = f"https://archive.org/download/{identifier}/{filename}"
    try:
        print(f"  ⬇️  {filename[:60]}")
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=16384):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  ダウンロード失敗: {e}")
        return False


def trim_and_fade(src: Path, dst: Path, duration: int = DURATION) -> bool:
    """ffmpegで指定秒数にトリム + フェードイン/アウト"""
    fade_out_start = duration - 5
    cmd = [
        "ffmpeg", "-nostdin",
        "-i", str(src),
        "-t", str(duration),
        "-af", f"afade=t=in:d=5,afade=t=out:st={fade_out_start}:d=5,volume=0.75",
        "-c:a", "libmp3lame", "-q:a", "2",
        "-y", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="著作権フリーBGM自動ダウンロード")
    parser.add_argument("--client", required=True)
    parser.add_argument("--keyword", help="検索キーワード（省略時は自動）")
    args = parser.parse_args()

    client_dir = get_client_dir(args.client)
    bgm_dir = client_dir / "assets" / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    out_path = bgm_dir / "meditation.mp3"
    tmp_path = bgm_dir / "_tmp_download.mp3"

    queries = [args.keyword] if args.keyword else DEFAULT_QUERIES
    random.shuffle(queries)  # 毎回違うクエリから試す

    for query in queries:
        print(f"\n🔍 検索中: 「{query}」")
        docs = search_archive(query)
        if not docs:
            print("  結果なし。次のクエリへ...")
            continue

        random.shuffle(docs)

        for doc in docs[:8]:
            identifier = doc["identifier"]
            title = doc.get("title", identifier)
            print(f"  候補: {title[:50]}")

            result = get_mp3_url(identifier)
            if not result:
                continue

            id_, fname = result
            if not download_file(id_, fname, tmp_path):
                continue

            print("  ✂️  180秒にトリム + フェード処理中...")
            if trim_and_fade(tmp_path, out_path):
                tmp_path.unlink(missing_ok=True)
                print(f"\n✅ BGM更新完了")
                print(f"   タイトル : {title}")
                print(f"   ライセンス: CC0 Public Domain（著作権フリー）")
                print(f"   保存先   : {out_path}")
                print(f"\n確認するには: afplay {out_path}")
                return

            tmp_path.unlink(missing_ok=True)

    print("\n❌ ダウンロードに失敗しました。時間をおいて再試行してください。")
    sys.exit(1)


if __name__ == "__main__":
    main()
