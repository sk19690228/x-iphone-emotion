import os
from google_auth_oauthlib.flow import InstalledAppFlow

# 利用したいGoogle APIのスコープを指定（例：Googleドライブ、スプレッドシートなど）
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    # Google Cloud Consoleからダウンロードした認証情報ファイルのパス
    client_secrets_path = 'credentials.json' 
    
    if not os.path.exists(client_secrets_path):
        print(f"エラー: {client_secrets_path} が見つかりません。Google Cloudからダウンロードしてください。")
        return

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
    creds = flow.run_local_server(port=0)
    
    # 画面にリフレッシュトークンが表示されます
    print("\n--- 認証成功 ---")
    print(f"アクセストークン: {creds.token}")
    print(f"リフレッシュトークン: {creds.refresh_token}")

if __name__ == '__main__':
    main()
