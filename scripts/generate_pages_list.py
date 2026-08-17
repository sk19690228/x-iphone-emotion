"""
GitHub Pages で公開する、当日分ポスト一覧ページ (public/index.html) を生成する。

publish_list.yml から定期的・手動投稿後に実行され、Google Drive 上の
iphone_reposts_YYYYMMDD.md を読み込んで、各ポストのリプライ文・ID・
投稿ステータスを一覧表示する。投稿ボタンは持たず、閲覧専用。
投稿はここに表示されたIDをコピーし、Actionsの「Manual Post to X」
ワークフローから手動で行う。
"""

import html
import os
from datetime import datetime, timedelta, timezone

from drive_reply_common import fetch_markdown_from_drive, load_status, parse_posts, today_jst_str

OUTPUT_DIR = "public"

STATUS_LABEL = {"pending": "未投稿", "posted": "投稿済み", "failed": "失敗"}

STYLE = """
body { font-family: -apple-system, "Hiragino Sans", sans-serif; max-width: 720px; margin: 1.5rem auto; padding: 0 1rem; color: #1a1a1a; }
h1 { font-size: 1.2rem; }
.hint { background: #f0f4ff; border-radius: 8px; padding: .8rem; font-size: .9rem; line-height: 1.5; }
.card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
.meta { display: flex; justify-content: space-between; align-items: center; font-size: .85rem; margin-bottom: .5rem; }
.reply { white-space: pre-wrap; background: #f7f7f7; border-radius: 6px; padding: .6rem; margin: .5rem 0; }
.idrow { display: flex; align-items: center; gap: .5rem; font-size: .85rem; }
.idrow code { background: #eee; padding: .2rem .4rem; border-radius: 4px; word-break: break-all; }
button.copy-btn { font-size: .8rem; padding: .3rem .6rem; cursor: pointer; }
.badge { display: inline-block; font-size: .75rem; padding: .1rem .5rem; border-radius: 10px; color: #fff; }
.badge.pending { background: #999; }
.badge.posted { background: #2e7d32; }
.badge.failed { background: #c62828; }
.error { color: #c62828; font-size: .85rem; margin-top: .4rem; }
.updated { color: #888; font-size: .75rem; margin-top: 2rem; }
"""


def render_card(post, status):
    entry = status.get(post["id"], {})
    st = entry.get("status", "pending")
    error = entry.get("error")
    error_html = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return f"""
    <div class="card">
      <div class="meta">
        <a href="{html.escape(post['url'])}" target="_blank" rel="noopener">元ポストを開く</a>
        <span class="badge {st}">{STATUS_LABEL.get(st, st)}</span>
      </div>
      <div class="reply">{html.escape(post['reply'])}</div>
      <div class="idrow">
        <code>{html.escape(post['id'])}</code>
        <button class="copy-btn" data-id="{html.escape(post['id'])}">IDをコピー</button>
      </div>
      {error_html}
    </div>
    """


def render_html(date_str, posts, status, workflow_url, generated_at):
    if posts:
        body = "".join(render_card(post, status) for post in posts)
    else:
        body = "<p>本日分のポストが見つかりませんでした。</p>"

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>iPhone repost 投稿一覧</title>
<style>{STYLE}</style>
</head>
<body>
  <h1>{date_str} のポスト一覧</h1>
  <p class="hint">
    投稿するには、IDをコピーして
    <a href="{html.escape(workflow_url)}" target="_blank" rel="noopener">Actionsの手動投稿ワークフロー</a>
    を開き「Run workflow」→ tweet_id に貼り付けて実行してください。
  </p>
  {body}
  <p class="updated">最終更新: {generated_at}</p>
<script>
document.querySelectorAll(".copy-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    navigator.clipboard.writeText(btn.dataset.id);
    const original = btn.textContent;
    btn.textContent = "コピーしました";
    setTimeout(() => btn.textContent = original, 1500);
  }});
}});
</script>
</body>
</html>
"""


def main():
    date_str = today_jst_str()
    filename = f"iphone_reposts_{date_str}.md"

    markdown_text = fetch_markdown_from_drive(filename)
    posts = parse_posts(markdown_text) if markdown_text else []
    status = load_status(date_str)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    workflow_url = f"https://github.com/{repo}/actions/workflows/manual_post.yml" if repo else "#"

    jst = timezone(timedelta(hours=9))
    generated_at = datetime.now(jst).strftime("%Y-%m-%d %H:%M JST")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_html(date_str, posts, status, workflow_url, generated_at))

    print(f"[SUCCESS] {OUTPUT_DIR}/index.html を生成しました（{len(posts)}件）。")


if __name__ == "__main__":
    main()
