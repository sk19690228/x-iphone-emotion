"""
Google Drive 用の OAuth リフレッシュトークンを取得するための、
ローカル環境で一度だけ実行するスクリプト。

事前準備:
    1. Google Cloud Console で OAuth クライアント（アプリケーションの種類:
       デスクトップアプリ）を作成する。
    2. ダウンロードした JSON を client_secret.json という名前でこの
       スクリプトと同じディレクトリに置く。

実行:
    python scripts/get_google_refresh_token.py

ブラウザが開くので Google アカウントでログイン・許可すると、
ターミナルに client_id / client_secret / refresh_token が表示される。
これらを GitHub Secrets の
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN
に設定する。
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n=== 以下を GitHub Secrets に設定してください ===")
    print(f"GOOGLE_OAUTH_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_OAUTH_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
