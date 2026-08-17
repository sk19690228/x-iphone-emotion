"""
GitHub Pages で公開する、当日分ポスト一覧ページ (public/index.html) を生成する。

publish_list.yml から定期的・手動投稿後に実行され、Google Drive 上の
iphone_reposts_YYYYMMDD.md を毎回読み込んで、各ポストのリプライ文・ID・
投稿ステータス（results/manual_reply_status_YYYYMMDD.json、
manual_post.yml が更新する）を反映したページを生成する。

ページ自体は静的HTMLで、開いた時点でDriveへ問い合わせ直すわけではない
（それをブラウザから安全に行うには別途Googleサインインの仕組みが要る）。
その代わりpublish_list.ymlが定期的に（および投稿直後に）このスクリプトを
再実行してページを作り直すことで、常に最新に近い内容を保つ。

投稿ボタンは持たず閲覧専用。投稿はここに表示されたIDをコピーし、
Actionsの「Manual Post to X」ワークフローから手動で行う。
"""

import html
import json
import os
from datetime import datetime, timedelta, timezone

from drive_reply_common import fetch_markdown_from_drive, load_status, parse_posts, today_jst_str

OUTPUT_DIR = "public"

STATUS_LABEL = {"pending": "未投稿", "posted": "投稿済み", "failed": "失敗"}

STYLE = """
:root {
  --bg: #F5F6F8;
  --surface: #FFFFFF;
  --surface-2: #ECEEF2;
  --text: #1B1D22;
  --text-muted: #6B7280;
  --border: #E2E4E9;
  --accent: #FF5A36;
  --success: #1FA971;
  --success-bg: #E4F7EE;
  --success-text: #0E6B45;
  --fail: #C62828;
  --fail-bg: #FCE8E8;
  --shadow: 0 1px 2px rgba(20,22,27,.04), 0 8px 24px rgba(20,22,27,.06);
  --radius: 16px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14161B; --surface: #1D2027; --surface-2: #262A33; --text: #EDEEF1;
    --text-muted: #9096A3; --border: #2E323C; --accent: #FF7A57;
    --success: #34C98A; --success-bg: #163229; --success-text: #6FE0AF;
    --fail: #FF6B6B; --fail-bg: #331616;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--text);
  font-family: -apple-system, "Hiragino Sans", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 640px; margin: 0 auto; padding: 28px 18px 80px; display: flex; flex-direction: column; gap: 20px; }
header.app-header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.app-name { font-size: 1.05rem; font-weight: 700; margin: 0; }
.app-sub { font-size: .78rem; color: var(--text-muted); margin: 2px 0 0; }
.counter { font-variant-numeric: tabular-nums; font-weight: 700; font-size: .9rem; color: var(--text-muted); white-space: nowrap; }
.counter strong { color: var(--text); font-size: 1.1rem; }
.progress-track { height: 6px; border-radius: 999px; background: var(--surface-2); overflow: hidden; }
.progress-fill { height: 100%; background: var(--accent); border-radius: inherit; }
.hint { background: var(--surface-2); border-radius: 10px; padding: .7rem .9rem; font-size: .82rem; line-height: 1.5; color: var(--text-muted); }
.hint a { color: var(--accent); font-weight: 600; }
.current-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 22px; display: flex; flex-direction: column; gap: 16px; }
.current-card.all-done { align-items: center; text-align: center; padding: 40px 24px; }
.card-top { display: flex; align-items: center; justify-content: space-between; }
.index-badge { font-size: 1.7rem; font-weight: 800; }
.index-badge .of { font-size: 1rem; font-weight: 600; color: var(--text-muted); }
.id-row { display: flex; align-items: center; gap: 8px; }
.id-tag { font-size: .7rem; font-family: ui-monospace, Menlo, Consolas, monospace; color: var(--text-muted); background: var(--surface-2); padding: 4px 8px; border-radius: 6px; word-break: break-all; }
.step-label { font-size: .72rem; font-weight: 700; color: var(--text-muted); letter-spacing: .04em; text-transform: uppercase; margin: 0; }
.source-box { border-left: 3px solid var(--border); padding: 2px 0 2px 12px; font-size: .85rem; color: var(--text-muted); line-height: 1.6; white-space: pre-wrap; word-break: break-word; max-height: 120px; overflow-y: auto; }
.reply-box { background: var(--surface-2); border-radius: 12px; padding: 14px 16px; font-size: 1rem; font-weight: 500; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.action-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
button, a.btn-step { font-family: inherit; cursor: pointer; border: none; border-radius: 12px; font-weight: 600; display: inline-flex; align-items: center; justify-content: center; gap: 6px; text-decoration: none; }
.btn-step { background: var(--surface); color: var(--text); border: 1.5px solid var(--border); padding: 13px 10px; font-size: .9rem; min-height: 48px; }
.btn-primary { background: var(--accent); color: #fff; padding: 15px; font-size: .95rem; width: 100%; min-height: 52px; }
.btn-ghost { background: transparent; color: var(--text-muted); padding: 6px 8px; font-size: .8rem; font-weight: 500; }
.badge { display: inline-block; font-size: .72rem; font-weight: 700; padding: 3px 9px; border-radius: 999px; }
.badge.pending { background: var(--surface-2); color: var(--text-muted); }
.badge.posted { background: var(--success-bg); color: var(--success-text); }
.badge.failed { background: var(--fail-bg); color: var(--fail); }
.error-box { background: var(--fail-bg); color: var(--fail); font-size: .82rem; border-radius: 8px; padding: 8px 10px; line-height: 1.5; }
.list-section h2 { font-size: .75rem; font-weight: 700; color: var(--text-muted); letter-spacing: .04em; text-transform: uppercase; margin: 0 0 8px; }
.queue-list { display: flex; flex-direction: column; gap: 6px; }
.queue-row { display: grid; grid-template-columns: 26px 1fr auto; align-items: center; gap: 10px; padding: 9px 11px; border-radius: 10px; background: var(--surface); border: 1px solid var(--border); cursor: pointer; text-align: left; width: 100%; font-family: inherit; font-weight: 500; }
.queue-row.current { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.queue-num { font-size: .75rem; font-weight: 700; color: var(--text-muted); text-align: center; }
.queue-preview { font-size: .82rem; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.queue-row.posted .queue-preview { color: var(--text-muted); }
.toast { position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%) translateY(8px); background: var(--text); color: var(--bg); padding: 10px 18px; border-radius: 999px; font-size: .82rem; font-weight: 600; opacity: 0; pointer-events: none; transition: opacity .2s ease, transform .2s ease; box-shadow: var(--shadow); z-index: 10; }
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.updated { color: var(--text-muted); font-size: .72rem; text-align: center; }
.fatal-error { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; font-size: .85rem; white-space: pre-wrap; }
"""

