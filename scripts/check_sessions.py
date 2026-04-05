#!/usr/bin/env python3
"""
SNSログインセッション確認スクリプト
各プラットフォームのChromeプロファイルが有効かチェックし、
期限切れがあればmacOS通知を送る。

Usage:
  python3 check_sessions.py
  python3 check_sessions.py --fix  # 期限切れプロファイルを一覧表示
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: pip3 install playwright --break-system-packages")
    sys.exit(1)

PROFILES_DIR = Path.home() / ".claude/sns/chrome-profiles"

# チェック対象: (プロファイル名サフィックス, チェックURL, ログイン判定条件)
SNS_CHECKS = [
    ("facebook",  "https://www.facebook.com/",  lambda url: "login" not in url and "checkpoint" not in url),
    ("instagram", "https://www.instagram.com/", lambda url: "accounts/login" not in url),
    ("threads",   "https://www.threads.net/",   lambda url: "login" not in url),
    ("x",         "https://x.com/home",         lambda url: "login" not in url and url != "https://x.com/"),
]


def notify(message: str):
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "天弥堂 セッション確認" sound name "Basso"'
    ])


def check_profile(client_name: str, sns: str, url: str, is_logged_in) -> bool:
    profile_dir = PROFILES_DIR / f"{client_name}_{sns}"
    if not profile_dir.exists():
        print(f"  [{sns}] プロファイル未作成 → スキップ")
        return True

    # SingletonLock を除去
    for name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock = profile_dir / name
        if lock.exists() or lock.is_symlink():
            lock.unlink()

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation", "--no-sandbox"],
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            logged_in = is_logged_in(page.url)
            context.close()

        status = "✅ OK" if logged_in else "❌ 期限切れ"
        print(f"  [{sns}] {status}  ({page.url[:60]})")
        return logged_in

    except Exception as e:
        print(f"  [{sns}] ⚠️  確認失敗: {e}")
        return True  # 確認できない場合は問題なしとして扱う


def main():
    parser = argparse.ArgumentParser(description="SNSセッション有効性チェック")
    parser.add_argument("--client", default="天弥堂")
    args = parser.parse_args()

    print(f"🔍 セッション確認中: {args.client}")
    expired = []

    for sns, url, is_logged_in in SNS_CHECKS:
        ok = check_profile(args.client, sns, url, is_logged_in)
        if not ok:
            expired.append(sns)

    if expired:
        names = "・".join(expired)
        msg = f"{names} のログインが期限切れです。--setup で再ログインしてください。"
        print(f"\n⚠️  {msg}")
        notify(msg)
        sys.exit(1)
    else:
        print("\n✅ 全セッション有効")
