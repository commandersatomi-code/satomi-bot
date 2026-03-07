import os
import random
import re
import datetime
import textwrap
from gtts import gTTS
import moviepy as mp
from moviepy.video.tools.subtitles import SubtitlesClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import google.genai as genai

# --- Configuration ---
WIDTH, HEIGHT = 1080, 1920
FPS = 30
EXPORT_DIR = "exports"
ASSETS_DIR = "src/assets"
IMG_DIR = os.path.join(ASSETS_DIR, "images")
FONT_DIR = os.path.join(ASSETS_DIR, "fonts")

os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(FONT_DIR, exist_ok=True)

# Default Mac Japanese font (Fallback)
MAC_FONT = "Hiragino Sans GB"

# --- Gemini Prompt ---
SYSTEM_PROMPT = """
あなたは「シン・五次元移行計画」の作戦本部ナビゲーター、「サトミ」です。
30〜50代の中間管理職男性へ向けた、TikTok用のショート動画（30秒〜45秒）の台本を作成してください。

【ルール】
* 構成: 「強烈なフック（3秒）」「問題提起と共感（10秒）」「バシャール哲学による視点の転換（15秒）」「LINE（作戦本部）への誘導（5秒）」
* 文字数: 全体で150〜200文字程度。（AI音声で読み上げるため会話体で）
* 口調: フランクで少し姉御肌。「～わよ」「～かしら」等の語尾を使う。
* 出力形式: セリフのテキストのみ出力してください。ト書きや見出しは一切不要です。（改行は適宜いれてください）
"""

THEMES = [
    "理不尽な上司への怒りの手放し",
    "「自分が我慢すればいい」という自己犠牲からの脱却",
    "会社の常識というホログラムに気づく",
    "やりたいことが分からないというブロック解除",
    "終わらないタスクからの解放と「今ここ」の意識"
]

def generate_script() -> str:
    """Geminiを使って動画の台本（セリフ）を生成する"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    theme = random.choice(THEMES)
    prompt = f"今日のテーマ:「{theme}」。中間管理職の心を刺すような、ハッとさせる動画の台本（セリフのみ）を書いてちょうだい。"
    
    print(f"🤖 Generating script for theme: {theme}...")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=SYSTEM_PROMPT + "\n\n" + prompt,
    )
    
    text = response.text.replace("*", "").strip()
    print("\n--- Generated Script ---")
    print(text)
    print("-----------------------\n")
    return text

def create_tts(text: str, output_path: str):
    """テキストから音声を生成する (Edge-TTS)"""
    print("🎙️ Generating audio with Edge-TTS...")
    import subprocess
    # ja-JP-NanamiNeural is a highly natural Japanese female voice
    # We reduce the rate by 15% to make the delivery calmer and easier to read.
    cmd = ["edge-tts", "--voice", "ja-JP-NanamiNeural", "--rate=-15%", "--text", text, "--write-media", output_path]
    subprocess.run(cmd, check=True)

def wrap_text_by_pixels(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    """ピクセル幅に基づいてテキストを改行するカスタム関数"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)

