"""Speech-to-text via Vosk (local)."""

import json
import logging
from pathlib import Path

from vosk import KaldiRecognizer, Model

log = logging.getLogger(__name__)

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

    log.debug("STT: processing %d bytes of audio", len(audio_data))

    # Process audio in chunks for better accuracy
    chunk_size = 4000
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i : i + chunk_size]
        _recognizer.AcceptWaveform(chunk)

    result = json.loads(_recognizer.FinalResult())
    text = result.get("text", "")
    log.info("STT: %r", text)

    # Reset recognizer for next utterance
    _recognizer.Reset()

    return text
