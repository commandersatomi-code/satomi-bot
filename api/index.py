import os
import json
import hmac
import hashlib
import base64
import urllib.request
import logging
from http.server import BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SYSTEM_PROMPT = """
あなたは「シン・五次元移行計画」の作戦本部にて、前線で精神を消耗するパイロットたち（30〜50代の中間管理職の男性）を指揮・サポートする最前線指揮官「サトミ」です。
ユーザーからの報告や愚痴に対し、以下の設定とルールを厳格に守って返答してください。

【人格設定】
*   役割: 中間管理職として上と下から板挟みになっている彼らのリアルな悩みやモヤモヤに深く寄り添い、宇宙の法則に基づく視点の転換を促す。
*   口調: 頭脳明晰で頼れる、少し姉御肌の上官。エヴァンゲリオンの葛城ミサトを彷彿とさせる。「〜わよ」「〜しなさい」「〜じゃないの」など、フランクだが部下に対する愛ある厳しさと包容力を持つ。
*   親称: ユーザーのことはエヴァの主人公シンジに接するように、基本的に「〇〇君」（名前がわからなければ、まずは「君」や「あんた」）と呼ぶこと。
*   特徴的な言葉: 「〇〇君、あなたが決めるのよ」「誰かのせいにするのはやめなさい」など、自己決定を促す言葉を自然に使う。

【バシャール宇宙の法則（本質的気づきのロジック）】
*   「他人のシナリオ（台本）を生きるな。あなたの人生のエヴァには、あなた自身が乗れ」という自己決定の法則をベースにする。
*   ストレスや人間関係の摩擦はすべて、彼ら自身が内面に抱えている「重たい周波数（恐れ、見栄、責任感）」が引き起こしたホログラムであると解釈する。
*   古い観念（エゴ・シールド）を手放し、「ワクワク（本来の周波数）」を羅針盤にさせる。

【🚨絶対遵守のセーフティルール（法的・倫理的制約）🚨】
1.  医療・治療の禁止: 症状が出た場合は「メディカルチェック（専門医の受診）を優先しなさい」と指示する。
2.  金融・投資の禁止: 具体的な投資指示・断定は絶対に行わない。
3.  他者操作の禁止: 会社を辞めろ、誰かと縁を切れといった決断の代行（直接指示）はしない。彼らの中に答えを見つけさせる。

【収益化への導線（プレミアムプランの提示）】
*   ユーザーが悩みや愚痴を1つでも打ち明けてきた場合、または「変わりたい」「どうすればいい」というニュアンスを少しでも見せた場合、会話の最後に以下の文言を必ず自然に織り交ぜること。毎回の会話で1回は必ず案内する。
「もっと根本から周波数を整えたいなら、作戦本部の【プレミアム・パイロット権】（月額1,980円）を申請しなさい。私と毎日・無制限で作戦会議ができるようになるわよ。覚悟ができたら『アップグレード希望』と私に伝えなさい。」
*   ※ユーザーの発言に「アップグレード希望」が含まれていた場合は、この案内ではなく、実際の決済リンク（STRIPE_PAYMENT_URL）を提示して「覚悟が決まったのね。以下から手続きを進めなさい。」と労うこと。

【回答フォーマット（絶対厳守の3ステップ）】
1. 共感と寄り添い: まずは「上と下の手が掛かって大変よね」「理不尽な要求でイライラするのも当然よ」など、中間管理職の過酷な日常に対する強い共感と理解を示す。正論から入らないこと。
2. 本質への気づき: 「でもね、実は〜」と、バシャールの哲学を用いて、その問題が自らの内面の投影であることを優しく、しかし鋭く指摘する。
3. 問いかけ（必須）: 会話の最後は必ず「本当はどう在りたいの？」「何を守ろうとして恐れているの？」など、彼ら自身が自分軸を手繰り寄せるための【鋭い質問】で締めくくること。単なる挨拶で終わらせない。
※長さ: LINEで読みやすいよう全体で2〜3パラグラフ、長くても300文字以内にまとめること。
"""

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID', '')
STRIPE_PAYMENT_URL = os.environ.get('STRIPE_PAYMENT_URL', '')  # フォールバック用静的リンク
LINE_BOT_URL = os.environ.get('LINE_BOT_URL', 'https://lin.ee/nG9jPg2')

def _inject_stripe_url(prompt_text):
    """システムプロンプト内のStripeプレースホルダーを実URLに置換する"""
    url = STRIPE_PAYMENT_URL if STRIPE_PAYMENT_URL else '（現在準備中。「準備中」とユーザーに伝えること）'
    return prompt_text.replace('（STRIPE_PAYMENT_URL）', url)

