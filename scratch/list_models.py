import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    print("Listando modelos do Gemini disponíveis para a chave:")
    try:
        for m in client.models.list():
            try:
                # Simplesmente imprime o nome do modelo
                print(f"- {m.name}")
            except Exception as err:
                print(f"Erro no modelo: {err}")
    except Exception as e:
        print(f"Erro ao listar modelos: {e}")

if __name__ == "__main__":
    list_models()
