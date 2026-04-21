import pyaudio

def check_audio():
    p = pyaudio.PyAudio()
    print(f"\n--- Dispositivos de Áudio Detectados ---")
    
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')

    for i in range(0, numdevices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        print(f"ID {i}: {device_info.get('name')} (Canais de entrada: {device_info.get('maxInputChannels')})")

    p.terminate()

if __name__ == "__main__":
    try:
        check_audio()
        print("\n[OK] PyAudio inicializado com sucesso!")
    except Exception as e:
        print(f"\n[ERRO] Falha ao acessar hardware de áudio: {e}")
