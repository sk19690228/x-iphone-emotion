import os
from google import genai

# 環境変数からAPIキーを取得
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def main():
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY が設定されていません。")
        return

    print("=== 利用可能なモデル一覧を取得中 ===")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # APIサーバーから直接利用可能なモデル一覧を取得
        for m in client.models.list_models():
            # generateContent（コンテンツ生成）に対応しているモデルのみ表示
            if "generateContent" in m.supported_generation_methods:
                print(f"モデル名: {m.name}")
                
        print("====================================")
        print("上記に表示された『models/...』の『...』の部分が現在使える正しいモデル名です。")
        
    except Exception as e:
        print(f"[ERROR] 一覧の取得に失敗しました: {e}")

if __name__ == "__main__":
    main()
