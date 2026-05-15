"""
Agente de Automação de Navegador do Zé das Coisas
===================================================
Módulo baseado em Playwright para navegação web semântica e controlada.

Princípios de segurança:
  - Perfil temporário isolado (sem acesso aos cookies do navegador do sistema).
  - Bloqueio de URLs perigosas (file://, chrome://, about:).
  - Timeout rígido de 30s para todas as operações.
  - Extensões desabilitadas.
"""

import asyncio
from typing import Optional


# URLs que NUNCA devem ser acessadas
BLOCKED_URL_PREFIXES = [
    "file://",
    "chrome://",
    "about:",
    "chrome-extension://",
    "javascript:",
    "data:text/html",
]


class WebOperatorAgent:
    """
    Operador de navegador controlado pelo Zé das Coisas.
    
    Usa Playwright para gerenciar uma instância isolada de Chromium
    com sandbox de segurança ativo.
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self._initialized = False

    async def initialize(self) -> str:
        """Inicializa o navegador Playwright com configurações de segurança."""
        if self._initialized and self._page:
            return "Navegador já está ativo."

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ("Erro: Biblioteca 'playwright' não instalada. "
                    "Execute: pip install playwright && python -m playwright install chromium")

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-extensions",
                    "--disable-plugins",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--disable-background-networking",
                ]
            )
            # Contexto isolado (sem cookies, sem localStorage persistente)
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="pt-BR",
            )
            self._page = await context.new_page()
            self._initialized = True
            print("[BROWSER] ✅ Navegador Playwright iniciado (modo isolado).")
            return "Navegador iniciado com sucesso em modo seguro isolado."
        except Exception as e:
            error_msg = f"Erro ao iniciar navegador: {str(e)}"
            print(f"[BROWSER] ❌ {error_msg}")
            return error_msg

    def _is_url_blocked(self, url: str) -> bool:
        """Verifica se a URL é bloqueada por segurança."""
        url_lower = url.lower().strip()
        return any(url_lower.startswith(prefix) for prefix in BLOCKED_URL_PREFIXES)

    async def browser_navigate(self, url: str) -> str:
        """
        Navega para uma URL no navegador controlado.
        URLs file://, chrome:// e about: são bloqueadas por segurança.
        """
        if not self._initialized:
            init_result = await self.initialize()
            if "Erro" in init_result:
                return init_result

        if self._is_url_blocked(url):
            return f"⛔ URL bloqueada por segurança: {url}"

        # Adiciona protocolo se ausente
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = await self._page.title()
            current_url = self._page.url
            print(f"[BROWSER] Navegou para: {current_url} — '{title}'")
            return f"Navegado com sucesso para {current_url}. Título: '{title}'"
        except Exception as e:
            return f"Erro ao navegar para {url}: {str(e)}"

    async def browser_click(self, selector: str) -> str:
        """Clica em um elemento da página usando seletores CSS/XPath/texto."""
        if not self._page:
            return "Navegador não está ativo. Use browser_navigate primeiro."

        try:
            await self._page.click(selector, timeout=10000)
            print(f"[BROWSER] Clicou em: {selector}")
            return f"Elemento '{selector}' clicado com sucesso."
        except Exception as e:
            return f"Erro ao clicar em '{selector}': {str(e)}"

    async def browser_type(self, selector: str, text: str) -> str:
        """Digita texto em um campo de formulário."""
        if not self._page:
            return "Navegador não está ativo. Use browser_navigate primeiro."

        try:
            await self._page.fill(selector, text, timeout=10000)
            print(f"[BROWSER] Digitou em '{selector}': {text[:50]}...")
            return f"Texto inserido no campo '{selector}'."
        except Exception as e:
            return f"Erro ao digitar em '{selector}': {str(e)}"

    async def browser_get_content(self) -> str:
        """Extrai o texto limpo da página atual para análise pelo Zé."""
        if not self._page:
            return "Navegador não está ativo."

        try:
            content = await self._page.locator("body").inner_text(timeout=10000)
            # Limita o retorno para não sobrecarregar o contexto do Gemini
            truncated = content[:4000]
            if len(content) > 4000:
                truncated += f"\n\n[... conteúdo truncado, total: {len(content)} caracteres]"
            return truncated
        except Exception as e:
            return f"Erro ao extrair conteúdo: {str(e)}"

    async def browser_screenshot(self) -> Optional[bytes]:
        """Captura screenshot do navegador para análise visual pelo Gemini."""
        if not self._page:
            return None

        try:
            return await self._page.screenshot(full_page=False, timeout=10000)
        except Exception as e:
            print(f"[BROWSER] Erro ao capturar screenshot: {e}")
            return None

    async def close(self):
        """Encerra o navegador e libera recursos."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._browser = None
            self._playwright = None
            self._page = None
            self._initialized = False
            print("[BROWSER] Navegador encerrado.")

    @property
    def is_active(self) -> bool:
        return self._initialized and self._page is not None
