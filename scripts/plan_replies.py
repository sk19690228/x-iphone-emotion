"""
毎朝 6:10 (JST) に実行するスクリプト。

Google Drive 上の iphone_reposts_YYYYMMDD.md を読み込み、
本日分のリプライ投稿スケジュール（30〜45分間隔）を算出して
results/reply_plan_YYYYMMDD.json に保存する。

実際の X への投稿は post_reply.py が別のワークフローで
定期的に実行され、このプランに沿って1件ずつ行う。
"""

import json
import os
import random
from datetime import datetime, timedelta, timezone

from drive_reply_common import (
    fetch_markdown_from_drive,
    parse_posts,
    plan_path_for,
    today_jst_str,
)

MIN_INTERVAL_MIN = 30
MAX_INTERVAL_MIN = 45
FIRST_POST_BUFFER_MIN = 2


def build_schedule(posts, start_time_utc):
    scheduled_at = start_time_utc + timedelta(minutes=FIRST_POST_BUFFER_MIN)
    plan = []
    for post in posts:
        plan.append(
            {
                "id": post["id"],
                "url": post["url"],
                "reply": post["reply"],
                "scheduled_at": scheduled_at.isoformat(),
                "status": "pending",
            }
        )
        scheduled_at += timedelta(minutes=random.uniform(MIN_INTERVAL_MIN, MAX_INTERVAL_MIN))
    return plan


def main():
    date_str = today_jst_str()
    plan_path = plan_path_for(date_str)

    if os.path.exists(plan_path):
        print(f"[INFO] {plan_path} は既に存在するため、再生成しません。")
        return

    filename = f"iphone_reposts_{date_str}.md"
    print(f"[INFO] Google Drive から {filename} を取得します。")
    markdown_text = fetch_markdown_from_drive(filename)
    if markdown_text is None:
        print(f"[WARN] {filename} が Google Drive に見つかりませんでした。")
        return

    posts = parse_posts(markdown_text)
    if not posts:
        print("[INFO] リプライ対象のポストがありませんでした。")
        return

    plan = build_schedule(posts, datetime.now(timezone.utc))

    os.makedirs(os.path.dirname(plan_path), exist_ok=True)
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "posts": plan}, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] {len(plan)} 件のリプライ予定を {plan_path} に保存しました。")


if __name__ == "__main__":
    main()
