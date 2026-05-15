import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def test_conn():
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"Chave encontrada: {api_key[:10]}...{api_key[-5:] if api_key else ''}")
    client = genai.Client(api_key=api_key)
    
    model_id = "gemini-2.5-flash-native-audio-latest"
    
    print(f"Tentando estabelecer conexão Live com {model_id}...")
    try:
        async with client.aio.live.connect(model=model_id, config=types.LiveConnectConfig(response_modalities=["AUDIO"])) as session:
            print("✅ SUCESSO! Conexão Live com áudio nativo estabelecida com sucesso!")
            # Enviar uma mensagem de texto simples
            print("Enviando mensagem de texto: 'Olá, você está online?'")
            await session.send(input="Olá, você está online?", end_of_turn=True)
            
            # Aguardar resposta
            print("Aguardando resposta do Gemini...")
            async for response in session.receive():
                if response.server_content and response.server_content.model_turn:
                    print("✅ Recebeu resposta do modelo!")
                    break
    except Exception as e:
        print(f"❌ Falha na conexão com {model_id}: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
