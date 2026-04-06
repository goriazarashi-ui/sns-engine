#!/usr/bin/env python3
"""
SNS投稿状況レポートをGitHub Gistに投稿するスクリプト。
cronで定期実行してスマホから確認できるようにする。

Usage:
  python3 report.py --client 天弥堂
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

_SNS_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = _SNS_ROOT / "outputs"
GIST_ID_FILE = LOG_DIR / "gist_id.txt"


def parse_log(log_path: Path, lines: int = 80) -> list[dict]:
    """ログファイルを解析して投稿結果リストを返す"""
    if not log_path.exists():
        return []
    content = log_path.read_text(encoding="utf-8", errors="ignore")
    tail = "\n".join(content.splitlines()[-lines:])

    results = []
    current = {}
    for line in tail.splitlines():
        m = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
        if m:
            ts = m.group(1)
            if "▶ 試行" in line:
                attempt_m = re.search(r'試行 (\d+)/(\d+)', line)
                if attempt_m:
                    current = {"ts": ts, "attempt": int(attempt_m.group(1)), "total": int(attempt_m.group(2))}
            elif "✅ 成功" in line:
                current["status"] = "success"
                current["ts"] = ts
                results.append(dict(current))
                current = {}
            elif "🚨 全" in line:
                current["status"] = "failed"
                current["ts"] = ts
                results.append(dict(current))
                current = {}
    return results


def get_last_result(log_path: Path) -> dict:
    """最新の実行結果を返す"""
    results = parse_log(log_path)
    if not results:
        # ログはあるが試行形式でない（旧形式）場合
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8", errors="ignore")
            tail = content.splitlines()[-30:]
            for line in reversed(tail):
                if "✅ 投稿完了" in line or "✅ 完了" in line:
                    return {"status": "success", "ts": "", "attempt": 1}
                if "❌" in line or "ERROR" in line:
                    return {"status": "failed", "ts": "", "attempt": 1}
        return {"status": "unknown", "ts": "", "attempt": 1}
    return results[-1]


def status_emoji(result: dict) -> str:
    s = result.get("status", "unknown")
    if s == "success":
        attempt = result.get("attempt", 1)
        return "✅" if attempt == 1 else f"⚠️ ({attempt}回目で成功)"
    elif s == "failed":
        return "❌ 全試行失敗"
    return "？ 未実行"


def build_report(client_name: str) -> str:
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    sns_list = [
        ("X",                  "cron_x.log"),
        ("Instagram (フィード)", "cron_instagram.log"),
        ("Instagram (リール)",    "cron_instagram_reel.log"),
        ("Threads",            "cron_threads.log"),
        ("TikTok",             "cron_tiktok.log"),
        ("YouTube Shorts",     "cron_youtube.log"),
    ]

    # 直近の日次生成
    daily_log = LOG_DIR / "cron_daily.log"
    daily_result = get_last_result(daily_log)

    lines = []
    lines.append(f"# 📊 SNS投稿レポート — {client_name}")
    lines.append(f"更新: {now}\n")

    lines.append("## 日次コンテンツ生成")
    lines.append(f"| 項目 | 状態 |")
    lines.append(f"|------|------|")
    lines.append(f"| generate_daily | {status_emoji(daily_result)} |")
    lines.append("")

    # キャッシュ内容確認
    for slot in ["morning", "evening"]:
        cache_path = LOG_DIR / f"daily_cache_{client_name}_{slot}.json"
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                if data.get("date") == today:
                    slot_ja = "朝" if slot == "morning" else "夜"
                    lines.append(f"### {slot_ja}のコンテンツ（{data['date']}）")
                    lines.append(f"- **Activity**: {data['activity']}")
                    lines.append(f"- **X**: {data['x_text'][:60]}...")
                    lines.append(f"- **Instagram**: {data['instagram_caption'][:60]}...")
                    lines.append("")
            except Exception:
                pass

    lines.append("## 各SNS投稿状況")
    lines.append("| SNS | 状態 | 最終実行 |")
    lines.append("|-----|------|---------|")
    for sns_name, log_file in sns_list:
        result = get_last_result(LOG_DIR / log_file)
        ts = result.get("ts", "—")
        lines.append(f"| {sns_name} | {status_emoji(result)} | {ts} |")

    lines.append("")
    lines.append("---")
    lines.append(f"*自動生成 by Claude Code — {now}*")

    return "\n".join(lines)


def get_or_create_gist(token: str, content: str) -> str:
    """GistIDがあれば更新、なければ新規作成。GistのURLを返す。"""
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "User-Agent": "sns-report-bot",
    }

    filename = "sns_report.md"

    if GIST_ID_FILE.exists():
        gist_id = GIST_ID_FILE.read_text().strip()
        # 更新
        payload = json.dumps({
            "files": {filename: {"content": content}}
        }).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.github.com/gists/{gist_id}",
            data=payload, headers=headers, method="PATCH"
        )
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read())
                return data["html_url"]
        except urllib.error.HTTPError:
            GIST_ID_FILE.unlink(missing_ok=True)

    # 新規作成
    payload = json.dumps({
        "description": "SNS投稿レポート — 天弥堂",
        "public": False,
        "files": {filename: {"content": content}}
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/gists",
        data=payload, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read())
        gist_id = data["id"]
        GIST_ID_FILE.write_text(gist_id)
        return data["html_url"]


def main():
    parser = argparse.ArgumentParser(description="SNS投稿レポートをGistに投稿")
    parser.add_argument("--client", default="天弥堂")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_GIST_TOKEN")
    if not token:
        print("ERROR: GITHUB_GIST_TOKEN が設定されていません")
        sys.exit(1)

    content = build_report(args.client)
    url = get_or_create_gist(token, content)
    print(f"✅ レポート更新: {url}")


if __name__ == "__main__":
    main()
