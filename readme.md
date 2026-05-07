# 🔮 Zé das Coisas AI - Multimodal Live Assistant (Jarvis / Amigo Virtual)

Este projeto é um ecossistema avançado de RAG (Retrieval-Augmented Generation) e assistente pessoal inteligente chamado **Zé das Coisas**. Ele permite que você carregue e gerencie **qualquer tipo de PDF, DOCX ou TXT de até 200MB**, realize a indexação offline local de forma extremamente veloz e converse de maneira fluida e divertida por **áudio em tempo real** — com um sotaque nordestino cativante de 50% — usando a nova API Multimodal Live do Google Gemini.

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
Nesta etapa instalamos os motores do RAG local (embeddings locais offline `all-MiniLM-L6-v2` e banco vetorial ChromaDB) e o novo SDK do Google GenAI para sessões Multimodais Live:
```bash
pip install -U langchain langchain-community langchain-chroma langchain-text-splitters pypdf python-dotenv langchain-huggingface sentence-transformers pyaudio google-genai docx2txt
```

**3. Instale as Dependências do Desktop (Node/Electron)**
```bash
npm install
```

---

## 🚀 Nível Três: Botando pra Quebrar

Terminamos! Você possui duas maneiras incríveis de interagir com o Zé das Coisas:

### Opção A: Interface Gráfica Premium Desktop (Recomendado)
Para iniciar a maravilhosa interface visual em Electron (com controle de biblioteca de documentos, upload inteligente, configurações e visualizações animadas de voz):
```bash
npm run dev
```

### Opção B: Conversação via Terminal (CLI)
Com o seu ambiente virtual ativado, rode:
```bash
python main.py
```

- **A PRIMEIRA VEZ:** Se você acabou de carregar seus documentos, o sistema notará automaticamente e indexará de forma offline usando sua CPU/GPU local de forma super rápida.
- **DALI PARA A FRENTE:** Ele abrirá o microfone instantaneamente. É só falar com a sua voz e ouvir o Zé das Coisas te responder como um amigo pessoal, consultando os arquivos que você colocou!

Para encerrar a conversa na CLI, simplesmente diga **"Sair"** ou pressione `Ctrl+C`.

---

## 📂 Visão Geral da Estrutura

Deixamos tudo altamente modular, limpo e profissional.

```text
ze-das-coisas/
├── docs/               # 📄 DOCUMENTOS: Insira aqui qualquer PDF, DOCX ou TXT (até 200MB)
├── chroma_db/          # 🧠 BANCO VETORIAL: Sua base de conhecimento indexada offline localmente
├── src/                # ⚙️ MOTORES: A lógica de RAG, embeddings locais e WebSocket (app.py, engine.py)
├── desktop/            # 💻 DESKTOP APP: Código-fonte do app de Electron e interface visual premium
├── .env                # 🔐 CONFIG: Sua chave de segurança GOOGLE_API_KEY
├── venv/               # 📦 PYTHON VENV: Biblioteca local Python isolada
└── main.py             # 🎤 SESSÃO DE VOZ CLI: Ponto de entrada para conversação por voz via terminal
```
