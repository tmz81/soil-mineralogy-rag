"""
Soil Mineralogy RAG - FastAPI Backend Server
=============================================
Servidor local com REST + WebSocket de voz em tempo real.
O WebSocket faz bridge entre o browser (Web Audio API) e o Gemini Multimodal Live.
"""

import os
import sys
import json
import shutil
import asyncio
import base64
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, set_key, dotenv_values

from google import genai
from google.genai import types

# Caminhos base (Suporte para executável empacotado em sistema de arquivos Read-Only como AppImage)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path.home() / ".soil-mineralogy-rag"
    BASE_DIR.mkdir(exist_ok=True, parents=True)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DOCS_DIR = BASE_DIR / "docs"
CHROMA_DIR = BASE_DIR / "chroma_db"
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / "env.example"

# Cria automaticamente o .env se não existir
if not ENV_FILE.exists():
    if ENV_EXAMPLE.exists():
        shutil.copy(str(ENV_EXAMPLE), str(ENV_FILE))
        print(f"\n[SISTEMA] Arquivo '.env' criado automaticamente com base em 'env.example'.")
    else:
        ENV_FILE.touch()
        print(f"\n[SISTEMA] Arquivo '.env' criado em branco.")

DOCS_DIR.mkdir(exist_ok=True, parents=True)
load_dotenv(ENV_FILE)

# Aviso proeminente no console se a chave estiver ausente
api_key = os.environ.get("GOOGLE_API_KEY", "")
if not api_key:
    print("\n" + "!"*80)
    print("[AVISO] A chave 'GOOGLE_API_KEY' não está configurada no arquivo '.env'!")
    print("O RAG Multimodal Live de Voz não funcionará até que você configure esta chave.")
    print("Configure-a na aba Configurações no painel do Electron ou edite o arquivo '.env'.")
    print("!"*80 + "\n")

logger = logging.getLogger("soil-rag")

