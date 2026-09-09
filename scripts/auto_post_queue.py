"""
毎日 AM6:00 頃から、その日分のリプライ文（①パターン目）を
30〜90分間隔でXへ自動投稿するためのスクリプト。

.github/workflows/auto_post.yml から短い間隔（10分おき）で繰り返し
実行され、当日分のキュー（results/auto_post_queue_YYYYMMDD.json）を見て
「次に投稿する時刻」が来ていれば1件だけ投稿し、次回の投稿時刻を
30〜90分後のランダムな時刻に再設定する。時間帯の制限は設けず、
その日の投稿が尽きるまで続ける。
"""

import json
import os
import random
from datetime import datetime, timedelta, timezone

from drive_reply_common import (
    PLAN_DIR,
    get_x_client,
    load_replies,
    load_status,
    post_reply,
    save_status,
    today_jst_str,
)

MIN_INTERVAL_MIN = 30
MAX_INTERVAL_MIN = 90


def queue_path_for(date_str):
    return os.path.join(PLAN_DIR, f"auto_post_queue_{date_str}.json")


def load_queue(date_str):
    path = queue_path_for(date_str)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(date_str, queue):
    os.makedirs(PLAN_DIR, exist_ok=True)
    with open(queue_path_for(date_str), "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def main():
    date_str = today_jst_str()
    replies = load_replies(date_str)
    if not replies:
        print(f"[INFO] {date_str} 分のリプライ文がまだ作成されていません。")
        return

    status = load_status(date_str)
    now = datetime.now(timezone.utc)

    queue = load_queue(date_str)
    if queue is None:
        order = list(replies.keys())
        pending = [tid for tid in order if status.get(tid, {}).get("status") != "posted"]
        queue = {"pending": pending, "next_post_at": now.isoformat()}
        save_queue(date_str, queue)
        print(f"[INFO] {date_str} 分の投稿キューを作成しました（{len(pending)}件）。")

    pending = [tid for tid in queue["pending"] if status.get(tid, {}).get("status") != "posted"]
    if not pending:
        print(f"[INFO] {date_str} 分は全て投稿済みです。")
        queue["pending"] = []
        save_queue(date_str, queue)
        return

    next_post_at = datetime.fromisoformat(queue["next_post_at"])
    if now < next_post_at:
        print(f"[INFO] 次の投稿予定は {next_post_at.isoformat()} です。まだ時間ではありません。")
        queue["pending"] = pending
        save_queue(date_str, queue)
        return

    tweet_id = pending[0]
    reply_text = replies.get(tweet_id)
    if isinstance(reply_text, list):
        # ①パターン目（配列の先頭）を自動投稿に使う。
        reply_text = reply_text[0] if reply_text else None

    if not reply_text:
        print(f"[WARN] {tweet_id} のリプライ文が空のためスキップします。")
        pending = pending[1:]
        queue["pending"] = pending
        queue["next_post_at"] = now.isoformat()
        save_queue(date_str, queue)
        return

    client = get_x_client()
    try:
        reply_id = post_reply(client, tweet_id, reply_text)
        status[tweet_id] = {
            "status": "posted",
            "reply_id": reply_id,
            "posted_at": now.isoformat(),
        }
        save_status(date_str, status)
        print(f"[SUCCESS] {tweet_id} へ自動リプライしました (reply_id={reply_id})")
    except Exception as e:
        status[tweet_id] = {
            "status": "failed",
            "error": str(e),
            "posted_at": now.isoformat(),
        }
        save_status(date_str, status)
        print(f"[ERROR] {tweet_id} への自動リプライに失敗しました: {e}")

    pending = pending[1:]
    interval_min = random.uniform(MIN_INTERVAL_MIN, MAX_INTERVAL_MIN)
    queue["pending"] = pending
    queue["next_post_at"] = (now + timedelta(minutes=interval_min)).isoformat()
    save_queue(date_str, queue)
    print(
        f"[INFO] 次の自動投稿は {queue['next_post_at']} 頃の予定です"
        f"（残り{len(pending)}件）。"
    )


if __name__ == "__main__":
    main()
