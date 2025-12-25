"""Claude API conversation handling with persistent memory."""

import os
import uuid
from pathlib import Path

from anthropic import Anthropic

from headband import memory

_client: Anthropic | None = None
_conversation: list[dict[str, str]] = []
_message_hashes: list[str] = []
_session_id: str = ""
_system_hash: str = ""
_data_dir: Path | None = None

MODEL = os.environ.get("HEADBAND_MODEL", "claude-3-5-sonnet-20241022")
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are a helpful assistant embedded in a magic headband. \
Keep responses concise and conversational - they will be spoken aloud via TTS."""


def init(api_key: str | None = None, data_dir: Path | None = None) -> None:
    """Initialize the Anthropic client and memory system."""
    global _client, _session_id, _system_hash, _data_dir

    _client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    _data_dir = data_dir
    _session_id = uuid.uuid4().hex[:12]

    # Initialize memory storage
    memory.init_data_repo(data_dir)

    # Store system prompt as a message
    _system_hash = memory.store_system(SYSTEM_PROMPT, _session_id, data_dir)


def chat(user_message: str) -> str:
    """Send a message to Claude and return the response."""
    if _client is None:
        msg = "Client not initialized. Call init() first."
        raise RuntimeError(msg)

    # Store user message
    user_hash = memory.store_message(
        role="user",
        content=user_message,
        session_id=_session_id,
        data_dir=_data_dir,
    )
    _message_hashes.append(user_hash)
    _conversation.append({"role": "user", "content": user_message})

    # Store context snapshot (what Claude sees)
    context_hash = memory.store_context(
        message_hashes=_message_hashes.copy(),
        system_hash=_system_hash,
        data_dir=_data_dir,
    )

    response = _client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=_conversation,
    )

    # Extract text from response
    assistant_message = ""
    for block in response.content:
        if hasattr(block, "text"):
            assistant_message += block.text

    # Store assistant response with context reference
    assistant_hash = memory.store_message(
        role="assistant",
        content=assistant_message,
        session_id=_session_id,
        context_hash=context_hash,
        data_dir=_data_dir,
    )
    _message_hashes.append(assistant_hash)
    _conversation.append({"role": "assistant", "content": assistant_message})

    return assistant_message


def reset_conversation() -> None:
    """Clear conversation history and start a new session."""
    global _session_id, _system_hash
    _conversation.clear()
    _message_hashes.clear()
    _session_id = uuid.uuid4().hex[:12]
    _system_hash = memory.store_system(SYSTEM_PROMPT, _session_id, _data_dir)


def sync() -> None:
    """Sync memory to remote git repository."""
    memory.sync(_data_dir)


def get_session_id() -> str:
    """Get the current session ID."""
    return _session_id
