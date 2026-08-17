# スマホからの手動投稿

自動投稿は行わず、GitHub（PagesとActions）を使ってスマホから
手動でXへリプライを投稿する運用。

- **一覧の閲覧**: `publish_list.yml` が定期的に（JST 5:00〜22:00の30分おき）と
  投稿直後に、Google Drive上の当日分 `iphone_reposts_YYYYMMDD.md` を読み込んで
  GitHub Pagesに一覧ページを自動公開する（`scripts/generate_pages_list.py`）。
- **投稿の実行**: `manual_post.yml`（Actionsのworkflow_dispatch）に
  投稿したいポストのIDを入力して実行すると、そのポストだけにXへリプライする
  （`scripts/manual_post.py`）。

## 事前準備（初回のみ）

1. リポジトリの **Settings → Pages → Build and deployment → Source** を
   **GitHub Actions** に設定する（Claude Codeからは変更できないため、
   リポジトリの管理者が手動で設定する必要がある）。
2. `publish_list.yml` を一度 `workflow_dispatch` で手動実行するか、
   次回のスケジュール実行を待つと、一覧ページが
   `https://<ユーザー名>.github.io/<リポジトリ名>/` に公開される。
   URLはブックマークやホーム画面に追加しておくと便利。

## スマホでの操作手順

1. 公開された一覧ページ（上記URL）をブラウザで開き、その日のポスト一覧を確認する。
   各カードに元ポストへのリンク・リプライ文・ステータス（未投稿/投稿済み/失敗）・
   ポストIDが表示される。
2. 投稿したいポストの「IDをコピー」ボタンをタップしてIDをコピーする。
3. GitHub Mobileアプリ（またはブラウザ）でリポジトリの
   **Actions → Manual Post to X → Run workflow** を開く。
   一覧ページの案内リンクからも直接開ける。
4. `tweet_id` にコピーしたIDを貼り付けて実行する（`date` は当日分なら空欄でよい）。
5. 実行が終わると `results/manual_reply_status_YYYYMMDD.json` が更新され、
   その後まもなく一覧ページのステータスも「投稿済み」（失敗時はエラー内容）に
   自動更新される。

## 認証情報の設定

`GOOGLE_OAUTH_CLIENT_ID` などのGitHub Secretsは
[docs/REPLY_BOT_SETUP.md](./REPLY_BOT_SETUP.md) の手順で設定したものをそのまま使う。

## 補足

- `daily_run.yml`（`results/reply_plan_YYYYMMDD.json` の生成）は今回は変更していない。
  今の運用では読まれなくなったファイルだが、必要であれば別途整理する。
- X API側の投稿制限（無償プランだと「フォロー中/メンションされた投稿にしか
  リプライできない」等）により投稿が失敗することがある。失敗時はエラー内容が
  一覧ページとAction実行ログの両方に表示される。
