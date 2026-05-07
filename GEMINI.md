# 🔮 Zé das Coisas AI - Multimodal Live Assistant (Jarvis / Amigo Virtual)

Este repositório contém um ecossistema avançado de RAG (Retrieval-Augmented Generation) pessoal e de uso geral chamado **Zé das Coisas**. O sistema integra a API Multimodal Live do Google Gemini para interações de voz em tempo real (como um amigo virtual estilo Jarvis) e processamento local de documentos de qualquer assunto (PDF, DOCX, TXT) para máxima precisão e performance.

## 🚀 Visão Geral do Projeto

A arquitetura é modular e oferece três formas principais de interação com a base de conhecimento (documentos na pasta `docs/`):

1.  **Multimodal Live RAG (Voz):** Conversação fluida e divertida por áudio com o assistente "Zé das Coisas", utilizando `gemini-3.1-flash-live-preview`.
2.  **Desktop App (Electron):** Uma interface visual moderna que gerencia documentos (de até 200MB), configurações e sessões de voz/texto através de um backend FastAPI.
3.  **CLI Text RAG:** Interface de terminal para consultas rápidas de texto puro.

### Tecnologias Principais
- **LLMs:** Google Gemini (`gemini-3.1-flash-live-preview` e `gemini-flash-latest`).
- **Orquestração RAG:** LangChain.
- **Banco de Vetores:** ChromaDB (Persistência local em `./chroma_db`).
- **Embeddings:** HuggingFace `all-MiniLM-L6-v2` (Execução local em CPU/GPU).
- **Backend:** FastAPI (Servidor REST e WebSocket bridge).
- **Frontend/Desktop:** Electron, HTML/CSS/JS (Vanilla).

## 📂 Estrutura de Diretórios

- `main.py`: 🎤 Ponto de entrada para a sessão de voz CLI (Multimodal Live).
- `src/`: ⚙️ Núcleo do sistema.
    - `app.py`: Servidor FastAPI que alimenta o app desktop.
    - `engine.py`: Motor central de documentos (Indexação, Busca Rápida e Busca Profunda).
    - `rag.py`: Script CLI para consultas textuais simples.
- `desktop/`: 💻 Código-fonte da aplicação Electron.
- `docs/`: 📄 Repositório de PDFs, DOCXs e TXTs técnicos. A inteligência do seu assistente nasce aqui.
- `chroma_db/`: 🧠 Memória vetorial persistente.
- `scripts/`: 🛠️ Utilitários de diagnóstico e verificação de ambiente.
- `scratch/`: 🧪 Experimentos e testes rápidos de API.

## 🛠️ Comandos Principais

### Desenvolvimento e Execução
- **Iniciar App Desktop (Dev):**
  ```bash
  npm run dev
  ```
- **Iniciar Sessão de Voz (CLI):**
  ```bash
  python main.py
  ```
- **Iniciar CLI de Texto:**
  ```bash
  python src/rag.py
  ```

### Configuração e Build
- **Instalar Dependências Node (Raiz e Desktop):**
  ```bash
  npm install
  ```
- **Gerar Executáveis (Desktop):**
  ```bash
  npm run build:linux  # Ou build:win, build:mac
  ```

## 📝 Convenções e Fluxos

- **Estratégia de RAG:**
    - **Busca Rápida (`query_documents`):** Recupera os 5 trechos mais relevantes dos arquivos carregados. Baixíssima latência.
    - **Busca Profunda (`deep_query_documents`):** Realiza expansão de query via LLM (3 variações) e recupera até 12 trechos. Possui timeout de 1.5s para evitar gargalos de API.
- **Indexação Automática:** O sistema detecta novos arquivos em `docs/` na inicialização e reconstrói o banco se estiver vazio.
- **Identidade da IA:** O assistente chama-se **Zé das Coisas**, possui sotaque nordestino moderado (50%), tom caloroso, prestativo e sutilmente intelectual, atuando como um amigo virtual inteligente no estilo Jarvis.
- **Segurança:** Chaves de API SEMPRE no arquivo `.env` como `GOOGLE_API_KEY`. Nunca comitar este arquivo.

## 📋 TODO / Evolução
- [x] Implementar interface Desktop com Electron.
- [x] Otimizar latência da expansão de busca profunda (timeout 1.5s).
- [x] Implementar suporte para outros tipos de documentos (TXT, DOCX) de até 200MB.
- [x] Refatorar para assistente inteligente de uso geral (Zé das Coisas).
