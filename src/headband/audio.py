"""Audio input (VAD via silero-vad) and output (TTS via Piper)."""

import logging
from pathlib import Path

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray
from piper.voice import PiperVoice
from silero_vad import VADIterator, load_silero_vad

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000

# VAD setup
_vad_model = load_silero_vad()
_vad_iterator = VADIterator(_vad_model, sampling_rate=SAMPLE_RATE)

# TTS setup - load voice lazily
_tts_voice: PiperVoice | None = None


def load_voice(model_path: Path) -> None:
    """Load a Piper voice model."""
    global _tts_voice
    _tts_voice = PiperVoice.load(str(model_path))


def detect_voice_activity(audio_chunk: NDArray[np.float32]) -> bool:
    """Detect voice activity in an audio chunk using silero-vad."""
    result = _vad_iterator(audio_chunk)
    return result is not None


def record_until_silence(timeout: float = 10.0) -> NDArray[np.float32]:
    """Record audio until silence is detected or timeout reached."""
    chunks: list[NDArray[np.float32]] = []
    chunk_size = 512  # ~32ms at 16kHz

    def callback(
        indata: NDArray[np.float32],
        frames: int,  # noqa: ARG001
        time: object,  # noqa: ARG001
        status: object,  # noqa: ARG001
    ) -> None:
        chunks.append(indata.copy().flatten())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.float32,
        blocksize=chunk_size,
        callback=callback,
    ):
        sd.sleep(int(timeout * 1000))

    return np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)


def speak(text: str) -> None:
    """Synthesize and play text via Piper TTS."""
    if _tts_voice is None:
        msg = "Voice not loaded. Call load_voice() first."
        raise RuntimeError(msg)

    log.info("TTS: %r", text)
    audio_chunks = list(_tts_voice.synthesize_stream_raw(text))
    audio_data = b"".join(audio_chunks)
    log.debug("TTS: synthesized %d bytes", len(audio_data))

    # Piper outputs 16-bit PCM at 22050 Hz by default
    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(samples, samplerate=22050)
    sd.wait()
