# X リプライボット 認証情報セットアップ手順

Google Drive 上の `iphone_reposts_YYYYMMDD.md` を読み込み、Xへリプライを
投稿するための認証情報（Google Drive / X API）のセットアップ手順。

投稿自体は自動実行ではなく、GitHub PagesとActionsを使ってスマホから手動で
行う運用になっている。一覧の見方・投稿の操作手順は
[docs/MOBILE_POSTING.md](./MOBILE_POSTING.md) を参照。

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

- `publish_list.yml` を Actions タブから `workflow_dispatch` で手動実行し、
  GitHub Pagesに一覧ページが公開されることを確認する（初回はリポジトリの
  Settings → Pages → Source を GitHub Actions に設定しておくこと）。
- `manual_post.yml` を手動実行し、指定したポストへ投稿されて
  `results/manual_reply_status_YYYYMMDD.json` が更新されることを確認する。

詳しい操作手順は [docs/MOBILE_POSTING.md](./MOBILE_POSTING.md) を参照。

## 補足・運用上の注意

- リプライ投稿に失敗したポストは `results/manual_reply_status_YYYYMMDD.json` の
  ステータスが `failed` になり、エラー内容が一覧ページにも表示される。
  同じIDで `manual_post.yml` を再実行すれば再試行できる。
- X API の投稿回数制限（プランによって異なる）に注意すること。
