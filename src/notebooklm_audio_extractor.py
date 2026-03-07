import os
import argparse
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def transcribe_and_extract_clips(audio_path: str):
    """
    Uses Gemini 1.5 Pro to transcribe a NotebookLM Audio Overview 
    and extract the most viral/interesting 15-30 second clips for TikTok.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY is not set in .env")
        return

    if not os.path.exists(audio_path):
        print(f"❌ Error: Audio file not found at {audio_path}")
        return

    print(f"🎙️ Uploading '{audio_path}' to Gemini...")
    genai.configure(api_key=api_key)
    
    try:
        # Upload the file to Gemini API
        audio_file = genai.upload_file(path=audio_path)
        print(f"✅ Uploaded as: {audio_file.uri}")
        
        prompt = """
        これはNotebookLMで生成された、 আমারプロジェクト「新5D移行計画（サトミ司令、Ishikawa Hybrid、136.1Hzのコズミックチューニング等）」に関する英語のポッドキャスト音声です。
        
        この音声の中から、TikTokなどのショート動画のBGMとして使える、**最も熱く語っている、驚愕している、または興味深い部分（15秒〜30秒程度）**を3箇所抽出してください。
        
        以下のフォーマットで出力してください。
        
        【抽出候補 1】
        時間: 00:00 - 00:00
        英語の文字起こし: (該当部分の正確な英語の文字起こし)
        日本語の意訳（ミサト風）: (ショート動画のテロップにそのまま使える、少し大げさでサトミ/ミサト風の意訳。「〜なのよ」「〜でしょ？」など)
        選んだ理由: (なぜここがバズりやすいか)
        
        【抽出候補 2】
        ...
        """
        
        print("🧠 Analyzing audio and generating short video clips ideas...")
        # Use gemini-1.5-pro for audio processing (flash is also OK but pro is better for complex audio logic)
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content([prompt, audio_file])
        
        print("\n" + "="*50)
        print("🎬 TikTok/Shorts 抽出候補まとめ")
        print("="*50)
        print(response.text)
        print("="*50)
        
        # Cleanup
        genai.delete_file(audio_file.name)
        print("\n🗑️ Cleaned up uploaded file from Gemini.")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract viral clips from NotebookLM Audio Overviews")
    parser.add_argument("audio_path", help="Path to the downloaded NotebookLM .wav or .mp3 file")
    args = parser.parse_args()
    
    transcribe_and_extract_clips(args.audio_path)
