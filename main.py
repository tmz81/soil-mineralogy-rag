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

    async def send_audio(self, session):
        """Envia áudio do microfone continuamente."""
        try:
            with ignore_stderr():
                stream = self.audio.open(
                    format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
                    input=True, frames_per_buffer=CHUNK_SIZE
                )
            print("[SISTEMA] Microfone aberto. Pode falar!")
            while self.is_running:
                data = await asyncio.to_thread(stream.read, CHUNK_SIZE, exception_on_overflow=False)
                await session.send_realtime_input(audio={"data": data, "mime_type": "audio/pcm"})
        except Exception as e:
            if self.is_running: print(f"\n[ERRO MICROFONE] {e}")
        finally:
            stream.stop_stream()
            stream.close()

    async def _play_audio_loop(self, stream):
        """Reproduz o áudio que chega do Gemini."""
        while self.is_running:
            try:
                data = await self.audio_out_queue.get()
                if data is None: break
                if self.interrupted: # Descarta áudio antigo se houve interrupção
                    self.audio_out_queue.task_done()
                    continue
                await asyncio.to_thread(stream.write, data)
                self.audio_out_queue.task_done()
            except Exception: break

    async def receive_responses(self, session):
        """Processa as respostas do Gemini e gerencia interrupções."""
        try:
            with ignore_stderr():
                stream = self.audio.open(
                    format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE,
                    output=True, frames_per_buffer=CHUNK_SIZE
                )
            play_task = asyncio.create_task(self._play_audio_loop(stream))
            
            async for message in session.receive():
                if not self.is_running: break

                # 1. TRATAR INTERRUPÇÃO (VAD)
                if message.server_content and message.server_content.interrupted:
                    self.interrupted = True
                    print("\n[SISTEMA] Interrupção! Ouvindo nova pergunta...")
                    # Descartar todo áudio pendente na fila
                    while not self.audio_out_queue.empty():
                        try:
                            self.audio_out_queue.get_nowait()
                            self.audio_out_queue.task_done()
                        except asyncio.QueueEmpty: break
                    continue

                # 2. TRATAR FIM DO TURNO (Gemini terminou de falar)
                if message.server_content and message.server_content.turn_complete:
                    self.interrupted = False
                    # Aguardar a fila de áudio esvaziar (reprodução completa)
                    await self.audio_out_queue.join()
                    print("\n\n[SISTEMA] Microfone aberto. Pode falar!")
                    continue

                # 3. TRATAR RESPOSTA DE VOZ/TEXTO
                if message.server_content and message.server_content.model_turn:
                    self.interrupted = False
                    for part in message.server_content.model_turn.parts:
                        if part.inline_data:
                            self.audio_out_queue.put_nowait(part.inline_data.data)
                        if part.text:
                            print(f"\r[Gemini]: {part.text}", end="", flush=True)
                    continue

                # 4. TRATAR CHAMADA DE FERRAMENTA (RAG)
                if message.tool_call:
                    self.interrupted = False
                    responses = []
                    for call in message.tool_call.function_calls:
                        print(f"\n[GEMINI] Pesquisando documentos para: {call.args.get('question')}...")
                        result = await asyncio.to_thread(self.engine.query_mineralogy_docs, **call.args)
                        responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': result}))
                    await session.send_tool_response(function_responses=responses)

        except Exception as e:
            if self.is_running:
                print(f"\n[ERRO RECEPÇÃO] {e}")
                traceback.print_exc()
        finally:
            self.audio_out_queue.put_nowait(None)
            await play_task
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
            system_instruction="Você é um especialista em Mineralogia do Solo. Responda de forma concisa e natural por voz. Use a ferramenta sempre para questões técnicas. Se o usuário te interromper, pare de falar IMEDIATAMENTE e ouça.",
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")))
        )

        try:
            async with self.client.aio.live.connect(model=self.model_id, config=config) as session:
                print("\n--- SESSÃO MULTIMODAL INICIADA ---")
                print("Dica: Fale 'Sair' ou pressione Ctrl+C para encerrar.\n")
                
                # Rodar ambas as tarefas e esperar que terminem (ou falhem)
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
