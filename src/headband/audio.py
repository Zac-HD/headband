"""Audio input (VAD via silero-vad) and output (TTS via Piper)."""

import logging
import os
import queue
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray
from piper.voice import PiperVoice
from silero_vad import VADIterator, load_silero_vad

log = logging.getLogger(__name__)

# Allow override via environment
INPUT_DEVICE = os.environ.get("HEADBAND_INPUT_DEVICE")
OUTPUT_DEVICE = os.environ.get("HEADBAND_OUTPUT_DEVICE")

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


def _get_input_device() -> int | str | None:
    """Get input device, checking availability."""
    if INPUT_DEVICE is not None:
        try:
            return int(INPUT_DEVICE)
        except ValueError:
            return INPUT_DEVICE

    # Check if default device exists
    try:
        sd.query_devices(kind="input")
        return None  # Use default
    except sd.PortAudioError:
        # List available devices
        devices = sd.query_devices()
        log.error("No default input device. Available devices:")
        for i, d in enumerate(devices):
            log.error(
                "  [%d] %s (in=%d, out=%d)",
                i,
                d["name"],
                d["max_input_channels"],
                d["max_output_channels"],
            )
        msg = "No input device available. Set HEADBAND_INPUT_DEVICE to device index."
        raise RuntimeError(msg) from None


def _get_output_device() -> int | str | None:
    """Get output device, checking availability."""
    if OUTPUT_DEVICE is not None:
        try:
            return int(OUTPUT_DEVICE)
        except ValueError:
            return OUTPUT_DEVICE

    try:
        sd.query_devices(kind="output")
        return None
    except sd.PortAudioError:
        devices = sd.query_devices()
        log.error("No default output device. Available devices:")
        for i, d in enumerate(devices):
            log.error(
                "  [%d] %s (in=%d, out=%d)",
                i,
                d["name"],
                d["max_input_channels"],
                d["max_output_channels"],
            )
        msg = "No output device available. Set HEADBAND_OUTPUT_DEVICE to device index."
        raise RuntimeError(msg) from None


def check_audio_devices() -> None:
    """Check that audio devices are available. Call early to fail fast."""
    _get_input_device()
    _get_output_device()
    log.debug("Audio devices OK")


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
        _frames: int,
        _time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            log.warning("Audio callback status: %s", status)
        audio_queue.put(indata.copy().flatten())

    log.debug("Listening for speech...")

    input_device = _get_input_device()
    with sd.InputStream(
        device=input_device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.float32,
        blocksize=CHUNK_SAMPLES,
        latency="high",  # Larger buffer to avoid overflow
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
    import io
    import wave

    if _tts_voice is None:
        msg = "Voice not loaded. Call load_voice() first."
        raise RuntimeError(msg)

    log.info("TTS: %r", text)

    # Synthesize to in-memory WAV
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        _tts_voice.synthesize(text, wav_file)

    # Read back the audio data
    wav_buffer.seek(0)
    with wave.open(wav_buffer, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        audio_data = wav_file.readframes(wav_file.getnframes())

    log.debug("TTS: synthesized %d bytes at %d Hz", len(audio_data), sample_rate)

    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    output_device = _get_output_device()
    sd.play(samples, samplerate=sample_rate, device=output_device)
    sd.wait()
