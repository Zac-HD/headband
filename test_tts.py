#!/usr/bin/env python3
"""Quick TTS test script."""

import io
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper.voice import PiperVoice

MODELS_DIR = Path.home() / "headband" / "models"
PIPER_VOICE = MODELS_DIR / "en_US-lessac-medium.onnx"

ULYSSES = """
Old age hath yet his honour and his toil;
Death closes all: but something ere the end,
Some work of noble note, may yet be done,
Not unbecoming men that strove with Gods.
"""

print(f"Loading voice from {PIPER_VOICE}")
voice = PiperVoice.load(str(PIPER_VOICE))
print(f"Voice loaded, sample rate: {voice.config.sample_rate}")

print("Synthesizing...")

# Method 1: Try synthesize with WAV
wav_buffer = io.BytesIO()
with wave.open(wav_buffer, "wb") as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(voice.config.sample_rate)
    voice.synthesize(ULYSSES, wav_file)

wav_buffer.seek(0)
with wave.open(wav_buffer, "rb") as wav_file:
    sample_rate = wav_file.getframerate()
    audio_data = wav_file.readframes(wav_file.getnframes())

print(f"Method 1 (synthesize to WAV): {len(audio_data)} bytes at {sample_rate} Hz")

if len(audio_data) == 0:
    print("Trying alternative methods...")

    # Method 2: Check what methods exist
    print(f"Available methods: {[m for m in dir(voice) if not m.startswith('_')]}")

    # Method 3: Try synthesize_ids_to_raw if available
    if hasattr(voice, "synthesize_stream_raw"):
        chunks = list(voice.synthesize_stream_raw(ULYSSES))
        audio_data = b"".join(chunks)
        print(f"Method 2 (synthesize_stream_raw): {len(audio_data)} bytes")

    # Method 4: Try audio_float generator
    if hasattr(voice, "synthesize_wav"):
        print("Has synthesize_wav method")

if len(audio_data) > 0:
    print("Playing audio...")
    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(samples, samplerate=sample_rate)
    sd.wait()
    print("Done!")
else:
    print("No audio generated!")
