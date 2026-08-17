# 手動投稿Webアプリ

`webapp/` は Google Drive の `iphone_reposts_YYYYMMDD.md` を読み込み、
ボタン操作で1件ずつXにリプライを投稿するローカル専用のWebアプリ。
自動投稿（`post_reply.yml`の定期実行）は停止し、投稿はこのアプリから手動で行う運用。

## 使い方

1. リポジトリ直下に `.env` を作成し、[docs/REPLY_BOT_SETUP.md](./REPLY_BOT_SETUP.md) の
   GitHub Secretsと同じ環境変数（`GOOGLE_OAUTH_CLIENT_ID` など）を設定する。
2. 依存関係をインストールして起動する。

   ```bash
   pip install -r requirements.txt
   python webapp/app.py
   ```

3. ブラウザで `http://127.0.0.1:5001` を開く。
4. 日付を選んで「読み込む」を押すと、その日の `iphone_reposts_YYYYMMDD.md` の
   ポスト一覧が表示される。各ポストの「投稿する」ボタンでXへリプライを投稿する。
5. 投稿結果（成功/失敗）は `results/manual_reply_status_YYYYMMDD.json` に保存され、
   ページを再読み込みしても投稿済みの状態は保持される。失敗した場合はエラー内容が
   表示され、「再投稿する」ボタンで再試行できる。

自分だけがローカルで使うことを想定しており、認証や公開アクセス対策は行っていない。
外部に公開したり、他人と共有した状態で起動しないこと。

## 自動投稿ワークフローについて

- `post_reply.yml` はスケジュール実行を停止済み（`workflow_dispatch` の手動実行のみ残してある）。
- `daily_run.yml`（`results/reply_plan_YYYYMMDD.json` を生成する処理）は
  現状そのまま残っている。このアプリはDriveから直接読み込むため
  `reply_plan_YYYYMMDD.json` には依存しない。不要であれば別途停止を検討してほしい。
