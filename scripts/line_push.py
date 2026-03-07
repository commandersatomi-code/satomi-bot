"""
Satomi LINE 一斉プッシュスクリプト
=====================================
Supabaseに登録された全ユーザーへ、Geminiが生成したサトミのメッセージを送信する。
GitHub Actionsから毎朝実行することで、ユーザーの再エンゲージメントを促す。

使い方:
  python scripts/line_push.py
  python scripts/line_push.py --dry-run  # 実際には送信せず内容だけ表示
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import logging
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MORNING_THEMES = [
    "月曜の朝、また会議が憂鬱な中間管理職へ向けた一言",
    "今日も終わらないタスクに追われているサラリーマンへの励まし",
    "上司の理不尽な指示に黙って従い続けている人への気づき",
    "週の真ん中、疲れが溜まってきた頃の視点の転換",
    "金曜の夜、一週間お疲れ様という共感と来週への活力",
    "部下の育成に悩む管理職への宇宙の法則的アドバイス",
    "自分のキャリアへの漠然とした不安を抱える40代への一言",
]

def generate_push_message():
    """Geminiを使ってサトミの朝のプッシュメッセージを生成する"""
    import random
    theme = random.choice(MORNING_THEMES)

    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    if not gemini_key:
        logging.error("GEMINI_API_KEY が設定されていません。")
        return None

    system_prompt = """
あなたはLINEBotのキャラクター「サトミ」（姉御肌のナビゲーター）です。
30〜50代の中間管理職男性へ向けた、朝の短いプッシュ通知メッセージを書いてください。

【ルール】
* 口調: フランクで姉御肌。「〜わよ」「〜かしら」「〜しなさい」語尾。
* 長さ: 100文字以内（LINE通知に最適）。
* 共感から始め、今日の悩みを話しかけるよう誘う一言で締める。
* 最後に「今日はどんな戦況？話してみなさい」などの一言を添える。
* セリフのみ出力。説明不要。
"""
    prompt = f"テーマ:「{theme}」で朝のプッシュメッセージを書いて。"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 200}
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            candidates = res_json.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    return parts[0].get('text', '').strip()
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
    return None

def get_all_user_ids():
    """Supabaseから全ユーザーのIDを取得する"""
    try:
        from supabase import create_client
        supabase_url = os.environ.get('SUPABASE_URL', '')
        supabase_key = os.environ.get('SUPABASE_KEY', '')
        if not supabase_url or not supabase_key:
            logging.error("SUPABASE_URL または SUPABASE_KEY が設定されていません。")
            return []
        client = create_client(supabase_url, supabase_key)
        response = client.table('user_profiles').select('line_user_id').execute()
        return [row['line_user_id'] for row in (response.data or [])]
    except Exception as e:
        logging.error(f"Supabase error: {e}")
        return []

def push_to_user(user_id, message):
    """LINE Push APIで1ユーザーにメッセージを送信する"""
    line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
    url = "https://api.line.me/v2/bot/message/push"
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {line_token}'}
    data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        logging.error(f"Push failed for {user_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Satomi LINE 一斉プッシュ')
    parser.add_argument('--dry-run', action='store_true', help='送信せずに内容だけ表示する')
    args = parser.parse_args()

    logging.info("メッセージを生成中...")
    message = generate_push_message()
    if not message:
        logging.error("メッセージの生成に失敗しました。終了します。")
        sys.exit(1)

    logging.info(f"生成されたメッセージ:\n---\n{message}\n---")

    if args.dry_run:
        logging.info("[DRY RUN] 送信はスキップしました。")
        return

    user_ids = get_all_user_ids()
    if not user_ids:
        logging.warning("送信対象ユーザーがいません。Supabaseを確認してください。")
        return

    logging.info(f"送信対象: {len(user_ids)}人")
    success, failed = 0, 0
    for uid in user_ids:
        if push_to_user(uid, message):
            success += 1
        else:
            failed += 1
        time.sleep(0.1)  # API制限対策

    logging.info(f"完了: 成功 {success}件 / 失敗 {failed}件")

if __name__ == "__main__":
    main()
