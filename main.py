import os
import json
from datetime import datetime, timedelta, timezone
import tweepy
from dotenv import load_dotenv
from google import genai
from google.genai import types

# .env ファイルから環境変数を読み込み
load_dotenv()

X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not X_BEARER_TOKEN or not GEMINI_API_KEY:
    raise ValueError("環境変数 (X_BEARER_TOKEN または GEMINI_API_KEY) が設定されていません。")

# 1. X API から過去24時間のポストを取得
def fetch_recent_tweets(query="IPHONE -is:retweet lang:ja", max_count=100):
    client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
    
    # 過去24時間（UTC）を指定
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
            print("[INFO] 対象のポストが見つかりませんでした。")
            return []
            
        posts = []
        for tweet in response.data:
            posts.append({
                "id": tweet.id,
                "text": tweet.text,
                "url": f"https://x.com/i/status/{tweet.id}"
            })
        return posts

    except Exception as e:
        print(f"[ERROR] X API取得失敗: {e}")
        return []

# 2. Gemini API で感情豊かなポストを30件選定
def analyze_and_select_emotional_posts(posts):
    if not posts:
        return []

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
以下は過去24時間に投稿された「IPHONE」に関するポスト群です。
この中から、人間らしい感情（歓喜、悲しみ、怒り、驚き、困惑、愛着など）が濃く出ている個人投稿を「最大30件」選んでください。

【厳格な除外対象】
- 宣伝、アフィリエイト、懸賞・キャンペーン、ボット(bot)、ニュース自動配信
- 単なる性能紹介や感情の伴わない事実報告

【入力データ】
{json.dumps(posts, ensure_ascii=False, indent=2)}
"""

    # Geminiにレスポンス構造（JSON）を指示
    config = types.GenerateContentConfig(
        system_instruction="あなたはSNSから人間味あふれるリアルな感情投稿を特定するリサーチャーです。",
        temperature=0.2,
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "emotion": {"type": "STRING", "description": "分類された感情（例: 歓喜, 困惑, 怒り）"},
                    "reason": {"type": "STRING", "description": "選定理由・感情の背景"},
                    "text": {"type": "STRING"},
                    "url": {"type": "STRING"}
                },
                "required": ["id", "emotion", "text", "url"]
            }
        }
    )

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=config
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERROR] Gemini API処理失敗: {e}")
        return []

# 3. メイン処理と結果出力
def main():
    print(f"=== 処理開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    # ポスト取得
    raw_posts = fetch_recent_tweets()
    print(f"[INFO] 取得ポスト数: {len(raw_posts)} 件")
    
    if not raw_posts:
        return

    # LLM分析
    selected_posts = analyze_and_select_emotional_posts(raw_posts)
    print(f"[INFO] 厳選ポスト数: {len(selected_posts)} 件")

    # 結果を日付別のJSONファイルとして保存
    os.makedirs("results", exist_ok=True)
    filename = f"results/emotional_iphone_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(selected_posts, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] 保存完了: {filename}")

if __name__ == "__main__":
    main()