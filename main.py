import os
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timedelta, timezone
import tweepy
from google import genai
from google.genai import types

# 環境変数の読み込み
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MAIL_ADDRESS = os.environ.get("MAIL_ADDRESS")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

if not all([X_BEARER_TOKEN, GEMINI_API_KEY, MAIL_ADDRESS, MAIL_PASSWORD]):
    raise ValueError("必要な環境変数（APIキーまたはメール設定）が不足しています。")

# 1. X API ポスト取得
def fetch_recent_tweets(query="IPHONE -is:retweet lang:ja", max_count=100):
    client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
    now_utc = datetime.now(timezone.utc)
    start_time = now_utc - timedelta(hours=24)
    
    try:
        response = client.search_recent_tweets(
            query=query,
            start_time=start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            max_results=min(max_count, 100),
            tweet_fields=["created_at", "public_metrics"]
        )
        if not response.data:
            return []
        return [{"id": t.id, "text": t.text, "url": f"https://x.com/i/status/{t.id}"} for t in response.data]
    except Exception as e:
        print(f"[ERROR] X API: {e}")
        return []

# 2. Gemini API 感情ポスト選定
# 2. Gemini API 感情ポスト選定
def analyze_and_select_emotional_posts(posts):
    if not posts:
        return []

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
以下は過去24時間に投稿された「IPHONE」に関するポスト群です。
この中から、人間らしい感情（歓喜、悲しみ、怒り、驚き、困惑、愛着など）が濃く出ている個人投稿を「最大30件」選んでください。

【除外対象】宣伝、アフィリエイト、懸賞、ボット(bot)、ニュース自動配信、事実のみの報告

【入力データ】
{json.dumps(posts, ensure_ascii=False, indent=2)}
"""

    try:
        # Interactions API または標準生成で安定動作する gemini-2.0-flash を使用
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="SNSから人間味あふれるリアルな感情投稿を特定するアナリストです。",
                temperature=0.2,
                response_mime_type="application/json",
                response_schema={
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING"},
                            "emotion": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                            "text": {"type": "STRING"},
                            "url": {"type": "STRING"}
                        },
                        "required": ["id", "emotion", "text", "url"]
                    }
                }
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERROR] Gemini API: {e}")
        return []

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
以下は過去24時間に投稿された「IPHONE」に関するポスト群です。
この中から、人間らしい感情（歓喜、悲しみ、怒り、驚き、困惑、愛着など）が濃く出ている個人投稿を「最大30件」選んでください。

【除外対象】宣伝、アフィリエイト、懸賞、ボット(bot)、ニュース自動配信、事実のみの報告

【入力データ】
{json.dumps(posts, ensure_ascii=False, indent=2)}
"""

    config = types.GenerateContentConfig(
        system_instruction="SNSから人間味あふれるリアルな感情投稿を特定するアナリストです。",
        temperature=0.2,
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "emotion": {"type": "STRING"},
                    "reason": {"type": "STRING"},
                    "text": {"type": "STRING"},
                    "url": {"type": "STRING"}
                },
                "required": ["id", "emotion", "text", "url"]
            }
        }
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERROR] Gemini API: {e}")
        return []

# 3. Gmail送信処理
def send_email(selected_posts):
    today_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"【X感情分析】iPhoneに関する注目ポスト 30選 ({today_str})"

    # メール本文の整形
    body_lines = [f"過去24時間の「iPhone」に関する感情豊かなポスト ({len(selected_posts)}件) です。\n", "="*50]
    
    for i, item in enumerate(selected_posts, 1):
        body_lines.append(f"\n■ No.{i} [{item.get('emotion', '感情')}]")
        body_lines.append(f"本文: {item.get('text')}")
        body_lines.append(f"URL : {item.get('url')}")
        body_lines.append("-" * 30)

    body = "\n".join(body_lines)

    # メール作成
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = MAIL_ADDRESS
    msg["To"] = MAIL_ADDRESS

    # Gmail SMTP サーバー経由で送信
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(MAIL_ADDRESS, MAIL_PASSWORD)
            server.send_message(msg)
        print("[SUCCESS] Gmail送信成功")
    except Exception as e:
        print(f"[ERROR] Gmail送信失敗: {e}")

def main():
    print("=== 処理開始 ===")
    raw_posts = fetch_recent_tweets()
    if not raw_posts:
        print("ポストが見つかりませんでした。")
        return

    selected_posts = analyze_and_select_emotional_posts(raw_posts)
    
    if selected_posts:
        send_email(selected_posts)
    else:
        print("選定されたポストがありませんでした。")

if __name__ == "__main__":
    main()
