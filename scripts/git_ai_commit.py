import os
import sys
import subprocess
from google import genai
from dotenv import load_dotenv

def get_git_diff():
    # Verifica se há arquivos em staging (staged changes)
    diff = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True).stdout.strip()
    
    # Se não houver nada no staging, verifica as alterações gerais
    if not diff:
        diff_unstaged = subprocess.run(["git", "diff"], capture_output=True, text=True).stdout.strip()
        if not diff_unstaged:
            return None, False
        
        # Pergunta ao usuário se quer adicionar tudo ao staging
        print("\n[GIT AI] Nenhum arquivo em staging (git add).")
        confirm = input("Deseja adicionar todas as alterações atuais ao commit? (s/n): ").strip().lower()
        if confirm in ['s', 'sim', 'y', 'yes']:
            subprocess.run(["git", "add", "."])
            diff = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True).stdout.strip()
        else:
            print("[GIT AI] Operação cancelada. Use 'git add <arquivos>' e tente novamente.")
            sys.exit(0)
            
    return diff, True

def generate_commit_message(diff):
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[ERRO] GOOGLE_API_KEY não encontrada no arquivo .env.")
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""Você é um assistente especializado em Git. Escreva uma mensagem de commit curta, clara e profissional baseada no git diff fornecido abaixo.
Siga as convenções de commits semânticos (Conventional Commits), por exemplo:
- feat: adicionar nova funcionalidade
- fix: corrigir bug
- refactor: refatorar código existente
- docs: atualizar documentação
- style: formatação, ponto e vírgula ausente, etc.

Regras:
1. Retorne APENAS a linha de assunto do commit (e opcionalmente um corpo curto se as alterações forem muito complexas).
2. Não inclua Markdown, crases ou explicações extras.
3. Responda em Português do Brasil.

Git Diff:
{diff[:4000]}
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip().replace('`', '')
    except Exception as e:
        print(f"[ERRO API GEMINI] {e}")
        sys.exit(1)

def main():
    print("🤖 Analisando alterações com Gemini...")
    diff, has_changes = get_git_diff()
    
    if not has_changes or not diff:
        print("ℹ️ Nenhuma alteração detectada para commit.")
        return

    commit_message = generate_commit_message(diff)
    print("\n✍️ Mensagem sugerida pelo Gemini:")
    print(f"--------------------------------------------------\n{commit_message}\n--------------------------------------------------")
    
    confirm = input("Confirmar commit com esta mensagem? (s/n): ").strip().lower()
    if confirm in ['s', 'sim', 'y', 'yes']:
        result = subprocess.run(["git", "commit", "-m", commit_message], capture_output=True, text=True)
        if result.returncode == 0:
            print("🎉 Commit realizado com sucesso!")
            print(result.stdout)
        else:
            print("❌ Falha ao realizar commit:")
            print(result.stderr)
    else:
        print("[GIT AI] Commit cancelada pelo usuário.")

if __name__ == "__main__":
    main()
