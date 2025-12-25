#!/usr/bin/env bash
# Run headband with auto-update from git
set -uo pipefail

# Ensure uv is in PATH
export PATH="$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BRANCH="${HEADBAND_BRANCH:-main}"
HEADBAND_PID=""

cleanup() {
    echo "Shutting down..."
    if [ -n "$HEADBAND_PID" ] && kill -0 "$HEADBAND_PID" 2>/dev/null; then
        kill "$HEADBAND_PID"
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

start_headband() {
    echo "Starting headband..."
    uv run python -m headband &
    HEADBAND_PID=$!
}

restart_headband() {
    echo "Restarting headband..."
    if [ -n "$HEADBAND_PID" ] && kill -0 "$HEADBAND_PID" 2>/dev/null; then
        kill "$HEADBAND_PID"
        wait "$HEADBAND_PID" 2>/dev/null || true
    fi
    uv sync --quiet
    start_headband
}

get_commit_age_seconds() {
    local commit_time
    commit_time=$(git log -1 --format=%ct HEAD 2>/dev/null || echo 0)
    local now
    now=$(date +%s)
    echo $((now - commit_time))
}

# Initial start
git fetch origin "$BRANCH" --quiet
git reset --hard "origin/$BRANCH" --quiet
uv sync --quiet
start_headband

echo "Auto-update watcher running (Ctrl+C to stop)"

while true; do
    # Check how old the current commit is
    age=$(get_commit_age_seconds)
    if [ "$age" -gt 3600 ]; then
        # Commit is >1 hour old, poll less frequently
        sleep_time=60
    else
        # Recent activity, poll frequently
        sleep_time=5
    fi

    sleep "$sleep_time"

    # Check if headband crashed and restart if needed
    if ! kill -0 "$HEADBAND_PID" 2>/dev/null; then
        echo "Headband process died, restarting..."
        start_headband
    fi

    # Check for updates
    old_head=$(git rev-parse HEAD)
    git fetch origin "$BRANCH" --quiet 2>/dev/null || continue
    new_head=$(git rev-parse "origin/$BRANCH")

    if [ "$old_head" != "$new_head" ]; then
        echo "Update available: $old_head -> $new_head"
        git reset --hard "origin/$BRANCH" --quiet
        restart_headband
    fi
done
