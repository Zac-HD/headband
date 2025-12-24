"""Speech-to-text via cloud API (Deepgram, Whisper API, etc.)."""


async def transcribe(audio_data: bytes) -> str:
    """Send audio to cloud STT and return transcription."""
    raise NotImplementedError
