# headband

A "magic headband" (Pathfinder-style) powered by Raspberry Pi Zero 2 W, featuring bone-conduction speakers, MEMS microphones, LED noodles, and Claude AI integration.

## Hardware

- **Compute:** Raspberry Pi Zero 2 W
- **Audio output:** Bone-conduction transducers (TBD: I2S DAC or USB audio)
- **Audio input:** MEMS microphones (TBD: I2S ADC or USB audio)
- **Lighting:** [Adafruit nOOds](https://www.adafruit.com/product/5509) flexible LED filaments (3V, PWM-controlled)

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  MEMS Mic   │───▶│ silero-vad  │───▶│    Vosk     │
└─────────────┘    │  (local)    │    │   (local)   │
                   └─────────────┘    └──────┬──────┘
                                             │
┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐
│Bone Speaker │◀───│ Piper TTS   │◀───│   Claude    │
└─────────────┘    │  (local)    │    │    API      │
                   └─────────────┘    └─────────────┘

┌─────────────┐
│ LED nOOds   │  (ambient patterns, future: reactive)
└─────────────┘
```

## Models

Download these models for local processing:

- **Vosk STT:** [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models) (~40MB)
- **Piper TTS:** [en_US voices](https://github.com/rhasspy/piper/blob/master/VOICES.md) (pick one ~20-100MB)

## Development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies
uv sync

# Run
uv run python -m headband

# Lint & typecheck
uv run ruff check .
uv run pyright

# Run pre-commit hooks
pre-commit run --all-files
```

## License

AGPL-3.0 - see [LICENSE](LICENSE)
