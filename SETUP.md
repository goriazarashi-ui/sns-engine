# SNS自動投稿 セットアップ手順書

---

## 0. 新規クライアントの場合の準備（元PC側）

既存クライアント（天弥堂など）をそのまま別PCに移行する場合はこのステップは不要です。
**別のクライアントで新規セットアップする場合のみ**実施してください。

> **setup.sh が自動作成します**
> 別PCのセットアップ時にクライアント名を入力すると、profile.json と .env のひな形が自動で生成されます。後から編集することもできます。

---

## 1. ファイルを取得する（別PC側の作業）

別PCのターミナルを開きます。
（Finder → アプリケーション → ユーティリティ → ターミナル）

GitHubからクローンします。

```bash
mkdir -p ~/.claude
git clone https://github.com/goriazarashi-ui/sns-engine.git ~/.claude/sns
```

確認します。

```bash
ls ~/.claude/sns
# scripts/ skills/ setup.sh などが表示されればOK
```

---

## 1b. すでにインストール済みのPCを最新に更新する（パッチを当てる）

開発機（いつも作業しているPC）でスクリプトを修正したあと、
クライアントPC（自動投稿が動いているPC）を最新の状態にする手順です。

---

### 手順の全体像

やることは **3ステップ** だけです。

```
① ターミナルを開く
② SNSフォルダに移動する
③ コマンドを2つ実行する
```

所要時間: 約3〜5分（ネット速度による）

---

### ステップ①　ターミナルを開く

クライアントPCで「ターミナル」を開きます。

- Finder → アプリケーション → ユーティリティ → **ターミナル**
- または、Spotlight（`Cmd + Space`）で「ターミナル」と入力して Enter

黒い（または白い）画面が出たらOKです。

---

### ステップ②　SNSフォルダに移動する

ターミナルに以下を入力して Enter を押します。

**SNSが `~/.claude/sns` にある場合（ほとんどの場合はこれ）:**

```bash
cd ~/.claude/sns
```

**別の場所にインストールした場合:**

```bash
cd /インストールした場所のパス
```

> **わからない場合の探し方:**
> ```bash
> find ~ -name "sns_morning.sh" -type f 2>/dev/null
> ```
> 表示されたパスの `scripts/sns_morning.sh` を除いた部分がSNSフォルダです。
> 例: `/Users/ryuji/sns-engine/scripts/sns_morning.sh` → `cd /Users/ryuji/sns-engine`

Enter を押したあと、エラーが出なければ移動完了です。

---

### ステップ③　コマンドを実行する

**以下を1行ずつ、入力して Enter を押してください。**

**1行目: 最新のコードをダウンロード**

```bash
git pull
```

こんな感じの表示が出たら成功です:

```
remote: Enumerating objects: ...
Updating xxxxxxx..yyyyyyy
Fast-forward
 scripts/sns_morning.sh | 7 ++++---
 ...
```

> `Already up to date.` と出たら、すでに最新です。ステップ③の2行目に進んでください。

> **エラーが出た場合:**
>
> `error: Your local changes ...` と出たら、以下を実行してからもう一度 `git pull` してください:
> ```bash
> git stash
> git pull
> ```

**2行目: 更新スクリプトを実行**

```bash
bash update.sh
```

自動で以下が実行されます（画面にチェックマークが出ていきます）:

```
✅ クライアント: 天弥堂
✅ コード更新完了
✅ Python パッケージ更新完了
✅ Playwright Chrome 更新完了
✅ LaunchAgent 再登録完了
✅ LaunchAgent: 5 件稼働中
✅ クライアント設定: 4 / 4 件OK
```

最後に「アップデート完了！」と出たら成功です。

---

### ステップ④（確認）　ちゃんと動いているか見る

念のため確認したい場合は、以下を入力してください:

```bash
launchctl list | grep sns
```

こんな感じで **5行** 出ればOKです:

