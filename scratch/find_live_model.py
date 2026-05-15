import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def try_model(model_id):
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    try:
        async with client.aio.live.connect(model=model_id, config=types.LiveConnectConfig(response_modalities=["TEXT"])) as session:
            print(f"✅ SUCESSO com {model_id}!")
            return True
    except Exception as e:
        err_str = str(e)
        if "quota" in err_str.lower() or "limit" in err_str.lower():
            print(f"⚠️ {model_id} SUCESSO (mas com erro de cota): {e}")
            return True
        else:
            print(f"❌ Falha com {model_id}: {e}")
            return False

async def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # Obter lista de todos os modelos
    models = []
    for m in client.models.list():
        models.append(m.name.replace("models/", ""))
    
    print(f"Testando {len(models)} modelos...")
    for model_id in models:
        # Testa apenas os modelos que podem ter suporte ao Live (geralmente flash, pro, ou exp)
        if any(x in model_id for x in ["flash", "pro", "exp", "live"]):
            await try_model(model_id)

if __name__ == "__main__":
    asyncio.run(main())
