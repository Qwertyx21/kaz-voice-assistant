#!/usr/bin/env bash
# ==============================================================================
# Kaz Hybrid AI Voice Assistant Launcher
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure ALSA mixer levels are optimal if amixer is installed
# (Eliminates clipping and prevents acoustic self-feedback)
if command -v amixer >/dev/null 2>&1; then
    amixer -c 0 sset "Internal Mic Boost" 1 >/dev/null 2>&1 || true
    amixer -c 0 sset "Capture" 60% >/dev/null 2>&1 || true
fi

# Locate and activate Python virtual environment
if [ -d "${SCRIPT_DIR}/venv" ]; then
    source "${SCRIPT_DIR}/venv/bin/activate"
elif [ -d "${HOME}/voice_assistant_env" ]; then
    source "${HOME}/voice_assistant_env/bin/activate"
fi

python3 "${SCRIPT_DIR}/assistant.py" "$@"
