"""
Sistema de Permissões por Tiers do Zé das Coisas
=================================================
Classifica cada ação do agente em 4 níveis de permissão:

  Tier 0 (🟢 Livre)         → Execução imediata, sem aviso.
  Tier 1 (🟡 Notifica)      → Executa e notifica o usuário na UI.
  Tier 2 (🔴 Pede Permissão)→ BLOQUEIA até o usuário aprovar na UI.
  Tier 3 (⛔ Proibido)      → RECUSA sempre. Informa que não tem permissão.
"""

import asyncio
from enum import IntEnum
from typing import Optional, Callable, Awaitable

class PermissionTier(IntEnum):
    FREE = 0        # 🟢 Livre
    NOTIFY = 1      # 🟡 Notifica
    ASK = 2         # 🔴 Pede permissão
    FORBIDDEN = 3   # ⛔ Proibido


# ── Mapeamento de ferramentas → tier de permissão ──────────────────────────
TOOL_PERMISSIONS = {
    # Tier 0: Livre — operações de leitura e consulta
    "query_documents":        PermissionTier.FREE,
    "deep_query_documents":   PermissionTier.FREE,
    "adjust_system_volume":   PermissionTier.FREE,
    "scroll_web_page":        PermissionTier.FREE,
    "capture_screen":         PermissionTier.FREE,

    # Tier 1: Notifica — abre coisas mas não modifica estado
    "open_system_browser":    PermissionTier.NOTIFY,
    "play_youtube_video":     PermissionTier.NOTIFY,
    "open_local_directory":   PermissionTier.NOTIFY,
    "control_wifi":           PermissionTier.NOTIFY,
    "control_bluetooth":      PermissionTier.NOTIFY,
    "browser_navigate":       PermissionTier.NOTIFY,
    "browser_get_content":    PermissionTier.NOTIFY,
    "browser_screenshot":     PermissionTier.NOTIFY,

    # Tier 2: Pede Permissão — ações que interagem/modificam estado
    "click_on_coordinates":   PermissionTier.ASK,
    "press_keyboard_key":     PermissionTier.ASK,
    "interact_with_web_page": PermissionTier.ASK,
    "browser_click":          PermissionTier.ASK,
    "browser_type":           PermissionTier.ASK,

    # Tier 3: Proibido — nunca permitido
    "execute_shell_command":  PermissionTier.FORBIDDEN,
    "delete_system_file":     PermissionTier.FORBIDDEN,
}


class PermissionManager:
    """
    Gerencia o fluxo de consentimento entre o Engine (Python) e a UI (Electron).
    
    Em modo CLI (main.py), todas as ações Tier 2 são auto-aprovadas com log no console.
    Em modo Desktop (app.py), ações Tier 2 enviam um pedido via WebSocket e aguardam resposta.
    """

    def __init__(self):
        # Callback assíncrono para pedir permissão à UI (definido pelo app.py ou main.py)
        self._ask_permission_callback: Optional[Callable[..., Awaitable[bool]]] = None
        # Callback para notificar a UI (definido pelo app.py ou main.py)
        self._notify_callback: Optional[Callable[..., Awaitable[None]]] = None
        # Modo CLI: auto-aprova Tier 2 com log
        self.cli_mode = True

    def set_ask_callback(self, callback: Callable[..., Awaitable[bool]]):
        """Define o callback para pedir permissão (modo Desktop)."""
        self._ask_permission_callback = callback
        self.cli_mode = False

    def set_notify_callback(self, callback: Callable[..., Awaitable[None]]):
        """Define o callback para notificar ações (modo Desktop)."""
        self._notify_callback = callback

    def get_tier(self, tool_name: str) -> PermissionTier:
        """Retorna o tier de permissão de uma ferramenta."""
        return TOOL_PERMISSIONS.get(tool_name, PermissionTier.ASK)

    async def check_permission(self, tool_name: str, tool_args: dict) -> tuple[bool, str]:
        """
        Verifica se a ação pode ser executada.
        
        Retorna (permitido: bool, mensagem: str).
        """
        tier = self.get_tier(tool_name)

        # ── Tier 0: Livre ──
        if tier == PermissionTier.FREE:
            return True, ""

        # ── Tier 1: Notifica ──
        if tier == PermissionTier.NOTIFY:
            description = self._describe_action(tool_name, tool_args)
            if self._notify_callback:
                await self._notify_callback(tool_name, description)
            else:
                print(f"[AGENTE] 🟡 Executando: {description}")
            return True, ""

        # ── Tier 2: Pede Permissão ──
        if tier == PermissionTier.ASK:
            description = self._describe_action(tool_name, tool_args)

            if self.cli_mode:
                # No CLI, loga e auto-aprova
                print(f"[AGENTE] 🔴 Ação sensível auto-aprovada (modo CLI): {description}")
                return True, ""

            if self._ask_permission_callback:
                granted = await self._ask_permission_callback(tool_name, description, tool_args)
                if granted:
                    return True, ""
                else:
                    return False, f"Ação '{tool_name}' negada pelo usuário."
            else:
                # Sem callback configurado, bloqueia por segurança
                print(f"[AGENTE] 🔴 BLOQUEADO (sem callback de permissão): {description}")
                return False, "Sistema de permissões não configurado. Ação bloqueada por segurança."

        # ── Tier 3: Proibido ──
        if tier == PermissionTier.FORBIDDEN:
            return False, f"Ação '{tool_name}' é proibida pelo protocolo de segurança do Zé das Coisas."

        return False, "Tier de permissão desconhecido."

    def _describe_action(self, tool_name: str, tool_args: dict) -> str:
        """Gera uma descrição legível da ação para exibir ao usuário."""
        descriptions = {
            "click_on_coordinates": lambda a: f"Clicar na posição ({a.get('x')}, {a.get('y')}) da tela",
            "press_keyboard_key": lambda a: f"Pressionar a tecla '{a.get('key')}' no teclado",
            "interact_with_web_page": lambda a: f"Interagir com página web: {a.get('action')} {a.get('target', '')}".strip(),
            "browser_click": lambda a: f"Clicar no elemento '{a.get('selector')}' no navegador controlado",
            "browser_type": lambda a: f"Digitar texto no campo '{a.get('selector')}' no navegador controlado",
            "open_system_browser": lambda a: f"Abrir navegador em: {a.get('url')}",
            "play_youtube_video": lambda a: f"Reproduzir no YouTube: {a.get('search_query')}",
            "open_local_directory": lambda a: f"Abrir pasta: {a.get('path', '~/') or '~/'}",
            "control_wifi": lambda a: f"{'Ligar' if a.get('state') == 'on' else 'Desligar'} o Wi-Fi",
            "control_bluetooth": lambda a: f"{'Ligar' if a.get('state') == 'on' else 'Desligar'} o Bluetooth",
            "browser_navigate": lambda a: f"Navegar para: {a.get('url')}",
            "browser_get_content": lambda a: "Extrair conteúdo de texto da página",
            "browser_screenshot": lambda a: "Capturar screenshot do navegador",
        }
        
        formatter = descriptions.get(tool_name)
        if formatter:
            try:
                return formatter(tool_args)
            except Exception:
                pass
        
        return f"{tool_name}({tool_args})"
