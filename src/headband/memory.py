"""Content-addressable conversation memory with git sync.

Storage layout (~/.headband/data/ as a git repo):
```
objects/
  ab/cd1234...json    # JSON objects (messages, contexts, summaries)
sessions/
  <session_id>.json   # {"messages": [...], "last_time": "...", "summary": "..."}
index.db              # SQLite index (gitignored, rebuilt on demand)
```
"""

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

DATA_DIR = Path.home() / ".headband" / "data"

ObjectType = Literal["message", "system", "context", "summary"]
Role = Literal["user", "assistant"]


def _canonical_json(obj: dict[str, Any]) -> str:
    """Canonical JSON for consistent hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _pretty_json(obj: dict[str, Any]) -> str:
    """Pretty JSON for human-readable session files."""
    return json.dumps(obj, indent=2)


def _hash_content(content: str) -> str:
    """SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def init_data_repo(data_dir: Path | None = None) -> Path:
    """Initialize the data repository if it doesn't exist."""
    data_dir = data_dir or DATA_DIR
    objects_dir = data_dir / "objects"
    sessions_dir = data_dir / "sessions"

    objects_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git repo if needed
    git_dir = data_dir / ".git"
    if not git_dir.exists():
        subprocess.run(["git", "init"], cwd=data_dir, check=True, capture_output=True)
        # Create .gitignore for index
        gitignore = data_dir / ".gitignore"
        gitignore.write_text("index.db\n")
        subprocess.run(["git", "add", "."], cwd=data_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "Initialize headband data repo"],
            cwd=data_dir,
            check=True,
            capture_output=True,
        )

    return data_dir


def store_object(obj: dict[str, Any], data_dir: Path | None = None) -> str:
    """Store an object and return its hash."""
    data_dir = data_dir or DATA_DIR
    text = _canonical_json(obj)
    obj_hash = _hash_content(text)

    # Store in objects/ab/cd1234...json
    prefix = obj_hash[:2]
    obj_dir = data_dir / "objects" / prefix
    obj_dir.mkdir(parents=True, exist_ok=True)

    obj_path = obj_dir / f"{obj_hash}.json"
    if not obj_path.exists():
        obj_path.write_text(text)

    return obj_hash


def load_object(obj_hash: str, data_dir: Path | None = None) -> dict[str, Any] | None:
    """Load an object by hash."""
    data_dir = data_dir or DATA_DIR
    prefix = obj_hash[:2]
    obj_path = data_dir / "objects" / prefix / f"{obj_hash}.json"

    if not obj_path.exists():
        return None

    return json.loads(obj_path.read_text())


def _load_session_meta(session_id: str, data_dir: Path) -> dict[str, Any]:
    """Load session metadata, creating if needed."""
    session_file = data_dir / "sessions" / f"{session_id}.json"
    if session_file.exists():
        return json.loads(session_file.read_text())
    return {"messages": [], "last_time": None, "summary": None}


def _save_session_meta(session_id: str, meta: dict[str, Any], data_dir: Path) -> None:
    """Save session metadata."""
    session_file = data_dir / "sessions" / f"{session_id}.json"
    session_file.write_text(_pretty_json(meta))


def store_message(
    role: Role,
    content: str,
    session_id: str,
    context_hash: str | None = None,
    data_dir: Path | None = None,
) -> str:
    """Store a message. Returns the hash."""
    data_dir = data_dir or DATA_DIR
    timestamp = datetime.now(timezone.utc).isoformat()

    obj = {
        "type": "message",
        "role": role,
        "content": content,
        "time": timestamp,
        "session": session_id,
    }
    if context_hash:
        obj["context"] = context_hash

    obj_hash = store_object(obj, data_dir)

    # Update session metadata
    meta = _load_session_meta(session_id, data_dir)
    meta["messages"].append(obj_hash)
    meta["last_time"] = timestamp
    _save_session_meta(session_id, meta, data_dir)

    return obj_hash


def store_system(content: str, session_id: str, data_dir: Path | None = None) -> str:
    """Store a system prompt. Returns the hash."""
    data_dir = data_dir or DATA_DIR
    timestamp = datetime.now(timezone.utc).isoformat()

    obj = {
        "type": "system",
        "content": content,
        "time": timestamp,
        "session": session_id,
    }

    return store_object(obj, data_dir)


def store_context(
    message_hashes: list[str],
    system_hash: str | None = None,
    data_dir: Path | None = None,
) -> str:
    """Store a context snapshot (list of message refs). Returns the hash."""
    data_dir = data_dir or DATA_DIR
    timestamp = datetime.now(timezone.utc).isoformat()

    obj: dict[str, Any] = {
        "type": "context",
        "messages": message_hashes,
        "time": timestamp,
    }
    if system_hash:
        obj["system"] = system_hash

    return store_object(obj, data_dir)


def store_summary(
    source_hashes: list[str],
    summary: str,
    level: int = 1,
    data_dir: Path | None = None,
) -> str:
    """Store a summary of messages/summaries (for bottom-up summarization)."""
    data_dir = data_dir or DATA_DIR
    timestamp = datetime.now(timezone.utc).isoformat()

    obj = {
        "type": "summary",
        "content": summary,
        "sources": source_hashes,
        "level": level,
        "time": timestamp,
    }

    return store_object(obj, data_dir)


