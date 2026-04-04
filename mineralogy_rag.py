import os
from dotenv import load_dotenv

# Basic environment setup
load_dotenv()
os.makedirs("./docs", exist_ok=True)
DB_PATH = "./chroma_db"

# Core Imports from stable sub-packages
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def setup_rag():
    try:
        # 1. Embeddings e LLM
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        llm = ChatGoogleGenerativeAI(model="models/gemini-flash-latest", temperature=0.1)

        # 2. Carregar ou Criar Banco de Dados
        if os.path.exists(DB_PATH) and os.path.isdir(DB_PATH) and os.listdir(DB_PATH):
            print("--- Carregando banco de dados persistente ---")
            vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
        else:
            print("--- Criando novo banco de dados a partir dos PDFs em ./docs ---")
            if not os.path.exists("./docs") or not os.listdir("./docs"):
                print("ERRO: Nenhum PDF encontrado na pasta './docs'.")
                return None
                
            loader = DirectoryLoader("./docs", glob="*.pdf", loader_cls=PyPDFLoader)
            docs = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(docs)
            
            vectorstore = Chroma.from_documents(
                documents=splits, 
                embedding=embeddings, 
                persist_directory=DB_PATH
            )
            print(f"--- Sucesso: {len(splits)} trechos indexados ---")

        # 3. Construir a Chain usando LCEL (Mais robusto e moderno)
        template = """Você é um Engenheiro de IA e Especialista em Mineralogia do Solo. 
        Use os seguintes trechos de documentos técnicos para responder à pergunta. 
        Se a resposta não estiver no contexto, diga que não encontrou, mas tente formular uma explicação baseada em princípios gerais de mineralogia se possível.

        Contexto: {context}

        Pergunta: {question}

        Resposta Científica:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

        # Esta é a forma moderna e infalível de criar o RAG sem depender do módulo 'chains' que está falhando
        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        
        return rag_chain
    except Exception as e:
        print(f"Erro durante o setup: {e}")
        return None

def main():
    print("\n" + "="*50)
    print("SISTEMA RAG DE MINERALOGIA DO SOLO - PRONTO")
    print("="*50 + "\n")

    rag_chain = setup_rag()
    
    if not rag_chain:
        print("\n[!] Configure seus PDFs na pasta 'docs' e sua GOOGLE_API_KEY no .env para começar.")
        return

    print("Sistema Ativo. Digite sua pergunta sobre solos ou mineralogia.")
    print("(Digite 'sair' para encerrar)\n")

    while True:
        try:
            query = input("Pergunta: ").strip()
        except EOFError:
            break
            
        if query.lower() in ["sair", "exit", "quit"]:
            print("Encerrando... Até logo.")
            break
        
        if not query:
            continue

        print("\nAnalisando documentos técnicos...")
        try:
            # Invocar a chain LCEL
            response = rag_chain.invoke(query)
            print(f"\nResposta:\n{response}")
            print("\n" + "-"*30)
        except Exception as e:
            print(f"Erro ao processar pergunta: {e}")

if __name__ == "__main__":
    main()
