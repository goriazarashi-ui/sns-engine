#!/usr/bin/env python3
"""
SNS投稿スクリプトのリトライラッパー
失敗時に最大N回リトライする。全試行失敗時はログに記録。

Usage:
  python3 run_with_retry.py --retries 3 --delay 60 -- python3 post_x.py --client 天弥堂 --generate
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


LOG_DIR = Path.home() / ".claude/outputs"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_with_retry(cmd: list, retries: int, delay: int) -> bool:
    for attempt in range(1, retries + 1):
        log(f"▶ 試行 {attempt}/{retries}: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, text=True)
            if result.returncode == 0:
                log(f"✅ 成功 (試行 {attempt})")
                return True
            log(f"❌ 失敗 (exit={result.returncode})")
        except Exception as e:
            log(f"❌ 例外発生: {e}")
        if attempt < retries:
            log(f"⏳ {delay}秒後にリトライ...")
            time.sleep(delay)

    log(f"🚨 全{retries}回失敗: {' '.join(cmd)}")
    return False


def main():
    parser = argparse.ArgumentParser(description="SNS投稿リトライラッパー")
    parser.add_argument("--retries", type=int, default=3, help="最大リトライ回数 (default: 3)")
    parser.add_argument("--delay", type=int, default=60, help="リトライ間隔秒数 (default: 60)")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="実行するコマンド（-- の後に指定）")
    args = parser.parse_args()

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        print("ERROR: 実行コマンドを指定してください")
        sys.exit(1)

    success = run_with_retry(cmd, args.retries, args.delay)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