```
-   0   com.imamuramaki.sns.morning
-   0   com.imamuramaki.sns.evening
-   0   com.imamuramaki.sns.fetch_trends
-   0   com.imamuramaki.sns.grow_assets
-   0   com.imamuramaki.sns.check_sessions
```

---

### うまくいかないときは

| 症状 | 対処法 |
|------|--------|
| `cd` でエラー | SNSフォルダのパスが違います。上の「探し方」を試してください |
| `git pull` で認証エラー | GitHub にログインが必要です。`git config credential.helper osxkeychain` を実行してから再度 `git pull` |
| `git pull` でローカル変更エラー | `git stash` → `git pull` の順で実行 |
| `bash update.sh` で Python エラー | `python3 --version` を実行。表示されなければ `brew install python` |
| LaunchAgent が 5件未満 | `bash update.sh` をもう一度実行 |

---

### 2回目以降の更新

2回目以降は、もっと簡単です。ターミナルを開いて以下の1行だけ:

```bash
bash ~/.claude/sns/update.sh
```

（`update.sh` の中で自動的に `git pull` も実行します）

> 別の場所にインストールしている場合は `bash /インストール先のパス/update.sh`

---

## 3. セットアップスクリプトを実行する（別PC側・自動）

```bash
bash ~/.claude/sns/setup.sh
```

最初に**クライアント名の入力**を求められます。

```
▶ クライアント設定
  クライアント名を入力してください: ○○株式会社
```

- **既存クライアントの場合**（天弥堂など）: そのまま入力すればOKです
- **新規クライアントの場合**: 入力するとSNSアカウント情報（メール・パスワード等）を追加で聞かれます。後から `~/.claude/sns/clients/クライアント名/.env` を編集することもできます

その後、以下が自動でインストールされます。
途中でパスワードを求められたら、Macのログインパスワードを入力してください。

- Homebrew（パッケージ管理ツール）
- Python3
- ffmpeg（動画生成ツール）
- Google Chrome
- Playwright（ブラウザ自動操作ライブラリ）
- numpy / requests / Pillow（Pythonライブラリ）
- Flux venv（torch / diffusers / transformers / accelerate）※初回は時間がかかります
- LaunchAgent（5つの自動実行スケジュール）
  - 朝 7:58 — SNS全プラットフォーム投稿
  - 夜 17:58 — SNS全プラットフォーム投稿
  - 深夜 1:00 — トレンド取得
  - 深夜 2:00 — アセット画像拡充
  - 毎週月曜 9:00 — ログインセッション確認
- 著作権フリーBGM（ローカル生成）

途中で以下の質問が出ます。

```
GITHUB_GIST_TOKEN を入力してください（スキップ: Enter）:
```

#### これは何？

毎日の投稿結果（成功/失敗）をスマホのブラウザから確認できるレポート機能の設定です。
投稿が終わるたびに自動でレポートが更新され、こんなURLでスマホから見られます。

```
https://gist.github.com/（あなたのGitHubユーザー名）/xxxxxxxxxxxxxxxx
```

#### トークンの作り方

GitHubアカウントが必要です（無料）。
アカウントがない場合は Enter でスキップしてください（後から追加できます）。

1. ブラウザで https://github.com にアクセスしてログイン
2. 右上のアイコンをクリック → **Settings**
3. 左メニューの一番下 → **Developer settings**
4. **Personal access tokens** → **Tokens (classic)**
5. **Generate new token (classic)** をクリック
6. 以下を設定する
   - Note（メモ）: `sns-report`（何でもよい）
   - Expiration（有効期限）: `No expiration`（期限なし）
   - スコープ: **gist** にチェックを入れる（他は不要）
7. 一番下の **Generate token** をクリック
8. `ghp_` から始まるトークンが表示される → コピーする（この画面を閉じると二度と見られない）

コピーしたトークンをターミナルに貼り付けて Enter を押してください。

---

## 4. Claude Code にログインする（手動）

```bash
claude
```

