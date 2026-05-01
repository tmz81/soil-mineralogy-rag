import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print(f"API Key: {api_key}")

try:
    client = genai.Client(api_key=api_key)
    # Try a known standard model
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Hello"
    )
    print(f"Response: {response.text}")
    print("API Key is VALID for gemini-1.5-flash.")
except Exception as e:
    print(f"API Key check FAILED: {e}")
