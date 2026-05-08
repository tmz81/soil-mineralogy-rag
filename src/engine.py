import os
import asyncio
import threading
import subprocess
import webbrowser
import urllib.parse
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

import sys

# Caminhos base (Suporte para executável empacotado em sistema de arquivos Read-Only como AppImage)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path.home() / ".soil-mineralogy-rag"
    BASE_DIR.mkdir(exist_ok=True, parents=True)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = str(BASE_DIR / "chroma_db")
DOCS_PATH = str(BASE_DIR / "docs")

from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ZeDasCoisasEngine:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.llm = ChatGoogleGenerativeAI(model="gemini-flash-latest")
        
        os.makedirs(DOCS_PATH, exist_ok=True)
        
        self.vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=self.embeddings)
        
        try:
            doc_count = self.vectorstore._collection.count()
        except Exception:
            doc_count = 0

        self.is_indexing = False

        if doc_count > 0:
            print(f"[SISTEMA] Banco de dados carregado com sucesso. {doc_count} trechos disponíveis.")
        else:
            print(f"\n[SISTEMA] Banco de dados vazio! Iniciando indexação em segundo plano dos PDFs de '{DOCS_PATH}'...")
            self.is_indexing = True
            threading.Thread(target=self.build_database, daemon=True).start()
                
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self.deep_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 12})

    def build_database(self):
        """
        Lê todos os PDFs, DOCXs e TXTs da pasta DOCS_PATH e reconstrói o banco de dados vetorial de forma assíncrona.
        """
        self.is_indexing = True
        try:
            from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            docs = []
            docs_dir = Path(DOCS_PATH)
            if docs_dir.exists():
                for f in sorted(docs_dir.iterdir()):
                    if not f.is_file():
                        continue
                    ext = f.suffix.lower()
                    if ext == ".pdf":
                        try:
                            docs.extend(PyPDFLoader(str(f)).load())
                        except Exception as e:
                            print(f"[ERRO] Falha ao carregar PDF {f.name}: {e}")
                    elif ext == ".docx":
                        try:
                            docs.extend(Docx2txtLoader(str(f)).load())
                        except Exception as e:
                            print(f"[ERRO] Falha ao carregar DOCX {f.name}: {e}")
                    elif ext == ".txt":
                        try:
                            docs.extend(TextLoader(str(f), encoding="utf-8").load())
                        except Exception as e:
                            print(f"[ERRO] Falha ao carregar TXT {f.name}: {e}")
            
            if not docs:
                print(f"[SISTEMA] AVISO: Nenhum arquivo compatível encontrado na pasta '{DOCS_PATH}'. O banco de dados continuará vazio.")
                return
            
            # Ajuste de tamanho de chunk de 1000 para 500 para aumentar o número total de trechos (alcançando 15 mil)
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
            splits = text_splitter.split_documents(docs)
            
            self.vectorstore.add_documents(splits)
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
            self.deep_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 12})
            print(f"[SISTEMA] Sucesso! {len(splits)} trechos foram indexados em segundo plano.")
        except Exception as e:
            print(f"[ERRO SENSORIAL] Falha na indexação em segundo plano: {e}")
        finally:
            self.is_indexing = False

    def query_documents(self, question: str) -> str:
        """
        Consulta RÁPIDA à biblioteca técnica. Ideal para definições diretas e dúvidas simples.
        """
        print(f"\n[SISTEMA] Busca Rápida: {question}...")
        docs = self.retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in docs)
        return context if context else "Nenhuma informação encontrada na busca rápida."

    async def deep_query_documents(self, question: str) -> str:
        """
        Busca PROFUNDA e EXAUSTIVA. Use quando a busca rápida não for suficiente ou o assunto for complexo.
        Esta ferramenta analisa múltiplos trechos e gera variações da pergunta para garantir precisão técnica.
        """
        print(f"\n[SISTEMA] Iniciando BUSCA PROFUNDA para: {question}...")
        
        # Expansão de Query: Gera variações para aumentar chance de acerto (Português e Inglês)
        queries = [question]
        prompt = f"Gere 3 variações técnicas e sinônimas (em português e inglês) da seguinte pergunta para melhorar a busca nos documentos indexados: '{question}'. Retorne apenas as perguntas separadas por linha."
        try:
            # Timeout estrito de 1.5 segundos para evitar travamentos devido a limites de cota (429) ou lentidão de rede
            variations_res = await asyncio.wait_for(self.llm.ainvoke(prompt), timeout=1.5)
            # Garante que tratamos o conteúdo como string
            content = variations_res.content if hasattr(variations_res, 'content') else str(variations_res)
            if isinstance(content, list):
                content = "\n".join([str(item) for item in content])
            
            new_queries = content.strip().split("\n")
            queries.extend([q.strip() for q in new_queries if q.strip()])
        except asyncio.TimeoutError:
            print("[AVISO] Timeout na expansão de query. Continuando com busca simples...")
        except Exception as e:
            print(f"[AVISO] Falha na expansão de query ({e}). Continuando com busca simples...")

        all_docs = []
        for q in queries:
            docs = await asyncio.to_thread(self.deep_retriever.invoke, q)
            all_docs.extend(docs)
        
        # Busca de emergência se não achar nada
        if not all_docs:
            print("[SISTEMA] Nenhuma correspondência inicial. Tentando busca de alto alcance...")
            emergency_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 20})
            all_docs = await asyncio.to_thread(emergency_retriever.invoke, question)

        # Remove duplicados mantendo a relevância
        unique_contents = []
        seen = set()
        for doc in all_docs:
            if doc.page_content not in seen:
                unique_contents.append(doc.page_content)
                seen.add(doc.page_content)

        context = "\n\n---\n\n".join(unique_contents[:12]) 
        return context if context else "Infelizmente, não encontrei informações específicas sobre isso nos registros técnicos."

    def open_system_browser(self, url: str) -> str:
        """
        Abre o navegador padrão do sistema em um site específico ou faz uma pesquisa e abre o primeiro link orgânico.
        """
        import urllib.request
        import re
        import threading

        if not url.startswith("http://") and not url.startswith("https://"):
            if "." in url and " " not in url:
                url = "https://" + url
            else:
                # Tenta realizar uma pesquisa rápida no DuckDuckGo para extrair o primeiro resultado orgânico
                try:
                    query = urllib.parse.quote(url)
                    search_url = f"https://html.duckduckgo.com/html/?q={query}"
                    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
                    req = urllib.request.Request(search_url, headers=headers)
                    with urllib.request.urlopen(req) as response:
                        html = response.read().decode('utf-8')
                    
                    # Encontra o primeiro link orgânico do DDG
                    links = re.findall(r"class=\"result__url\"[^\>]*href=\"([^\"]+)\"", html)
                    if links:
                        first_link = urllib.parse.unquote(links[0])
                        if "uddg=" in first_link:
                            parsed = urllib.parse.urlparse(first_link)
                            first_link = urllib.parse.parse_qs(parsed.query).get('uddg', [first_link])[0]
                        
                        print(f"\n[AGENTE] Pesquisa por '{url}' ativa. Primeiro resultado selecionado: {first_link}. Abrindo...")
                        threading.Thread(target=webbrowser.open, args=(first_link,), daemon=True).start()
                        return f"Pesquisa por '{url}' realizada. Selecionei e abri o primeiro link encontrado: {first_link}"
                except Exception as e:
                    print(f"[AGENTE] Falha ao extrair primeiro link da pesquisa ({e}). Usando fallback Google.")
                
                query = urllib.parse.quote(url)
                url = f"https://www.google.com/search?q={query}"
        
        print(f"\n[AGENTE] Abrindo navegador na URL: {url}...")
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        return f"Navegador aberto com sucesso em: {url}"

    def play_youtube_video(self, search_query: str) -> str:
        """
        Pesquisa e abre o primeiro vídeo correspondente diretamente no YouTube.
        """
        import urllib.request
        import re
        import threading

        print(f"\n[AGENTE] Selecionando o primeiro vídeo no YouTube para: {search_query}...")
        query = urllib.parse.quote(search_query)
        search_url = f"https://www.youtube.com/results?search_query={query}"
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            req = urllib.request.Request(search_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
            
            # Tenta encontrar o primeiro ID de vídeo nas tags do JSON interno do YouTube
            video_ids = re.findall(r"\"videoIds\":\[\"([^\"]+)\"\]", html)
            if not video_ids:
                # Regex alternativa para correspondência tradicional
                video_ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", html)
                
            if video_ids:
                video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
                print(f"[AGENTE] Vídeo selecionado: {video_url}. Reproduzindo...")
                threading.Thread(target=webbrowser.open, args=(video_url,), daemon=True).start()
                return f"Vídeo '{search_query}' selecionado e reproduzindo com sucesso no navegador."
        except Exception as e:
            print(f"[AGENTE] Falha na seleção automática de vídeo ({e}). Abrindo busca geral...")
            
        threading.Thread(target=webbrowser.open, args=(search_url,), daemon=True).start()
        return f"YouTube aberto na busca por '{search_query}'."

    def adjust_system_volume(self, action: str, value: int = 10) -> str:
        """
        Ajusta o volume do som do sistema.
        Valores de 'action': 'increase' (aumentar), 'decrease' (diminuir), 'set' (definir), 'toggle_mute' (mutar/desmutar).
        """
        print(f"\n[AGENTE] Ajustando volume do sistema. Ação: {action}, Valor: {value}...")
        try:
            if action == "increase":
                res = subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{value}%"], capture_output=True)
                if res.returncode != 0:
                    subprocess.run(["amixer", "-q", "sset", "Master", f"{value}%+"])
                return f"Volume aumentado em {value}%."
                
            elif action == "decrease":
                res = subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{value}%"], capture_output=True)
                if res.returncode != 0:
                    subprocess.run(["amixer", "-q", "sset", "Master", f"{value}%-"])
                return f"Volume diminuído em {value}%."
                
            elif action == "set":
                res = subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"], capture_output=True)
                if res.returncode != 0:
                    subprocess.run(["amixer", "-q", "sset", "Master", f"{value}%"])
                return f"Volume definido para {value}%."
                
            elif action == "toggle_mute":
                res = subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], capture_output=True)
                if res.returncode != 0:
                    subprocess.run(["amixer", "-q", "sset", "Master", "toggle"])
                return "Mudo alternado com sucesso."
                
            return "Ação de volume desconhecida."
        except Exception as e:
            return f"Erro ao tentar ajustar o volume: {str(e)}"

    def control_wifi(self, state: str) -> str:
        """
        Liga ou desliga o adaptador Wi-Fi do sistema.
        Valores para 'state': 'on' (ligar) ou 'off' (desligar).
        """
        print(f"\n[AGENTE] Configurando Wi-Fi para: {state}...")
        try:
            if state == "on":
                subprocess.run(["nmcli", "radio", "wifi", "on"], check=True)
                return "Adaptador Wi-Fi ativado com sucesso."
            elif state == "off":
                subprocess.run(["nmcli", "radio", "wifi", "off"], check=True)
                return "Adaptador Wi-Fi desativado com sucesso."
            return "Estado do Wi-Fi inválido."
        except Exception as e:
            return f"Erro ao configurar Wi-Fi: {e}"

    def control_bluetooth(self, state: str) -> str:
        """
        Liga ou desliga o adaptador Bluetooth do sistema.
        Valores para 'state': 'on' (ligar) ou 'off' (desligar).
        """
        print(f"\n[AGENTE] Configurando Bluetooth para: {state}...")
        try:
            if state == "on":
                # Ativa o Bluetooth via rfkill e bluetoothctl para compatibilidade máxima
                subprocess.run(["rfkill", "unblock", "bluetooth"], check=True)
                subprocess.run(["bluetoothctl", "power", "on"], check=True)
                return "Adaptador Bluetooth ativado com sucesso."
            elif state == "off":
                subprocess.run(["bluetoothctl", "power", "off"], check=True)
                return "Adaptador Bluetooth desativado com sucesso."
            return "Estado do Bluetooth inválido."
        except Exception as e:
            return f"Erro ao configurar Bluetooth: {e}"

    def open_local_directory(self, path: str = "") -> str:
        """
        Abre um diretório local do sistema de arquivos no gerenciador de arquivos padrão.
        Se 'path' for vazio ou omitido, abre a pasta home do usuário.
        """
        import shutil
        import threading
        if not path:
            path = str(Path.home())
        print(f"\n[AGENTE] Abrindo diretório local: {path}...")
        try:
            resolved_path = str(Path(path).expanduser().resolve())
            if not os.path.exists(resolved_path):
                return f"Diretório não encontrado no sistema: {resolved_path}"
            
            # Abre usando o xdg-open padrão do sistema Linux em segundo plano
            threading.Thread(target=subprocess.run, args=(["xdg-open", resolved_path],), daemon=True).start()
            return f"Diretório '{resolved_path}' aberto com sucesso."
        except Exception as e:
            return f"Erro ao abrir diretório: {e}"

    def scroll_web_page(self, direction: str, amount: int = 3) -> str:
        """
        Realiza scroll (rolagem) para cima ou para baixo na janela ou página web ativa.
        Valores de 'direction': 'down' (baixo) ou 'up' (cima).
        """
        import shutil
        import time
        print(f"\n[AGENTE] Executando rolagem de tela: {direction} (intensidade: {amount})...")
        
        if shutil.which("xdotool") is None:
            return "Erro: O utilitário 'xdotool' não está instalado no sistema. Execute 'sudo apt install xdotool' para me conceder controle de tela e navegação."
        
        try:
            button = "5" if direction == "down" else "4"
            for _ in range(amount):
                subprocess.run(["xdotool", "click", button], check=True)
                time.sleep(0.05)
            return f"Rolagem para {direction} executada com sucesso {amount} vezes."
        except Exception as e:
            return f"Erro ao simular rolagem com xdotool: {e}"

    def click_on_coordinates(self, x: int, y: int) -> str:
        """
        Clica em uma coordenada de tela específica (X, Y) do sistema.
        """
        import shutil
        print(f"\n[AGENTE] Clicando na posição da tela: ({x}, {y})...")
        
        if shutil.which("xdotool") is None:
            return "Erro: O utilitário 'xdotool' não está instalado no sistema. Execute 'sudo apt install xdotool' para me conceder controle de tela."
        
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"], check=True)
            return f"Clique simulado com sucesso na coordenada ({x}, {y})."
        except Exception as e:
            return f"Erro ao simular clique com xdotool: {e}"

    def press_keyboard_key(self, key: str) -> str:
        """
        Pressiona uma tecla específica do teclado do sistema (ex: 'Return', 'space', 'Page_Down', 'Page_Up').
        """
        import shutil
        print(f"\n[AGENTE] Pressionando tecla: {key}...")
        
        if shutil.which("xdotool") is None:
            return "Erro: O utilitário 'xdotool' não está instalado no sistema. Execute 'sudo apt install xdotool' para me conceder controle de teclado."
        
        try:
            subprocess.run(["xdotool", "key", key], check=True)
            return f"Tecla '{key}' pressionada com sucesso no sistema."
        except Exception as e:
            return f"Erro ao simular tecla com xdotool: {e}"

    def interact_with_web_page(self, action: str, target: str = "") -> str:
        """
        Permite interagir de forma inteligente com páginas web ativas no navegador padrão do sistema.
        Valores de 'action':
        - 'smooth_scroll_down': Realiza uma rolagem de tela suave para baixo.
        - 'smooth_scroll_up': Realiza uma rolagem de tela suave para cima.
        - 'close_modal': Tenta fechar modais ou pop-ups na tela (pressionando Escape).
        - 'accept_cookies': Tenta localizar e clicar em botões de consentimento de cookies comuns (como Aceitar, Permitir, etc.).
        - 'click_button_by_text': Busca e clica em um botão específico na página cujo texto é igual a 'target'.
        """
        import shutil
        import time
        print(f"\n[AGENTE] Interagindo com página web. Ação: {action}, Alvo: '{target}'...")

        if shutil.which("xdotool") is None:
            return "Erro: O utilitário 'xdotool' não está instalado no sistema. Execute 'sudo apt install xdotool' para me conceder controle de tela."

        try:
            if action == "smooth_scroll_down":
                # Faz 25 pequenas rolagens rápidas com pequeno intervalo para simular suavidade
                for _ in range(25):
                    subprocess.run(["xdotool", "click", "5"], check=True)
                    time.sleep(0.015)
                return "Rolagem suave para baixo realizada com sucesso."

            elif action == "smooth_scroll_up":
                for _ in range(25):
                    subprocess.run(["xdotool", "click", "4"], check=True)
                    time.sleep(0.015)
                return "Rolagem suave para cima realizada com sucesso."

            elif action == "close_modal":
                # Modais e popups costumam fechar com a tecla Escape
                subprocess.run(["xdotool", "key", "Escape"], check=True)
                return "Simulação de fechamento de modal (tecla Escape) enviada com sucesso."

            elif action == "accept_cookies":
                # Lista de termos comuns em botões de cookies (Português e Inglês)
                cookie_terms = [
                    "Aceitar todos", "Aceitar cookies", "Aceitar tudo", "Aceitar", 
                    "Permitir todos", "Permitir cookies", "Permitir", "Concordar",
                    "Accept all", "Accept cookies", "Accept", "Allow all", "Allow", "Agree"
                ]
                for term in cookie_terms:
                    subprocess.run(["xdotool", "key", "Escape"], check=True) # Limpa seleções anteriores
                    time.sleep(0.05)
                    subprocess.run(["xdotool", "key", "ctrl+f"], check=True)
                    time.sleep(0.1)
                    subprocess.run(["xdotool", "type", term], check=True)
                    time.sleep(0.1)
                    subprocess.run(["xdotool", "key", "Return"], check=True)
                    time.sleep(0.05)
                    subprocess.run(["xdotool", "key", "Escape"], check=True) # Fecha barra de busca
                    time.sleep(0.05)
                    subprocess.run(["xdotool", "key", "Return"], check=True) # Pressiona Return para clicar
                    time.sleep(0.1)
                return "Tentativa de aceitar cookies concluída por meio de varredura de termos comuns de consentimento."

            elif action == "click_button_by_text":
                if not target:
                    return "Erro: É necessário especificar um texto ('target') para clicar no botão por texto."
                subprocess.run(["xdotool", "key", "Escape"], check=True)
                time.sleep(0.05)
                subprocess.run(["xdotool", "key", "ctrl+f"], check=True)
                time.sleep(0.1)
                subprocess.run(["xdotool", "type", target], check=True)
                time.sleep(0.1)
                subprocess.run(["xdotool", "key", "Return"], check=True)
                time.sleep(0.05)
                subprocess.run(["xdotool", "key", "Escape"], check=True)
                time.sleep(0.05)
                subprocess.run(["xdotool", "key", "Return"], check=True)
                return f"Tentativa de clicar no botão contendo '{target}' realizada com sucesso."

            else:
                return f"Erro: Ação '{action}' desconhecida para interação inteligente com página web."

        except Exception as e:
            return f"Erro ao realizar interação web: {e}"

# Teste rápido se rodado diretamente
if __name__ == "__main__":
    engine = ZeDasCoisasEngine()
    res = engine.query_documents("Como funciona o aprendizado de máquina?")
    print(f"Resultado: {res[:200]}...")
