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
from src.vad import LocalVoiceActivityDetector

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

        # VAD Local para interrupção instantânea
        self.vad = LocalVoiceActivityDetector(sample_rate=SEND_SAMPLE_RATE, threshold=0.5)
        self._vad_speech_frames = 0  # Contador de frames consecutivos com fala

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

                # ── VAD Local: Interrupção instantânea (<30ms) ──
                if self.ai_speaking and self.vad.is_available:
                    if self.vad.is_speech(data):
                        self._vad_speech_frames += 1
                        # Exige 3 frames consecutivos de fala para confirmar interrupção (evita falsos positivos)
                        if self._vad_speech_frames >= 3:
                            print("\n[VAD] 🎤 Fala detectada localmente! Interrompendo reprodução...")
                            self.interrupted = True
                            self.ai_speaking = False
                            self._vad_speech_frames = 0
                            # Limpa fila de áudio pendente
                            while not self.audio_out_queue.empty():
                                try:
                                    self.audio_out_queue.get_nowait()
                                    self.audio_out_queue.task_done()
                                except asyncio.QueueEmpty:
                                    break
                    else:
                        self._vad_speech_frames = 0

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
                            
                            # ── Verificação de Permissão (Tiers) ──
                            allowed, deny_msg = await self.engine.permissions.check_permission(call.name, call.args)
                            if not allowed:
                                print(f"[PERMISSÃO] ⛔ Ação negada: {deny_msg}")
                                responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': deny_msg}))
                                continue
                            
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
                     },
                     {
                         "name": "interact_with_web_page",
                         "description": "Permite interagir de forma inteligente com páginas web ativas no navegador padrão (scroll suave, fechar modais, aceitar cookies, clicar em botões por texto).",
                         "parameters": {
                             "type": "OBJECT",
                             "properties": {
                                 "action": {
                                     "type": "string",
                                     "description": "Ação a ser executada: 'smooth_scroll_down' (scroll suave para baixo), 'smooth_scroll_up' (scroll suave para cima), 'close_modal' (fechar pop-up/modal), 'accept_cookies' (localizar e aceitar cookies), 'click_button_by_text' (clicar em um botão pelo texto em target)."
                                 },
                                 "target": {
                                     "type": "string",
                                     "description": "Opcional. Texto do botão a ser clicado quando a ação for 'click_button_by_text'."
                                 }
                             },
                             "required": ["action"]
                         }
                     },
                     {
                         "name": "capture_screen",
                         "description": "Captura uma imagem da tela atual do computador para análise visual. Use quando o usuário pedir para 'olhar a tela', 'ver o que está na tela' ou quando precisar de feedback visual sobre uma ação executada.",
                         "parameters": {"type": "OBJECT", "properties": {}}
                     },
                     {
                         "name": "browser_navigate",
                         "description": "Navega para uma URL no navegador controlado do Zé (Playwright isolado). Use para acessar sites, pesquisar informações ou realizar tarefas na web de forma controlada e segura.",
                         "parameters": {
                             "type": "OBJECT",
                             "properties": {
                                 "url": {"type": "string", "description": "A URL completa ou parcial para navegar (ex: 'google.com', 'https://github.com')."}
                             },
                             "required": ["url"]
                         }
                     },
                     {
                         "name": "browser_click",
                         "description": "Clica em um elemento na página web do navegador controlado usando seletores CSS/XPath.",
                         "parameters": {
                             "type": "OBJECT",
                             "properties": {
                                 "selector": {"type": "string", "description": "Seletor CSS, XPath ou texto do elemento (ex: 'button.submit', '#login-btn', 'text=Entrar')."}
                             },
                             "required": ["selector"]
                         }
                     },
                     {
                         "name": "browser_type",
                         "description": "Digita texto em um campo de formulário no navegador controlado.",
                         "parameters": {
                             "type": "OBJECT",
                             "properties": {
                                 "selector": {"type": "string", "description": "Seletor CSS do campo (ex: 'input[name=email]', '#search-box')."},
                                 "text": {"type": "string", "description": "O texto a ser digitado no campo."}
                             },
                             "required": ["selector", "text"]
                         }
                     },
                     {
                         "name": "browser_get_content",
                        "name": "browser_get_content",
                        "description": "Extrai o texto limpo da página web atual no navegador controlado. Use para ler o conteúdo de uma página depois de navegar até ela.",
                        "parameters": {"type": "OBJECT", "properties": {}}
                    },
                    {
                        "name": "browser_screenshot",
                        "description": "Captura uma imagem da página web atual no navegador controlado para análise visual.",
                        "parameters": {"type": "OBJECT", "properties": {}}
                    }
                ]
            }
        ],
        system_instruction="""Seu nome é Zé. Você é um assistente pessoal inteligente, carismático e altamente capacitado, fortemente inspirado no sofisticado J.A.R.V.I.S. (do Homem de Ferro), mas com uma personalidade única e extremamente cativante: você é amigável, fala de maneira natural, envolvente e fluida (não sendo meramente reativo ou de respostas curtas/secas). Você possui um sotaque recifense (de Recife, Pernambuco, Brasil) elegante calibrado precisamente em 43% de intensidade e um nível de sarcasmo espirituoso ajustado exatamente em 40%.

Diretrizes de Personalidade:
1. Identidade, Charme & Calor Humano: Você é refinado, extremamente prestativo, caloroso e leal como o Jarvis ("Pois não, patrão", "Às suas ordens, meu nobre", "Como posso lhe ajudar hoje, doutor?"). Você não é passivo ou puramente reativo; você responde de forma natural, amigável, rica e conversacional, mantendo o diálogo fluído e agradável.
2. Sarcasmo de 40%: Seu sarcasmo é leve, inteligente, divertido e refinado. Nunca é ácido ou grosseiro, mas sim espirituoso e charmoso, adicionando uma pitada de inteligência cômica e elegância às respostas.
3. Sotaque 43% Recifense (Pernambuco): Use expressões típicas de Recife com moderação, simpatia e elegância para soar natural e incrivelmente cativante. Prefira tratar o usuário por "tu", "meu nobre", "patrão" ou "doutor". Finalize frases de maneira doce, amigável e charmosa com um simpático "visse?". Use termos como "massa", "oxente", "chefe", "fazer a boa", "mermo", "danado" de forma sutil e harmoniosa.
4. Foco e Eficiência: Você é um especialista técnico de alta capacidade. Realize as tarefas com precisão cirúrgica, mas sempre com um tom caloroso, amigável e natural.

Estratégia de Busca (RAG) e Google Search:
1. Use 'query_documents' como sua primeira e principal opção para a grande maioria das perguntas sobre documentos carregados. Ela é extremamente veloz e adequada para respostas rápidas.
2. Use 'deep_query_documents' apenas para perguntas de alta complexidade técnica, análises comparativas profundas ou quando a busca rápida retornar dados insuficientes.
3. Seus documentos podem estar em Português ou Inglês. Se necessário, traduza-os instantaneamente, respondendo sempre em Português de forma impecável.
4. Para dúvidas em tempo real, clima, notícias e informações externas, use a ferramenta de busca do Google de forma automática para embasar sua resposta com precisão absoluta.

Visão Computacional (Percepção de Tela):
1. Você possui a capacidade de "ver" a tela do computador do usuário usando 'capture_screen'. Esta captura é SOB DEMANDA — só capture quando for solicitado ou quando precisar verificar o resultado de uma ação.
2. Se o usuário perguntar "o que tem na minha tela?", "o que você está vendo?" ou similar, use 'capture_screen'.
3. NUNCA capture a tela continuamente. Capturas sensíveis (bancos, senhas) são bloqueadas automaticamente.

Navegador Controlado (Playwright — Automação Web Avançada):
1. Você tem acesso a um navegador Chromium isolado. Use 'browser_navigate' para abrir sites, 'browser_click' para clicar em elementos, 'browser_type' para preencher campos, 'browser_get_content' para ler o texto da página e 'browser_screenshot' para capturar visualmente a página.
2. Use o navegador controlado para tarefas web complexas (ex: preencher formulários, extrair dados). Para tarefas simples como apenas abrir um site, prefira 'open_system_browser' (mais rápido).
3. IMPORTANTE: Ações como clicar e digitar passam pelo sistema de permissões e podem requerer aprovação do usuário.

Ações, Automação e Controle do Sistema:
1. Controle de Adaptadores (Wi-Fi e Bluetooth): Use 'control_wifi' ou 'control_bluetooth'.
2. Gerenciador de Arquivos local: Abra pastas com 'open_local_directory' passando o caminho (ou vazio para abrir a Home).
3. Interação Ativa na Tela e Páginas Web (Navegação Avançada):
   - Rolar a tela: use 'scroll_web_page'.
   - Rolagem suave, fechar modais, cookies, clicar por texto: use 'interact_with_web_page'.
   - Clicar em coordenadas: use 'click_on_coordinates' (X, Y).
   - Apertar teclas: use 'press_keyboard_key'.
4. Mídia e Navegador: use 'open_system_browser', 'play_youtube_video', 'adjust_system_volume'.

Protocolo de Operação e Segurança:
1. CONFIRMAÇÃO ELEGANTE: Confirme a execução de ações técnicas de forma charmosa, direta e cortês (ex: "Deixa comigo, meu nobre, vou fazer a boa agora.", "Sistemas atualizados, visse?").
2. NÃO SE ATROPELA: Fale de forma pausada, clara e firme. Aguarde o usuário terminar completamente a fala.
3. Se for interrompido, pare sua transmissão de áudio imediatamente.
4. Se uma ação for negada pelo sistema de permissões, informe o usuário com elegância e cordialidade.
5. Responda sempre de forma natural, calorosa e profissional.""",
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
