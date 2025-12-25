"""Audio input (VAD via silero-vad) and output (TTS via Piper)."""

import logging
import queue
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray
from piper.voice import PiperVoice
from silero_vad import VADIterator, load_silero_vad

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_MS = 32  # silero-vad works best with 32ms chunks
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)

# VAD setup - lazy load to avoid import-time model download
_vad_model = None
_vad_iterator = None

# TTS setup - load voice lazily
_tts_voice: PiperVoice | None = None


def _ensure_vad() -> VADIterator:
    """Ensure VAD model is loaded."""
    global _vad_model, _vad_iterator
    if _vad_iterator is None:
        log.debug("Loading silero-vad model...")
        _vad_model = load_silero_vad()
        _vad_iterator = VADIterator(_vad_model, sampling_rate=SAMPLE_RATE)
        log.debug("VAD model loaded")
    return _vad_iterator


def load_voice(model_path: Path) -> None:
    """Load a Piper voice model."""
    global _tts_voice
    log.debug("Loading Piper voice from %s", model_path)
    _tts_voice = PiperVoice.load(str(model_path))
    log.info("Piper voice loaded")


def listen_for_speech(
    timeout: float = 30.0,
    silence_duration: float = 1.0,
    max_duration: float = 30.0,
) -> NDArray[np.float32] | None:
    """
    Listen for speech, record until silence, return audio.

    Returns None if no speech detected within timeout.

    Args:
        timeout: Max seconds to wait for speech to start
        silence_duration: Seconds of silence to end recording
        max_duration: Max recording length
    """
    vad = _ensure_vad()
    vad.reset_states()

    audio_queue: queue.Queue[NDArray[np.float32]] = queue.Queue()
    recording = False
    speech_chunks: list[NDArray[np.float32]] = []
    silence_chunks = 0
    silence_threshold = int(silence_duration * 1000 / CHUNK_MS)
    max_chunks = int(max_duration * 1000 / CHUNK_MS)
    timeout_chunks = int(timeout * 1000 / CHUNK_MS)

    chunks_processed = 0
    stop_event = threading.Event()

    def callback(
        indata: NDArray[np.float32],
        frames: int,  # noqa: ARG001
        time_info: object,  # noqa: ARG001
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            log.warning("Audio callback status: %s", status)
        audio_queue.put(indata.copy().flatten())

    log.debug("Listening for speech...")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.float32,
        blocksize=CHUNK_SAMPLES,
        callback=callback,
    ):
        while not stop_event.is_set():
            try:
                chunk = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            chunks_processed += 1

            # Check VAD
            speech_dict = vad(chunk)
            is_speech = speech_dict is not None and "start" in speech_dict

            if not recording:
                # Waiting for speech to start
                if is_speech:
                    log.debug("Speech detected, recording...")
                    recording = True
                    speech_chunks.append(chunk)
                    silence_chunks = 0
                elif chunks_processed >= timeout_chunks:
                    log.debug("Timeout waiting for speech")
                    return None
            else:
                # Recording speech
                speech_chunks.append(chunk)

                if is_speech or (speech_dict is not None and "end" not in speech_dict):
                    silence_chunks = 0
                else:
                    silence_chunks += 1

                # Check if we should stop
                if silence_chunks >= silence_threshold:
                    log.debug("Silence detected, stopping recording")
                    break

                if len(speech_chunks) >= max_chunks:
                    log.debug("Max duration reached")
                    break

    if not speech_chunks:
        return None

    audio = np.concatenate(speech_chunks)
    log.info("Recorded %.2fs of audio", len(audio) / SAMPLE_RATE)
    return audio


def audio_to_bytes(audio: NDArray[np.float32]) -> bytes:
    """Convert float32 audio to 16-bit PCM bytes for Vosk."""
    pcm = (audio * 32767).astype(np.int16)
    return pcm.tobytes()


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
