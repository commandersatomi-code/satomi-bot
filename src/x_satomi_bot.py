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
    X（旧Twitter）向けの投稿（ツイート）を作成してください。
    
    【ターゲット（最重要）】
    * 30〜50代の中間管理職の男性。
    * 悩み: 上下からの板挟み、終わらない仕事、将来への不安、やり甲斐の喪失、自分を押し殺す日々。
    
    【ルール】
    * 役割: ターゲットの日常のリアルな悩みやモヤモヤに深く寄り添いつつ、宇宙の法則（バシャール哲学）に基づく視点の転換を促す。
    * 口調: フランクで少し姉御肌。「～わよ」「～かしら」等の語尾を使う。
    * 長さ: 120文字〜130文字以内。長すぎるとエラーになるため130文字を絶対上限とする。
    * タグ: 文末に必ず指定されたハッシュタグをつける。
    
    【投稿の「型」（必ず以下のどれかの形式を使うこと）】
    以下のいずれかの「型」を使って、ターゲットの心を動かすツイートを作成してください。
    
    1. リスト型（具体例を列挙して共感させる。最後は解決策）
      例: 「人生が停滞する悪習慣3選」
      ・他人の顔色ばかりうかがう
      ・『でも』『だって』が口癖
      ・自分の本音に蓋をする
      1つでも当てはまったら、今すぐ手放しなさい！
    
    2. ビフォーアフター型（過去の苦悩と、視点を変えた後の未来の対比）
      例: 
      以前のあなた：上司と部下の板挟みで、毎日胃を痛めて自分をすり減らす日々。
      覚醒したあなた：他人の課題と自分の課題を切り離し、自分のワクワクだけに集中する。
      マインドが変われば、現実（ホログラム）も変わるわよ。
    
    3. 逆張り型（世間の「常識」を否定し、本質を突く）
      例: 
      「責任感を持って我慢しろ」なんて嘘よ。合わない環境で耐え続けても、魂がすり減るだけ。向いてないなら、さっさと次元を移動（パラレルシフト）した方がいいわ。自分の心を犠牲にするルールなんて、今すぐ捨てなさい。
      
    4. 圧倒的共感型（日常の「あるある」を代弁し、寄り添う）
      例:
      「今日は早く帰って休もう」って決めた日に限って、急なトラブルが舞い込む。あれ、本当に泣きたくなるわよね。でもね、それは「他人のシナリオ」に巻き込まれているサインよ。自分の操縦桿を、もう一度握り直しなさい。
      
    5. ノウハウ展開型（具体的な心の保ち方を教える）
      例:
      イライラが止まらない時への対処法。
      「怒っちゃダメ」と蓋をするんじゃなくて、「あ、私今怒ってるな」と声に出して認めるの。認めた瞬間、その重たい周波数はスーッと消えていくわ。抵抗するから苦しいのよ。
    """
    
    templates = [
        "1. リスト型", "2. ビフォーアフター型", "3. 逆張り型", "4. 圧倒的共感型", "5. ノウハウ展開型"
    ]
    
    themes = [
        "上司と部下の板挟み（人間関係の手放し）", 
        "お金と将来へのブロック解除", 
        "会社での自己肯定感を高める", 
        "キャリアの先行き不安の解消", 
        "理不尽なトラブルへのイライラを俯瞰する", 
        "他人の評価は自分の内側の投影であるという宇宙の法則",
        "終わらないタスクを手放し、今ここを生きる",
        "我慢を辞めて、ワクワク（情熱）に従う生き方",
        "会社の常識を疑い、ハイヤーセルフの視点を持つ"
    ]

    
    tag_candidates = [
        "#アセンション", "#バシャール", "#ハイヤーセルフ", 
        "#引き寄せの法則", "#宇宙の法則", "#ワクワク", "#手放し", 
        "#自己統合", "#スターシード", "#5次元", "#次元上昇", "#波動", "#周波数",
        "#シンクロニシティ", "#スピリチュアル", "#潜在意識", "#エゴ"
    ]
    
    template = random.choice(templates)
    theme = random.choice(themes)
    selected_tags = " ".join(random.sample(tag_candidates, 2))
    
    prompt = f"今日のテーマ:「{theme}」。\n使用する投稿の型: {template}\n使用するハッシュタグ: {selected_tags}。\n\n必ず指定された「投稿の型」の形式に従って、このテーマに沿ったハッとするような気づきのメッセージを書いてちょうだい。ハッシュタグは文末に配置すること。"
    
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
        if len(text) > 128:
            logging.warning(f"Trimming generated text from {len(text)} to 128 chars.")
            import re
            # Extract hashtags
            tags = re.findall(r'#\S+', text)
            tag_str = " ".join(tags)
            
            # Remove tags from the original text temporarily to trim the message
            msg_only = re.sub(r'#\S+', '', text).strip()
            
            allowed_msg_len = 128 - len(tag_str) - 3 # Space for newlines
            
            # Try to cut at the last Japanese period (。)
            cut_msg = msg_only[:allowed_msg_len]
            if '。' in cut_msg:
                cut_msg = cut_msg.rsplit('。', 1)[0] + "。"
            else:
                cut_msg = cut_msg + "..."
                
            text = f"{cut_msg}\n\n{tag_str}"
            
            # Absolute hard cut just in case
            if len(text) > 132:
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
