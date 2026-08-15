# X 自動リプライボット セットアップ手順

Google Drive 上の `iphone_reposts_YYYYMMDD.md` を毎朝 6:10 (JST) に読み込み、
30〜45分間隔で1件ずつ元ポストへリプライを投稿する仕組み。GitHub Actions の
2つのワークフローで構成される。

- `.github/workflows/daily_run.yml`（毎朝6:00 JST に1回）
  `scripts/plan_replies.py` を実行し、Google Drive からその日の Markdown を取得・解析して
  `results/reply_plan_YYYYMMDD.json` に投稿スケジュールを保存する。
- `.github/workflows/post_reply.yml`（日中15分おき）
  `scripts/post_reply.py` を実行し、予定時刻を過ぎている最初の未投稿ポストがあれば
  1件だけ X にリプライを投稿し、プランファイルの状態を更新する。

## 1. iphone_reposts_YYYYMMDD.md のフォーマット

Google Drive にこの命名規則でファイルを保存しておく（例: `iphone_reposts_20260814.md`）。

```markdown
# iPhone Emotional Posts Repost - 2026-08-15

## 1
**元ポスト文**
元ポストの本文（任意、記録用。複数行可）

**URL**
https://twitter.com/i/web/status/1234567890123456789

**リポスト文**
```
この投稿へ返信する文章（複数行可）
```

## 2
**元ポスト文**
...

**URL**
https://twitter.com/i/web/status/9876543210987654321

**リポスト文**
```
別の返信文
```
```

- `## <番号>` で1件ずつ区切る（番号に重複・欠番があっても動作する）。
- `**URL**` の次の行にあるURLからポストIDを自動抽出する。
- `**リポスト文**` のコードブロック（\`\`\` で囲まれた部分）内のテキストが、そのままリプライとして投稿される。
- `**元ポスト文**` は記録用で、投稿内容には使われない（省略しても動作するが、URLと一致する`**URL**`の直前に置くこと）。

## 2. Google Drive の OAuth リフレッシュトークンを取得する（ローカルで1回だけ）

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成し、
   「Google Drive API」を有効化する。
2. 「APIとサービス」→「認証情報」で OAuth クライアントID
   （アプリケーションの種類: デスクトップアプリ）を作成し、JSON をダウンロードする。
3. ダウンロードした JSON を `client_secret.json` としてリポジトリ直下に置く
   （**コミットしないこと**。`.gitignore` に追加済み）。
4. 依存関係をインストールしてスクリプトを実行する。

   ```bash
   pip install -r requirements.txt
   python scripts/get_google_refresh_token.py
   ```

5. ブラウザが開くのでログイン・許可すると、ターミナルに
   `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` / `GOOGLE_OAUTH_REFRESH_TOKEN`
   が表示される。これらを GitHub Secrets に設定する。

## 3. X Developer App の認証情報を取得する

1. [X Developer Portal](https://developer.x.com/) でアプリを作成し、
   「User authentication settings」で **Read and Write** 権限を有効にする
   （OAuth 1.0a、投稿するアカウントで Access Token を発行する）。
2. 以下を取得する。
   - API Key / API Key Secret（Consumer Key/Secret）
   - Access Token / Access Token Secret（投稿するアカウントに紐づくもの）

## 4. GitHub Secrets の設定

リポジトリの Settings → Secrets and variables → Actions に以下を登録する。

| Secret名 | 内容 |
| --- | --- |
| `GOOGLE_OAUTH_CLIENT_ID` | 手順2で取得 |
| `GOOGLE_OAUTH_CLIENT_SECRET` | 手順2で取得 |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | 手順2で取得 |
| `GOOGLE_DRIVE_FOLDER_ID`（任意） | Markdown を探すフォルダIDを限定したい場合 |
| `X_API_KEY` | 手順3で取得 |
| `X_API_SECRET` | 手順3で取得 |
| `X_ACCESS_TOKEN` | 手順3で取得 |
| `X_ACCESS_TOKEN_SECRET` | 手順3で取得 |

## 5. 動作確認

- `daily_run.yml` を Actions タブから `workflow_dispatch` で手動実行し、
  `results/reply_plan_YYYYMMDD.json` が生成・コミットされることを確認する。
- `post_reply.yml` を手動実行し、予定時刻を過ぎたポストが投稿されて
  ステータスが `posted` に更新されることを確認する。

## 補足・運用上の注意

- 投稿間隔は30〜45分のランダムだが、実際のチェックは15分おきのため
  最大で数分〜十数分ずれることがある。
- 同じ日の `reply_plan_YYYYMMDD.json` が既に存在する場合、
  `plan_replies.py` はプランを再生成しない（誤って手動再実行しても上書きされない）。
- リプライ投稿に失敗したポストはステータスが `failed` になり、
  その回のワークフローではスキップされずエラーとして記録される
  （次のポストの処理には進む）。再試行が必要な場合はプランファイルを手動編集する。
- X API の投稿回数制限（プランによって異なる）に注意すること。
