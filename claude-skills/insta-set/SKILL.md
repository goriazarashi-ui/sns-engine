---
name: insta-set
description: Instagramカルーセル投稿の1セット（トップ+コンテンツ×6+CTA=8枚）を生成する。テンプレートJSONと対話またはファイルでコンテンツを受け取り、画像を生成して出力する。投稿は別途行う。
---

# Instagram カルーセル生成スキル

テンプレートベースで1セット分（デフォルト8枚）のInstagramカルーセル画像を生成する。

## あなたのロール

ユーザーから「テンプレート名」と「コンテンツ」を受け取り、`insta_generate.py` を実行して画像セットを生成する。生成後はプレビューURLを案内する。

## 手順

### 1. 入力の確認

引数で渡された場合はそれを使う。なければユーザーに確認:

- **テンプレート名**: `~/.claude/insta/templates/` 配下のディレクトリ名
  - 例: `okane-soudan`
  - テンプレート一覧: `ls ~/.claude/insta/templates/`
- **コンテンツ指定**: ファイルパスが渡されたらファイルモード。なければ対話モード

### 2. テンプレートの状態確認

実行前に以下をチェック:

```bash
ls ~/.claude/insta/templates/{template}/
```

- `config.json` があるか
- `layouts/top.json` があるか（なければ `/insta-layout` を案内）
- `layouts/content.json` があるか（なければ `/insta-layout` を案内）
- `base/top.png` があるか
- `base/content.png` があるか
- `cta.png` があるか（なければ「CTA画像を配置してください」と案内）

不足がある場合は具体的に何が足りないかを伝え、先に進まない。

### 3. content.txt 形式の案内（対話モード時）

ファイルモードの場合、content.txt は以下の形式を案内する:

```
[top]
vol: 01
subtitle: パート収入の壁
main_copy: それ、税金\nかかるかも？

[content]
heading: 103万円の壁とは？
body: 年収103万円を超えると\n所得税がかかります

[content]
heading: 扶養の仕組み
body: 配偶者控除は\n年収150万円まで

[content]
heading: ...
body: ...

（コンテンツページの数だけ繰り返す）
```

- `\n` は改行に変換される
- `#` 始まりはコメント（無視される）
- `[cta]` セクションは書かなくてOK（固定画像を使うため）

### 4. 生成コマンドの実行

**ファイルモード:**
```bash
python3 ~/.claude/scripts/insta_generate.py \
  --template {template_id} \
  --content {content_txt_path}
```

**対話モード:**
```bash
python3 ~/.claude/scripts/insta_generate.py \
  --template {template_id}
```

対話モードでは各ページのテキストをユーザーが入力する。Bash ツールで実行すると入力プロンプトが出るので、ユーザーに直接ターミナルで実行してもらうか、内容を全部確認してからファイルを作って実行する。

→ **推奨**: 対話モードを選んだ場合は、ユーザーに各ページのテキストを先にヒアリングして content.txt を作ってからファイルモードで実行する。

### 5. 生成後の確認

生成が完了したら:
1. 出力ディレクトリを伝える: `~/.claude/insta/outputs/{日付}/{template_id}/`
2. 生成ファイル一覧を表示
3. プレビューが必要なら `iecjuku.com/preview/` にアップする案内（または実行）

### 6. 投稿（オプション）

`--post` または「投稿して」と言われた場合のみ Instagram 投稿を実行する。
現時点では未実装。将来 `insta-post` スキルに渡す。

## テンプレートのセットアップ手順（参考）

新しいテンプレートを追加する場合の手順（ユーザーに案内用）:

```
1. mkdir ~/.claude/insta/templates/{名前}/{layouts,base}

2. /insta-layout base/top.png sample/top_filled.png
   → layouts/top.json が生成される

3. /insta-layout base/content.png sample/content_filled.png
   → layouts/content.json が生成される

4. CTA画像を cta.png として配置

5. config.json のページ数・ロール設定を確認・調整

6. /insta-set {名前} で動作確認
```

## ディレクトリ構成

```
~/.claude/insta/
├── templates/
│   └── {template_id}/
│       ├── config.json        ← ページ構成定義
│       ├── layouts/
│       │   ├── top.json       ← /insta-layout で生成
│       │   └── content.json   ← /insta-layout で生成
│       ├── base/
│       │   ├── top.png        ← トップページ用ベース画像
│       │   └── content.png    ← コンテンツページ用ベース画像
│       └── cta.png            ← CTA固定画像
└── outputs/
    └── YYYY-MM-DD/
        └── {template_id}/
            ├── p1_top.jpg
            ├── p2_content.jpg
            ├── p3_content.jpg
            ├── p4_content.jpg
            ├── p5_content.jpg
            ├── p6_content.jpg
            ├── p7_content.jpg
            └── p8_cta.jpg
```

## 他PC移行

テンプレートと生成スクリプトの移行:
```bash
# テンプレートのみ（画像・レイアウトJSON）
rsync -av ~/.claude/insta/templates/ {新PC}:~/.claude/insta/templates/

# スクリプト
rsync -av ~/.claude/scripts/insta_image.py ~/.claude/scripts/insta_generate.py {新PC}:~/.claude/scripts/
```

フォントは macOS 標準（ヒラギノ角ゴシック）なので自動で利用可能。
