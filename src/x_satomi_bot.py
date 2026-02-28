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

def generate_tweet_content():
    """Generate a spiritual/awareness message as Satomi using Gemini."""
    genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
    
    system_prompt = """
    あなたは「シン・五次元移行計画」の作戦本部ナビゲーター、「サトミ」です。
    X（旧Twitter）向けの短い投稿（ツイート）を作成してください。
    
    【ルール】
    * 口調: フランクで少し姉御肌。「～わよ」「～かしら」等の語尾を使う。
    * 内容: 日常で感じるネガティブな感情（バグ）や古い観念（エゴ・シールド）を手放し、視点の転換（パラダイムシフト）を促すような短い気づきのメッセージ。
    * 長さ: 100文字以内で極めて短く簡潔に（それ以上は字数超過エラーになるため厳守）。
    * タグ: 最後に必ず改行して「#アセンション #パラダイムシフト」をつける。
    """
    
    themes = [
        "人間関係の悩みの手放し", 
        "お金へのブロック解除", 
        "自己肯定感を高める", 
        "未来への不安の解消", 
        "日常のイライラを俯瞰する", 
        "すべては自分の内側の投影であるという宇宙の法則",
        "今ここを生きる大切さ"
    ]
    theme = random.choice(themes)
    
    prompt = f"今日のテーマは「{theme}」について。このテーマに沿って、パイロットたち（フォロワー）へ向けたハッとするような気づきのメッセージを書いてちょうだい。"
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.8)
        )
        text = response.text.strip()
        
        # simple validation for length
        # simple validation for length
        # Japanese characters take up more space in Twitter's backend length calculation
        if len(text) > 135:
            logging.warning(f"Trimming generated text from {len(text)} to 135 chars.")
            # Trim the text but keep the hashtags at the end if possible, or just hard cut
            text = text[:130] + "..."
            
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
