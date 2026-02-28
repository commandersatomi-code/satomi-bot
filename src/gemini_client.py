import os
import sys
from google import genai

# Add project root directory to Python path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.config import GEMINI_API_KEY
except ImportError:
    print("Error: Could not import GEMINI_API_KEY from src/config.py.")
    print("Please ensure the file exists and contains GEMINI_API_KEY.")
    sys.exit(1)

def list_gemini_models():
    """
    Lists available Gemini models.
    """
    if not GEMINI_API_KEY or "YOUR_API_KEY" in GEMINI_API_KEY:
        print("Error: Gemini API key is not configured or is a placeholder. Please set your GEMINI_API_KEY in src/config.py.")
        return

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("\n--- Available Gemini Models ---")
        for model in client.models.list():
            print(f"Model Name: {model.name}")
            print(f"Supported Actions: {model.supported_actions}")
            print("-" * 20)
        print("-----------------------------\n")
    except Exception as e:
        print(f"An error occurred while listing Gemini models: {e}")


def generate_gemini_content(prompt: str, model_name: str = "models/gemini-3-pro-preview") -> str:
    """
    Sends a prompt to the Gemini API and returns the generated content.

    Args:
        prompt (str): The prompt string to send to the Gemini model.
        model_name (str): The name of the Gemini model to use. Defaults to "models/gemini-2.5-flash".

    Returns:
        str: The generated content from the Gemini model, or an error message.
    """
    if not GEMINI_API_KEY or "YOUR_API_KEY" in GEMINI_API_KEY:
        return "Error: Gemini API key is not configured or is a placeholder. Please set your GEMINI_API_KEY in src/config.py."

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        return f"Error configuring Gemini API client: {e}"

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"An error occurred while calling the Gemini API: {e}"

if __name__ == "__main__":
    print("--- Testing Gemini API client ---")
    test_prompt = "こんにちは、Gemini。あなたの名前は何ですか？"
    print(f"Sending test prompt: '{test_prompt}'")
    
    # Test with the now-corrected default model
    response_text = generate_gemini_content(test_prompt)
    print(f"\n--- Gemini Response ({generate_gemini_content.__defaults__[0]}) ---")
    print(response_text)
    print("------------------------------------------\n")