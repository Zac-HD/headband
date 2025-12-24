"""Audio input (VAD) and output (TTS via Piper)."""


def detect_voice_activity() -> bool:
    """Detect if there's voice activity from the MEMS microphone."""
    raise NotImplementedError


def speak(text: str) -> None:
    """Synthesize and play text via Piper TTS to bone-conduction output."""
    raise NotImplementedError
