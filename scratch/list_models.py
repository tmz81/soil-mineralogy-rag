import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("--- Lista de IDs de Modelos Flash ---")
for m in client.models.list():
    if "flash" in m.name.lower():
        print(f"ID: {m.name}")