SCRIPT = r"""
(function () {
  "use strict";
  try { main(); } catch (err) {
    var page = document.querySelector(".page");
    if (page) page.style.display = "none";
    var box = document.createElement("div");
    box.className = "fatal-error";
    box.textContent = "ページの読み込み中にエラーが発生しました。\n" + (err && err.message ? err.message : String(err));
    document.body.appendChild(box);
  }

  function main() {
    var posts = JSON.parse(document.getElementById("posts-data").textContent);
    var cardArea = document.getElementById("cardArea");
    var queueList = document.getElementById("queueList");
    var doneCountEl = document.getElementById("doneCount");
    var totalCountEl = document.getElementById("totalCount");
    var progressFill = document.getElementById("progressFill");
    var toast = document.getElementById("toast");

    totalCountEl.textContent = String(posts.length);

    var toastTimer = null;
    function showToast(message) {
      toast.textContent = message;
      toast.classList.add("show");
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(function () { toast.classList.remove("show"); }, 1600);
    }

    function copyText(text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          showToast("コピーしました");
        }, function () { fallbackCopy(text); });
      } else {
        fallbackCopy(text);
      }
    }

    function fallbackCopy(text) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try {
        document.execCommand("copy");
        showToast("コピーしました");
      } catch (e) {
        showToast("コピーに失敗しました");
      }
      document.body.removeChild(ta);
    }

    function firstPendingIndex() {
      for (var i = 0; i < posts.length; i++) {
        if (posts[i].status !== "posted") return i;
      }
      return -1;
    }

    function postedCount() {
      var n = 0;
      for (var i = 0; i < posts.length; i++) if (posts[i].status === "posted") n++;
      return n;
    }

    var activeIndex = firstPendingIndex();

    function render() {
      var count = postedCount();
      doneCountEl.textContent = String(count);
      progressFill.style.width = (posts.length ? (count / posts.length) * 100 : 0) + "%";
      renderCard();
      renderList();
    }

    function renderCard() {
      cardArea.innerHTML = "";

      if (activeIndex === -1) {
        var doneCard = document.createElement("div");
        doneCard.className = "current-card all-done";
        doneCard.innerHTML =
          '<p style="font-size:2rem;margin:0;">✅</p>' +
          '<p style="font-weight:700;font-size:1.05rem;margin:10px 0 4px;">全' + posts.length + '件、投稿済みです</p>' +
          '<p style="color:var(--text-muted);font-size:.85rem;margin:0;">お疲れさまでした。</p>';
        cardArea.appendChild(doneCard);
        return;
      }

      var post = posts[activeIndex];
      var card = document.createElement("div");
      card.className = "current-card";

      var top = document.createElement("div");
      top.className = "card-top";
      top.innerHTML =
        '<div class="index-badge">' + (activeIndex + 1) + '<span class="of"> / ' + posts.length + '</span></div>' +
        '<span class="badge ' + post.status + '">' + statusLabel(post.status) + '</span>';
      card.appendChild(top);

      if (post.error) {
        var errBox = document.createElement("div");
        errBox.className = "error-box";
        errBox.textContent = post.error;
        card.appendChild(errBox);
      }

      var sourceLabel = document.createElement("p");
      sourceLabel.className = "step-label";
      sourceLabel.textContent = "元ポスト文";
      card.appendChild(sourceLabel);

      var sourceBox = document.createElement("div");
      sourceBox.className = "source-box";
      sourceBox.textContent = post.source_text || "(本文なし)";
      card.appendChild(sourceBox);

      var replyLabel = document.createElement("p");
      replyLabel.className = "step-label";
      replyLabel.textContent = "リプライ文";
      card.appendChild(replyLabel);

      var replyBox = document.createElement("div");
      replyBox.className = "reply-box";
      replyBox.textContent = post.reply;
      card.appendChild(replyBox);

      var actionRow = document.createElement("div");
      actionRow.className = "action-row";

      var openBtn = document.createElement("a");
      openBtn.href = post.url;
      openBtn.target = "_blank";
      openBtn.rel = "noopener noreferrer";
      openBtn.className = "btn-step";
      openBtn.textContent = "元ポストを開く";

      var copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn-step";
      copyBtn.textContent = "文章をコピー";
      copyBtn.addEventListener("click", function () { copyText(post.reply); });

      actionRow.appendChild(openBtn);
      actionRow.appendChild(copyBtn);
      card.appendChild(actionRow);

      var idRow = document.createElement("div");
      idRow.className = "id-row";
      var idTag = document.createElement("code");
      idTag.className = "id-tag";
      idTag.textContent = post.id;
      var idCopyBtn = document.createElement("button");
      idCopyBtn.type = "button";
      idCopyBtn.className = "btn-ghost";
      idCopyBtn.textContent = "IDをコピー";
      idCopyBtn.addEventListener("click", function () { copyText(post.id); });
      idRow.appendChild(idTag);
      idRow.appendChild(idCopyBtn);
      card.appendChild(idRow);

      var postBtn = document.createElement("a");
      postBtn.href = window.WORKFLOW_URL;
      postBtn.target = "_blank";
      postBtn.rel = "noopener noreferrer";
      postBtn.className = "btn-primary";
      postBtn.style.textDecoration = "none";
      postBtn.textContent = "投稿ワークフローを開く";
      card.appendChild(postBtn);

      var skipBtn = document.createElement("button");
      skipBtn.type = "button";
      skipBtn.className = "btn-ghost";
      skipBtn.style.alignSelf = "center";
      skipBtn.textContent = "次の未投稿へスキップ";
      skipBtn.addEventListener("click", function () {
        var nextIndex = -1;
        for (var i = activeIndex + 1; i < posts.length; i++) {
          if (posts[i].status !== "posted") { nextIndex = i; break; }
        }
        if (nextIndex === -1) {
          for (var j = 0; j < activeIndex; j++) {
            if (posts[j].status !== "posted") { nextIndex = j; break; }
          }
        }
        if (nextIndex !== -1) {
          activeIndex = nextIndex;
          renderCard();
          renderList();
        }
      });
      card.appendChild(skipBtn);

      cardArea.appendChild(card);
    }

    function statusLabel(status) {
      return {pending: "未投稿", posted: "投稿済み", failed: "失敗"}[status] || status;
    }

    function renderList() {
      queueList.innerHTML = "";
      posts.forEach(function (post, i) {
        var row = document.createElement("button");
        row.type = "button";
        row.className = "queue-row " + post.status + (i === activeIndex ? " current" : "");
        row.innerHTML =
          '<span class="queue-num">' + (i + 1) + '</span>' +
          '<span class="queue-preview"></span>' +
          '<span class="badge ' + post.status + '">' + statusLabel(post.status) + '</span>';
        row.querySelector(".queue-preview").textContent = post.reply.split("\n")[0];
        row.addEventListener("click", function () {
          activeIndex = i;
          renderCard();
          renderList();
        });
        queueList.appendChild(row);
      });
    }

    render();
  }
})();
"""