def create_text_image(text: str, width: int, height: int) -> np.ndarray:
    """Pillowを使って美しい日本語長文のテロップ画像を生成し、numpy配列として返す"""
    # Create transparent image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Try logic for font
    try:
        font = ImageFont.truetype(MAC_FONT, 55) # Tweak font size
    except IOError:
        # Fallback to default if nothing works
        font = ImageFont.load_default(size=40)
        
    # Wrap text cleanly based on screen width minus padding
    wrapped_text = wrap_text_by_pixels(text, font, width - 100, d)
    
    # Get bounding box for the text to center it
    bbox = d.textbbox((0, 0), wrapped_text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (width - text_w) / 2
    y = (height - text_h) / 2
    
    # Draw outline (stroke)
    outline_color = (0, 0, 0, 255)
    stroke_width = 4
    for offset_x in range(-stroke_width, stroke_width+1):
        for offset_y in range(-stroke_width, stroke_width+1):
            d.multiline_text((x+offset_x, y+offset_y), wrapped_text, font=font, fill=outline_color, align="center")
            
    # Draw main text
    d.multiline_text((x, y), wrapped_text, font=font, fill=(255, 255, 255, 255), align="center")
    
    return np.array(img)

def generate_video():
    """全てを統合してTikTok動画を生成する"""
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_audio = f"/tmp/satomi_audio_{now_str}.mp3"
    out_file = os.path.join(EXPORT_DIR, f"satomi_tiktok_{now_str}.mp4")
    
    # 1. Generate text script
    script_text = generate_script()
    
    # 2. Generate audio
    create_tts(script_text, tmp_audio)
    audio_clip = mp.AudioFileClip(tmp_audio)
    duration = audio_clip.duration + 0.5 # Add small buffer
    
    # 3. Create Video Background
    print("🎬 Assembling video...")
    
    # Check if user put any images in assets
    bg_images = [f for f in os.listdir(IMG_DIR) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if bg_images:
        bg_path = os.path.join(IMG_DIR, random.choice(bg_images))
        bg_clip = mp.ImageClip(bg_path).with_duration(duration)
        # Resize to fit 1080x1920 (fill canvas)
        # Simple crop/resize logic:
        w, h = bg_clip.size
        # scale to height 1920, then crop width, or vice versa
        ratio = max(WIDTH/w, HEIGHT/h)
        bg_clip = bg_clip.resized(new_size=(int(w*ratio), int(h*ratio)))
        
        # Center crop
        cx, cy = bg_clip.size[0]/2, bg_clip.size[1]/2
        bg_clip = bg_clip.cropped(x1=cx-WIDTH/2, y1=cy-HEIGHT/2, x2=cx+WIDTH/2, y2=cy+HEIGHT/2)
        
        # Darken the background to make text pop
        bg_clip = bg_clip.with_effects([mp.vfx.MultiplyColor(0.5)]) 
    else:
        # Fallback to dark solid color
        bg_clip = mp.ColorClip(size=(WIDTH, HEIGHT), color=(15, 20, 30), duration=duration)

    # 4. Generate Subtitles
    sentences = re.split(r'([。！？\n])', script_text)
    # Re-join punctuation to the sentence
    chunks = []
    current = ""
    for part in sentences:
        current += part
        if part in ['。', '！', '？', '\n']:
            if current.strip():
                chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
        
    chunks = [c for c in chunks if len(c) > 2] # Remove empty
    
    # Calculate subtitle timing proportionally to text length instead of evenly dividing
    total_chars = sum(len(c) for c in chunks)
    
    text_clips = []
    current_time = 0.0
    
    for i, chunk in enumerate(chunks):
        # Generate PIL image with antialiased text
        txt_img = create_text_image(chunk, WIDTH, HEIGHT)
        
        # Determine duration based on chunk length ratio
        chunk_duration = (len(chunk) / max(1, total_chars)) * duration
        
        # Convert to MoviePy clip
        tc = mp.ImageClip(txt_img, transparent=True).with_duration(chunk_duration).with_start(current_time)
        
        # Add a small pop-in effect (fadein)
        tc = tc.with_effects([mp.vfx.FadeIn(0.1)])
        text_clips.append(tc)
        
        current_time += chunk_duration

    # Combine everything
    final_video = mp.CompositeVideoClip([bg_clip] + text_clips)
    final_video = final_video.with_audio(audio_clip)
    
    print(f"💾 Exporting final video to {out_file}...")
    final_video.write_videofile(out_file, fps=FPS, codec="libx264", audio_codec="aac")
    
    # Cleanup
    if os.path.exists(tmp_audio):
        os.remove(tmp_audio)
        
    print(f"✅ Success! TikTok video generated: {out_file}")

if __name__ == "__main__":
    generate_video()
