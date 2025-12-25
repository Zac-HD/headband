"""Magic headband: Claude AI + bone-conduction audio + LED noodles."""

import logging
import os
import signal
import sys
from pathlib import Path

__version__ = "0.1.0"

log = logging.getLogger(__name__)

# Default model paths (can be overridden via env vars)
MODELS_DIR = Path(os.environ.get("HEADBAND_MODELS", Path.home() / "headband" / "models"))
VOSK_MODEL = MODELS_DIR / "vosk-model-small-en-us-0.15"
PIPER_VOICE = MODELS_DIR / "en_US-lessac-medium.onnx"


def main() -> None:
    """Entry point for the headband application."""
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("headband v%s starting", __version__)

    # Handle shutdown gracefully
    running = True

    def shutdown(signum: int, frame: object) -> None:  # noqa: ARG001
        nonlocal running
        log.info("Received signal %d, shutting down", signum)
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        # Import here to avoid loading models at import time
        from headband import audio, claude, stt

        # Load models
        log.info("Loading Vosk model from %s", VOSK_MODEL)
        stt.load_model(VOSK_MODEL)

        log.info("Loading Piper voice from %s", PIPER_VOICE)
        audio.load_voice(PIPER_VOICE)

        # Initialize Claude
        log.info("Initializing Claude API")
        claude.init()

        log.info("Headband ready - listening for speech")

        # Main conversation loop
        while running:
            # Listen for speech
            speech_audio = audio.listen_for_speech(timeout=30.0)

            if speech_audio is None:
                log.debug("No speech detected, continuing to listen")
                continue

            # Transcribe
            audio_bytes = audio.audio_to_bytes(speech_audio)
            text = stt.transcribe(audio_bytes)

            if not text.strip():
                log.debug("Empty transcription, ignoring")
                continue

            log.info("User: %s", text)

            # Get response from Claude
            response = claude.chat(text)
            log.info("Claude: %s", response)

            # Speak response
            audio.speak(response)

    except Exception:
        log.exception("Fatal error in main loop")
        sys.exit(1)

    log.info("Headband stopped")
