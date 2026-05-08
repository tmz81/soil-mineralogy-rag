# 🔮 Guia de Modelos Gemini Live - Zé das Coisas AI

Este documento detalha o mapeamento, as quotas, as diferenças e o comportamento dos modelos da API Multimodal Live (WebSockets) do Google Gemini integrados neste projeto. Ele serve como manual de referência técnica para o usuário e como contexto de inicialização rápida para assistentes de IA em futuras sessões de desenvolvimento.

---

## 📊 Histórico de Transição e Mapeamento de Modelos

| Período | Modelo Configurado | Identificador de API (`ID`) | Status de Cota (Nível Gratuito) | Modos Suportados |
| :--- | :--- | :--- | :--- | :--- |
| **Anterior** | Gemini 3.1 Flash Live (Preview) | `gemini-3.1-flash-live-preview` | **Limitado** (Máximo de 20 a 30 requisições diárias - RPD) | Texto, Áudio, Vídeo, Ferramentas |
| **Atual (Recomendado)** | Gemini 2.5 Flash Native Audio Dialog | `gemini-2.5-flash-native-audio-latest` | **TOTALMENTE ILIMITADO** (`RPD: 0/unlimited`) | Áudio Nativo, Voz Bidirecional, Ferramentas |

---

## 🔍 Diferenças Técnicas Cruzadas

### 1. `gemini-3.1-flash-live-preview` (O Modelo Anterior)
* **Arquitetura**: Modelo de última geração focado em tarefas complexas gerais com suporte a multimodalidade.
* **Gargalo**: No plano gratuito do Google AI Studio, as cotas diárias para a família 3.1 são extremamente rígidas. O limite de **20-30 requisições diárias (RPD)** é facilmente estourado em sessões de teste e desenvolvimento contínuo, gerando o erro de conexão:
  > `[Voice WS] Erro na sessão: 1011 None. You exceeded your current quota...`

### 2. `gemini-2.5-flash-native-audio-latest` (O Modelo Atual)
* **Arquitetura**: O **Native Audio Dialog** é um modelo altamente otimizado para diálogo por voz bidirecional de baixíssima latência. Diferente de sistemas tradicionais que usam conversão de texto-para-voz secundária (TTS), ele processa e responde áudio e tom de voz de forma **nativa**, reduzindo atrasos na comunicação.
* **Vantagem de Cota**: Por ser um modelo especializado para chamadas de áudio ao vivo de baixo custo, o Google disponibiliza este endpoint de forma **Ilimitada (0 / Unlimited)** na cota gratuita do AI Studio. É perfeito para desenvolvimento ininterrupto.
* **Suporte a Ferramentas**: Suporta todas as nossas ferramentas de RAG local (`query_documents` e `deep_query_documents`) e o Google Search grounding nativo.

---

## 🛠️ Como Funciona a Configuração Dinâmica (`.env`)

Para evitar engessar o código-fonte, a definição do modelo de voz foi refatorada para ser **100% dinâmica**. Tanto o backend do App Electron (`src/app.py`) quanto o CLI de terminal (`main.py`) leem o modelo do seu arquivo `.env`:

### Como Alterar ou Fixar um Modelo:
Abra o seu arquivo `.env` (na raiz do projeto) e adicione ou edite a variável `LIVE_MODEL_ID`:

```env
# Para usar o modelo ilimitado de áudio nativo (Padrão e Recomendado):
LIVE_MODEL_ID=gemini-2.5-flash-native-audio-latest

# Se quiser voltar ao modelo 3.1 temporariamente (sujeito a limites de cota):
LIVE_MODEL_ID=gemini-3.1-flash-live-preview
```

> 💡 **Dica**: Se a variável `LIVE_MODEL_ID` não estiver definida no seu arquivo `.env`, o sistema adotará automaticamente o modelo ilimitado `gemini-2.5-flash-native-audio-latest` como padrão de segurança.

---

## 🧠 Nota para Futuras Sessões de IA (Contexto Automático)
Sempre que você (ou um novo agente de IA) iniciar uma sessão de suporte neste repositório, lembre-se de ler este arquivo `GEMINI_MODELS.md` para identificar instantaneamente o modelo ativo. 

Se o usuário reportar erros de conexão de WebSocket (como `1011` ou `1008`), o primeiro passo deve ser:
1. Executar o script `scratch/list_models.py` para verificar quais modelos estão listados na API Key dele.
2. Sugerir a alteração do `LIVE_MODEL_ID` no `.env` para apontar para o modelo ilimitado ou o modelo ativo listado.
