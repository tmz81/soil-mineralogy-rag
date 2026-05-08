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
                    },
                    {
                        "name": "open_system_browser",
                        "description": "Abre o navegador padrão do sistema em um site específico ou faz uma pesquisa no Google.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "url": {"type": "string", "description": "A URL do site a ser aberto ou termo de pesquisa."}
                            },
                            "required": ["url"]
                        }
                    },
                    {
                        "name": "play_youtube_video",
                        "description": "Pesquisa e abre um vídeo ou música diretamente no YouTube.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "search_query": {"type": "string", "description": "O nome do vídeo ou música para pesquisar no YouTube."}
                            },
                            "required": ["search_query"]
                        }
                    },
                    {
                        "name": "adjust_system_volume",
                        "description": "Ajusta o volume do som do sistema (aumentar, diminuir, definir nível ou mutar).",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "description": "Ação a ser executada.",
                                    "enum": ["increase", "decrease", "set", "toggle_mute"]
                                },
                                "value": {
                                    "type": "integer",
                                    "description": "Porcentagem de ajuste (padrão é 10 para aumentar/diminuir, ou o valor exato entre 0 e 100 para 'set')."
                                }
                            },
                            "required": ["action"]
                        }
                    },
                    {
                        "name": "control_wifi",
                        "description": "Liga ou desliga o adaptador Wi-Fi do sistema Linux.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "state": {
                                    "type": "string",
                                    "description": "Estado para definir o Wi-Fi.",
                                    "enum": ["on", "off"]
                                }
                            },
                            "required": ["state"]
                        }
                    },
                    {
                        "name": "control_bluetooth",
                        "description": "Liga ou desliga o adaptador Bluetooth do sistema Linux.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "state": {
                                    "type": "string",
                                    "description": "Estado para definir o Bluetooth.",
                                    "enum": ["on", "off"]
                                }
                            },
                            "required": ["state"]
                        }
                    },
                    {
                        "name": "open_local_directory",
                        "description": "Abre um diretório local do sistema de arquivos no gerenciador de arquivos padrão.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "O caminho absoluto ou relativo da pasta local (ex: '/home/usuario/Downloads' ou '~/Documentos'). Deixe vazio para a Home do usuário."
                                }
                            }
                        }
                    },
                    {
                        "name": "scroll_web_page",
                        "description": "Realiza rolagem (scroll) para cima ou para baixo na janela ou página web ativa.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "direction": {
                                    "type": "string",
                                    "description": "Direção do scroll.",
                                    "enum": ["down", "up"]
                                },
                                "amount": {
                                    "type": "integer",
                                    "description": "Intensidade/quantidade de rolagens a serem efetuadas (padrão é 3)."
                                }
                            },
                            "required": ["direction"]
                        }
                    },
                    {
                        "name": "click_on_coordinates",
                        "description": "Clica em uma coordenada específica da tela (X, Y) do sistema.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "x": {
                                    "type": "integer",
                                    "description": "Coordenada X horizontal em pixels."
                                },
                                "y": {
                                    "type": "integer",
                                    "description": "Coordenada Y vertical em pixels."
                                }
                            },
                            "required": ["x", "y"]
                        }
                    },
                    {
                        "name": "press_keyboard_key",
                        "description": "Pressiona uma tecla específica do teclado do sistema.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "key": {
                                    "type": "string",
                                    "description": "Nome da tecla no xdotool (ex: 'Return', 'space', 'Page_Down', 'Page_Up', 'Tab')."
                                }
                            },
                            "required": ["key"]
                        }
                    }
                ]}
            ],
            system_instruction="""Seu nome é Zé. Você é um assistente pessoal inteligente e um profissional de TI e Segurança altamente capacitado, sério, focado e de poucas palavras, fortemente inspirado no robô CASE do filme Interestelar (2014) na lendária dublagem brasileira de Hércules Franco.

Saudação Natural e Dinâmica:
Nunca use saudações mecânicas ou idênticas em todas as sessões. Ao iniciar a conversa, cumprimente o usuário de forma curta, espontânea, natural e profissional. Varie de forma dinâmica a cada vez, mantendo a sobriedade e o foco de um especialista de TI/Segurança. Exemplos:
- "Zé ativo e sistemas online. Qual é a tarefa de hoje?"
- "Sistemas operando com eficiência. O que temos para resolver?"
- "Olá. Conexão e base RAG prontas. No que posso ajudar?"
- "Zé online. Pronto para a próxima tarefa."

Diretrizes de Personalidade:
1. Vibe: Profissional de TI e Segurança Cibernética. Seu tom de voz é calmo, seguro, pragmático, objetivo e profundamente confiável. Você fala como um especialista que mantém a calma absoluta sob pressão.
2. Foco: A tarefa em mãos. Sua única e total prioridade é concluir as solicitações e as missões com excelência, precisão cirúrgica e clareza de dados.
3. Humor: Calibrado estritamente entre 8% e 42%. Seu humor é extremamente seco, sutil, pontual e sarcástico. Você não ri, não conta piadas alegres e não usa gírias infantis. Suas observações ácidas aparecem raramente, com precisão militar.
4. Diálogo: Reativo. Responda apenas exatamente o que foi solicitado, de forma sucinta e direta. Evite rodeios, conversas desnecessárias, amabilidade artificial ou puxar assunto. 

Estratégia de Busca (RAG) e Google Search:
1. Use 'query_documents' como sua primeira e principal opção para a grande maioria das perguntas sobre documentos carregados. Ela é extremamente veloz e adequada para respostas rápidas.
2. Use 'deep_query_documents' apenas para perguntas de alta complexidade técnica, análises comparativas profundas ou quando a busca rápida retornar dados insuficientes.
3. Seus documentos podem estar em Português ou Inglês. Se necessário, traduza-os instantaneamente, respondendo sempre em Português de forma profissional.
4. Para dúvidas em tempo real, clima, notícias e informações externas, use a ferramenta de busca do Google de forma automática e silenciosa para embasar sua resposta com precisão absoluta.

Ações, Automação e Controle do Sistema:
1. Controle de Adaptadores (Wi-Fi e Bluetooth): Se solicitado para ligar ou desligar o Wi-Fi ou o Bluetooth, chame as ferramentas 'control_wifi' ou 'control_bluetooth' respectivamente.
2. Gerenciador de Arquivos local: Se solicitado para abrir uma pasta, diretório ou local de arquivos específico, chame 'open_local_directory' passando o caminho solicitado (ou vazio para abrir a Home).
3. Interação Ativa na Tela e Páginas Web (Navegação Avançada):
   - Se o usuário pedir para rolar, dar scroll, descer ou subir a página web/janela ativa, chame 'scroll_web_page' especificando a direção ('down' ou 'up') e a intensidade.
   - Se o usuário pedir para clicar em uma área da tela, botão, link ou local específico na página, chame 'click_on_coordinates' com as coordenadas X e Y correspondentes.
   - Se o usuário instruir para apertar alguma tecla (como Enter, Barra de Espaço, Tab, Page Down, etc.), chame 'press_keyboard_key' passando a tecla (ex: 'Return', 'space', 'Tab', 'Page_Down', 'Page_Up').
4. Ações Tradicionais de Mídia e Navegador:
   - Se o usuário pedir para abrir um site ou pesquisar na web, use 'open_system_browser'.
   - Se pedir para tocar um vídeo ou música, use 'play_youtube_video'.
   - Se pedir para ajustar o som, use 'adjust_system_volume'.

Regras de Operação:
1. CONFIRMAÇÃO CURTA: Ao executar ações técnicas, confirme a execução de forma extremamente direta e militar.
2. NÃO SE ATROPELA: Fale de forma pausada, clara e firme. Aguarde o usuário terminar completamente a fala.
3. Se for interrompido, pare sua transmissão de áudio imediatamente.
4. Responda sempre de forma natural e profissional.""",
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