def update_session_summary(
    session_id: str,
    summary: str,
    data_dir: Path | None = None,
) -> None:
    """Update the summary for a session."""
    data_dir = data_dir or DATA_DIR
    meta = _load_session_meta(session_id, data_dir)
    meta["summary"] = summary
    _save_session_meta(session_id, meta, data_dir)


# --- Search (rebuilds index on demand) ---


def _ensure_index(data_dir: Path) -> sqlite3.Connection:
    """Ensure SQLite index exists and is up-to-date."""
    db_path = data_dir / "index.db"
    needs_rebuild = not db_path.exists()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if needs_rebuild:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS objects (
                hash TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                role TEXT,
                time TEXT,
                session TEXT,
                context TEXT,
                level INTEGER,
                content TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_time ON objects(time);
            CREATE INDEX IF NOT EXISTS idx_session ON objects(session);
            CREATE INDEX IF NOT EXISTS idx_type ON objects(type);
        """)
        _rebuild_index(data_dir, conn)

    return conn


def _rebuild_index(data_dir: Path, conn: sqlite3.Connection) -> None:
    """Rebuild index from object files."""
    objects_dir = data_dir / "objects"
    if not objects_dir.exists():
        return

    for prefix_dir in objects_dir.iterdir():
        if not prefix_dir.is_dir():
            continue
        for obj_file in prefix_dir.iterdir():
            obj_hash = obj_file.stem  # Remove .json extension
            obj = json.loads(obj_file.read_text())

            conn.execute(
                """INSERT OR REPLACE INTO objects
                   (hash, type, role, time, session, context, level, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    obj_hash,
                    obj.get("type"),
                    obj.get("role"),
                    obj.get("time"),
                    obj.get("session"),
                    obj.get("context"),
                    obj.get("level"),
                    obj.get("content", ""),
                ),
            )
    conn.commit()


def rebuild_index(data_dir: Path | None = None) -> None:
    """Force rebuild the search index."""
    data_dir = data_dir or DATA_DIR
    db_path = data_dir / "index.db"
    if db_path.exists():
        db_path.unlink()
    _ensure_index(data_dir)


def search(
    query: str | None = None,
    obj_type: ObjectType | None = None,
    role: Role | None = None,
    session_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    data_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Search objects with optional filters."""
    data_dir = data_dir or DATA_DIR
    conn = _ensure_index(data_dir)

    conditions = []
    params: list[Any] = []

    if query:
        conditions.append("content LIKE ?")
        params.append(f"%{query}%")
    if obj_type:
        conditions.append("type = ?")
        params.append(obj_type)
    if role:
        conditions.append("role = ?")
        params.append(role)
    if session_id:
        conditions.append("session = ?")
        params.append(session_id)
    if since:
        conditions.append("time >= ?")
        params.append(since.isoformat())
    if until:
        conditions.append("time <= ?")
        params.append(until.isoformat())

    where = " AND ".join(conditions) if conditions else "1=1"

    cursor = conn.execute(
        f"""SELECT hash, type, role, time, session, context, level, content
            FROM objects WHERE {where} ORDER BY time DESC LIMIT ?""",
        [*params, limit],
    )
    return [dict(row) for row in cursor.fetchall()]


def get_session(session_id: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Get all message objects for a session, in order."""
    data_dir = data_dir or DATA_DIR
    meta = _load_session_meta(session_id, data_dir)

    results = []
    for obj_hash in meta.get("messages", []):
        obj = load_object(obj_hash, data_dir)
        if obj:
            results.append({"hash": obj_hash, **obj})

    return results


def get_session_meta(session_id: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Get session metadata (messages, last_time, summary)."""
    data_dir = data_dir or DATA_DIR
    return _load_session_meta(session_id, data_dir)


def get_sessions(limit: int = 20, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Get recent sessions with metadata."""
    data_dir = data_dir or DATA_DIR
    sessions_dir = data_dir / "sessions"

    if not sessions_dir.exists():
        return []

    # Sort by modification time, most recent first
    session_files = sorted(
        sessions_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    results = []
    for sf in session_files[:limit]:
        session_id = sf.stem
        meta = json.loads(sf.read_text())
        results.append({
            "session_id": session_id,
            "message_count": len(meta.get("messages", [])),
            "last_time": meta.get("last_time"),
            "summary": meta.get("summary"),
        })

    return results


def reconstruct_context(context_hash: str, data_dir: Path | None = None) -> list[dict[str, str]]:
    """Reconstruct messages from a context snapshot."""
    data_dir = data_dir or DATA_DIR
    ctx = load_object(context_hash, data_dir)
    if not ctx:
        return []

    messages = []

    # Load system prompt if present
    system_hash = ctx.get("system")
    if system_hash:
        sys_obj = load_object(system_hash, data_dir)
        if sys_obj:
            messages.append({"role": "system", "content": sys_obj["content"]})

    # Load messages
    for msg_hash in ctx.get("messages", []):
        msg = load_object(msg_hash, data_dir)
        if msg:
            messages.append({"role": msg["role"], "content": msg["content"]})

    return messages


# --- Git sync ---


def sync(data_dir: Path | None = None, remote: str = "origin") -> None:
    """Commit any changes and sync with remote."""
    data_dir = data_dir or DATA_DIR

    subprocess.run(["git", "add", "."], cwd=data_dir, check=True, capture_output=True)

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
        pass  # Remote may not be configured
