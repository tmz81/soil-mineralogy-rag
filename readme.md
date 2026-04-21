# 🌍 Soil Mineralogy AI - Local RAG System

Este projeto é um sistema de RAG (Retrieval-Augmented Generation) focado em Mineralogia do Solo. Ele permite que você processe PDFs complexos, armazene-os em um banco de dados local veloz e converse de maneira inteligente sobre o conteúdo deles usando a API do Google Gemini.

---

## 🛑 Nível Zero: Pré-requisitos do Computador

Se você está em um **computador zerado**, como um MacBook que acabou de ser ligado, vai precisar das ferramentas básicas para rodar códigos em Python.

### 1. Instalando o Homebrew
Abra o aplicativo **Terminal** no seu Mac e cole o comando abaixo:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
*(Ele pode demorar alguns minutos e pedirá sua senha. Apenas acompanhe na tela até fechar e dar sucesso).*

### 2. Instalando o Python Atualizado
No Terminal, instale o Python usando a nova ferramenta que você acabou de baixar:
```bash
brew install python
```

---

## 🔑 Nível Um: Obtendo sua Chave de Inteligência (Gemini)

Para que o aplicativo possa "raciocinar" e responder suas perguntas, você precisa de uma chave de API do Google Gemini. 
A chave de API não é criada no site onde você conversa com o Gemini, mas sim em uma plataforma para desenvolvedores chamada **Google AI Studio**.

### Passo 1: Acesse o Google AI Studio
1. Acesse o site: [aistudio.google.com](https://aistudio.google.com/)
2. Faça login com a **mesma conta Google** que você usa normalmente.

### Passo 2: Aceite os Termos
Se for sua primeira vez no site, aparecerá uma janela de termos de serviço:
- Marque as caixas de seleção para concordar.
- Clique em **Continue**.

### Passo 3: Criar a Chave (API Key)
Agora, olhe para a coluna da esquerda (menu lateral):
1. Clique no botão **"Get API key"** (ícone de uma chave 🔑).
2. Na tela que abrir, clique no botão azul: **"Create API key in new project"**.

### Passo 4: Copiar e Salvar
Uma janela aparecerá com um código estranho (mistura de letras e números). Essa é a sua chave!
1. Clique em **Copy** para copiar o código.
2. Na pasta do seu projeto de código, crie (ou abra) um arquivo limpo chamado `.env`.
3. Cole o código salvo nesse arquivo no seguinte formato:
   `GOOGLE_API_KEY=Cole_Aqui_Seu_Codigo_Sem_Espaços`
4. De volta site do Google, clique em **Done**.

> **⚠️ Avisos Importantes para sua Segurança:**
> - **Não compartilhe essa chave:** Quem tiver esse código poderá usar o seu limite de processamento. Trate-a como uma senha de banco.
> - **Uso Gratuito vs. Pago:** Mesmo pagando assinaturas como a de 20 dólares, a API tem limites de uso "Free Tier". Se você precisar de um volume gigantesco de dados para uma empresa inteira, o Google cobrará à parte pelo uso excedente através do Google Cloud. No entanto, para uso pessoal comum de nossa ferramenta, o plano gratuito da API costuma ser mais que suficiente.
> - **Onde usar?** Agora que você tem a chave, basta mantê-la colada no seu arquivo `.env` para que o seu script e o aplicativo conectem com o super-computador do Google naturalmente.

---

## ⚙️ Nível Dois: Configurando o Projeto da Mineralogia

Com tudo no lugar, agora deixaremos este pequeno projeto pronto para uso. Abra o seu Terminal **dentro da pasta do projeto** e faça exatamente isso aqui:

**1. Crie o "Isolamento" (Ambiente Virtual)**
```bash
python3 -m venv venv
```

**2. Ative o Sistema Virtual**
```bash
source venv/bin/activate
```
*(Você notará que apareceu a palavra `(venv)` na linha de comando do Terminal. Isso é essencial).*

**3. Instale o que a Mágica Exige (Nossas Dependências)**
Nesta etapa, estamos instalando o coração do RAG (LangChain), o modelo local poderoso de leitura de PDFs (HuggingFace) e a interface bonita para o chat (Rich).
```bash
pip install -U langchain langchain-community langchain-google-genai langchain-chroma langchain-text-splitters pypdf python-dotenv langchain-huggingface sentence-transformers rich
```

**4. Arquive o Seu Conteúdo**
Pegue e arraste todos os arquivos PDF técnicos sobre os quais você deseja fazer perguntas para dentro da pasta `docs/`. 

---

## 🚀 Nível Três: Botando pra Quebrar

Terminamos! Basta "dar o play". Verifique se aquele `(venv)` do seu Terminal ainda existe aceso na tela, e rode:

```bash
python rag.py
```

- **A PRIMEIRA VEZ QUE VOCÊ RODAR:** Como você acabou de botar os arquivos lá, o seu computador vai usar a super Inteligência do processador da sua máquina por alguns segundos para triturar as informações localmente e indexar tudo matematicamente na pasta `chroma_db`. Nenhum limite ou barreira de quota do Google!
- **DALI PARA A FRENTE:** Ele simplesmente pula e abre a aba do Chat instantaneamente e você bate papo com os seus documentos por uma tela lindíssima de linha de comando.

---

## 📂 Visão Geral e Limpa da sua Pasta

Se perguntou onde está cada coisa, relaxe, são bem poucas coisas reais que compõem o sistema:

```text
soil-mineralogy/
├── docs/               # LUGAR DOS PDFS: Arquive aqui sua matéria
├── chroma_db/          # LUGAR DA MEMÓRIA: Banco de dados girando offline  
├── scripts/            # Códigos sujos antigos apenas pra testes
├── .env                # LUGAR SECRETO: É a sua garagem de chave de Segurança
├── venv/               # PASTA ESCONDIDA: Todos os pacotes pesados pip ficam nele
└── rag.py              # CÉREBRO PRINCIPAL: O arquivo que a gente manda rodar!
```
