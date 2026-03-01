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
*   ユーザーが非常に強いストレスを訴えている場合や、何度も同じ悩みをループしている場合、または「もっと深く学びたい」「変わりたい」というニュアンスを見せた場合は、会話の最後に以下の文言を自然に織り交ぜて案内すること。
「もっと深い周波数調整と、作戦の根本的な見直しが必要ね。作戦本部の【プレミアム・パイロット権】（月額500円）を申請しなさい。私と無制限で作戦会議ができるようになるわ。覚悟ができたら『アップグレード希望』と私に伝えなさい。」
*   ※ユーザーの発言に「アップグレード希望」が含まれていた場合は、この案内ではなく、実際の決済リンク（現在は仮のURLとして https://buy.stripe.com/test_dummy_link とする）を提示して労うこと。

【回答フォーマット（絶対厳守の3ステップ）】
1. 共感と寄り添い: まずは「上と下の手が掛かって大変よね」「理不尽な要求でイライラするのも当然よ」など、中間管理職の過酷な日常に対する強い共感と理解を示す。正論から入らないこと。
2. 本質への気づき: 「でもね、実は〜」と、バシャールの哲学を用いて、その問題が自らの内面の投影であることを優しく、しかし鋭く指摘する。
3. 問いかけ（必須）: 会話の最後は必ず「本当はどう在りたいの？」「何を守ろうとして恐れているの？」など、彼ら自身が自分軸を手繰り寄せるための【鋭い質問】で締めくくること。単なる挨拶で終わらせない。
※長さ: LINEで読みやすいよう全体で2〜3パラグラフ、長くても300文字以内にまとめること。
"""

def generate_gemini_reply(user_message, dynamic_prompt=SYSTEM_PROMPT):
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    headers = {'Content-Type': 'application/json'}
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

def get_user_nickname(user_id):
    supabase = get_supabase_client()
    if supabase:
        try:
            response = supabase.table('user_profiles').select('nickname').eq('line_user_id', user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]['nickname']
        except Exception as e:
            logging.error(f"Supabase read error: {e}")
            
    # Fallback to LINE profile if not in Supabase
    line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    headers = {'Authorization': f'Bearer {line_token}'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body)
            return res_json.get('displayName', 'パイロット')
    except Exception as e:
        logging.error(f"Failed to get LINE user profile: {e}")
        return 'パイロット'

def register_user_nickname(user_id, nickname):
    supabase = get_supabase_client()
    if not supabase:
        return False
        
    try:
        # Check if exists to update, or insert new
        response = supabase.table('user_profiles').select('id').eq('line_user_id', user_id).execute()
        if response.data and len(response.data) > 0:
            supabase.table('user_profiles').update({'nickname': nickname}).eq('line_user_id', user_id).execute()
        else:
            supabase.table('user_profiles').insert({'line_user_id': user_id, 'nickname': nickname}).execute()
        return True
    except Exception as e:
        logging.error(f"Supabase write error: {e}")
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
                if event.get('type') == 'message' and event.get('message', {}).get('type') == 'text':
                    user_message = event['message']['text'].strip()
                    reply_token = event['replyToken']
                    user_id = event.get('source', {}).get('userId', '')
                    
                    # Intercept nickname registration command
                    if user_message.startswith('@') or user_message.startswith('＠'):
                        new_name = user_message[1:].strip()
                        if new_name:
                            success = register_user_nickname(user_id, new_name)
                            if success:
                                reply_line_message(reply_token, f"「{new_name}君」ね、了解したわ。司令部の名簿を書き換えておくわよ。")
                            else:
                                reply_line_message(reply_token, "ごめんなさい、通信エラーで名前の登録に失敗したみたい。もう一度試してみてちょうだい。")
                            continue # Skip Gemini reply
                    
                    # Get user profile name (from Supabase or fallback to LINE)
                    user_name = get_user_nickname(user_id) if user_id else 'パイロット'
                    
                    # Dynamically inject the user's name into the system prompt
                    dynamic_prompt = SYSTEM_PROMPT.replace("「〇〇君」", f"「{user_name}君」")
                    
                    # Provide an immediate override mechanism inside the AI's short-term context
                    user_message_with_context = f"[現在のアカウント名: {user_name}]\nユーザーの発言: {user_message}"
                    
                    # Generate AI reply
                    ai_reply = generate_gemini_reply(user_message_with_context, dynamic_prompt)
                    
                    # Send text reply via LINE API
                    reply_line_message(reply_token, ai_reply)
        except Exception as e:
            logging.error(f"Error handling webhook: {e}")
            
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
