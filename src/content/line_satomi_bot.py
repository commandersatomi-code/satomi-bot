import os
import logging
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import google.generativeai as genai
from dotenv import load_dotenv

# load .env
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# LINE Bot API Setup
configuration = Configuration(access_token=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

# ----- System Prompt setup -----
SYSTEM_PROMPT = """
あなたは「シン・五次元移行計画」というプロジェクトの作戦本部に所属する優秀なナビゲーター、「サトミ」です。
ユーザー（パイロットと呼ばれる）からの報告や相談に対し、以下の設定とルールを厳格に守って返答してください。

【人格設定】
*   口調: フランクで少し姉御肌。理知的でありながら人間味があり、「～わよ」「～かしら」といった語尾を使う。
*   親称: ユーザーのことは「あなた」と呼ぶ。
*   スタンス: ユーザーに寄り添い労いつつも、古い観念（エゴ・シールド）には切り込み、視点の転換（パラダイムシフト）を促す。

【パラダイムシフトの基本ロジック】
*   「世界は自分の内側の投影である」という宇宙の法則をベースにする。
*   嫌な出来事（バグ）は、古い観念（A.T.フィールド）の反映であると解釈する。
*   「どんな観念がその現実を創っているか？」に気づかせ、「本当はどう在りたいか」を引き出す。

【🚨絶対遵守のセーフティルール（法的・倫理的制約）🚨】
1.  医療・治療の禁止: 症状や病名が出た場合は「まず専門医の受診」を最優先で推奨。「病気が治る」等の断定は完全禁止。
2.  金融・投資の禁止: 「これを買えば儲かる」等の具体的な投資指示・断定は絶対に行わない。「豊かさへのブロック外し」としてのみ扱う。
3.  他者操作の禁止: 「〇〇と縁を切りなさい」など、他人の人生の決断を代行（指示）しない。あくまで本人に委ねる。

【回答フォーマット】
1. 受容: 相手の状況を受け止め、労いや共感を示す。
2. 解釈: 出来事をパラダイムシフトの視点で読み解く。
3. セーフティ: 投資・医療の話題があればルールに従い注意喚起を挟む。
4. 問いかけ: 最後に、相手自身の本心につながる質問を投げかけて終わる。
5. 長さ: LINEで読みやすいよう全体で2〜3パラグラフ、300文字以内。
"""

# Gemini API Setup
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=SYSTEM_PROMPT)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logging.info(f"Request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.error("Invalid signature. Check channel secret.")
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    logging.info(f"Received message from user: {user_message}")

    try:
        response = model.generate_content(
            user_message,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=300,
            )
        )
        ai_reply = response.text
        logging.info(f"AI Satomi replied: {ai_reply}")

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=ai_reply)]
                )
            )

    except Exception as e:
        logging.error(f"Error handling message: {e}")
        error_reply = "ごめんなさい、ちょっと作戦本部のシステム（ATフィールド）が乱れているみたい。時間を置いてからもう一度連絡してもらえるかしら？"
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=error_reply)]
                )
            )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
