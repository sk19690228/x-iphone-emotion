"""
X 自動リプライボットの共通ユーティリティ。

Google Drive 上の iphone_reposts_YYYYMMDD.md を読み込み、
X API v2 (OAuth 1.0a User Context) でリプライを投稿するための
共通処理をまとめている。plan_replies.py / post_reply.py から利用する。

--- iphone_reposts_YYYYMMDD.md のフォーマット ---

## [1]
- ID: 1234567890123456789
- URL: https://twitter.com/i/web/status/1234567890123456789
- 本文: 元ポストの本文（任意）
- リプライ: この投稿へ返信する文章

## [2]
...

ID と URL はどちらか一方があればよい（URL からポストIDを自動抽出する）。
リプライ は必須。
"""

import io
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


_FIELD_RE = re.compile(r"^-\s*([^:：]+)[:：]\s*(.*)$")
_TWEET_ID_RE = re.compile(r"status/(\d+)")
_HEADER_SPLIT_RE = re.compile(r"(?=^##\s*\[\d+\])", re.MULTILINE)


def parse_posts(markdown_text):
    posts = []
    for block in _HEADER_SPLIT_RE.split(markdown_text):
        block = block.strip()
        if not block.startswith("##"):
            continue

        fields = {}
        for line in block.splitlines()[1:]:
            m = _FIELD_RE.match(line.strip())
            if m:
                fields[m.group(1).strip().upper()] = m.group(2).strip()

        tweet_id = fields.get("ID")
        url = fields.get("URL")
        if not tweet_id and url:
            m = _TWEET_ID_RE.search(url)
            if m:
                tweet_id = m.group(1)
        reply_text = fields.get("リプライ") or fields.get("REPLY")

        if not tweet_id or not reply_text:
            continue

        posts.append(
            {
                "id": tweet_id,
                "url": url,
                "source_text": fields.get("本文") or fields.get("TEXT"),
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
