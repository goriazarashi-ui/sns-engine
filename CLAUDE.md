# SNS自動投稿プロジェクト

@.claude/rules/project.md
@.claude/rules/clients.md

# Compact Instructions

コンテキストを圧縮する際、以下の情報を必ず保持すること：

1. **作業中のタスク**: 何を修正・追加しようとしていたか、どこまで完了したか
2. **エラー情報**: 発生したエラーのメッセージと原因、未解決のものは特に詳細に
3. **クライアント**: 天弥堂（対象SNS: X・Instagram・Threads・Facebook・TikTok・YouTube Shorts）
4. **変更済みファイル**: このセッションで編集したファイルのパスと変更内容の要点
5. **LaunchAgent状態**: plistの設定変更があった場合はその内容（時刻・スクリプトパス）
6. **Playwrightセッション**: --setup 済みのSNSと未完了のもの
7. **次のステップ**: ユーザーから指示されているが未着手の作業
