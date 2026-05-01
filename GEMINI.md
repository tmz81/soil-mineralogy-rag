# 🌍 Soil Mineralogy AI - Multimodal Live RAG

Este projeto implementa um sistema avançado de RAG (Retrieval-Augmented Generation) focado em Mineralogia do Solo, utilizando a API Multimodal Live do Google Gemini para interações de voz em tempo real e LangChain com ChromaDB para recuperação de documentos técnicos.

## 🚀 Visão Geral do Projeto

A arquitetura do projeto é dividida em dois fluxos principais:
1.  **Multimodal Live RAG:** Permite conversar com a IA usando voz, com o Gemini consultando PDFs locais em tempo real.
2.  **Text-based CLI RAG:** Uma interface de texto via terminal para consultas rápidas e detalhadas nos documentos.

### Tecnologias Principais
- **LLM:** Google Gemini (`gemini-3.1-flash-live-preview` e `gemini-flash-latest`)
- **Orquestração:** LangChain
- **Banco de Vetores:** ChromaDB (Persistência local em `./chroma_db`)
- **Embeddings:** HuggingFace `all-MiniLM-L6-v2` (Execução local)
- **Áudio:** PyAudio e `google-genai` Multimodal Live API

## 📂 Estrutura de Diretórios

- `docs/`: 📄 Repositório de PDFs técnicos. Adicione novos materiais aqui.
- `src/`: ⚙️ Código-fonte principal.
    - `engine.py`: Lógica central do motor de mineralogia (Indexação e Busca).
    - `rag.py`: Interface CLI baseada em texto.
- `chroma_db/`: 🧠 Armazenamento persistente do banco de vetores.
- `scripts/`: 🛠️ Utilitários de verificação e diagnóstico.
- `scratch/`: 🧪 Scripts de teste e experimentação.
- `main.py`: 🎤 Ponto de entrada para a sessão Multimodal Live (Voz).

## 🛠️ Comandos Principais

### Execução
- **Iniciar Sessão de Voz:**
  ```bash
  python main.py
  ```
- **Iniciar CLI de Texto:**
  ```bash
  python src/rag.py
  ```

### Verificação e Configuração
- **Verificar Dependências:**
  ```bash
  python scripts/verify_imports.py
  ```
- **Configurar Ambiente:**
  Certifique-se de ter o arquivo `.env` com a sua `GOOGLE_API_KEY`.

## 📝 Convenções de Desenvolvimento

- **Indexação Automática:** Na primeira execução, o sistema indexa automaticamente todos os PDFs da pasta `docs/`.
- **Configuração via .env:** Todas as chaves e variáveis sensíveis devem estar no arquivo `.env`.
- **Processamento Local:** Os embeddings são gerados localmente usando a CPU/GPU do dispositivo para maior velocidade e privacidade na busca.
- **VAD (Voice Activity Detection):** O sistema `main.py` gerencia interrupções de voz automaticamente.

## 📋 TODO / Futuras Melhorias
- [ ] Implementar suporte para outros tipos de documentos além de PDF.
- [ ] Adicionar interface web (Streamlit ou FastAPI).
- [ ] Otimizar o tempo de resposta do RAG em bases de dados muito grandes.
