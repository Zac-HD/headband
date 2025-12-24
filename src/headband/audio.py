"""Audio input (VAD via silero-vad) and output (TTS via Piper)."""


def detect_voice_activity() -> bool:
    """Detect voice activity from MEMS microphone using silero-vad."""
    raise NotImplementedError


def speak(text: str) -> None:
    """Synthesize and play text via Piper TTS to bone-conduction output."""
    raise NotImplementedError
