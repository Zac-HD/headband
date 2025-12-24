"""Speech-to-text via Vosk (local)."""

import json
from pathlib import Path

from vosk import KaldiRecognizer, Model

# Small model for Pi Zero 2 W - download from https://alphacephei.com/vosk/models
# Recommended: vosk-model-small-en-us-0.15 (~40MB)
_model: Model | None = None
_recognizer: KaldiRecognizer | None = None

SAMPLE_RATE = 16000


def load_model(model_path: Path) -> None:
    """Load Vosk model from disk."""
    global _model, _recognizer
    _model = Model(str(model_path))
    _recognizer = KaldiRecognizer(_model, SAMPLE_RATE)


def transcribe(audio_data: bytes) -> str:
    """Transcribe audio bytes to text using Vosk."""
    if _recognizer is None:
        msg = "Model not loaded. Call load_model() first."
        raise RuntimeError(msg)

    _recognizer.AcceptWaveform(audio_data)
    result = json.loads(_recognizer.FinalResult())
    return result.get("text", "")
