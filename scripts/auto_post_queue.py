"""
その日だけでなく、まだ投稿されていない過去分（バックログ）も含めて、
古い日付から順に①パターン目のリプライ文を30〜90分間隔でXへ自動投稿する
スクリプト。

.github/workflows/auto_post.yml から短い間隔（10分おき）で繰り返し
実行され、results/replies_YYYYMMDD.json が存在する全ての日付を走査して
まだ投稿されていない(pending)ものを日付の古い順・ファイル内の並び順で
1件だけ選び、「次に投稿する時刻」が来ていれば投稿する。投稿後は次回の
投稿時刻を30〜90分後のランダムな時刻に再設定する。時間帯の制限は設けず、
バックログも含めて尽きるまで続ける。

前回の実装は当日分(today_jst_str())のreplies_*.jsonしか見ておらず、
日付が変わると前日分の未投稿分が永久に取り残される問題があったため、
全日付を毎回スキャンする方式に変更した。
"""

import json
import os
import random
import re
from datetime import datetime, timedelta, timezone

from drive_reply_common import (
    PLAN_DIR,
    get_x_client,
    load_replies,
    load_status,
    post_reply,
    save_status,
)

MIN_INTERVAL_MIN = 30
MAX_INTERVAL_MIN = 90

STATE_PATH = os.path.join(PLAN_DIR, "auto_post_state.json")
_REPLIES_FILE_RE = re.compile(r"^replies_(\d{8})\.json$")


def _all_reply_dates():
    if not os.path.isdir(PLAN_DIR):
        return []
    dates = []
    for name in os.listdir(PLAN_DIR):
        m = _REPLIES_FILE_RE.match(name)
        if m:
            dates.append(m.group(1))
    return sorted(dates)


def _collect_pending():
    """未投稿のリプライを (date_str, tweet_id, reply_text) のリストで返す。

    日付の古い順、各日付内はreplies_*.jsonの並び順(=元ポストの登場順)。
    """
    pending = []
    for date_str in _all_reply_dates():
        replies = load_replies(date_str)
        if not replies:
            continue
        status = load_status(date_str)
        for tweet_id, reply_text in replies.items():
            if status.get(tweet_id, {}).get("status") == "posted":
                continue
            if isinstance(reply_text, list):
                # ①パターン目（配列の先頭）を自動投稿に使う。
                reply_text = reply_text[0] if reply_text else None
            if not reply_text:
                continue
            pending.append((date_str, tweet_id, reply_text))
    return pending


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    os.makedirs(PLAN_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    pending = _collect_pending()
    if not pending:
        print("[INFO] 未投稿のリプライはありません。")
        return

    now = datetime.now(timezone.utc)
    state = load_state()
    next_post_at_str = state.get("next_post_at")
    next_post_at = datetime.fromisoformat(next_post_at_str) if next_post_at_str else now

    if now < next_post_at:
        print(
            f"[INFO] 次の投稿予定は {next_post_at.isoformat()} です。"
            f"まだ時間ではありません（残り{len(pending)}件）。"
        )
        return

    date_str, tweet_id, reply_text = pending[0]
    status = load_status(date_str)

    client = get_x_client()
    try:
        reply_id = post_reply(client, tweet_id, reply_text)
        status[tweet_id] = {
            "status": "posted",
            "reply_id": reply_id,
            "posted_at": now.isoformat(),
        }
        save_status(date_str, status)
        print(f"[SUCCESS] {date_str} {tweet_id} へ自動リプライしました (reply_id={reply_id})")
    except Exception as e:
        status[tweet_id] = {
            "status": "failed",
            "error": str(e),
            "posted_at": now.isoformat(),
        }
        save_status(date_str, status)
        print(f"[ERROR] {date_str} {tweet_id} への自動リプライに失敗しました: {e}")

    interval_min = random.uniform(MIN_INTERVAL_MIN, MAX_INTERVAL_MIN)
    state["next_post_at"] = (now + timedelta(minutes=interval_min)).isoformat()
    save_state(state)
    remaining = len(pending) - 1
    print(
        f"[INFO] 次の自動投稿は {state['next_post_at']} 頃の予定です"
        f"（残り{remaining}件）。"
    )


if __name__ == "__main__":
    main()
