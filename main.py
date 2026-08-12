import os
import json
import requests
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from openai import OpenAI  # Grok APIはOpenAI互換クライアントで呼び出せます

# --- 環境変数設定 ---
XAI_API_KEY = os.environ.get("XAI_API_KEY")
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN")
MAIL_ADDRESS = os.environ.get("MAIL_ADDRESS")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_TO = os.environ.get("MAIL_TO")

# 1. X (Twitter) API からポストを取得
def fetch_iphone_posts():
    if not X_BEARER_TOKEN:
        print("[ERROR] X_BEARER_TOKEN が設定されていません。")
        return []

    url = "https://api.x.com/2/tweets/search/recent"
    
    # 24時間前の時刻をISO 8601形式で生成
    JST = timezone(timedelta(hours=+9))
    since_time = (datetime.now(JST) - timedelta(days=1)).isoformat()
    
    query = "IPHONE -is:retweet -is:reply lang:ja"
    params = {
        "query": query,
        "max_results": 50,
        "start_time": since_time,
        "tweet.fields": "author_id,created_at,text"
    }
    headers = {
        "Authorization": f"Bearer {X_BEARER_TOKEN}"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 402:
            print("[ERROR] X API: 402 Payment Required (クレジットを使い切っています)")
            return []
        
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] X API 取得失敗: {e}")
        return []

# 2. Grok API (xAI) を使った感情ポスト選定
def analyze_and_select_emotional_posts(posts):
    if not posts:
        return []

    # Grok APIクライアントの初期化（base_urlに xAI のエンドポイントを指定）
    client = OpenAI(
        api_key=XAI_API_KEY,
        base_url="https://api.x.ai/v1"
    )

    prompt = f"""
あなたはSNSから人間味あふれるリアルな感情投稿を特定するアナリストです。
以下は過去24時間に投稿された「iPhone」に関するポスト群です。
この中から、人間らしい感情（歓喜、悲しみ、怒り、驚き、困惑、愛着など）が濃く出ている個人投稿を「最大30件」選んでください。

【除外対象】宣伝、アフィリエイト、懸賞、ボット(bot)、ニュース自動配信、事実のみの報告

【出力フォーマット】
必ず以下のキーを持つJSON配列(ARRAY)形式のみで出力してください。マークダウンのコードブロックや解説は一切含めず、純粋なJSON文字列のみを返してください。
[
  {{
    "text": "本文",
    "url": "https://twitter.com/i/web/status/ポストID"
  }}
]

【入力データ】
{json.dumps(posts, ensure_ascii=False, indent=2)}
"""

    try:
        # Grokの最新モデルを指定
        response = client.chat.completions.create(
            model="grok-4.5",
            messages=[
                {"role": "system", "content": "あなたは厳格なJSON出力アシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        res_text = response.choices[0].message.content.strip()
        
        # マークダウンのコードブロックが含まれていた場合の保険処理
        if res_text.startswith("```json"):
            res_text = res_text[7:]
        elif res_text.startswith("```"):
            res_text = res_text[3:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]
            
        return json.loads(res_text.strip())
    except Exception as e:
        print(f"[ERROR] Grok API: {e}")
        return []

# 3. Gmail 送信
def send_email(selected_posts):
    if not MAIL_ADDRESS or not MAIL_PASSWORD or not MAIL_TO:
        print("[ERROR] メール設定が不足しています。")
        return

    subject = f"【Grok選定】iPhoneの感情豊かなポスト通知 ({datetime.now().strftime('%Y-%m-%d')})"
    
    body = f"Grokによる感情分析結果（全 {len(selected_posts)} 件）\n\n"
    for i, post in enumerate(selected_posts, 1):
        body += f"--- [{i}] 感情: {post.get('emotion')} ---\n"
        body += f"理由: {post.get('reason')}\n"
        body += f"本文: {post.get('text')}\n"
        body += f"URL: [https://twitter.com/x/status/](https://twitter.com/x/status/){post.get('id')}\n\n"

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = MAIL_ADDRESS
    msg['To'] = MAIL_TO
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(MAIL_ADDRESS, MAIL_PASSWORD)
            server.sendmail(MAIL_ADDRESS, MAIL_TO, msg.as_string())
        print("[SUCCESS] Gmail送信成功")
    except Exception as e:
        print(f"[ERROR] Gmail送信失敗: {e}")

# --- メイン処理 ---
def main():
    print("=== 処理開始 ===")
    posts = fetch_iphone_posts()
    
    if not posts:
        print("ポストが見つかりませんでした。")
        return

    selected_posts = analyze_and_select_emotional_posts(posts)
    
    if not selected_posts:
        print("選定されたポストがありませんでした。")
        return

    send_email(selected_posts)

if __name__ == "__main__":
    main()
