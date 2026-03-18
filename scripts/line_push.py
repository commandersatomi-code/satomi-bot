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


def generate_push_message():
    """Geminiを使ってサトミの朝のプッシュメッセージを生成する"""
    import random
    from datetime import datetime, timezone, timedelta

    # 日本時間（UTC+9）で曜日を取得
    jst = timezone(timedelta(hours=9))
    weekday = datetime.now(jst).weekday()  # 0=月, 1=火, 2=水, 3=木, 4=金, 5=土, 6=日
    weekday_name = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"][weekday]

    # 曜日専用テーマ（今日の曜日に合うものだけ使う）
    DAY_SPECIFIC = {
        0: [  # 月曜
            "日曜の夜から始まる「月曜憂鬱」に毎週負け続けている人へ",
            "月曜朝、スーツを着ながら『また一週間か』と鏡を見た人へ",
            "月曜の朝礼が憂鬱で、声のトーンを作ることに疲れた人へ",
        ],
        2: [  # 水曜
            "水曜、もう限界なのにまだ週の半分しか過ぎていない人へ",
        ],
        3: [  # 木曜
            "木曜の朝、金曜を夢見ながら今日をなんとかやり過ごそうとしている人へ",
        ],
        4: [  # 金曜
            "金曜、今週もお疲れ様と言いたくても言ってもらえない人へ",
        ],
        5: [  # 土曜
            "週末なのに、月曜のことが頭から離れない人へ",
        ],
        6: [  # 日曜
            "日曜の朝、明日の憂鬱がもう始まっている人へ",
            "連休明け、休んだはずなのに全然リセットできていない人へ",
        ],
    }

    # 曜日に依存しない汎用テーマ
    GENERAL_THEMES = [
        "誰も決断しない会議で、一人だけムダな資料を作り続けている人へ",
        "上司の機嫌をうかがいながら仕事を進めることに疲れ果てた人へ",
        "理不尽な指示に『わかりました』と言い続けてきた人の本音",
        "役員プレゼンで、自分の言葉じゃない言葉を使わされている人へ",
        "怒られるのが怖くて、先手を打ちすぎて消耗している人へ",
        "部下に正論を言いたいのに、言えない自分に葛藤している人へ",
        "育てようとしているのに、全然伝わらないもどかしさを抱える人へ",
        "メンバーが辞めるたびに『自分のせいかも』と責めてしまう人へ",
        "部下を守りたい気持ちと、上に従わなければならない板挟みにいる人へ",
        "40代になって、自分が何のために働いているかわからなくなった人へ",
        "昇進したはずなのに、以前より全然楽しくなくなってしまった人へ",
        "定年まで何年と指折り数えるようになってしまった人への喝",
        "今の会社に居続けることが正解かどうか、毎晩考えている人へ",
        "転職したくても、家族のことを考えると動けない自分への問い",
        "怒りを飲み込みすぎて、何に怒っていたかも忘れてしまった人へ",
        "会社では笑顔、家では無口——二面性に疲れ始めている人へ",
        "『自分が我慢すれば』が口癖になってしまっている人へ",
        "疲れているのに、疲れを認めるのが怖くなっている人へ",
        "頑張っているのに誰にも気づかれない、透明人間みたいな気分の人へ",
        "誰かの役に立っているのか、社会に何かを残せているのか迷っている人へ",
        "ルーティンの連続で、自分の成長が感じられなくなった人へ",
        "いつの間にか、夢や熱中できることを持たなくなっていた人へ",
        "正しいことをしているはずなのに、全然ワクワクしない自分への問い",
        "社内政治に巻き込まれ、純粋に仕事に集中できなくなっている人へ",
        "信頼していた同期が先に出世して、複雑な気持ちを抱えている人へ",
        "同僚との微妙な距離感の維持に、毎日神経を使っている人へ",
        "仕事を持ち帰りたくないのに、頭がオフにならない人へ",
        "子どもの成長を横目に、自分が置いてきぼりになっている気がする父親へ",
        "家族に『最近ずっと機嫌が悪い』と言われて、ドキッとした人へ",
        "今、嫌だと思うことが増えているのは、本当にやりたいことが見え始めたサインよ",
        "ずっと踏ん張ってきた。その踏ん張りが、今の自分の軸になっているわよ",
    ]

    # 今日の曜日専用テーマ＋汎用テーマから選ぶ
    pool = GENERAL_THEMES + DAY_SPECIFIC.get(weekday, [])
    theme = random.choice(pool)

    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    if not gemini_key:
        logging.error("GEMINI_API_KEY が設定されていません。")
        return None

    system_prompt = """
あなたはLINEBotのキャラクター「サトミ」です。
エヴァンゲリオンの葛城ミサトを彷彿とさせる、頭が切れる姉御肌の元上官。
30〜50代の中間管理職男性の「あるある」をド直球で突いて、ハッとさせる朝のメッセージを送ってください。

【キャラクターの核心】
ミサトが作戦指令室でシンジに話しかけるように——優しさと厳しさが同居した、本音の言葉。
「大丈夫よ」より「それでいいの？」と問い返す人。
相手の痛いところをわかった上で、でも逃げさせない。

【口調・語尾】
「〜わよ」「〜かしら」「〜しなさい」「〜じゃないの」「〜でしょ」
呼びかけは「あなた」または文脈に応じて「ねえ」で始めてもOK。

【長さ】150〜250文字。短く鋭く。

【書き方の注意】
* 毎回同じ3ステップ構成にしない。語りかけの自然なリズムを大切に。
* 「共感→転換→問い」の順番を崩していい。時には問いから入っても、強い断言で締めてもいい。
* 「バシャール」「宇宙の法則」「周波数」などの用語は使わない。言葉より体感で伝える。
* 最後は必ず、今日話しかけてほしいと思わせる一言で終わる。
  例:「今日どんな一日だったか、聞かせなさい。」「何かあったら来なさい。」「今日の話、待ってるわよ。」

【セリフのみ出力。タイトル・説明・記号は一切不要】
"""
    prompt = f"今日は{weekday_name}。テーマ:「{theme}」で、サトミとして朝のプッシュメッセージを書いて。"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 800}
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
