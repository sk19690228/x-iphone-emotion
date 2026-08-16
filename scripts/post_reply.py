"""
15分おきに実行するスクリプト。

results/reply_plan_YYYYMMDD.json のうち、pending な投稿が残っている
最も古いものを確認し、予定時刻を過ぎている最初の未投稿ポストが
1件あれば X API v2 (OAuth 1.0a User Context) でリプライを投稿する。
「本日分」に限定しないため、日付をまたいでも取りこぼさない。

1回の実行につき最大1件のみ処理することで、
plan_replies.py が算出した 30〜45分間隔のスケジュールに沿って
順番に1件ずつリプライが投稿されるようにしている。
"""

import json
from datetime import datetime, timezone

from drive_reply_common import find_pending_plan_path, get_x_client, post_reply


def main():
    plan_path = find_pending_plan_path()

    if plan_path is None:
        print("[INFO] pending な投稿が残っているプランファイルはありません。")
        return

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    pending = [p for p in plan["posts"] if p["status"] == "pending"]
    if not pending:
        print("[INFO] 本日分のリプライは全て処理済みです。")
        return

    target = pending[0]
    scheduled_at = datetime.fromisoformat(target["scheduled_at"])
    now = datetime.now(timezone.utc)

    if scheduled_at > now:
        print(f"[INFO] 次のリプライ予定は {scheduled_at.isoformat()} です。まだ時間ではありません。")
        return

    client = get_x_client()
    try:
        reply_id = post_reply(client, target["id"], target["reply"])
        target["status"] = "posted"
        target["reply_id"] = reply_id
        target["posted_at"] = now.isoformat()
        print(f"[SUCCESS] {target['id']} へリプライしました (reply_id={reply_id})")
    except Exception as e:
        target["status"] = "failed"
        target["error"] = str(e)
        target["posted_at"] = now.isoformat()
        print(f"[ERROR] {target['id']} へのリプライに失敗しました: {e}")

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
