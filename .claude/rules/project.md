# プロジェクト構成

## ディレクトリ
- `scripts/` — SNSごとの投稿スクリプト (post_x.py, post_instagram.py, ...)
- `skills/` — コンテンツ生成スキル (generate_daily.py, generate_video.py, ...)
- `clients/` — クライアントごとの設定・テンプレート・アセット

## 自動実行
- LaunchAgent で朝7:58・夕17:58に sns_morning.sh / sns_evening.sh を実行
- plist: ~/Library/LaunchAgents/com.imamuramaki.sns.{morning,evening}.plist
- ログ: ~/.claude/outputs/launchagent_{morning,evening}.log

## コンテンツ生成フロー
1. generate_daily.py がClaudeを呼び、X/Instagram/Facebook/Threads用テキスト＋画像を一括生成
2. 結果を ~/.claude/outputs/daily_cache_{client}_{morning|evening}.json にキャッシュ
3. 各 post_*.py がキャッシュを読み込んで投稿

## 投稿スクリプト共通引数
- `--client 天弥堂` （必須）
- `--generate` : キャッシュから生成テキストを使用
- `--template` : templates/ のローテーションを使用
- `--text "..."` : 直接テキスト指定

## Playwright
- 自動化専用Chromeプロファイル: ~/.claude/sns/chrome-profiles/{client}_{sns}/
- 初回のみ --setup でログイン保存が必要
