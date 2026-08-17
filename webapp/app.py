"""
Google Drive の iphone_reposts_YYYYMMDD.md を読み込み、ボタン操作で
1件ずつ手動でXにリプライを投稿するためのローカル用Webアプリ。

起動方法:
    pip install -r requirements.txt
    python webapp/app.py
起動後 http://127.0.0.1:5001 をブラウザで開く。

認証情報は scripts/ 配下のスクリプトと同じ環境変数
(GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REFRESH_TOKEN /
GOOGLE_DRIVE_FOLDER_ID / X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET)
をリポジトリ直下の .env から読み込む。自分だけがローカルで使うことを想定しており、
認証や公開アクセス対策は行っていない。
"""

import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

load_dotenv()

from drive_reply_common import (  # noqa: E402
    fetch_markdown_from_drive,
    get_x_client,
    parse_posts,
    post_reply,
    today_jst_str,
)

app = Flask(__name__)

STATUS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def status_path_for(date_str):
    return os.path.join(STATUS_DIR, f"manual_reply_status_{date_str}.json")


def load_status(date_str):
    path = status_path_for(date_str)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_status(date_str, status):
    os.makedirs(STATUS_DIR, exist_ok=True)
    with open(status_path_for(date_str), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def load_posts_for(date_str):
    filename = f"iphone_reposts_{date_str}.md"
    markdown_text = fetch_markdown_from_drive(filename)
    if markdown_text is None:
        return filename, None
    return filename, parse_posts(markdown_text)


@app.route("/")
def index():
    return render_template("index.html", today=today_jst_str())


@app.route("/api/posts")
def api_posts():
    date_str = request.args.get("date", today_jst_str())
    filename, posts = load_posts_for(date_str)
    if posts is None:
        return jsonify({"error": f"{filename} がGoogle Driveに見つかりませんでした。"}), 404

    status = load_status(date_str)
    result = []
    for post in posts:
        entry = status.get(post["id"], {})
        result.append(
            {
                "id": post["id"],
                "url": post["url"],
                "source_text": post["source_text"],
                "reply": post["reply"],
                "status": entry.get("status", "pending"),
                "reply_id": entry.get("reply_id"),
                "error": entry.get("error"),
                "posted_at": entry.get("posted_at"),
            }
        )
    return jsonify({"filename": filename, "posts": result})


@app.route("/api/post", methods=["POST"])
def api_post():
    body = request.get_json(force=True)
    date_str = body.get("date")
    tweet_id = body.get("id")
    if not date_str or not tweet_id:
        return jsonify({"error": "date と id は必須です。"}), 400

    _, posts = load_posts_for(date_str)
    if posts is None:
        return jsonify({"error": "対象のMarkdownファイルが見つかりませんでした。"}), 404

    post = next((p for p in posts if p["id"] == tweet_id), None)
    if post is None:
        return jsonify({"error": "指定されたポストが見つかりませんでした。"}), 404

    status = load_status(date_str)
    now = datetime.now(timezone.utc).isoformat()
    try:
        client = get_x_client()
        reply_id = post_reply(client, tweet_id, post["reply"])
        status[tweet_id] = {"status": "posted", "reply_id": reply_id, "posted_at": now}
        save_status(date_str, status)
        return jsonify({"status": "posted", "reply_id": reply_id})
    except Exception as e:
        status[tweet_id] = {"status": "failed", "error": str(e), "posted_at": now}
        save_status(date_str, status)
        return jsonify({"status": "failed", "error": str(e)}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5001)
