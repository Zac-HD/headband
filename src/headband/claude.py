"""Claude API conversation handling."""

import os

from anthropic import Anthropic

_client: Anthropic | None = None
_conversation: list[dict[str, str]] = []

SYSTEM_PROMPT = """You are a helpful assistant embedded in a magic headband. \
Keep responses concise and conversational - they will be spoken aloud via TTS."""


def init(api_key: str | None = None) -> None:
    """Initialize the Anthropic client."""
    global _client
    _client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))


def chat(user_message: str) -> str:
    """Send a message to Claude and return the response."""
    if _client is None:
        msg = "Client not initialized. Call init() first."
        raise RuntimeError(msg)

    _conversation.append({"role": "user", "content": user_message})

    response = _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=_conversation,
    )

    assistant_message = response.content[0].text
    _conversation.append({"role": "assistant", "content": assistant_message})

    return assistant_message


def reset_conversation() -> None:
    """Clear conversation history."""
    _conversation.clear()
