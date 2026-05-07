import os
import asyncio
import threading
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

class MineralogyEngine:
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
            
            self.vectorstore = Chroma.from_documents(
                documents=splits, 
                embedding=self.embeddings, 
                persist_directory=DB_PATH
            )
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
            self.deep_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 12})
            print(f"[SISTEMA] Sucesso! {len(splits)} trechos foram indexados em segundo plano.")
        except Exception as e:
            print(f"[ERRO SENSORIAL] Falha na indexação em segundo plano: {e}")
        finally:
            self.is_indexing = False

    def query_mineralogy_docs(self, question: str) -> str:
        """
        Consulta RÁPIDA à biblioteca técnica. Ideal para definições diretas e dúvidas simples.
        """
        print(f"\n[SISTEMA] Busca Rápida: {question}...")
        docs = self.retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in docs)
        return context if context else "Nenhuma informação encontrada na busca rápida."

    async def deep_query_mineralogy_docs(self, question: str) -> str:
        """
        Busca PROFUNDA e EXAUSTIVA. Use quando a busca rápida não for suficiente ou o assunto for complexo.
        Esta ferramenta analisa múltiplos trechos e gera variações da pergunta para garantir precisão técnica.
        """
        print(f"\n[SISTEMA] Iniciando BUSCA PROFUNDA para: {question}...")
        
        # Expansão de Query: Gera variações para aumentar chance de acerto (Português e Inglês)
        queries = [question]
        prompt = f"Gere 3 variações técnicas e sinônimas (em português e inglês) da seguinte pergunta sobre mineralogia do solo para melhorar a busca em PDFs: '{question}'. Retorne apenas as perguntas separadas por linha."
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

# Teste rápido se rodado diretamente
if __name__ == "__main__":
    engine = MineralogyEngine()
    res = engine.query_mineralogy_docs("O que é caulinita?")
    print(f"Resultado: {res[:200]}...")
