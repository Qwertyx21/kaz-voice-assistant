#!/usr/bin/env bash
# ==============================================================================
# Kaz Hybrid AI Voice Assistant Setup Script
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "========================================================"
echo "  🚀 Installing Kaz Hybrid Voice Assistant"
echo "========================================================"

# 1. Check system dependencies
echo -e "\n[1/5] Checking system packages..."
if command -v apt-get >/dev/null 2>&1; then
    echo "Ensuring required audio and build libraries are installed..."
    sudo apt-get update -qq || true
    sudo apt-get install -y python3-venv python3-pip portaudio19-dev libasound2-dev playerctl libpulse0
fi

# 2. Set up Python virtual environment
echo -e "\n[2/5] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip

# 3. Install Python requirements
echo -e "\n[3/5] Installing Python dependencies..."
pip install -r requirements.txt

# 4. Download Wake Word & Speech Models
echo -e "\n[4/5] Downloading models..."
MODELS_DIR="${HOME}/voice_assistant_models"
mkdir -p "${MODELS_DIR}"

# Vosk lightweight model for custom grammar ("Hey Kaz")
if [ ! -d "${MODELS_DIR}/vosk-model-small-en-us-0.15" ]; then
    echo "Downloading Vosk small US model..."
    wget -q --show-progress -O /tmp/vosk.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip -q /tmp/vosk.zip -d "${MODELS_DIR}/"
    rm -f /tmp/vosk.zip
fi

# OpenWakeWord pretrained models
echo "Downloading OpenWakeWord models..."
python3 -c "import openwakeword; openwakeword.utils.download_models()"

# 5. Configuration Setup
echo -e "\n[5/5] Checking configuration..."
CONFIG_TARGET="${HOME}/.assistant_config.json"
if [ ! -f "${CONFIG_TARGET}" ] && [ ! -f "config.json" ]; then
    cp config.example.json "${CONFIG_TARGET}"
    echo "Created template configuration at: ${CONFIG_TARGET}"
    echo "Please add your GEMINI_API_KEY and Spotify Developer credentials to it."
else
    echo "Configuration already found."
fi

echo -e "\n========================================================"
echo "  ✅ Setup Complete!"
echo "  1. Add your keys in ~/.assistant_config.json"
echo "  2. (Optional) Run ./link_spotify.py to link personal playlists"
echo "  3. Start Kaz by running: ./start_assistant.sh"
echo "========================================================\n"
