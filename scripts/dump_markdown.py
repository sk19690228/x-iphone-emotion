"""
指定日（省略時は当日 JST）の iphone_reposts_YYYYMMDD.md を
Google Driveから取得し、標準出力にそのまま出力する。

毎日のリプライ文自動作成フロー（GitHub Actionsの workflow_dispatch
経由で起動し、実行ログから本文を取り出す）で使うための恒久スクリプト。
"""

import os
import sys

from drive_reply_common import fetch_markdown_from_drive, today_jst_str


def main():
    date_str = os.environ.get("TARGET_DATE", "").strip() or today_jst_str()
    filename = f"iphone_reposts_{date_str}.md"

    print(f"[INFO] Google Drive から {filename} を取得します。")
    markdown_text = fetch_markdown_from_drive(filename)
    if markdown_text is None:
        print(f"[WARN] {filename} が Google Drive に見つかりませんでした。")
        sys.exit(1)

    print(f"[INFO] {filename} を取得しました（{len(markdown_text)}文字）。")
    print("[DUMP-START]")
    print(markdown_text)
    print("[DUMP-END]")


if __name__ == "__main__":
    main()
