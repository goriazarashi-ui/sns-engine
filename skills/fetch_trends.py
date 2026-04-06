#!/usr/bin/env python3
"""
トレンド取得スキル（新規・既存スキルに非依存）
複数のRSSフィードを巡回し、過去7日分の記事からキーワードを抽出する。
結果は ~/.claude/outputs/trends_cache.json に保存される。

Usage:
  python3 fetch_trends.py
  python3 fetch_trends.py --days 7 --verbose
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import feedparser
    import requests
except ImportError:
    print("ERROR: pip3 install feedparser requests --break-system-packages")
    sys.exit(1)

_SNS_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = _SNS_ROOT / "outputs/trends_cache.json"
CLAUDE_BIN = Path.home() / ".local/bin/claude"

# 対象RSSフィード
RSS_FEEDS = {
    "ライフスタイル": [
        ("NHK 生活・文化", "https://www3.nhk.or.jp/rss/news/cat3.xml"),
        ("Yahoo Japan ライフ", "https://news.yahoo.co.jp/rss/topics/life.xml"),
    ],
    "ウェルネス・美容": [
        ("VOGUE Japan", "https://www.vogue.co.jp/feed/rss"),
        ("ELLE Japan", "https://www.elle.com/jp/rss/all.xml"),
    ],
    "SNS・マーケティング": [
        ("MarkeZine", "https://markezine.jp/rss/index.rss"),
        ("ITmedia マーケティング", "https://marketing.itmedia.co.jp/mm/rss/2.0/bursts.xml"),
    ],
}


def fetch_feed(name: str, url: str, days: int, verbose: bool) -> list[dict]:
    """RSSフィードを取得し、指定日数以内の記事を返す"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    articles = []

    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            # 日付取得
            published = None
            for field in ["published_parsed", "updated_parsed"]:
                t = getattr(entry, field, None)
                if t:
                    published = datetime(*t[:6], tzinfo=timezone.utc)
                    break

            if published and published < cutoff:
                continue

            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()[:200]
            if title:
                articles.append({"title": title, "summary": summary})

        if verbose:
            print(f"  {name}: {len(articles)}件", file=sys.stderr)

    except Exception as e:
        if verbose:
            print(f"  {name}: 取得失敗 ({e})", file=sys.stderr)

    return articles


def extract_keywords(articles_by_genre: dict, verbose: bool) -> dict:
    """Claude CLI を使ってキーワードとトレンドを抽出する"""
    # 全記事タイトルをジャンル別にまとめる
    sections = []
    for genre, articles in articles_by_genre.items():
        if not articles:
            continue
        titles = "\n".join(f"・{a['title']}" for a in articles[:30])
        sections.append(f"【{genre}】\n{titles}")

    if not sections:
        return {}

    prompt = f"""以下は過去7日間のニュース・記事タイトルです。
天弥堂（フレグランス・占い・陶芸・Webデザインのサロン）のSNS投稿に活かせる視点で分析してください。
※「アロマ」という言葉は使わないこと。香りの表現は「フレグランス」を使うこと。

{chr(10).join(sections)}

以下のJSON形式のみで出力してください。説明不要。

{{
  "weekly_keywords": ["キーワード1", "キーワード2", ...],
  "themes": [
    {{"theme": "テーマ名", "summary": "一行説明", "relevance": "天弥堂との関連性"}},
    ...
  ],
  "content_hints": ["投稿ネタのヒント1", "ヒント2", ...],
  "ta_analysis": [
    {{
      "trend": "トレンドキーワードや現象",
      "ta_perspective": "交流分析（エゴグラム・ストローク・人生脚本・ゲーム・OKグラムなど）の視点で読み解いた分析",
      "post_angle": "このTA視点で天弥堂が投稿できるコンテンツのアイデア"
    }},
    ...
  ]
}}"""

    if verbose:
        print("🤖 Claude がキーワード抽出中...", file=sys.stderr)

    result = subprocess.run(
        [str(CLAUDE_BIN), "-p", prompt],
        capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0 or not result.stdout.strip():
        return {}

    # JSON部分を抽出
    raw = result.stdout.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return {}

    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {}


def main():
    parser = argparse.ArgumentParser(description="RSSからトレンドキーワードを取得")
    parser.add_argument("--days", type=int, default=7, help="取得対象の日数（デフォルト: 7）")
    parser.add_argument("--verbose", action="store_true", help="詳細ログを表示")
    args = parser.parse_args()

    print("📡 RSSフィード巡回中...", file=sys.stderr)

    articles_by_genre: dict[str, list] = {}
    total = 0

    for genre, feeds in RSS_FEEDS.items():
        articles_by_genre[genre] = []
        for name, url in feeds:
            items = fetch_feed(name, url, args.days, args.verbose)
            articles_by_genre[genre].extend(items)
            total += len(items)

    print(f"📰 合計 {total} 件収集（過去{args.days}日）", file=sys.stderr)

    if total == 0:
        print("⚠️  記事が取得できませんでした", file=sys.stderr)
        sys.exit(1)

    keywords = extract_keywords(articles_by_genre, args.verbose)

    result = {
        "fetched_at": datetime.now().isoformat(),
        "days": args.days,
        "article_counts": {g: len(a) for g, a in articles_by_genre.items()},
        "total_articles": total,
        **keywords,
    }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 保存: {CACHE_PATH}", file=sys.stderr)

    if keywords.get("weekly_keywords"):
        print(f"🔑 週間キーワード: {', '.join(keywords['weekly_keywords'][:8])}", file=sys.stderr)
    if keywords.get("ta_analysis"):
        print(f"🧠 TA分析: {len(keywords['ta_analysis'])}件", file=sys.stderr)


if __name__ == "__main__":
    main()
