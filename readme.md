# 🌍 Soil Mineralogy AI - Multimodal Live RAG

Este projeto é um sistema avançado de RAG (Retrieval-Augmented Generation) focado em Mineralogia do Solo. Ele permite que você processe PDFs complexos, armazene-os em um banco de dados local veloz e converse de maneira inteligente — **via áudio em tempo real** — usando a nova API Multimodal do Google Gemini.

---

## 🛑 Nível Zero: Pré-requisitos do Computador

Se você está em um computador "limpo" (sem desenvolvimento configurado), vai precisar das bibliotecas de áudio para que o Python consiga ouvir o seu microfone e reproduzir o áudio.

### No Linux (Debian / Ubuntu)
Abra o seu terminal e instale as bibliotecas de áudio e de desenvolvimento:
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio python3-venv
```

### No macOS
Se você ainda não tem o Homebrew, instale-o primeiro:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Em seguida, instale as ferramentas necessárias:
```bash
brew install portaudio python
```

---

## 🔑 Nível Um: Obtendo sua Chave de Inteligência (Gemini)

Para que o aplicativo possa "raciocinar", você precisa de uma chave de API do Google Gemini AI Studio.

1. Acesse o site: [aistudio.google.com](https://aistudio.google.com/) e faça login.
2. Clique em **"Get API key"** (menu lateral).
3. Clique no botão azul: **"Create API key in new project"** e copie a sua chave.
4. Na pasta do seu projeto, crie um arquivo chamado `.env`.
5. Cole a sua chave nesse arquivo no seguinte formato:
   `GOOGLE_API_KEY=Cole_Aqui_Sua_Chave_Sem_Aspas`

---

## ⚙️ Nível Dois: Configurando o Projeto

Com tudo no lugar, agora deixaremos este projeto pronto para uso. Abra o seu Terminal **dentro da pasta do projeto** e execute:

**1. Crie e Ative o Isolamento (Ambiente Virtual)**
```bash
python3 -m venv venv
source venv/bin/activate
```

**2. Instale as Dependências Python**
Nesta etapa instalamos os motores do RAG local e o novo SDK do Google GenAI para sessões Multimodais Live:
```bash
pip install -U langchain langchain-community langchain-chroma langchain-text-splitters pypdf python-dotenv langchain-huggingface sentence-transformers pyaudio google-genai
```

**3. Arquive o Seu Conteúdo**
Pegue e arraste todos os arquivos PDF técnicos de Mineralogia do Solo para dentro da pasta `docs/`. O sistema construirá a inteligência a partir deles!

---

## 🚀 Nível Três: Botando pra Quebrar

Terminamos! Basta "dar o play" com o seu ambiente virtual ativado:

```bash
python main.py
```

- **A PRIMEIRA VEZ:** Se você acabou de colocar seus PDFs, o script notará automaticamente que o banco de dados está vazio e indexará todos os documentos usando sua CPU (HuggingFace MiniLM).
- **DALI PARA A FRENTE:** Ele abrirá o microfone instantaneamente. A sessão *"SESSÃO MULTIMODAL INICIADA"* será exibida no terminal. É só falar com a sua voz e ouvir o especialista em Mineralogia do Solo te responder consultando os PDFs!

Para encerrar a conversa, simplesmente diga **"Sair"** ou pressione `Ctrl+C`.

---

## 📂 Visão Geral do Projeto Organizado

Deixamos tudo altamente profissional, mantendo apenas **um arquivo principal** exposto.

```text
soil-mineralogy/
├── docs/               # 📄 LUGAR DOS PDFS: Coloque aqui o seu material didático
├── chroma_db/          # 🧠 LUGAR DA MEMÓRIA: Banco de dados girando offline  
├── src/                # ⚙️ MOTORES: A lógica de RAG, Embeddings e ferramentas do Gemini (engine.py)
├── .env                # 🔐 LUGAR SECRETO: É a sua garagem de chave de Segurança
├── venv/               # 📦 PASTA ESCONDIDA: Todos os pacotes pesados pip ficam nela
└── main.py             # 🎤 PONTO DE ENTRADA: O único arquivo que você roda para iniciar a mágica!
```
