# Headband

Magic headband project - a Pathfinder-style wearable AI assistant.

## Hardware Target

- Raspberry Pi Zero 2 W (quad-core ARM, 512MB RAM)
- Bone-conduction speakers (audio out)
- MEMS microphones (audio in)
- Adafruit nOOds LED filaments (simple PWM, not addressable)

## Architecture

```
Mic → silero-vad (local) → Vosk STT (local) → Claude API → Piper TTS (local) → Speaker
                                                  ↓
                                          memory (git repo)
```

All processing is local except Claude API calls.

## Key Files

- `src/headband/audio.py` - VAD + TTS (silero-vad, Piper)
- `src/headband/stt.py` - Speech-to-text (Vosk)
- `src/headband/claude.py` - Claude API conversation
- `src/headband/memory.py` - Content-addressable conversation storage
- `src/headband/leds.py` - LED control (PWM)
- `bootstrap.sh` - One-liner Pi setup
- `run.sh` - Auto-updating runner

## Memory System

Conversations are persisted to `~/.headband/data/` (a separate git repo for per-user sync):

```
~/.headband/data/
├── .git/                    # Sync to private remote
├── objects/
│   └── ab/cd1234...json     # Content-addressed messages + contexts
├── sessions/
│   └── <session_id>.json    # {messages: [], last_time, summary}
└── index.db                 # SQLite for fast search (gitignored)
```

Key features:
- **Content-addressable**: Messages stored by SHA256 hash
- **Context snapshots**: Each response records what Claude saw
- **Git sync**: Push to private remote for backup/multi-device
- **Search**: SQLite index for fast queries by content, time, session

## Development

```bash
uv sync                    # Install deps
uv run python -m headband  # Run
uv run ruff check .        # Lint
uv run pyright             # Typecheck
```

## Conventions

- Python 3.13+, strict pyright, ruff for linting
- Keep it simple - Pi Zero 2 W has limited resources
- Flat module structure until complexity warrants otherwise
- Models stored in `models/` (gitignored, downloaded by bootstrap)
