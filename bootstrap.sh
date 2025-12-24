#!/usr/bin/env bash
# Bootstrap script for magic headband on Raspberry Pi
# Run with: curl -sSL https://raw.githubusercontent.com/Zac-HD/headband/main/bootstrap.sh | bash
set -euo pipefail

REPO_URL="${HEADBAND_REPO:-https://github.com/Zac-HD/headband.git}"
INSTALL_DIR="${HEADBAND_DIR:-$HOME/headband}"
BRANCH="${HEADBAND_BRANCH:-main}"

echo "=== Magic Headband Bootstrap ==="
echo "Repo: $REPO_URL"
echo "Branch: $BRANCH"
echo "Install dir: $INSTALL_DIR"

# Install system dependencies
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y git python3.13 python3.13-venv portaudio19-dev

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Clone or update repo
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing repo..."
    cd "$INSTALL_DIR"
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
    git reset --hard "origin/$BRANCH"
else
    echo "Cloning repo..."
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
uv sync

# Download models if not present
MODELS_DIR="$INSTALL_DIR/models"
mkdir -p "$MODELS_DIR"

if [ ! -d "$MODELS_DIR/vosk-model-small-en-us-0.15" ]; then
    echo "Downloading Vosk model..."
    cd "$MODELS_DIR"
    curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip vosk-model-small-en-us-0.15.zip
    rm vosk-model-small-en-us-0.15.zip
fi

if [ ! -f "$MODELS_DIR/en_US-lessac-medium.onnx" ]; then
    echo "Downloading Piper voice..."
    cd "$MODELS_DIR"
    curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
    curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
fi

cd "$INSTALL_DIR"

echo ""
echo "=== Bootstrap complete! ==="
echo "Starting headband with auto-update..."
echo ""

exec "$INSTALL_DIR/run.sh"
