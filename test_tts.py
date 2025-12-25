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

sample_rate = voice.config.sample_rate
TEMP_WAV = Path("/tmp/ulysses.wav")

if not TEMP_WAV.exists():
    print("Synthesizing...")
    voice.synthesize_wav(ULYSSES, str(TEMP_WAV))
    print(f"Saved to {TEMP_WAV}")
else:
    print(f"Using cached {TEMP_WAV}")

print("Playing...")
with wave.open(str(TEMP_WAV), "rb") as wav_file:
    sample_rate = wav_file.getframerate()
    audio_data = wav_file.readframes(wav_file.getnframes())

print(f"Audio: {len(audio_data)} bytes at {sample_rate} Hz")

if len(audio_data) > 0:
    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(samples, samplerate=sample_rate)
    sd.wait()
    print("Done!")
else:
    print("No audio in file!")
