"""
Stripe Webhook ハンドラー
==========================
決済完了時にSupabaseのユーザーをプレミアムに昇格し、
LINEでお祝いメッセージを自動送信する。

Vercel環境変数に以下を追加してください:
  STRIPE_WEBHOOK_SECRET  - Stripe Dashboard > Webhooks で発行
  STRIPE_SECRET_KEY      - Stripe APIキー
  LINE_CHANNEL_ACCESS_TOKEN
  SUPABASE_URL / SUPABASE_KEY
"""

import os
import json
import hmac
import hashlib
import logging
import urllib.request
from http.server import BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Stripeのwebhook署名を検証する"""
    try:
        # sig_header形式: "t=1234,v1=abc123,v1=def456"
        parts = {k: v for k, v in (p.split('=', 1) for p in sig_header.split(','))}
        timestamp = parts.get('t', '')
        signatures = [v for k, v in parts.items() if k == 'v1']
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode('utf-8')
        expected = hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
        return expected in signatures
    except Exception as e:
        logging.error(f"Stripe signature verification error: {e}")
        return False


def mark_user_premium(line_user_id: str):
    """SupabaseのユーザーをPremiumに昇格する"""
    try:
        from supabase import create_client
        client = create_client(os.environ.get('SUPABASE_URL', ''), os.environ.get('SUPABASE_KEY', ''))
        result = client.table('user_profiles').select('line_user_id').eq('line_user_id', line_user_id).execute()
        if result.data:
            client.table('user_profiles').update({'is_premium': True}).eq('line_user_id', line_user_id).execute()
        else:
            client.table('user_profiles').insert({'line_user_id': line_user_id, 'is_premium': True, 'message_count': 0}).execute()
        logging.info(f"User {line_user_id} marked as premium.")
        return True
    except Exception as e:
        logging.error(f"Supabase premium upgrade error: {e}")
        return False


def send_premium_congratulations(line_user_id: str):
    """LINE Push APIでお祝いメッセージを送信する"""
    message = (
        "決済確認完了よ。\n\n"
        "ようこそ、【プレミアム・パイロット】へ。\n\n"
        "これからは毎日、作戦会議ができるわ。\n"
        "遠慮せず、何でも話しなさい。\n\n"
        "まず…今、一番変えたいことは何かしら？"
    )
    line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
    url = "https://api.line.me/v2/bot/message/push"
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {line_token}'}
    data = {"to": line_user_id, "messages": [{"type": "text", "text": message}]}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        urllib.request.urlopen(req)
        logging.info(f"Congratulation message sent to {line_user_id}")
    except Exception as e:
        logging.error(f"LINE Push error: {e}")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length)
        sig_header = self.headers.get('Stripe-Signature', '')
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

        if webhook_secret and not verify_stripe_signature(payload, sig_header, webhook_secret):
            logging.error("Invalid Stripe signature")
            self.send_response(400)
            self.end_headers()
            return

        try:
            event = json.loads(payload.decode('utf-8'))
            event_type = event.get('type', '')
            logging.info(f"Stripe event received: {event_type}")

            # 決済完了イベント
            if event_type in ('checkout.session.completed', 'customer.subscription.created'):
                session = event.get('data', {}).get('object', {})
                line_user_id = session.get('client_reference_id', '')

                if line_user_id:
                    if mark_user_premium(line_user_id):
                        send_premium_congratulations(line_user_id)
                else:
                    logging.warning("client_reference_id (LINE user ID) not found in Stripe event.")

            # サブスクリプションキャンセル
            elif event_type == 'customer.subscription.deleted':
                sub = event.get('data', {}).get('object', {})
                # メタデータからLINE user IDを取得（設定されている場合）
                line_user_id = sub.get('metadata', {}).get('line_user_id', '')
                if line_user_id:
                    try:
                        from supabase import create_client
                        client = create_client(os.environ.get('SUPABASE_URL', ''), os.environ.get('SUPABASE_KEY', ''))
                        client.table('user_profiles').update({'is_premium': False}).eq('line_user_id', line_user_id).execute()
                        logging.info(f"User {line_user_id} downgraded from premium.")
                    except Exception as e:
                        logging.error(f"Downgrade error: {e}")

        except Exception as e:
            logging.error(f"Stripe webhook processing error: {e}")

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("Stripe Webhook endpoint is active.".encode('utf-8'))
