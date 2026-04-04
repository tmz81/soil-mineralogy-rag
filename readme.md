🌍 Soil Mineralogy AI - Local RAG System

Este projeto é um sistema de RAG (Retrieval-Augmented Generation) focado em
Mineralogia do Solo. Ele permite que você processe PDFs técnicos complexos,
armazene-os em um banco de dados vetorial local (ChromaDB) e faça perguntas em
linguagem natural diretamente no seu terminal, utilizando a inteligência do Google
Gemini API.

🚀 Funcionalidades

- Processamento Inteligente: Divisão de textos respeitando terminologia científica.
- Memória Local: O banco de dados é persistido em disco; você só indexa os PDFs uma
  vez.
- Raciocínio Avançado: Utiliza o modelo Gemini 1.5 Flash para respostas precisas e
  rápidas.
- Custo Zero: Funciona inteiramente na camada gratuita (Free Tier) da Google AI.

---

🛠️ Pré-requisitos

- Python 3.10 ou superior instalado.
- Chave de API do Google Gemini (Obtenha em: Google AI Studio
  (https://aistudio.google.com/)).

---

📥 Instalação

🐧 No Linux (Ubuntu/Debian/etc)

1.  Abra o terminal na pasta do projeto.
2.  Crie o ambiente virtual:
    1 python3 -m venv venv
3.  Ative o ambiente:
    1 source venv/bin/activate
4.  Instale as dependências:
    1 pip install -U langchain langchain-community langchain-google-genai
    langchain-chroma langchain-text-splitters pypdf python-dotenv

🪟 No Windows (PowerShell)

1.  Abra o PowerShell na pasta do projeto.
2.  Crie o ambiente virtual:
    1 python -m venv venv
3.  Ative o ambiente:
    1 .\venv\Scripts\activate
4.  Instale as dependências:
    1 pip install -U langchain langchain-community langchain-google-genai
    langchain-chroma langchain-text-splitters pypdf python-dotenv

---

⚙️ Configuração

1.  Chave de API: No diretório raiz, abra o arquivo .env (ou crie um) e adicione sua
    chave:
    1 GOOGLE_API_KEY=SUA_CHAVE_AQUI
2.  Documentos: Coloque todos os seus arquivos PDF sobre mineralogia na pasta ./docs.
    (O sistema criará a pasta automaticamente se ela não existir).

---

🖥️ Como Rodar

Com o ambiente virtual ativado, execute o script principal:

1 python mineralogy_rag.py

O que esperar:

- Primeira execução: O sistema lerá os PDFs e criará a pasta chroma_db. Isso pode
  levar alguns segundos dependendo do tamanho dos arquivos.
- Execuções seguintes: O sistema carregará o banco de dados instantaneamente.
- Chat: Digite sua pergunta (ex: "Qual o efeito do alumínio na CTC do solo?") e
  aguarde a análise técnica.

---

⚠️ Solução de Problemas Comuns

┌─────────────────────┬───────────────────┬───────────────────────────────────┐
│ Erro │ Causa │ Solução │
├─────────────────────┼───────────────────┼───────────────────────────────────┤
│ 429 Resource │ Limite de cota do │ Aguarde 1 minuto e tente │
│ Exhausted │ Google atingido │ novamente. │
│ │ (100 req/min). │ │
│ 404 Model Not Found │ Nome do modelo │ O script já está configurado para │
│ │ incorreto ou │ usar models/gemini-flash-latest. │
│ │ indisponível. │ │
│ ModuleNotFoundError │ Biblioteca não │ Certifique-se de que o (venv) │
│ │ instalada ou venv │ aparece no início da sua linha de │
│ │ desativado. │ comando. │
└─────────────────────┴───────────────────┴───────────────────────────────────┘

---

📂 Estrutura do Projeto

1 soil-mineralogy-rag/
2 ├── docs/ # Seus PDFs de entrada
3 ├── chroma_db/ # Banco de dados vetorial (Gerado automaticamente)
4 ├── .env # Sua chave secreta do Google
5 ├── venv/ # Ambiente virtual Python
6 └── mineralogy_rag.py # Script principal do sistema

---
