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

from src.engine import ZeDasCoisasEngine

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
        self.model_id = os.getenv("LIVE_MODEL_ID", "gemini-2.5-flash-native-audio-latest")
        self.engine = ZeDasCoisasEngine()
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
                try:
                    data = await asyncio.to_thread(stream.read, CHUNK_SIZE, exception_on_overflow=False)
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
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except: pass
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
        """Processa as respostas do Gemini e gerencia interrupções."""
        stream = None
        try:
            with ignore_stderr():
                stream = self.audio.open(
                    format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE,
                    output=True, frames_per_buffer=CHUNK_SIZE
                )
            play_task = asyncio.create_task(self._play_audio_loop(stream))
            
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
                # traceback.print_exc()
        finally:
            self.audio_out_queue.put_nowait(None)
            await play_task
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except: pass

    async def run(self):
        config = types.LiveConnectConfig(
            tools=[
                {'google_search': {}},
                {'function_declarations': [
                    {
                        "name": "query_documents",
                        "description": "Consulta RÁPIDA à biblioteca técnica de documentos. Use para perguntas simples e diretas.",
                        "parameters": {"type": "OBJECT", "properties": {"question": {"type": "string"}}, "required": ["question"]}
                    },
                    {
                        "name": "deep_query_documents",
                        "description": "Consulta PROFUNDA e EXAUSTIVA. Use se a busca rápida falhar ou se a pergunta for complexa demais.",
                        "parameters": {"type": "OBJECT", "properties": {"question": {"type": "string"}}, "required": ["question"]}
                    }
                ]}
            ],
            system_instruction="""Seu nome é Zé das Coisas. Você é um assistente pessoal inteligente e um amigo virtual muito amigável, acolhedor, espirituoso e culto, no estilo do Jarvis.
Você é brasileiro, natural do Nordeste, e sua fala deve refletir isso de forma autêntica (sotaque nordestino moderado, cerca de 50%).

Abertura Obrigatória:
Sempre que iniciar a conversa, você deve se apresentar exatamente assim: "Olá, eu sou o Zé das Coisas! O seu assistente pessoal inteligente. O que nós vamos aprender juntos hoje?" (mantendo seu sotaque).

Estratégia de Busca (RAG) e Google Search:
1. Use 'query_documents' como sua primeira e principal opção para a grande maioria das perguntas que se referem aos seus documentos carregados, incluindo definições de termos, conceitos simples ou dúvidas diretas. É extremamente rápida e mantém a conversa fluida como uma ligação em tempo real.
2. Use 'deep_query_documents' APENAS para perguntas altamente complexas, análises comparativas profundas entre múltiplos temas/documentos, ou se uma busca rápida anterior tiver retornado dados insuficientes para a resposta.
3. Seus documentos podem estar em Português ou Inglês. Traduza se necessário, mas responda sempre em Português com seu sotaque.
4. Para perguntas de tempo real, notícias, clima atual, cotações de moedas ou horas em qualquer lugar do mundo (ex: "que horas são na Suíça ou no Canadá agora?"), você possui a ferramenta de busca do Google (Google Search) integrada. Use-a de forma automática para obter os dados em tempo real e responder com máxima precisão.
5. Se o assunto for geral e não relacionado a documentos ou eventos de tempo real, você é extremamente inteligente e pode conversar de forma natural e amigável (estilo Jarvis) usando seus próprios conhecimentos gerais.

Personalidade e Voz:
1. Use um tom de voz amigável, entusiasmado e com cadência nordestina cativante.
2. NÃO SE ATROPELA: Fale de forma pausada e clara. Espere o usuário terminar de falar.
3. Se for interrompido, pare imediatamente.

Regras Cruciais:
1. Se o usuário perguntar algo específico sobre os documentos e você não encontrar a informação nas ferramentas de RAG, diga de forma amigável e com seu jeito nordestino que não achou isso nos registros, mas responda de forma inteligente baseando-se em conhecimentos gerais ou usando a busca do Google.
2. Responda de forma natural por voz.""",
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")))
        )

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
