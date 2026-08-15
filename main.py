import json
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

JST = timezone(timedelta(hours=9))


# 1. X (Twitter) API からポストを取得
def fetch_iphone_posts():
    if not X_BEARER_TOKEN:
        print("[ERROR] X_BEARER_TOKEN が設定されていません。")
        return []

    url = "https://api.x.com/2/tweets/search/recent"

    since_time = (datetime.now(JST) - timedelta(days=1)).isoformat()

    query = "IPHONE -is:retweet -is:reply lang:ja"
    params = {
        "query": query,
        "max_results": 50,
        "start_time": since_time,
        "tweet.fields": "author_id,created_at,text",
    }
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 402:
            print("[ERROR] X API: 402 Payment Required")
            return []

        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] X API 取得失敗: {e}")
        return []


# 2. Gemini API を使った感情ポスト選定
def analyze_and_select_emotional_posts(posts):
    if not posts:
        return []

    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY が設定されていません。")
        return []

    prompt = f"""
あなたはSNSから人間味あふれるリアルな感情投稿を特定するアナリストです。
以下は過去24時間に投稿された「IPHONE」に関するポスト群です。
この中から、人間らしい感情（歓喜、悲しみ、怒り、驚き、困惑、愛着など）が濃く出ている個人投稿を「最大30件」選んでください。

【除外対象】宣伝、アフィリエイト、懸賞、ボット(bot)、ニュース自動配信、事実のみの報告

【出力フォーマット】
必ず以下のキーを持つJSON配列(ARRAY)形式のみで出力してください。マークダウンのコードブロックや解説は一切含めず、純粋なJSON文字列のみを返してください。
[
  {{
    "id": "ポストID",
    "emotion": "感情分類",
    "reason": "選定理由",
    "text": "本文",
    "url": "https://twitter.com/i/web/status/ポストID"
  }}
]

【入力データ】
{json.dumps(posts, ensure_ascii=False, indent=2)}
"""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="あなたは厳格なJSON出力アシスタントです。",
                temperature=0.2,
            ),
        )

        res_text = response.text.strip()

        if res_text.startswith("```json"):
            res_text = res_text[7:]
        elif res_text.startswith("```"):
            res_text = res_text[3:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]

        return json.loads(res_text.strip())
    except Exception as e:
        print(f"[ERROR] Gemini API: {e}")
        return []


# 3. 選定結果を results/ に JSON 保存
def save_results(selected_posts):
    os.makedirs("results", exist_ok=True)
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    path = f"results/emotional_iphone_{timestamp}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(selected_posts, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] {path} に保存しました（{len(selected_posts)}件）")


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

    save_results(selected_posts)


if __name__ == "__main__":
    main()
