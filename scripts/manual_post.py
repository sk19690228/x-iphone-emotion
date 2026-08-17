"""
GitHub Actions の workflow_dispatch から、指定した1件のポストへ
手動でXにリプライを投稿するスクリプト。

投稿対象の tweet_id は、generate_pages_list.py が生成する
GitHub Pages の一覧ページに表示されるIDをコピーして指定する想定。
"""

import os
import sys
from datetime import datetime, timezone

from drive_reply_common import (
    fetch_markdown_from_drive,
    get_x_client,
    load_status,
    parse_posts,
    post_reply,
    save_status,
    today_jst_str,
)


def main():
    tweet_id = os.environ.get("TWEET_ID", "").strip()
    if not tweet_id:
        print("[ERROR] TWEET_ID が指定されていません。")
        sys.exit(1)

    date_str = os.environ.get("TARGET_DATE", "").strip() or today_jst_str()
    filename = f"iphone_reposts_{date_str}.md"

    markdown_text = fetch_markdown_from_drive(filename)
    if markdown_text is None:
        print(f"[ERROR] {filename} がGoogle Driveに見つかりませんでした。")
        sys.exit(1)

    posts = parse_posts(markdown_text)
    post = next((p for p in posts if p["id"] == tweet_id), None)
    if post is None:
        print(f"[ERROR] tweet_id={tweet_id} は {filename} 内に見つかりませんでした。")
        sys.exit(1)

    status = load_status(date_str)
    existing = status.get(tweet_id)
    if existing and existing.get("status") == "posted":
        print(f"[INFO] {tweet_id} は既に投稿済みです (reply_id={existing.get('reply_id')})。")
        return

    now = datetime.now(timezone.utc).isoformat()
    client = get_x_client()
    try:
        reply_id = post_reply(client, tweet_id, post["reply"])
        status[tweet_id] = {"status": "posted", "reply_id": reply_id, "posted_at": now}
        save_status(date_str, status)
        print(f"[SUCCESS] {tweet_id} へリプライしました (reply_id={reply_id})")
    except Exception as e:
        status[tweet_id] = {"status": "failed", "error": str(e), "posted_at": now}
        save_status(date_str, status)
        print(f"[ERROR] {tweet_id} へのリプライに失敗しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
