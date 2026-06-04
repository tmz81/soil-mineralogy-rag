import pyaudio
from src.tools import ignore_stderr, AUDIO_FORMAT, AUDIO_CHANNELS, RECEIVE_SAMPLE_RATE, SEND_SAMPLE_RATE, CHUNK_SIZE

class AudioManager:
    """Gerencia o ciclo de vida do PyAudio e a leitura/reprodução de fluxos de áudio."""
    def __init__(self):
        with ignore_stderr():
            self.p = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None

    def start_input(self):
        """Inicia o stream de gravação do microfone."""
        with ignore_stderr():
            self.input_stream = self.p.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
        return self.input_stream

    def start_output(self):
        """Inicia o stream de reprodução nos alto-falantes."""
        with ignore_stderr():
            self.output_stream = self.p.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
                frames_per_buffer=CHUNK_SIZE
            )
        return self.output_stream

    def read_input(self) -> bytes:
        """Lê um chunk de áudio gravado no microfone."""
        if not self.input_stream:
            raise RuntimeError("Stream de entrada não iniciado. Chame start_input() primeiro.")
        return self.input_stream.read(CHUNK_SIZE, exception_on_overflow=False)

    def write_output(self, data: bytes):
        """Escreve dados de áudio para serem reproduzidos."""
        if not self.output_stream:
            raise RuntimeError("Stream de saída não iniciado. Chame start_output() primeiro.")
        self.output_stream.write(data)

    def stop_streams(self):
        """Para e fecha os streams ativos de áudio."""
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except:
                pass
            self.input_stream = None
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None

    def terminate(self):
        """Encerra a sessão do PyAudio por completo e limpa os recursos."""
        self.stop_streams()
        with ignore_stderr():
            try:
                self.p.terminate()
            except:
                pass
