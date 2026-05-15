"""
Módulo de Visão Computacional do Zé das Coisas
===============================================
Captura de tela sob demanda (não contínua) com compressão JPEG otimizada.

Princípios de segurança:
  - Visão SOB DEMANDA: só captura quando solicitado explicitamente.
  - Blocklist de janelas sensíveis: nunca captura telas com títulos proibidos.
  - Indicador visual: sinaliza quando a visão está ativa.
"""

import asyncio
import io
import subprocess
from typing import Optional


class ScreenPerception:
    """Captura de tela otimizada e segura para o Zé das Coisas."""

    # Títulos de janelas que NUNCA devem ser capturados (case-insensitive)
    BLOCKED_WINDOW_TITLES = [
        "keepass", "bitwarden", "1password", "lastpass",
        "internet banking", "banco do brasil", "itau", "bradesco", "nubank", "caixa",
        "gpg", "ssh-agent", "gnome-keyring",
    ]

    def __init__(self, target_width: int = 1024, target_height: int = 768):
        self.target_size = (target_width, target_height)
        self._mss = None
        self._is_active = False

    def _get_mss(self):
        """Lazy-load do mss para não importar até ser necessário."""
        if self._mss is None:
            try:
                from mss import mss
                self._mss = mss()
            except ImportError:
                raise RuntimeError(
                    "[VISÃO] Biblioteca 'mss' não instalada. Execute: pip install mss"
                )
        return self._mss

    def _get_active_window_title(self) -> str:
        """Obtém o título da janela ativa no Linux via xdotool."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def _is_sensitive_window(self) -> bool:
        """Verifica se a janela ativa é sensível (banco, senhas, etc)."""
        title = self._get_active_window_title().lower()
        return any(blocked in title for blocked in self.BLOCKED_WINDOW_TITLES)

    def capture_and_compress(self, quality: int = 70) -> Optional[bytes]:
        """
        Captura a tela principal e comprime para JPEG.
        
        Retorna None se a janela ativa estiver na blocklist de segurança.
        """
        from PIL import Image

        # Verificação de segurança: não captura janelas sensíveis
        if self._is_sensitive_window():
            print("[VISÃO] ⛔ Captura bloqueada: janela sensível detectada.")
            return None

        sct = self._get_mss()
        self._is_active = True

        try:
            # Captura o monitor principal
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)

            # Converte para Pillow Image (mss retorna BGRA)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Redimensiona mantendo proporção (essencial para o Gemini entender layout espacial)
            img.thumbnail(self.target_size, Image.Resampling.LANCZOS)

            # Comprime para JPEG em memória
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            return buffer.getvalue()
        finally:
            self._is_active = False

    async def capture_async(self, quality: int = 70) -> Optional[bytes]:
        """Versão assíncrona da captura (executa em thread separada)."""
        return await asyncio.to_thread(self.capture_and_compress, quality)

    async def send_frame_to_session(self, session, quality: int = 70) -> bool:
        """
        Captura um frame e envia para a sessão ativa do Gemini Live.
        
        Retorna True se o frame foi enviado, False se bloqueado ou com erro.
        """
        jpeg_data = await self.capture_async(quality)
        
        if jpeg_data is None:
            return False

        try:
            await session.send_realtime_input(
                media_chunks=[{
                    "data": jpeg_data,
                    "mime_type": "image/jpeg"
                }]
            )
            print(f"[VISÃO] 📸 Frame enviado ({len(jpeg_data) // 1024}KB)")
            return True
        except Exception as e:
            print(f"[VISÃO] Erro ao enviar frame: {e}")
            return False

    @property
    def is_active(self) -> bool:
        return self._is_active
