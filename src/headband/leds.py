"""LED nOOd control via PWM.

Adafruit nOOds are simple LED filaments (not addressable NeoPixels).
They need current-limiting resistors and can be dimmed via PWM.
"""


def set_brightness(value: float) -> None:
    """Set LED brightness (0.0 to 1.0) via PWM."""
    if not 0.0 <= value <= 1.0:
        msg = "Brightness must be between 0.0 and 1.0"
        raise ValueError(msg)
    raise NotImplementedError
