"""Content-addressable conversation memory with git sync.

Storage layout (~/.headband/data/ as a git repo):
```
objects/
  ab/cd1234...json    # content-addressed blobs (messages, contexts)
sessions/
  2024-01-15T12:34:56Z.json  # session metadata + message refs
index.db              # SQLite for fast search
```

Each object is stored by SHA256 of its canonical JSON representation.
"""

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# Default data directory - can be overridden
DATA_DIR = Path.home() / ".headband" / "data"


def _canonical_json(obj: dict[str, Any]) -> bytes:
    """Canonical JSON for consistent hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _hash_content(content: bytes) -> str:
    """SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def init_data_repo(data_dir: Path | None = None) -> Path:
    """Initialize the data repository if it doesn't exist."""
    data_dir = data_dir or DATA_DIR
    objects_dir = data_dir / "objects"
    sessions_dir = data_dir / "sessions"

    # Create directories
    objects_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git repo if needed
    git_dir = data_dir / ".git"
    if not git_dir.exists():
        subprocess.run(["git", "init"], cwd=data_dir, check=True, capture_output=True)
        # Create initial commit
        subprocess.run(["git", "add", "."], cwd=data_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "Initialize headband data repo"],
            cwd=data_dir,
            check=True,
            capture_output=True,
        )

    # Initialize SQLite index
    _init_index(data_dir)

    return data_dir


def _init_index(data_dir: Path) -> None:
    """Initialize SQLite search index."""
    db_path = data_dir / "index.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                hash TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                session_id TEXT,
                context_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS contexts (
                hash TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                message_hashes TEXT NOT NULL,  -- JSON array
                system_prompt TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_content ON messages(content);
        """)


def _get_db(data_dir: Path | None = None) -> sqlite3.Connection:
    """Get database connection."""
    data_dir = data_dir or DATA_DIR
    return sqlite3.connect(data_dir / "index.db")


def store_object(obj: dict[str, Any], data_dir: Path | None = None) -> str:
    """Store an object and return its hash."""
    data_dir = data_dir or DATA_DIR
    content = _canonical_json(obj)
    obj_hash = _hash_content(content)

    # Store in objects/ab/cd1234...json
    prefix = obj_hash[:2]
    obj_dir = data_dir / "objects" / prefix
    obj_dir.mkdir(parents=True, exist_ok=True)

    obj_path = obj_dir / f"{obj_hash}.json"
    if not obj_path.exists():
        obj_path.write_bytes(content)

    return obj_hash


def load_object(obj_hash: str, data_dir: Path | None = None) -> dict[str, Any] | None:
    """Load an object by hash."""
    data_dir = data_dir or DATA_DIR
    prefix = obj_hash[:2]
    obj_path = data_dir / "objects" / prefix / f"{obj_hash}.json"

    if not obj_path.exists():
        return None

    return json.loads(obj_path.read_bytes())


def store_message(
    role: Literal["user", "assistant"],
    content: str,
    session_id: str,
    context_hash: str | None = None,
    data_dir: Path | None = None,
) -> str:
    """Store a message and index it. Returns the message hash."""
    data_dir = data_dir or DATA_DIR
    timestamp = datetime.now(timezone.utc).isoformat()

    msg = {
        "type": "message",
        "timestamp": timestamp,
        "role": role,
        "content": content,
        "session_id": session_id,
        "context_hash": context_hash,
    }

    msg_hash = store_object(msg, data_dir)

    # Index in SQLite
    with _get_db(data_dir) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO messages
               (hash, timestamp, role, content, session_id, context_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (msg_hash, timestamp, role, content, session_id, context_hash),
        )

    return msg_hash


def store_context(
    message_hashes: list[str],
    system_prompt: str,
    data_dir: Path | None = None,
) -> str:
    """Store a context snapshot. Returns the context hash."""
    data_dir = data_dir or DATA_DIR
    timestamp = datetime.now(timezone.utc).isoformat()

    ctx = {
        "type": "context",
        "timestamp": timestamp,
        "message_hashes": message_hashes,
        "system_prompt": system_prompt,
    }

    ctx_hash = store_object(ctx, data_dir)

    # Index in SQLite
    with _get_db(data_dir) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO contexts
               (hash, timestamp, message_hashes, system_prompt)
               VALUES (?, ?, ?, ?)""",
            (ctx_hash, timestamp, json.dumps(message_hashes), system_prompt),
        )

    return ctx_hash


# --- Search and retrieval ---


def search_messages(
    query: str | None = None,
    role: Literal["user", "assistant"] | None = None,
    session_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    data_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Search messages with optional filters."""
    data_dir = data_dir or DATA_DIR

    conditions = []
    params: list[Any] = []

    if query:
        conditions.append("content LIKE ?")
        params.append(f"%{query}%")
    if role:
        conditions.append("role = ?")
        params.append(role)
    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)
    if since:
        conditions.append("timestamp >= ?")
        params.append(since.isoformat())
    if until:
        conditions.append("timestamp <= ?")
        params.append(until.isoformat())

    where = " AND ".join(conditions) if conditions else "1=1"

    with _get_db(data_dir) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            f"""SELECT hash, timestamp, role, content, session_id, context_hash
                FROM messages
                WHERE {where}
                ORDER BY timestamp DESC
                LIMIT ?""",
            [*params, limit],
        )
        return [dict(row) for row in cursor.fetchall()]


def get_session_messages(session_id: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Get all messages for a session, in order."""
    data_dir = data_dir or DATA_DIR

    with _get_db(data_dir) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT hash, timestamp, role, content, context_hash
               FROM messages
               WHERE session_id = ?
               ORDER BY timestamp ASC""",
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_recent_sessions(limit: int = 10, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Get recent sessions with message counts."""
    data_dir = data_dir or DATA_DIR

    with _get_db(data_dir) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT session_id,
                      MIN(timestamp) as started,
                      MAX(timestamp) as ended,
                      COUNT(*) as message_count
               FROM messages
               GROUP BY session_id
               ORDER BY ended DESC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def reconstruct_context(context_hash: str, data_dir: Path | None = None) -> dict[str, Any] | None:
    """Reconstruct a full context from its hash."""
    data_dir = data_dir or DATA_DIR

    ctx = load_object(context_hash, data_dir)
    if not ctx:
        return None

    messages = []
    for msg_hash in ctx.get("message_hashes", []):
        msg = load_object(msg_hash, data_dir)
        if msg:
            messages.append({"role": msg["role"], "content": msg["content"]})

    return {
        "system_prompt": ctx.get("system_prompt"),
        "messages": messages,
    }


# --- Git sync ---


def sync(data_dir: Path | None = None, remote: str = "origin") -> None:
    """Commit any changes and sync with remote."""
    data_dir = data_dir or DATA_DIR

    # Add all changes
    subprocess.run(["git", "add", "."], cwd=data_dir, check=True, capture_output=True)

    # Check if there are changes to commit
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=data_dir,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        subprocess.run(
            ["git", "commit", "-m", f"Sync {timestamp}"],
            cwd=data_dir,
            check=True,
            capture_output=True,
        )

    # Pull then push (if remote exists)
    try:
        subprocess.run(
            ["git", "pull", "--rebase", remote, "main"],
            cwd=data_dir,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "push", remote, "main"],
            cwd=data_dir,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        pass  # Remote may not be configured yet
