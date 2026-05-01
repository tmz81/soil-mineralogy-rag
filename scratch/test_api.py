import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print(f"API Key loaded (first 5 chars): {api_key[:5] if api_key else 'None'}")
print(f"API Key length: {len(api_key) if api_key else 0}")

try:
    client = genai.Client(api_key=api_key)
    # Just list models to check if API key is accepted
    for m in client.models.list():
        print(f"Model: {m.name}")
        break
    print("API Key is VALID.")
except Exception as e:
    print(f"API Key check FAILED: {e}")
