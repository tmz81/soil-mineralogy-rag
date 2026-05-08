# 🔮 Zé das Coisas AI - Project Documentation

This document provides essential context and instructions for the **Zé das Coisas AI** project (Soil Mineralogy RAG), an advanced multimodal assistant specializing in Retrieval-Augmented Generation (RAG) for technical documents.

---

## 🚀 Project Overview

**Zé das Coisas** is a personal assistant that combines the power of **Google Gemini Multimodal Live API** with a local **RAG (Retrieval-Augmented Generation)** engine. It allows users to index technical documents (PDF, DOCX, TXT) and interact with them via real-time voice or text.

### Key Technologies
- **AI/LLM:** Google Gemini (using `google-genai` and `gemini-2.0-flash-exp`).
- **RAG Framework:** LangChain (LCEL) with ChromaDB for vector storage.
- **Embeddings:** HuggingFace `all-MiniLM-L6-v2` (running locally).
- **Backend:** Python / FastAPI for the API and RAG engine.
- **Desktop Interface:** Electron (Node.js) providing a premium GUI.
- **Live Multimodal:** Real-time voice interaction with interruption support.

---

## 📂 Project Structure

- `docs/`: Repository for PDF, DOCX, and TXT documents (up to 200MB).
- `chroma_db/`: Local vector database storage.
- `src/`: Core logic and engines.
    - `engine.py`: The `ZeDasCoisasEngine` class, managing RAG, tool calls, and system automation.
    - `app.py`: FastAPI server bridging the desktop app and the RAG engine.
    - `rag.py`: CLI-based text RAG interface.
- `desktop/`: Electron-based frontend source code.
- `main.py`: Entry point for the CLI-based Multimodal Live voice session.
- `scripts/`: Utility scripts for model checking and import verification.

---

## 🛠 Building and Running

### Prerequisites
- **Python 3.10+**
- **Node.js & npm**
- **System Libraries:** `portaudio19-dev`, `python3-pyaudio`, `xdotool` (for system automation features).

### Setup
1. **Environment:** Create a `.env` file in the root with your `GOOGLE_API_KEY`.
2. **Python Venv:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt  # Or refer to the pip install list in README.md
   ```
3. **Node Dependencies:**
   ```bash
   npm install
   ```

### Execution
- **Desktop App (Recommended):**
  ```bash
  npm run dev
  ```
- **CLI Voice Assistant:**
  ```bash
  python main.py
  ```
- **CLI Text-based RAG:**
  ```bash
  python src/rag.py
  ```

### Building (Electron)
- **Linux:** `npm run build:linux`
- **Windows:** `npm run build:win`
- **macOS:** `npm run build:mac`

---

## 🧠 Development Conventions

- **Language:** The primary development language is Python (Backend/RAG) and JavaScript (Electron).
- **Style:** 
    - Use **LCEL (LangChain Expression Language)** for new RAG chains.
    - Maintain the "Zé" persona: a professional, focused, and slightly sarcastic TI/Security specialist (inspired by CASE from Interstellar).
- **Tooling:** The `ZeDasCoisasEngine` in `src/engine.py` is the central hub for all tool definitions. New capabilities (like browser control or system automation) should be added there.
- **Automation:** System automation (volume, wifi, click, scroll) uses `pactl`, `nmcli`, `bluetoothctl`, and `xdotool`.

---

## 📝 Usage Notes

- **Indexing:** The first run will automatically index documents in the `docs/` folder. Subsequent runs use the persisted `chroma_db/`.
- **Live Session:** The Gemini Live session in `main.py` and `app.py` supports real-time audio streaming and tool calling.
- **Port:** The FastAPI backend runs on `127.0.0.1:8765` by default.
