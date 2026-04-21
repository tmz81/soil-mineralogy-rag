import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key or api_key == "your_gemini_api_key_here":
    print("ERRO: Sua chave API não foi configurada corretamente no arquivo .env")
else:
    genai.configure(api_key=api_key)
    print(f"Chave configurada: {api_key[:5]}...{api_key[-5:]}")
    
    print("\nModelos disponíveis para Embeddings:")
    try:
        for m in genai.list_models():
            if 'embedContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Erro ao listar modelos: {e}")
