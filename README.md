# Kaz: Hybrid AI Voice Assistant for Linux

Kaz is an intelligent, low-latency Linux voice assistant designed to bridge local hardware control with cloud intelligence. It pairs lightweight offline wake-word recognition with Gemini Multimodal direct-audio tool calling, falling back to local Faster-Whisper when disconnected from the internet.

---

## Architecture Overview

```
                        [ Audio Input (16kHz PCM) ]
                                    │
                       [ Wake Word Engine (Local) ]
                  (Vosk: "Hey Kaz" | OpenWakeWord: "Hey Jarvis")
                                    │ (Trigger Detected)
               ┌────────────────────┴────────────────────┐
               ▼                                         ▼
     [ Immediate Media Pause ]                  [ 120ms Dual Chime ]
    (playerctl pause + buffer flush)                      │
                                                          ▼
                                              [ Dynamic VAD Recording ]
                                              (3s initial wait / 7s max)
                                                          │
                                               [ Internet Available? ]
                                                /                  \
                                            (Yes)                  (No)
                                              ▼                      ▼
                                     [ Gemini Multimodal ]  [ Faster-Whisper (tiny.en) ]
                                   (Direct Audio + Tools)            │
                                              │             [ Local Command Dispatcher ]
                                              │                      │
                                              └──────────┬───────────┘
                                                         ▼
                                            [ Tool Execution Engine ]
                                   ┌─────────────────────┼─────────────────────┐
                                   ▼                     ▼                     ▼
                           [ Spotify Control ]   [ System / Volume ]   [ High-Def Neural TTS ]
                          (playerctl track open)    (pactl / bat)        (edge-tts / pyttsx3)
```

---

## Key Engineering Solutions

### 1. Eliminating Acoustic Feedback & Self-Listening
* **Instant Auto-Pause:** When the wake word triggers, running media is paused immediately via `playerctl` and the microphone buffer is flushed so the assistant never hears or transcribes its own speaker audio.
* **Silent Resume:** If the user wakes Kaz but does not speak within the initial listening window, any previously paused track resumes automatically without verbal interruption (*no "I didn't hear anything"*).
* **Cooldown Buffer:** A 2.5-second cooldown window after playback initiation ensures song intros do not accidentally re-trigger the wake word.

### 2. High-Fidelity Bluetooth Audio Preservation (WirePlumber Fix)
* **The Problem:** Linux PipeWire / WirePlumber by default auto-switches Bluetooth earphones from high-fidelity stereo (**A2DP**) to hands-free phone-call mode (**HSP/HFP, mono 16kHz**) whenever an application starts capturing microphone input. This makes music sound muffled and degraded.
* **The Solution:** A dedicated WirePlumber configuration (`configs/11-bluetooth-policy.lua`) disables automatic profile downgrades. Earbuds remain in pristine A2DP stereo, while input capture routes cleanly through the laptop's internal microphone.

### 3. Direct Spotify Playback Without Premium
* Natural music queries are resolved against the Spotify Web API.
* Kaz retrieves the target track URI and triggers native desktop playback via:
  ```bash
  playerctl -p spotify open spotify:track:<TRACK_ID>
  ```
  This immediately streams the specific requested track on Linux without requiring a paid Spotify Premium subscription.
* Supports both public catalog tracks and personalized private user playlists via local OAuth token integration (`link_spotify.py`).

### 4. Hybrid Speech Synthesis
* **Online:** Natural human-intonation speech synthesis generated via `edge-tts` (default voice: `en-GB-RyanNeural`).
* **Offline:** Smooth fallback to local `pyttsx3` speech synthesis when offline.

---

## Project Structure

```
kaz-voice-assistant/
├── assistant.py               # Main assistant loop, audio VAD & tool dispatch
├── start_assistant.sh         # Portable launcher script (sets mixer levels & venv)
├── link_spotify.py            # One-time OAuth script for personal playlists
├── chime.wav                  # Low-latency activation chime
├── config.example.json        # Template configuration file
├── requirements.txt           # Python package dependencies
├── setup.sh                   # Automated environment & model installer
├── configs/
│   ├── .assistant_config.example.json
│   └── 11-bluetooth-policy.lua # WirePlumber Bluetooth stereo lock
└── extras/
    └── hardware/
        ├── asus-alc256-mic.conf # Realtek ALC256 kernel pin fix
        ├── asus-alc256-mic.fw   # ALC256 pin verb patch
        └── README.md            # Hardware setup & mixer guide
```

---

## Quick Start

### 1. Clone & Run Setup
```bash
git clone https://github.com/your-username/kaz-voice-assistant.git
cd kaz-voice-assistant
chmod +x setup.sh start_assistant.sh link_spotify.py
./setup.sh
```

### 2. Configure API Keys
Copy the template configuration to `~/.assistant_config.json`:
```bash
cp config.example.json ~/.assistant_config.json
nano ~/.assistant_config.json
```
Populate your credentials:
```json
{
  "GEMINI_API_KEY": "your_gemini_api_key_here",
  "SPOTIPY_CLIENT_ID": "your_spotify_client_id_here",
  "SPOTIPY_CLIENT_SECRET": "your_spotify_client_secret_here",
  "VOICE": "en-GB-RyanNeural"
}
```

* **Gemini API Key:** Free from [Google AI Studio](https://aistudio.google.com/).
* **Spotify Credentials:** Create a free app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard). In your app settings, add `http://127.0.0.1:8888/callback` as a Redirect URI.

### 3. (Optional) Link Personal Spotify Library
To let Kaz access your personal private playlists:
```bash
./link_spotify.py
```
Grant permission in the browser window to cache your user token.

### 4. Launch the Assistant
```bash
./start_assistant.sh
```

Or trigger an instant command without saying the wake word:
```bash
./start_assistant.sh now
```

---

## Command Reference

| Intent | Voice Command Examples |
| :--- | :--- |
| **Songs** | *"Play Starboy"*, *"Play Bohemian Rhapsody by Queen"* |
| **Playlists** | *"Play my calm playlist"*, *"Play Today's Top Hits"* |
| **Media** | *"Pause"*, *"Resume"*, *"Skip song"*, *"Previous"*, *"What song is this?"* |
| **Volume** | *"Volume up"*, *"Volume down"*, *"Mute"*, *"Unmute"* |
| **System** | *"What is my battery level?"*, *"What time is it?"*, *"What is the weather?"* |
| **Apps** | *"Open Chrome"*, *"Open Terminal"*, *"Open Files"*, *"Lock screen"* |
| **General AI** | Any factual, scientific, or reasoning question (answered in 1-2 spoken sentences) |

---

## Optional: Terminal Shortcut
To trigger Kaz from any directory:
```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/start_assistant.sh" ~/.local/bin/kaz
```
Ensure `~/.local/bin` is in your `$PATH`. You can then launch Kaz with `kaz` or `kaz now`.
