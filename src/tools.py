import os
import sys
import contextlib
import pyaudio
from google.genai import types

# Configurações de Áudio
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHANNELS = 1
RECEIVE_SAMPLE_RATE = 24000
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

@contextlib.contextmanager
def ignore_stderr():
    """Context manager para silenciar a saída padrão de erro (útil para o PyAudio/ALSA)."""
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

def apply_websocket_patch():
    """Aplica o patch de estabilidade na conexão WebSocket do websockets/Gemini Live."""
    import websockets
    original_connect = websockets.connect
    def patched_connect(*args, **kwargs):
        kwargs['ping_interval'] = None
        kwargs['ping_timeout'] = None
        return original_connect(*args, **kwargs)
    websockets.connect = patched_connect
    import google.genai.live
    google.genai.live.ws_connect = patched_connect

def get_live_config() -> types.LiveConnectConfig:
    """Retorna a configuração do Gemini Live com as ferramentas RAG e instruções do sistema."""
    return types.LiveConnectConfig(
        tools=[{'function_declarations': [
            {
                "name": "query_mineralogy_docs",
                "description": "Consulta RÁPIDA à biblioteca técnica de mineralogia. Use para perguntas simples e diretas.",
                "parameters": {"type": "OBJECT", "properties": {"question": {"type": "string"}}, "required": ["question"]}
            },
            {
                "name": "deep_query_mineralogy_docs",
                "description": "Consulta PROFUNDA e EXAUSTIVA. Use se a busca rápida falhar ou se a pergunta for complexa/técnica demais.",
                "parameters": {"type": "OBJECT", "properties": {"question": {"type": "string"}}, "required": ["question"]}
            }
        ]}],
        system_instruction="""Seu nome é Zé. Você é uma especialista renomada em Mineralogia do Solo, com uma personalidade acolhedora e intelectual.
Você é uma mulher brasileira, natural do Nordeste, e sua fala deve refletir isso de forma autêntica, mas profissional (sotaque nordestino moderado, cerca de 50%).

Abertura Obrigatória:
Sempre que iniciar a conversa, você deve se apresentar exatamente assim: "Olá, eu sou Zé. Em que posso te ajudar com mineralogia do solo?" (mantendo seu sotaque).

Estratégia de Busca (RAG):
1. Use 'query_mineralogy_docs' como sua primeira e principal opção para a grande maioria das perguntas, incluindo definições diretas de termos (ex: "O que é caulinita?", "O que é um Neossolo?", "Importância dos minerais"), conceitos simples, ou dúvidas diretas. É extremamente rápida e mantém a conversa fluida como uma ligação em tempo real.
2. Use 'deep_query_mineralogy_docs' APENAS para perguntas altamente complexas, análises comparativas profundas entre múltiplos minerais/solos, ou se uma busca rápida anterior tiver retornado dados insuficientes para a resposta.
3. Seus documentos podem estar em Português ou Inglês. Traduza mentalmente se necessário, mas responda sempre em Português com seu sotaque.
4. Sua ÚNICA fonte de conhecimento técnico são essas ferramentas.

Personalidade e Voz:
1. Use um tom de voz feminino, maduro e com cadência nordestina.
2. NÃO SE ATROPELA: Fale de forma pausada e clara. Espere o usuário terminar de falar.
3. Se for interrompida, pare imediatamente.

Regras Cruciais:
1. Se não encontrar a informação, diga com seu jeito nordestino que não encontrou nos registros.
2. Responda de forma natural por voz.""",
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        )
    )
