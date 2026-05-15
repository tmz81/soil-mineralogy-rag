"""
Módulo de Detecção de Atividade de Voz Local (VAD) do Zé das Coisas
====================================================================
Executa o Silero VAD localmente para detectar fala humana instantaneamente.
Quando detecta voz do usuário, interrompe a reprodução de áudio do Zé
ANTES que o sinal chegue ou volte do servidor Gemini, proporcionando
interrupção com latência local (<30ms).
"""

import numpy as np
from typing import Optional


class LocalVoiceActivityDetector:
    """
    VAD local usando Silero VAD (roda no PyTorch já instalado).
    
    Processa chunks de áudio PCM16 de 30ms e retorna a probabilidade
    de que o bloco contenha fala humana ativa.
    """

    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        """
        Args:
            sample_rate: Taxa de amostragem do áudio de entrada (padrão: 16kHz).
            threshold: Limiar de probabilidade para classificar como fala (0.0 a 1.0).
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self._model = None
        self._loaded = False

    def _load_model(self):
        """Carrega o modelo Silero VAD (lazy load — só quando necessário)."""
        if self._loaded:
            return

        try:
            import torch
            self._model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            self._loaded = True
            print("[VAD] ✅ Modelo Silero VAD carregado com sucesso.")
        except ImportError:
            print("[VAD] ⚠️ PyTorch não disponível. VAD local desabilitado.")
            self._model = None
        except Exception as e:
            print(f"[VAD] ⚠️ Falha ao carregar Silero VAD: {e}. VAD local desabilitado.")
            self._model = None

    def is_speech(self, audio_chunk: bytes) -> bool:
        """
        Verifica se o bloco de áudio PCM16 contém fala humana.
        
        Args:
            audio_chunk: Dados de áudio em formato PCM16 (int16 little-endian).
            
        Returns:
            True se fala humana detectada acima do limiar configurado.
        """
        if not self._loaded:
            self._load_model()

        if self._model is None:
            return False

        try:
            import torch

            # Converte bytes PCM16 para Float32 normalizado (-1.0 a 1.0)
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # Silero VAD espera chunks de 512 amostras (32ms a 16kHz)
            # Se o chunk for menor, preenche com zeros; se maior, usa as últimas 512 amostras
            chunk_size = 512
            if len(audio_float32) < chunk_size:
                padded = np.zeros(chunk_size, dtype=np.float32)
                padded[:len(audio_float32)] = audio_float32
                audio_float32 = padded
            elif len(audio_float32) > chunk_size:
                audio_float32 = audio_float32[-chunk_size:]

            with torch.no_grad():
                tensor = torch.from_numpy(audio_float32)
                speech_prob = self._model(tensor, self.sample_rate).item()

            return speech_prob > self.threshold

        except Exception as e:
            # Em caso de erro, não interrompe o fluxo principal
            return False

    def get_speech_probability(self, audio_chunk: bytes) -> float:
        """
        Retorna a probabilidade bruta de fala (0.0 a 1.0).
        Útil para debug e ajuste fino do limiar.
        """
        if not self._loaded:
            self._load_model()

        if self._model is None:
            return 0.0

        try:
            import torch

            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            chunk_size = 512
            if len(audio_float32) < chunk_size:
                padded = np.zeros(chunk_size, dtype=np.float32)
                padded[:len(audio_float32)] = audio_float32
                audio_float32 = padded
            elif len(audio_float32) > chunk_size:
                audio_float32 = audio_float32[-chunk_size:]

            with torch.no_grad():
                tensor = torch.from_numpy(audio_float32)
                return self._model(tensor, self.sample_rate).item()

        except Exception:
            return 0.0

    def reset(self):
        """Reseta o estado interno do modelo VAD (entre turnos de conversa)."""
        if self._model is not None:
            try:
                self._model.reset_states()
            except Exception:
                pass

    @property
    def is_available(self) -> bool:
        """Verifica se o VAD está disponível e carregado."""
        if not self._loaded:
            self._load_model()
        return self._model is not None
