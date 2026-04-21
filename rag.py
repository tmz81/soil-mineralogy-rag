import os
import warnings

# Ocultando todos os avisos (warnings) assustadores para foco total na interface
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from dotenv import load_dotenv

# Basic environment setup
load_dotenv()
os.makedirs("./docs", exist_ok=True)
DB_PATH = "./chroma_db"

# Core Imports from stable sub-packages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def setup_rag():
    try:
        # 1. Embeddings (Local via Mac M3) e LLM (Gemini Cloud)
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        llm = ChatGoogleGenerativeAI(model="models/gemini-flash-latest", temperature=0.1)

        # 2. Carregar ou Criar Banco de Dados
        if os.path.exists(DB_PATH) and os.path.isdir(DB_PATH) and os.listdir(DB_PATH):
            console.print("[dim]🔄 Carregando biblioteca de conhecimento local...[/dim]")
            vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
        else:
            console.print("[bold yellow]📚 Criando nova biblioteca de leitura a partir dos PDFs...[/bold yellow]")
            if not os.path.exists("./docs") or not os.listdir("./docs"):
                console.print("[bold red]❌ ERRO: Nenhum PDF encontrado na pasta './docs'.[/bold red]")
                return None
                
            loader = DirectoryLoader("./docs", glob="*.pdf", loader_cls=PyPDFLoader)
            docs = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(docs)
            
            console.print("[bold yellow]Iniciando indexação LOCAL de alta velocidade (usando o chip do seu Mac M3)...[/bold yellow]")
            vectorstore = Chroma.from_documents(
                documents=splits, 
                embedding=embeddings, 
                persist_directory=DB_PATH
            )
            console.print(f"[bold green]--- Sucesso: Todos os {len(splits)} trechos indexados na velocidade da luz! ---[/bold green]")

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
    # Limpa a tela para entregar uma experiência linda "estilo app"
    os.system('cls' if os.name == 'nt' else 'clear')

    console.print(Panel(
        "[bold cyan]Bem-vindo(a) ao Cérebro de Mineralogia do Solo[/bold cyan]\n"
        "[dim]Pergunte qualquer coisa sobre os PDFs arquivados e eu encontrarei a resposta.[/dim]",
        title="🌱 [bold green]Geo AI Local[/bold green]", 
        border_style="cyan"
    ))

    with console.status("[bold green]Despertando a Inteligência e carregando os livros...[/bold green]", spinner="dots"):
        rag_chain = setup_rag()
    
    if not rag_chain:
        console.print("\n[bold red][!] Insira os PDFs na pasta 'docs' e certifique-se do .env .[/bold red]")
        return

    console.print("\n[bold green]✅ Sistema Pronto![/bold green] O que você deseja saber?")
    console.print("[dim](Dica: Digite 'sair' quando quiser fechar)[/dim]\n")

    while True:
        try:
            query = Prompt.ask("\n[bold yellow]🤖 Pergunta[/bold yellow]")
            query = query.strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Encerrando... Até logo.[/dim]")
            break
            
        if query.lower() in ["sair", "exit", "quit"]:
            console.print("\n[dim]Encerrando... Até logo.[/dim]")
            break
        
        if not query:
            continue

        with console.status("[bold magenta]Analisando documentos técnicos...[/bold magenta]", spinner="point"):
            try:
                # Invocar a chain LCEL
                response = rag_chain.invoke(query)
                success = True
            except Exception as e:
                console.print(f"[bold red]Erro ao processar pergunta: {e}[/bold red]")
                success = False

        if success:
            console.print(Panel(Markdown(response), title="[bold blue]Resposta Científica[/bold blue]", border_style="blue"))

if __name__ == "__main__":
    main()
