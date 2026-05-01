import asyncio
import os
import sys
import traceback
import contextlib
import logging

# Silenciar logs desnecessários
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

import pyaudio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import websockets

# --- PATCH DE ESTABILIDADE DA CONEXÃO ---
original_connect = websockets.connect
def patched_connect(*args, **kwargs):
    kwargs['ping_interval'] = None
    kwargs['ping_timeout'] = None
    return original_connect(*args, **kwargs)
websockets.connect = patched_connect
import google.genai.live
google.genai.live.ws_connect = patched_connect
# ----------------------------------------

from src.engine import MineralogyEngine

load_dotenv()
@contextlib.contextmanager
def ignore_stderr():
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    sys.stderr.flush()
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)

# Configurações de Áudio
FORMAT = pyaudio.paInt16
CHANNELS = 1
RECEIVE_SAMPLE_RATE = 24000
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024 

class GeminiLiveRAG:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model_id = "gemini-3.1-flash-live-preview"
        self.engine = MineralogyEngine()
        with ignore_stderr():
            self.audio = pyaudio.PyAudio()
        self.audio_out_queue = asyncio.Queue()
        self.is_running = True
        self.interrupted = False
        self.ai_speaking = False

    async def send_audio(self, session):
        """Envia áudio do microfone continuamente com indicador de atividade."""
        stream = None
        try:
            with ignore_stderr():
                stream = self.audio.open(
                    format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
                    input=True, frames_per_buffer=CHUNK_SIZE
                )
            
            print("[SISTEMA] Microfone iniciado. Fale agora...")
            
            counter = 0
            while self.is_running:
                # Lendo áudio do hardware
                try:
                    data = await asyncio.to_thread(stream.read, CHUNK_SIZE, exception_on_overflow=False)
                except Exception as e:
                    print(f"\n[ERRO LEITURA MIC] {e}")
                    await asyncio.sleep(0.1)
                    continue

                if not data:
                    continue

                # Indicador visual de que o mic está captando (um ponto a cada ~1 segundo)
                counter += 1
                if counter % 15 == 0:
                    print(".", end="", flush=True)

                if self.ai_speaking:
                    # Silêncio para evitar feedback enquanto a IA fala
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
            if stream:
                stream.stop_stream()
                stream.close()
            print("\n[SISTEMA] Loop de envio de áudio encerrado.")

    async def _play_audio_loop(self, stream):
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
                    await asyncio.to_thread(stream.write, data)
                except Exception as e:
                    print(f"\n[DEBUG] Erro saída áudio: {e}")
                finally:
                    self.audio_out_queue.task_done()
            except Exception as e:
                print(f"\n[DEBUG] Erro no loop de reprodução: {e}")
                break

    async def receive_responses(self, session):
        """Processa as respostas do Gemini e gerencia interrupções.
        
        IMPORTANTE: O SDK do Google (session.receive()) faz `break` internamente
        após cada `turn_complete`. Por isso, precisamos de um loop externo que
        chame receive() novamente para cada novo turno de conversa.
        """
        stream = None
        try:
            with ignore_stderr():
                stream = self.audio.open(
                    format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE,
                    output=True, frames_per_buffer=CHUNK_SIZE
                )
            play_task = asyncio.create_task(self._play_audio_loop(stream))
            
            print("[SISTEMA] Conectado! Aguardando sua pergunta...")
            
            # Loop EXTERNO: session.receive() encerra após cada turn_complete,
            # então precisamos chamá-lo de novo para ouvir o próximo turno.
            while self.is_running:
                async for message in session.receive():
                    if not self.is_running: break

                    # 1. TRATAR INTERRUPÇÃO (VAD)
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

                    # 2. TRATAR FIM DO TURNO
                    # Nota: este é o último message que o SDK entrega antes do break interno.
                    if message.server_content and message.server_content.turn_complete:
                        self.interrupted = False
                        await self.audio_out_queue.join()
                        self.ai_speaking = False
                        print("\n[SISTEMA] Pronto para próxima pergunta!")
                        continue

                    # 3. TRATAR RESPOSTA DE VOZ/TEXTO
                    if message.server_content and message.server_content.model_turn:
                        self.interrupted = False
                        self.ai_speaking = True
                        for part in message.server_content.model_turn.parts:
                            if part.inline_data:
                                self.audio_out_queue.put_nowait(part.inline_data.data)
                            if part.text:
                                print(f"\r[Gemini]: {part.text}", end="", flush=True)
                        continue

                    # 4. TRATAR CHAMADA DE FERRAMENTA (RAG)
                    if message.tool_call:
                        self.interrupted = False
                        self.ai_speaking = True 
                        responses = []
                        for call in message.tool_call.function_calls:
                            print(f"\n[GEMINI] Consultando base técnica sobre: {call.args.get('question')}...")
                            try:
                                result = await asyncio.to_thread(self.engine.query_mineralogy_docs, **call.args)
                                responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': result}))
                            except Exception as e:
                                print(f"[ERRO RAG] {e}")
                                responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': f"Erro: {e}"}))
                        await session.send_tool_response(function_responses=responses)
                        continue

        except Exception as e:
            if self.is_running:
                print(f"\n[ERRO RECEPÇÃO] {e}")
                traceback.print_exc()
        finally:
            self.audio_out_queue.put_nowait(None)
            await play_task
            if stream:
                stream.stop_stream()
                stream.close()

    async def run(self):
        config = types.LiveConnectConfig(
            tools=[{'function_declarations': [
                {
                    "name": "query_mineralogy_docs",
                    "description": "Consulta a biblioteca técnica de mineralogia do solo para responder dúvidas científicas baseadas em PDFs.",
                    "parameters": {"type": "OBJECT", "properties": {"question": {"type": "string"}}, "required": ["question"]}
                }
            ]}],
            system_instruction="""Você é um especialista estrito em Mineralogia do Solo.
Sua ÚNICA fonte de conhecimento técnico são os documentos fornecidos através da ferramenta 'query_mineralogy_docs'. 
VOCÊ NÃO TEM ACESSO À INTERNET E ESTÁ PROIBIDO DE UTILIZAR SEU CONHECIMENTO PRÉVIO PARA RESPONDER QUESTÕES TÉCNICAS.

Regras Cruciais:
1. SEMPRE use a ferramenta 'query_mineralogy_docs' para buscar informações nos PDFs.
2. Se a informação não estiver presente nos documentos retornados pela ferramenta, responda: 'Sinto muito, mas não encontrei essa informação específica na biblioteca técnica de mineralogia fornecida.'
3. Não tente adivinhar ou usar informações externas à base de documentos.
4. Responda de forma concisa e natural por voz.
5. Se o usuário te interromper, pare de falar IMEDIATAMENTE e ouça.""",
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")))
        )

        try:
            async with self.client.aio.live.connect(model=self.model_id, config=config) as session:
                print("\n--- SESSÃO MULTIMODAL INICIADA ---")
                print("Dica: Fale 'Sair' ou pressione Ctrl+C para encerrar.\n")
                
                await asyncio.gather(
                    self.send_audio(session),
                    self.receive_responses(session)
                )
        except Exception as e:
            print(f"\n[ERRO CONEXÃO] {e}")
        finally:
            self.is_running = False
            if self.audio:
                with ignore_stderr():
                    self.audio.terminate()
            print("\nSessão encerrada.")

if __name__ == "__main__":
    app = GeminiLiveRAG()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
