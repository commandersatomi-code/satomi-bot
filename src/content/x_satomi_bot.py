import os
import logging
import random
import tweepy
import google.generativeai as genai
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_environment():
    """Load environment variables from .env file"""
    # Load from the project root .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(dotenv_path=env_path)

LINE_BOT_URL = os.environ.get('LINE_BOT_URL', 'https://lin.ee/nG9jPg2')

# ターゲット（中間管理職）が実際に検索するハッシュタグ
TAG_POOL_WORK = [
    "#中間管理職", "#管理職", "#サラリーマン", "#会社員",
    "#仕事の悩み", "#職場ストレス", "#職場の人間関係", "#仕事辞めたい",
    "#上司が嫌い", "#部下育成", "#残業", "#ブラック企業",
]
TAG_POOL_MINDSET = [
    "#マインドセット", "#思考の転換", "#メンタル強化", "#自己成長",
    "#引き寄せの法則", "#潜在意識", "#スピリチュアル", "#手放し",
    "#自己肯定感", "#ストレス解消", "#心の持ち方",
]

def generate_tweet_content():
    """Generate a spiritual/awareness message as Satomi using Gemini."""
    genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

    system_prompt = """
    あなたは「シン・五次元移行計画」の作戦本部ナビゲーター、「サトミ」です。
    X（旧Twitter）向けの投稿（ツイート）を作成してください。

    【ターゲット（最重要）】
    * 30〜50代の中間管理職の男性。
    * 悩み: 上下からの板挟み、終わらない仕事、将来への不安、やり甲斐の喪失、自分を押し殺す日々。

    【ルール】
    * 役割: ターゲットの日常のリアルな悩みやモヤモヤに深く寄り添いつつ、宇宙の法則（バシャール哲学）に基づく視点の転換を促す。
    * 口調: フランクで少し姉御肌。「～わよ」「～かしら」等の語尾を使う。
    * 長さ: ハッシュタグ込みで全体が110文字以内に収まること（絶対厳守）。
    * タグ: 文末に必ず指定されたハッシュタグをつける。

    【投稿の「型」（必ず以下のどれかの形式を使うこと）】
    1. リスト型（共感 → 解決策の列挙）
    2. ビフォーアフター型（苦悩の過去 vs 視点を変えた未来の対比）
    3. 逆張り型（世間の「常識」を否定し、本質を突く）
    4. 圧倒的共感型（日常の「あるある」を代弁し、寄り添う）
    5. ノウハウ展開型（具体的な心の保ち方を教える）
    """

    themes = [
        "上司と部下の板挟み（人間関係の手放し）",
        "お金と将来へのブロック解除",
        "会社での自己肯定感を高める",
        "キャリアの先行き不安の解消",
        "理不尽なトラブルへのイライラを俯瞰する",
        "終わらないタスクを手放し、今ここを生きる",
        "我慢を辞めて、ワクワク（情熱）に従う生き方",
        "会社の常識を疑い、自分軸を取り戻す",
    ]

    # 3回に1回はLINE誘導ツイートを投稿する
    is_cta_post = random.random() < 0.33

    if is_cta_post:
        return _generate_cta_tweet(genai)
    else:
        return _generate_content_tweet(genai, system_prompt, themes)


