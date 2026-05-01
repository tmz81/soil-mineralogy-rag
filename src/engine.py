import os
import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "./chroma_db"

from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class MineralogyEngine:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        # Usando o ID correto para a v1beta e LangChain
        self.llm = ChatGoogleGenerativeAI(model="gemini-flash-latest")
        
        # Cria a pasta docs se não existir
        os.makedirs("./docs", exist_ok=True)
        
        # Verifica se o banco de dados já existe
        if os.path.exists(DB_PATH) and os.path.isdir(DB_PATH) and os.listdir(DB_PATH):
            self.vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=self.embeddings)
        else:
            print("\n[SISTEMA] Primeira execução detectada! Lendo PDFs da pasta 'docs' e construindo o banco de dados local...")
            loader = DirectoryLoader("./docs", glob="*.pdf", loader_cls=PyPDFLoader)
            docs = loader.load()
            
            if not docs:
                print("[SISTEMA] AVISO: Nenhum PDF encontrado na pasta 'docs'. O banco de dados estará vazio.")
                self.vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=self.embeddings)
            else:
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                splits = text_splitter.split_documents(docs)
                
                self.vectorstore = Chroma.from_documents(
                    documents=splits, 
                    embedding=self.embeddings, 
                    persist_directory=DB_PATH
                )
                print(f"[SISTEMA] Sucesso! {len(splits)} trechos de PDFs foram indexados.")
                
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self.deep_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 12})

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
            variations_res = await self.llm.ainvoke(prompt)
            new_queries = variations_res.content.strip().split("\n")
            queries.extend([q.strip() for q in new_queries if q.strip()])
        except Exception as e:
            print(f"[AVISO] Falha na expansão de query: {e}")

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