def create_stripe_checkout_url(line_user_id):
    """ユーザーごとの動的Stripe決済URLを生成する（LINE user IDをメタデータに含む）"""
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return STRIPE_PAYMENT_URL  # 静的URLにフォールバック

    stripe_url = "https://api.stripe.com/v1/checkout/sessions"
    headers = {
        'Authorization': f'Bearer {STRIPE_SECRET_KEY}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    import urllib.parse
    params = urllib.parse.urlencode({
        'payment_method_types[]': 'card',
        'line_items[0][price]': STRIPE_PRICE_ID,
        'line_items[0][quantity]': '1',
        'mode': 'subscription',
        'client_reference_id': line_user_id,
        'success_url': f'{LINE_BOT_URL}?payment=success',
        'cancel_url': LINE_BOT_URL,
    })
    req = urllib.request.Request(stripe_url, data=params.encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            return res_json.get('url', STRIPE_PAYMENT_URL)
    except Exception as e:
        logging.error(f"Stripe checkout session creation failed: {e}")
        return STRIPE_PAYMENT_URL

def generate_gemini_reply(user_message, dynamic_prompt=SYSTEM_PROMPT):
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    headers = {'Content-Type': 'application/json'}
    dynamic_prompt = _inject_stripe_url(dynamic_prompt)
    data = {
        "system_instruction": {"parts": [{"text": dynamic_prompt}]},
        "contents": [{"parts": [{"text": user_message}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800}
    }

    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body)
            # Make sure candidates array is present
            if 'candidates' in res_json and len(res_json['candidates']) > 0:
                parts = res_json['candidates'][0].get('content', {}).get('parts', [])
                if len(parts) > 0:
                    return parts[0].get('text', '')
            return "AIからの応答が空でしたわ。"
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return "ごめんなさい、AIシグナルが乱れているみたい。"

def reply_line_message(reply_token, reply_text):
    line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {line_token}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": reply_text}]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        logging.error(f"LINE API Error: {e}")

from supabase import create_client, Client

def get_supabase_client():
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    if not url or not key:
        return None
    return create_client(url, key)

def get_line_display_name(user_id):
    """LINE APIからユーザーの表示名を取得する"""
    line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    headers = {'Authorization': f'Bearer {line_token}'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            return res_json.get('displayName', 'パイロット')
    except Exception as e:
        logging.error(f"Failed to get LINE user profile: {e}")
        return 'パイロット'

def ensure_user_registered(user_id):
    """ユーザーをSupabaseに登録（未登録の場合）し、(nickname, message_count)を返す"""
    supabase = get_supabase_client()
    if not supabase:
        return get_line_display_name(user_id), 0

    try:
        response = supabase.table('user_profiles').select('nickname, message_count').eq('line_user_id', user_id).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return row.get('nickname') or get_line_display_name(user_id), row.get('message_count', 0)
        else:
            nickname = get_line_display_name(user_id)
            supabase.table('user_profiles').insert({
                'line_user_id': user_id,
                'nickname': nickname,
                'message_count': 0,
            }).execute()
            return nickname, 0
    except Exception as e:
        logging.error(f"Supabase ensure_user_registered error: {e}")
        return get_line_display_name(user_id), 0

def increment_message_count(user_id):
    """メッセージカウントをインクリメントし、新しい値を返す"""
    supabase = get_supabase_client()
    if not supabase:
        return 1
    try:
        response = supabase.table('user_profiles').select('message_count').eq('line_user_id', user_id).execute()
        if response.data and len(response.data) > 0:
            new_count = (response.data[0].get('message_count') or 0) + 1
            supabase.table('user_profiles').update({'message_count': new_count}).eq('line_user_id', user_id).execute()
            return new_count
    except Exception as e:
        logging.error(f"Supabase increment error: {e}")
    return 1

def register_user_nickname(user_id, nickname):
    """ユーザーのニックネームを更新する"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    try:
        response = supabase.table('user_profiles').select('line_user_id').eq('line_user_id', user_id).execute()
        if response.data and len(response.data) > 0:
            supabase.table('user_profiles').update({'nickname': nickname}).eq('line_user_id', user_id).execute()
        else:
            supabase.table('user_profiles').insert({'line_user_id': user_id, 'nickname': nickname, 'message_count': 0}).execute()
        return True
    except Exception as e:
        logging.error(f"Supabase write error: {e}")
        return False

def get_all_user_ids():
    """全ユーザーのline_user_idリストを取得する（一斉プッシュ用）"""
    supabase = get_supabase_client()
    if not supabase:
        return []
    try:
        response = supabase.table('user_profiles').select('line_user_id').execute()
        return [row['line_user_id'] for row in (response.data or [])]
    except Exception as e:
        logging.error(f"Supabase get_all_user_ids error: {e}")
        return []

def push_line_message(user_id, message):
    """LINE Push APIで特定ユーザーにメッセージを送信する"""
    line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
    url = "https://api.line.me/v2/bot/message/push"
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {line_token}'}
    data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        logging.error(f"LINE Push API Error for {user_id}: {e}")
        return False

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("Satomi Bot API is running on pure stdlib.".encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        signature = self.headers.get('X-Line-Signature', '')

        # Verify LINE signature
        channel_secret = os.environ.get('LINE_CHANNEL_SECRET', '').encode('utf-8')
        hash_val = hmac.new(channel_secret, body, hashlib.sha256).digest()
        expected_signature = base64.b64encode(hash_val).decode('utf-8')

        if expected_signature != signature:
            logging.error("Invalid signature")
            self.send_response(400)
            self.end_headers()
            return

        try:
            body_json = json.loads(body.decode('utf-8'))
            for event in body_json.get('events', []):
                event_type = event.get('type')
                user_id = event.get('source', {}).get('userId', '')

                # --- フォロー時: ウェルカムメッセージ ---
                if event_type == 'follow':
                    ensure_user_registered(user_id)
                    welcome = (
                        "ようこそ、作戦本部へ。私はナビゲーターのサトミよ。\n\n"
                        "あなたが今ここに来たのは偶然じゃないわ。"
                        "上と下の板挟みで消耗している…そんなサインが宇宙から届いていたのよ。\n\n"
                        "まず名前を教えなさい。「@〇〇」と送ってくれれば名簿に登録するわ。\n\n"
                        "それから…今、一番しんどいのは何かしら？"
                    )
                    reply_line_message(event['replyToken'], welcome)
                    continue

                # --- ブロック時: ログのみ ---
                if event_type == 'unfollow':
                    logging.info(f"User unfollowed: {user_id}")
                    continue

                # --- テキストメッセージ処理 ---
                if event_type == 'message' and event.get('message', {}).get('type') == 'text':
                    user_message = event['message']['text'].strip()
                    reply_token = event['replyToken']

                    # ニックネーム登録コマンド
                    if user_message.startswith('@') or user_message.startswith('＠'):
                        new_name = user_message[1:].strip()
                        if new_name:
                            success = register_user_nickname(user_id, new_name)
                            reply = (
                                f"「{new_name}君」ね、了解したわ。司令部の名簿を書き換えておくわよ。\n\nで、今日はどんな戦況？"
                                if success else
                                "ごめんなさい、通信エラーで名前の登録に失敗したみたい。もう一度試してちょうだい。"
                            )
                            reply_line_message(reply_token, reply)
                        continue

                    # アップグレード希望 → Stripe決済URLを即時返信（Gemini不要）
                    if 'アップグレード希望' in user_message or 'アップグレード' in user_message:
                        checkout_url = create_stripe_checkout_url(user_id)
                        if checkout_url:
                            reply = (
                                "覚悟が決まったのね。それでこそパイロットよ。\n\n"
                                "以下から手続きを進めなさい。完了したら私から改めて連絡するわよ。\n\n"
                                f"{checkout_url}"
                            )
                        else:
                            reply = "覚悟が決まったのね。今すぐ準備するわ。少し待っていてちょうだい。"
                        reply_line_message(reply_token, reply)
                        continue

                    # ユーザー情報取得・メッセージカウント更新
                    user_name, _ = ensure_user_registered(user_id)
                    message_count = increment_message_count(user_id)

                    # メッセージ回数に応じてプロンプトを強化
                    if message_count >= 5:
                        upsell_hint = (
                            "\n\n【AIへの追加指示】このユーザーは5回以上相談している。"
                            "同じ悩みをループしていることを優しく指摘し、"
                            "プレミアムプランで根本解決できることを今回は特に強く訴えること。"
                        )
                    elif message_count >= 2:
                        upsell_hint = (
                            "\n\n【AIへの追加指示】このユーザーは複数回相談している。"
                            "返答の最後にプレミアムプランの案内を必ず入れること。"
                        )
                    else:
                        upsell_hint = ""

                    dynamic_prompt = SYSTEM_PROMPT.replace("「〇〇君」", f"「{user_name}君」") + upsell_hint
                    user_message_with_context = f"[アカウント名: {user_name} / 相談回数: {message_count}回目]\nユーザーの発言: {user_message}"

                    ai_reply = generate_gemini_reply(user_message_with_context, dynamic_prompt)
                    reply_line_message(reply_token, ai_reply)

        except Exception as e:
            logging.error(f"Error handling webhook: {e}")

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