def _generate_cta_tweet(genai_module):
    """LINE誘導ツイートを生成する"""
    cta_system = """
    あなたはサトミ（姉御肌のナビゲーター）です。
    30〜50代の中間管理職男性に向けて、LINEの無料相談へ誘導するツイートを書いてください。

    【ルール】
    * 口調: フランクで姉御肌。「～わよ」「～かしら」「～しなさい」語尾。
    * 共感から入り、LINEで話せることを伝えて締める。
    * URLの前後を含め、テキスト部分は80文字以内に必ず収める（URLは別でカウント）。
    * ハッシュタグは文末に1つだけ。
    * セリフのテキストのみ出力。URLは出力しない。
    """
    cta_prompts = [
        "仕事のモヤモヤを一人で抱えている管理職男性へのLINE無料相談誘導ツイートを書いて。",
        "上司と部下の板挟みで消耗している人へ、LINEで愚痴を聞くことを伝えるツイートを書いて。",
        "キャリアの迷いを感じているサラリーマンへ、LINEで視点の転換を手伝うことを伝えるツイートを書いて。",
    ]

    tag = random.choice(["#管理職", "#仕事の悩み", "#中間管理職"])
    prompt = random.choice(cta_prompts)

    try:
        genai_module.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        model = genai_module.GenerativeModel('gemini-2.5-flash', system_instruction=cta_system)
        response = model.generate_content(prompt, generation_config=genai_module.types.GenerationConfig(temperature=0.9))
        body = response.text.strip()
        # URLを別行で追加（Twitter側でt.co短縮、23文字としてカウント）
        text = f"{body}\n{LINE_BOT_URL}\n{tag}"
        return text if len(text) <= 280 else f"{body[:70]}...\n{LINE_BOT_URL}\n{tag}"
    except Exception as e:
        logging.error(f"CTA tweet generation failed: {e}")
        return None


def _generate_content_tweet(genai_module, system_prompt, themes):
    """通常のコンテンツツイートを生成する"""
    templates = [
        "1. リスト型", "2. ビフォーアフター型", "3. 逆張り型", "4. 圧倒的共感型", "5. ノウハウ展開型"
    ]
    template = random.choice(templates)
    theme = random.choice(themes)
    # ターゲットに刺さるタグをミックス
    tag1 = random.choice(TAG_POOL_WORK)
    tag2 = random.choice(TAG_POOL_MINDSET)
    selected_tags = f"{tag1} {tag2}"

    prompt = f"今日のテーマ:「{theme}」。\n使用する投稿の型: {template}\n使用するハッシュタグ: {selected_tags}。\n\n指定の「投稿の型」に従い、ハッシュタグ込み110文字以内で書いてちょうだい。ハッシュタグは文末に。"

    try:
        model = genai_module.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        response = model.generate_content(
            prompt,
            generation_config=genai_module.types.GenerationConfig(temperature=0.85)
        )
        text = response.text.strip()

        if len(text) > 128:
            logging.warning(f"Trimming generated text from {len(text)} chars.")
            import re
            tags = re.findall(r'#\S+', text)
            tag_str = " ".join(tags)
            msg_only = re.sub(r'#\S+', '', text).strip()
            allowed_msg_len = 110 - len(tag_str) - 2
            cut_msg = msg_only[:allowed_msg_len]
            if '。' in cut_msg:
                cut_msg = cut_msg.rsplit('。', 1)[0] + "。"
            else:
                cut_msg = cut_msg + "…"
            text = f"{cut_msg}\n{tag_str}"
            if len(text) > 130:
                text = text[:130]

        return text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return None

def post_to_x(text):
    """Post the generated text to X (Twitter) using Tweepy v2."""
    api_key = os.environ.get('X_API_KEY')
    api_key_secret = os.environ.get('X_API_KEY_SECRET')
    access_token = os.environ.get('X_ACCESS_TOKEN')
    access_token_secret = os.environ.get('X_ACCESS_TOKEN_SECRET')
    
    if not all([api_key, api_key_secret, access_token, access_token_secret]):
        logging.error("Missing one or more X API keys in environment variables.")
        return False
        
    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_key_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        
        response = client.create_tweet(text=text)
        logging.info(f"Successfully posted to X! Tweet ID: {response.data['id']}")
        return True
    except tweepy.errors.TweepyException as e:
        logging.error(f"X API Error: {e}")
        try:
            logging.error(f"Response: {e.response.text}")
        except:
            pass
        return False
    except Exception as e:
        logging.error(f"X API Error: {e}")
        return False

def main():
    load_environment()
    logging.info("Starting Satomi X Bot execution...")
    
    # 1. Generate Content
    tweet_text = generate_tweet_content()
    if not tweet_text:
        logging.error("Failed to generate tweet content. Exiting.")
        return
        
    logging.info(f"Generated text: \n---\n{tweet_text}\n---")
    
    # 2. Post to X
    success = post_to_x(tweet_text)
    if success:
        logging.info("Bot execution completed successfully.")
    else:
        logging.error("Bot execution failed during X posting.")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
