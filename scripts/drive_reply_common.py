"""
X 自動リプライボットの共通ユーティリティ。

Google Drive 上の iphone_reposts_YYYYMMDD.md を読み込み、
X API v2 (OAuth 1.0a User Context) でリプライを投稿するための
共通処理をまとめている。plan_replies.py / post_reply.py から利用する。

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


def find_pending_plan_path():
    """pending な投稿が残っている中で最も古いプランファイルのパスを返す。

    post_reply.py は15分おきに実行されるため、日付をまたいで実行が
    続いても（例: X APIの一時的な問題で投稿が遅れた場合など）、
    「本日分」に限定せず取りこぼしなく処理できるようにする。
    """
    if not os.path.isdir(PLAN_DIR):
        return None

    for filename in sorted(os.listdir(PLAN_DIR)):
        if not (filename.startswith("reply_plan_") and filename.endswith(".json")):
            continue
        path = os.path.join(PLAN_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        if any(p["status"] == "pending" for p in plan["posts"]):
            return path
    return None


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
        repost_match = _REPOST_RE.search(block)
        if not url_match or not repost_match:
            continue

        url = url_match.group(1).strip()
        reply_text = repost_match.group(1).strip()

        tweet_id_match = _TWEET_ID_RE.search(url)
        if not tweet_id_match or not reply_text:
            continue

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