def render_html(date_str, posts, status, workflow_url, generated_at):
    posts_data = []
    for post in posts:
        entry = status.get(post["id"], {})
        posts_data.append(
            {
                "id": post["id"],
                "url": post["url"],
                "source_text": post["source_text"],
                "reply": post["reply"],
                "status": entry.get("status", "pending"),
                "error": entry.get("error"),
            }
        )

    posts_json = json.dumps(posts_data, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>iPhone repost 投稿一覧</title>
<style>{STYLE}</style>
</head>
<body>
<div class="page">
  <header class="app-header">
    <div>
      <p class="app-name">{html.escape(date_str)} のポスト一覧</p>
      <p class="app-sub">元ポストを開く → 文章をコピー → Actionsで投稿</p>
    </div>
    <div class="counter"><strong id="doneCount">0</strong> / <span id="totalCount">0</span> 投稿済み</div>
  </header>

  <div class="progress-track"><div class="progress-fill" id="progressFill" style="width:0%;"></div></div>

  <p class="hint">
    IDをコピーし、<a href="{html.escape(workflow_url)}" target="_blank" rel="noopener">Actionsの手動投稿ワークフロー</a>
    を開いて「Run workflow」→ tweet_id に貼り付けて実行すると投稿されます。
  </p>

  <div id="cardArea"></div>

  <div class="list-section">
    <h2>一覧（{len(posts_data)}件）</h2>
    <div class="queue-list" id="queueList"></div>
  </div>

  <p class="updated">最終更新: {generated_at}</p>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script type="application/json" id="posts-data">{posts_json}</script>
<script>window.WORKFLOW_URL = {json.dumps(workflow_url)};</script>
<script>{SCRIPT}</script>
</body>
</html>
"""


def main():
    date_str = today_jst_str()
    filename = f"iphone_reposts_{date_str}.md"

    print(f"[INFO] Google Drive から {filename} を取得します。")
    markdown_text = fetch_markdown_from_drive(filename)
    if markdown_text is None:
        print(f"[WARN] {filename} が Google Drive に見つかりませんでした。")
        posts = []
    else:
        print(f"[INFO] {filename} を取得しました（{len(markdown_text)}文字）。")
        posts = parse_posts(markdown_text)
        if not posts:
            print("[WARN] ファイルは見つかりましたが、パース結果が0件でした。フォーマットを確認してください。")
            print("[DEBUG] 先頭500文字:")
            print(repr(markdown_text[:500]))
    status = load_status(date_str)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    workflow_url = f"https://github.com/{repo}/actions/workflows/manual_post.yml" if repo else "#"

    jst = timezone(timedelta(hours=9))
    generated_at = datetime.now(jst).strftime("%Y-%m-%d %H:%M JST")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_html(date_str, posts, status, workflow_url, generated_at))

    print(f"[SUCCESS] {OUTPUT_DIR}/index.html を生成しました（{len(posts)}件、対象日={date_str}）。")


if __name__ == "__main__":
    main()
