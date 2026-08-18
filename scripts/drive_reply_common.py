"""
X 自動リプライボットの共通ユーティリティ。

Google Drive 上の iphone_reposts_YYYYMMDD.md を読み込み、
X API v2 (OAuth 1.0a User Context) でリプライを投稿するための
共通処理をまとめている。plan_replies.py / manual_post.py /
generate_pages_list.py から利用する。

--- iphone_reposts_YYYYMMDD.md のフォーマット ---

## 1
**元ポスト文**
元ポストの本文（任意、記録用。複数行可）

**URL**
https://twitter.com/i/web/status/1234567890123456789

**リポスト文**
```
この投稿へ返信する文章（複数行可）
```

## 2
...

URL からポストIDを自動抽出する。**リポスト文** のコードブロック内の
テキストがそのままリプライとして投稿される。

**リポスト文** が無いポストも許容する（この場合 parse_posts() は
reply を None で返す）。返信文をClaude Codeが別途作成し、
results/replies_YYYYMMDD.json（{tweet_id: reply_text}）に保存する
運用のため。generate_pages_list.py / manual_post.py は
parse_posts() の結果とこのファイルをマージして最終的な reply を決める。
"""

import io
import json
import os
import re
from datetime import datetime, timezone, timedelta

import tweepy
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

JST = timezone(timedelta(hours=9))

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

PLAN_DIR = "results"


def today_jst_str():
    return datetime.now(JST).strftime("%Y%m%d")


def plan_path_for(date_str):
    return os.path.join(PLAN_DIR, f"reply_plan_{date_str}.json")


def status_path_for(date_str):
    """手動投稿の状態(投稿済み/失敗)を記録するJSONファイルのパス。

    manual_post.py が投稿結果を書き込み、generate_pages_list.py が
    一覧ページのステータス表示に読み込む。
    """
    return os.path.join(PLAN_DIR, f"manual_reply_status_{date_str}.json")


def load_status(date_str):
    path = status_path_for(date_str)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_status(date_str, status):
    os.makedirs(PLAN_DIR, exist_ok=True)
    with open(status_path_for(date_str), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def replies_path_for(date_str):
    """Claude Codeが作成したリプライ文({tweet_id: reply_text})を保存するJSONファイルのパス。

    Drive上のmdに **リポスト文** が無い場合、ここから補われる。
    """
    return os.path.join(PLAN_DIR, f"replies_{date_str}.json")


def load_replies(date_str):
    path = replies_path_for(date_str)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_replies(date_str, replies):
    os.makedirs(PLAN_DIR, exist_ok=True)
    with open(replies_path_for(date_str), "w", encoding="utf-8") as f:
        json.dump(replies, f, ensure_ascii=False, indent=2)


def get_drive_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=DRIVE_SCOPES,
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


def fetch_markdown_from_drive(filename):
    service = get_drive_service()
    query = f"name = '{filename}' and trashed = false"
    if DRIVE_FOLDER_ID:
        query += f" and '{DRIVE_FOLDER_ID}' in parents"

    result = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    files = result.get("files", [])
    if not files:
        return None

    file_id = files[0]["id"]
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8")


_TWEET_ID_RE = re.compile(r"status/(\d+)")
_HEADER_SPLIT_RE = re.compile(r"(?=^##\s+\d+\s*$)", re.MULTILINE)
_SOURCE_RE = re.compile(r"\*\*元ポスト文\*\*\s*\n(.*?)\n\*\*URL\*\*", re.DOTALL)
_URL_RE = re.compile(r"\*\*URL\*\*\s*\n+(\S+)")
_REPOST_RE = re.compile(r"\*\*リポスト文\*\*\s*\n```[^\n]*\n(.*?)\n```", re.DOTALL)


def parse_posts(markdown_text):
    posts = []
    for block in _HEADER_SPLIT_RE.split(markdown_text):
        block = block.strip()
        if not re.match(r"^##\s+\d+", block):
            continue

        url_match = _URL_RE.search(block)
        if not url_match:
            continue

        url = url_match.group(1).strip()

        tweet_id_match = _TWEET_ID_RE.search(url)
        if not tweet_id_match:
            continue

        repost_match = _REPOST_RE.search(block)
        reply_text = repost_match.group(1).strip() if repost_match else None

        source_match = _SOURCE_RE.search(block)
        source_text = source_match.group(1).strip() if source_match else None

        posts.append(
            {
                "id": tweet_id_match.group(1),
                "url": url,
                "source_text": source_text,
                "reply": reply_text,
            }
        )
    return posts


def get_x_client():
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post_reply(client, tweet_id, reply_text):
    response = client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
    return response.data["id"]
