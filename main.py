import asyncio
import os
import sys
import logging

# Silenciar logs desnecessários
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from google import genai
from google.genai import types
from dotenv import load_dotenv

from src.tools import apply_websocket_patch, get_live_config
apply_websocket_patch()

from src.engine import MineralogyEngine
from src.audio import AudioManager

load_dotenv()

class GeminiLiveRAG:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model_id = "gemini-3.1-flash-live-preview"
        self.engine = MineralogyEngine()
        self.audio_manager = AudioManager()
        self.audio_out_queue = asyncio.Queue()
        self.is_running = True
        self.interrupted = False
        self.ai_speaking = False

    async def send_audio(self, session):
        """Envia áudio do microfone continuamente com indicador de atividade."""
        try:
            self.audio_manager.start_input()
            print("[SISTEMA] Microfone ligado. Ouvindo...")
            
            counter = 0
            while self.is_running:
                try:
                    data = await asyncio.to_thread(self.audio_manager.read_input)
                except Exception as e:
                    print(f"\n[ERRO LEITURA MIC] {e}")
                    await asyncio.sleep(0.1)
                    continue

                if not data:
                    continue

                counter += 1
                if counter % 15 == 0:
                    print(".", end="", flush=True)

                if self.ai_speaking:
                    data = b'\x00' * len(data)
                
                try:
                    await session.send_realtime_input(audio={"data": data, "mime_type": "audio/pcm"})
                except Exception as e:
                    print(f"\n[SISTEMA] Conexão com Gemini fechada: {e}")
                    break
                    
                await asyncio.sleep(0)
        except Exception as e:
            if self.is_running: print(f"\n[ERRO CRÍTICO MIC] {e}")
        finally:
            self.audio_manager.stop_streams()
            print("\n[SISTEMA] Loop de envio de áudio encerrado.")

    async def _play_audio_loop(self):
        """Reproduz o áudio que chega do Gemini."""
        while self.is_running:
            try:
                data = await self.audio_out_queue.get()
                if data is None: 
                    self.audio_out_queue.task_done()
                    break
                
                if self.interrupted:
                    self.audio_out_queue.task_done()
                    continue
                
                try:
                    await asyncio.to_thread(self.audio_manager.write_output, data)
                except Exception as e:
                    print(f"\n[DEBUG] Erro saída áudio: {e}")
                finally:
                    self.audio_out_queue.task_done()
            except Exception as e:
                print(f"\n[DEBUG] Erro no loop de reprodução: {e}")
                break

    async def receive_responses(self, session):
        """Processa as respostas do Gemini e gerencia interrupções."""
        try:
            self.audio_manager.start_output()
            play_task = asyncio.create_task(self._play_audio_loop())
            
            print("[SISTEMA] Conectado! Aguardando sua pergunta...")
            
            while self.is_running:
                async for message in session.receive():
                    if not self.is_running: break

                    if message.server_content and message.server_content.interrupted:
                        self.interrupted = True
                        self.ai_speaking = False 
                        print("\n[SISTEMA] Interrupção detectada!")
                        while not self.audio_out_queue.empty():
                            try:
                                self.audio_out_queue.get_nowait()
                                self.audio_out_queue.task_done()
                            except asyncio.QueueEmpty: break
                        continue

                    if message.server_content and message.server_content.turn_complete:
                        # Pequeno delay para garantir que o áudio final foi processado
                        await asyncio.sleep(0.5)
                        self.interrupted = False
                        await self.audio_out_queue.join()
                        self.ai_speaking = False
                        print("\n[SISTEMA] Pronto para próxima pergunta!")
                        continue

                    if message.server_content and message.server_content.model_turn:
                        self.interrupted = False
                        self.ai_speaking = True
                        for part in message.server_content.model_turn.parts:
                            if part.inline_data:
                                self.audio_out_queue.put_nowait(part.inline_data.data)
                            if part.text:
                                print(f"\r[Zé]: {part.text}", end="", flush=True)
                        continue

                    if message.tool_call:
                        self.interrupted = False
                        self.ai_speaking = True 
                        responses = []
                        for call in message.tool_call.function_calls:
                            print(f"\n[GEMINI] Chamando ferramenta: {call.name}...")
                            try:
                                func = getattr(self.engine, call.name)
                                if asyncio.iscoroutinefunction(func):
                                    result = await func(**call.args)
                                else:
                                    result = await asyncio.to_thread(func, **call.args)
                                
                                responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': result}))
                            except Exception as e:
                                print(f"[ERRO FERRAMENTA] {e}")
                                responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': f"Erro: {e}"}))
                        await session.send_tool_response(function_responses=responses)
                        continue

        except Exception as e:
            if self.is_running:
                print(f"\n[ERRO RECEPÇÃO] {e}")
        finally:
            self.audio_out_queue.put_nowait(None)
            await play_task

    async def run(self):
        config = get_live_config()

        try:
            async with self.client.aio.live.connect(model=self.model_id, config=config) as session:
                print("\n--- SESSÃO MULTIMODAL INICIADA ---")
                await asyncio.gather(
                    self.send_audio(session),
                    self.receive_responses(session)
                )
        except Exception as e:
            print(f"\n[ERRO CONEXÃO] {e}")
        finally:
            self.is_running = False
            self.audio_manager.terminate()
            print("\nSessão encerrada.")

if __name__ == "__main__":
    app = GeminiLiveRAG()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
