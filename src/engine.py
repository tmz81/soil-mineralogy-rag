import os
from langchain_google_genai import ChatGoogleGenerativeAI
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

    def query_mineralogy_docs(self, question: str) -> str:
        """
        Consulta a biblioteca técnica de mineralogia do solo para responder dúvidas científicas.
        Use esta ferramenta sempre que precisar de informações precisas baseadas nos PDFs arquivados.
        """
        print(f"\n[SISTEMA] Consultando documentos para: {question}...")
        docs = self.retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in docs)
        
        if not context:
            return "Nenhuma informação específica encontrada nos documentos técnicos."
            
        return context

# Teste rápido se rodado diretamente
if __name__ == "__main__":
    engine = MineralogyEngine()
    res = engine.query_mineralogy_docs("O que é caulinita?")
    print(f"Resultado: {res[:200]}...")