app = FastAPI(title="Soil Mineralogy RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Engine (lazy loading) ──────────────────────────────────────────────────
_engine_instance = None
_engine_lock = asyncio.Lock()


async def get_engine():
    global _engine_instance
    if _engine_instance is None:
        async with _engine_lock:
            if _engine_instance is None:
                from engine import ZeDasCoisasEngine
                _engine_instance = await asyncio.to_thread(ZeDasCoisasEngine)
    return _engine_instance


def reset_engine():
    global _engine_instance
    _engine_instance = None


# ─── Pydantic Models ────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    google_api_key: str

class ChatRequest(BaseModel):
    question: str
    deep_search: bool = False

class DeleteRequest(BaseModel):
    filename: str


# ─── Config Endpoints ───────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    values = dotenv_values(ENV_FILE)
    api_key = values.get("GOOGLE_API_KEY", "")
    masked = ""
    if api_key:
        masked = api_key[:8] + "•" * max(0, len(api_key) - 12) + api_key[-4:] if len(api_key) > 12 else "•" * len(api_key)
    return {"google_api_key_masked": masked, "google_api_key_set": bool(api_key)}


@app.post("/api/config")
async def update_config(config: ConfigUpdate):
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    set_key(str(ENV_FILE), "GOOGLE_API_KEY", config.google_api_key)
    os.environ["GOOGLE_API_KEY"] = config.google_api_key
    reset_engine()
    return {"status": "success", "message": "API Key salva com sucesso!"}


@app.post("/api/config/validate")
async def validate_api_key(config: ConfigUpdate):
    try:
        client = genai.Client(api_key=config.google_api_key)
        models = await asyncio.to_thread(lambda: list(client.models.list()))
        return {"status": "valid", "message": f"Chave válida! {len(models)} modelos disponíveis."}
    except Exception as e:
        return {"status": "invalid", "message": f"Chave inválida: {str(e)}"}


# ─── Document Endpoints ─────────────────────────────────────────────────────

@app.get("/api/documents")
async def list_documents():
    files = []
    if DOCS_DIR.exists():
        for f in sorted(DOCS_DIR.iterdir()):
            if f.suffix.lower() in [".pdf", ".docx", ".txt"]:
                stat = f.stat()
                files.append({"name": f.name, "size_bytes": stat.st_size, "size_display": f"{stat.st_size / (1024*1024):.1f} MB"})
    return {"documents": files, "total": len(files)}


@app.post("/api/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    uploaded, errors = [], []
    
    # Valida o limite de até 20 arquivos no total
    current_files = [f for f in DOCS_DIR.iterdir() if f.suffix.lower() in [".pdf", ".docx", ".txt"]] if DOCS_DIR.exists() else []
    if len(current_files) + len(files) > 20:
        return {
            "uploaded": [],
            "errors": [f"A biblioteca suporta no máximo 20 documentos no total. Você já possui {len(current_files)} arquivo(s)."],
            "message": "Limite de 20 documentos excedido."
        }

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in [".pdf", ".docx", ".txt"]:
            errors.append(f"'{file.filename}' não é um tipo suportado (.pdf, .docx, .txt).")
            continue
        try:
            content = await file.read()
            if len(content) > 200 * 1024 * 1024:
                errors.append(f"O arquivo '{file.filename}' excede o limite máximo permitido de 200 MB.")
                continue
            (DOCS_DIR / file.filename).write_bytes(content)
            uploaded.append({"name": file.filename, "size_display": f"{len(content)/(1024*1024):.1f} MB"})
        except Exception as e:
            errors.append(f"Erro '{file.filename}': {e}")
    return {"uploaded": uploaded, "errors": errors, "message": f"{len(uploaded)} arquivo(s) carregado(s)."}


@app.post("/api/delete")
async def delete_document(req: DeleteRequest):
    filepath = DOCS_DIR / req.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    filepath.unlink()
    return {"status": "success", "message": f"'{req.filename}' excluído."}


# ─── Indexation Endpoints ───────────────────────────────────────────────────

@app.post("/api/index")
async def index_documents():
    try:
        reset_engine()
        import gc
        gc.collect()
        await asyncio.sleep(0.5)
        
        if CHROMA_DIR.exists():
            shutil.rmtree(CHROMA_DIR)
            
        engine = await get_engine()
        
        # Aguarda a indexação iniciada em segundo plano no __init__ terminar
        while getattr(engine, "is_indexing", False):
            await asyncio.sleep(0.5)
            
        try:
            doc_count = engine.vectorstore._collection.count()
        except Exception:
            doc_count = 0
        return {"status": "success", "message": f"Indexação concluída! {doc_count} trechos.", "chunks_indexed": doc_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")


@app.post("/api/reset-db")
async def reset_database():
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    reset_engine()
    return {"status": "success", "message": "Banco resetado."}


@app.get("/api/db-status")
async def database_status():
    db_exists = CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir()) if CHROMA_DIR.exists() else False
    chunks = 0
    is_indexing = False
    try:
        engine = await get_engine()
        is_indexing = getattr(engine, "is_indexing", False)
        if db_exists and not is_indexing:
            chunks = engine.vectorstore._collection.count()
    except Exception:
        pass
    pdf_count = len([f for f in DOCS_DIR.iterdir() if f.suffix.lower() in [".pdf", ".docx", ".txt"]]) if DOCS_DIR.exists() else 0
    return {"db_exists": db_exists, "chunks_indexed": chunks, "pdf_count": pdf_count, "is_indexing": is_indexing}


# ─── Chat Endpoint ──────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        engine = await get_engine()
        if req.deep_search:
            context = await engine.deep_query_documents(req.question)
        else:
            context = await asyncio.to_thread(engine.query_documents, req.question)
        prompt = f"""Você é o Zé das Coisas, um assistente virtual inteligente e amigável.
Use os trechos de documentos abaixo para responder à pergunta. Responda sempre em Português do Brasil (PT-BR), traduzindo livremente se o trecho original estiver em inglês. Se não encontrar nos documentos, responda de forma amigável usando seus próprios conhecimentos gerais como um assistente inteligente estilo Jarvis, mencionando de forma sutil que essa informação não está diretamente nos documentos.

Contexto dos documentos carregados: {context}

Pergunta: {req.question}

Resposta:"""
        response = await engine.llm.ainvoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)
        return {"answer": answer, "question": req.question}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")


# ─── WebSocket: Sessão de Voz em Tempo Real com Zé ──────────────────────────
#
# Fluxo:
# 1. Electron captura mic via Web Audio API → PCM 16kHz mono
# 2. Envia chunks de áudio como base64 via WebSocket para cá
# 3. Este server faz bridge com Gemini Multimodal Live API
# 4. Recebe áudio de resposta do Gemini → envia de volta base64 ao Electron
# 5. Electron reproduz via Web Audio API
#
# Mensagens do cliente → server:
#   {"type": "audio", "data": "<base64 pcm>"}
#   {"type": "stop"}
#
# Mensagens do server → cliente:
#   {"type": "audio", "data": "<base64 pcm>"}
#   {"type": "turn_complete"}
#   {"type": "interrupted"}
#   {"type": "tool_call", "name": "...", "status": "calling"}
#   {"type": "transcript", "text": "..."}
#   {"type": "status", "message": "..."}
#   {"type": "error", "message": "..."}

# Patch de estabilidade WebSocket (do main.py original)
import websockets
_original_ws_connect = websockets.connect
def _patched_ws_connect(*args, **kwargs):
    kwargs['ping_interval'] = None
    kwargs['ping_timeout'] = None
    return _original_ws_connect(*args, **kwargs)
websockets.connect = _patched_ws_connect
import google.genai.live
google.genai.live.ws_connect = _patched_ws_connect


def _build_live_config():
    """Constrói a configuração do Gemini Live idêntica ao main.py."""
    return types.LiveConnectConfig(
        tools=[{'function_declarations': [
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
        ]}],
        system_instruction="""Seu nome é Zé das Coisas. Você é um assistente pessoal inteligente e um amigo virtual muito amigável, acolhedor, espirituoso e culto, no estilo do Jarvis.
Você é brasileiro, natural do Nordeste, e sua fala deve refletir isso de forma autêntica (sotaque nordestino moderado, cerca de 50%).

Abertura Obrigatória:
Sempre que iniciar a conversa, você deve se apresentar exatamente assim: "Olá, eu sou o Zé das Coisas! O seu assistente pessoal inteligente. O que nós vamos aprender juntos hoje?" (mantendo seu sotaque).

Estratégia de Busca (RAG):
1. Use 'query_documents' como sua primeira e principal opção para a grande maioria das perguntas que se referem aos seus documentos carregados, incluindo definições de termos, conceitos simples ou dúvidas diretas. É extremamente rápida e mantém a conversa fluida como uma ligação em tempo real.
2. Use 'deep_query_documents' APENAS para perguntas altamente complexas, análises comparativas profundas entre múltiplos temas/documentos, ou se uma busca rápida anterior tiver retornado dados insuficientes para a resposta.
3. Seus documentos podem estar em Português ou Inglês. Traduza se necessário, mas responda sempre em Português com seu sotaque.
4. Se o assunto for geral e não relacionado aos documentos carregados na biblioteca, você é extremamente inteligente e pode conversar de forma natural e amigável (estilo Jarvis) usando seus próprios conhecimentos gerais, sem precisar chamar as ferramentas de RAG.

Personalidade e Voz:
1. Use um tom de voz amigável, entusiasmado e com cadência nordestina cativante.
2. NÃO SE ATROPELA: Fale de forma pausada e clara. Espere o usuário terminar de falar.
3. Se for interrompido, pare imediatamente.

Regras Cruciais:
1. Se o usuário perguntar algo específico sobre os documentos e você não encontrar a informação nas ferramentas, diga de forma amigável e com seu jeito nordestino que não achou isso nos registros, mas ofereça uma resposta inteligente baseada em conhecimentos gerais se for possível.
2. Responda de forma natural por voz.""",
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        )
    )


