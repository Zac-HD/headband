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

## Quick Start (Raspberry Pi)

One-liner to set up a fresh Pi:

```bash
curl -sSL https://raw.githubusercontent.com/Zac-HD/headband/main/bootstrap.sh | bash
```

This will:
- Install system dependencies (git, python3.13, portaudio)
- Install [uv](https://docs.astral.sh/uv/)
- Clone the repo to `~/headband`
- Download Vosk and Piper models

Then run with auto-update:

```bash
~/headband/run.sh
```

The run script polls git every 5s (or 60s if no recent commits) and restarts the code on updates.

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