初回起動時にブラウザが開くので、MAXプランのアカウントでログインします。
ログイン完了後、ターミナルに戻り Ctrl+C で終了します。

ログインできているか確認します。

```bash
claude -p "テスト"
```

「テスト成功」などの返答が返ってきたらOKです。

---

## 5. 各SNSにログインする（手動・1回だけ）

各SNSごとに専用のChromeプロファイルを作成します。
コマンドを実行するとChromeが自動で開くので、**3分以内**にSNSにログインしてください。

まず作業フォルダに移動します。

```bash
cd ~/.claude/sns
```

> `--client` の後は、setup.sh で入力したクライアント名を使ってください。

#### X（Twitter）

```bash
python3 scripts/post_x.py --client クライアント名 --setup
```

Chromeが開くので twitter.com / x.com にログインします。

#### Facebook

```bash
python3 scripts/post_facebook.py --client クライアント名 --setup
```

Chromeが開くので facebook.com にログインします。

#### Threads

```bash
python3 scripts/post_threads.py --client クライアント名 --setup
```

Chromeが開くので threads.net にログインします。

#### Instagram

```bash
python3 scripts/post_instagram.py --client クライアント名 --setup
```

Chromeが開くので instagram.com にログインします。

#### TikTok

```bash
python3 scripts/post_tiktok.py --client クライアント名 --setup
```

Chromeが開くので tiktok.com にログインします。

#### YouTube

```bash
python3 scripts/post_youtube_shorts.py --client クライアント名 --setup
```

Chromeが開くので youtube.com にログインします。

各SNS「✅ ログイン完了。セットアップ終了します。」と表示されたら成功です。

---

## 6. 動作確認

```bash
launchctl list | grep sns
```

以下のように**5件**表示されればOKです。

```
-   0   com.imamuramaki.sns.morning
-   0   com.imamuramaki.sns.evening
-   0   com.imamuramaki.sns.fetch_trends
-   0   com.imamuramaki.sns.grow_assets
-   0   com.imamuramaki.sns.check_sessions
```

次の朝7:58から自動投稿が始まります。

---

## トラブルシューティング

**`claude` コマンドが見つからない**

```bash
export PATH="$HOME/.local/bin:$PATH"
# 永続化する場合
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**SNSのログインエラー**

```bash
cd ~/.claude/sns
python3 scripts/post_x.py --client クライアント名 --setup  # 該当SNSを再実行
```

**ログを確認したい**

```bash
# 朝・夜の全体ログ
tail -f ~/.claude/outputs/launchagent_morning.log
tail -f ~/.claude/outputs/launchagent_evening.log

# SNSごとのログ
tail -f ~/.claude/outputs/cron_x.log
tail -f ~/.claude/outputs/cron_facebook.log
tail -f ~/.claude/outputs/cron_instagram.log
tail -f ~/.claude/outputs/cron_instagram_reel.log
tail -f ~/.claude/outputs/cron_threads.log
tail -f ~/.claude/outputs/cron_tiktok.log
tail -f ~/.claude/outputs/cron_youtube.log

# その他の自動実行ログ
tail -f ~/.claude/outputs/launchagent_fetch_trends.log
tail -f ~/.claude/outputs/launchagent_grow_assets.log
tail -f ~/.claude/outputs/launchagent_check_sessions.log
```

**LaunchAgentを手動で再起動したい**

```bash
# 例: morningを再起動
launchctl unload ~/Library/LaunchAgents/com.imamuramaki.sns.morning.plist
launchctl load   ~/Library/LaunchAgents/com.imamuramaki.sns.morning.plist
```

全件まとめて再起動する場合：

```bash
for label in morning evening fetch_trends grow_assets check_sessions; do
  launchctl unload ~/Library/LaunchAgents/com.imamuramaki.sns.${label}.plist
  launchctl load   ~/Library/LaunchAgents/com.imamuramaki.sns.${label}.plist
done
```
