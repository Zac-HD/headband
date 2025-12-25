"""Magic headband: Claude AI + bone-conduction audio + LED noodles."""

import logging
import signal
import sys
import time

__version__ = "0.1.0"

log = logging.getLogger(__name__)


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
        # TODO: Initialize audio, STT, TTS, Claude here
        log.info("Headband ready (stub mode - no audio yet)")

        while running:
            time.sleep(1)

    except Exception:
        log.exception("Fatal error in main loop")
        sys.exit(1)

    log.info("Headband stopped")