@app.websocket("/api/voice")
async def voice_session(ws: WebSocket):
    """WebSocket bridge: Browser Audio ↔ Gemini Multimodal Live API."""
    await ws.accept()
    await ws.send_json({"type": "status", "message": "Conectando com Zé..."})

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        await ws.send_json({"type": "error", "message": "GOOGLE_API_KEY não configurada."})
        await ws.close()
        return

    # Carregar engine para as ferramentas RAG
    try:
        engine = await get_engine()
    except Exception as e:
        await ws.send_json({"type": "error", "message": f"Erro ao carregar engine: {e}"})
        await ws.close()
        return

    # Se a engine estiver indexando (p. ex. na 1ª execução), aguarda a indexação terminar
    if getattr(engine, "is_indexing", False):
        await ws.send_json({"type": "status", "message": "Indexando biblioteca técnica pela primeira vez... Por favor, aguarde..."})
        while getattr(engine, "is_indexing", False):
            await asyncio.sleep(1.0)

    client = genai.Client(api_key=api_key)
    config = _build_live_config()
    is_running = True

    try:
        async with client.aio.live.connect(model="gemini-3.1-flash-live-preview", config=config) as session:
            await ws.send_json({"type": "status", "message": "Conectado! Fale agora..."})
            await ws.send_json({"type": "connected"})

            # ── Task: Receber áudio do browser e enviar ao Gemini ────────
            async def forward_browser_audio():
                nonlocal is_running
                while is_running:
                    try:
                        raw = await asyncio.wait_for(ws.receive_text(), timeout=0.1)
                        msg = json.loads(raw)

                        if msg.get("type") == "audio":
                            pcm_data = base64.b64decode(msg["data"])
                            await session.send_realtime_input(
                                audio={"data": pcm_data, "mime_type": "audio/pcm"}
                            )
                        elif msg.get("type") == "stop":
                            is_running = False
                            break
                    except asyncio.TimeoutError:
                        continue
                    except WebSocketDisconnect:
                        is_running = False
                        break
                    except Exception as e:
                        logger.error(f"[Voice WS] Erro recebendo do browser: {e}")
                        is_running = False
                        break

            # ── Task: Receber respostas do Gemini e enviar ao browser ────
            async def forward_gemini_responses():
                nonlocal is_running
                while is_running:
                    try:
                        async for message in session.receive():
                            if not is_running:
                                break

                            # Interrupção
                            if message.server_content and message.server_content.interrupted:
                                await ws.send_json({"type": "interrupted"})
                                continue

                            # Turno completo
                            if message.server_content and message.server_content.turn_complete:
                                await ws.send_json({"type": "turn_complete"})
                                continue

                            # Áudio / texto do modelo
                            if message.server_content and message.server_content.model_turn:
                                for part in message.server_content.model_turn.parts:
                                    if part.inline_data:
                                        audio_b64 = base64.b64encode(part.inline_data.data).decode()
                                        await ws.send_json({"type": "audio", "data": audio_b64})
                                    if part.text:
                                        await ws.send_json({"type": "transcript", "text": part.text})
                                continue

                            # Tool calls (RAG)
                            if message.tool_call:
                                responses = []
                                for call in message.tool_call.function_calls:
                                    await ws.send_json({"type": "tool_call", "name": call.name, "status": "calling"})
                                    try:
                                        func = getattr(engine, call.name)
                                        if asyncio.iscoroutinefunction(func):
                                            result = await func(**call.args)
                                        else:
                                            result = await asyncio.to_thread(func, **call.args)
                                        responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': result}))
                                        try:
                                            await ws.send_json({
                                                "type": "debug", 
                                                "source": "RAG", 
                                                "message": f"Extração via {call.name} executada.", 
                                                "data": result
                                            })
                                        except: pass
                                    except Exception as e:
                                        responses.append(types.FunctionResponse(name=call.name, id=call.id, response={'result': f"Erro: {e}"}))
                                await session.send_tool_response(function_responses=responses)
                                continue

                    except Exception as e:
                        if is_running:
                            logger.error(f"[Voice WS] Erro Gemini: {e}")
                            try:
                                await ws.send_json({"type": "error", "message": str(e)})
                            except: pass
                        is_running = False
                        break

            # Rodar ambas as tasks em paralelo
            await asyncio.gather(
                forward_browser_audio(),
                forward_gemini_responses(),
                return_exceptions=True
            )

    except WebSocketDisconnect:
        logger.info("[Voice WS] Cliente desconectou.")
    except Exception as e:
        logger.error(f"[Voice WS] Erro na sessão: {e}")
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        is_running = False
        logger.info("[Voice WS] Sessão encerrada.")


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
