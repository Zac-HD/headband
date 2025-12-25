#!/usr/bin/env python3
"""Quick TTS test script."""

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper.voice import PiperVoice

MODELS_DIR = Path.home() / "headband" / "models"
PIPER_VOICE = MODELS_DIR / "en_US-lessac-medium.onnx"

ULYSSES = """
you and I are old;
Old age hath yet his honour and his toil;
Death closes all: but something ere the end,
Some work of noble note, may yet be done,
Not unbecoming men that strove with Gods.
The lights begin to twinkle from the rocks:
The long day wanes: the slow moon climbs: the deep
Moans round with many voices. Come, my friends,
'T is not too late to seek a newer world.
Push off, and sitting well in order smite
The sounding furrows; for my purpose holds
To sail beyond the sunset, and the baths
Of all the western stars, until I die.
It may be that the gulfs will wash us down:
It may be we shall touch the Happy Isles,
And see the great Achilles, whom we knew.
Tho' much is taken, much abides; and tho'
We are not now that strength which in old days
Moved earth and heaven, that which we are, we are;
One equal temper of heroic hearts,
Made weak by time and fate, but strong in will
To strive, to seek, to find, and not to yield.
"""

print(f"Loading voice from {PIPER_VOICE}")
voice = PiperVoice.load(str(PIPER_VOICE))
print(f"Voice loaded, sample rate: {voice.config.sample_rate}")

print("Synthesizing...")
print(f"Available methods: {[m for m in dir(voice) if not m.startswith('_')]}")

sample_rate = voice.config.sample_rate

# Method 1: Try synthesize_wav (writes complete WAV to file path)
print("\n--- Method 1: synthesize_wav to temp file ---")
import tempfile

with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
    temp_path = f.name
voice.synthesize_wav(ULYSSES, temp_path)
with wave.open(temp_path, "rb") as wav_file:
    sample_rate = wav_file.getframerate()
    audio_data = wav_file.readframes(wav_file.getnframes())
print(f"synthesize_wav: {len(audio_data)} bytes at {sample_rate} Hz")

if len(audio_data) == 0:
    # Method 2: Try the lower-level pipeline
    print("\n--- Method 2: phonemize -> phonemes_to_ids -> phoneme_ids_to_audio ---")
    phonemes = voice.phonemize(ULYSSES)
    print(f"Phonemes: {phonemes[:100]}...")
    ids = voice.phonemes_to_ids(phonemes)
    print(f"IDs: {len(ids)} phoneme IDs")
    audio_array = voice.phoneme_ids_to_audio(ids)
    print(f"Audio array: {type(audio_array)}, shape: {getattr(audio_array, 'shape', 'N/A')}")
    if hasattr(audio_array, "__len__") and len(audio_array) > 0:
        audio_data = (audio_array * 32767).astype(np.int16).tobytes()
        print(f"Converted to {len(audio_data)} bytes")

if len(audio_data) > 0:
    print("\nPlaying audio...")
    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(samples, samplerate=sample_rate)
    sd.wait()
    print("Done!")
else:
    print("No audio generated!")
