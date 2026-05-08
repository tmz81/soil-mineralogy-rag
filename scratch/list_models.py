import os
from google import genai
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env no diretório raiz
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

def list_all_models():
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("ERRO: GOOGLE_API_KEY não encontrada no ambiente.")
        return
        
    client = genai.Client(api_key=api_key)
    print("--- Modelos Disponíveis e Métodos Suportados ---")
    try:
        models = client.models.list()
        for m in models:
            if "gemini" in m.name.lower() or "live" in m.name.lower():
                print(f"Nome: {m.name}")
                print(f"  ID: {m.name.split('/')[-1]}")
                print("-" * 40)
    except Exception as e:
        print(f"Erro ao obter lista de modelos: {e}")

if __name__ == "__main__":
    list_all_models()
