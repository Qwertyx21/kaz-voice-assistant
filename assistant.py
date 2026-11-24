#!/usr/bin/env python3
import os
import sys
import time
import datetime
import subprocess
import urllib.request
import json
import io
import wave
import base64
import socket
import asyncio
import edge_tts
import av
import numpy as np
import pyttsx3
import warnings

# Suppress noisy warnings
warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# --- Configuration Resolution ---
CONFIG_FILE = os.path.expanduser("~/.assistant_config.json")
local_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
if not os.path.exists(CONFIG_FILE) and os.path.exists(local_config):
    CONFIG_FILE = local_config

# --- Load Config (Spotify & Gemini API Keys) ---
config = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")

GEMINI_API_KEY = config.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

VOICE_NAME = config.get("VOICE", "en-GB-RyanNeural")

# --- Text-to-Speech Engine (Neural Online + pyttsx3 Offline) ---
local_engine = pyttsx3.init()
local_engine.setProperty('rate', 175)
local_engine.setProperty('volume', 1.0)

def speak_offline(text):
    try:
        local_engine.say(text)
        local_engine.runAndWait()
    except Exception as e:
        print(f"TTS Offline Error: {e}")

def speak(text):
    if not text:
        return
    print(f"\n[Kaz]: {text}")

    if is_online():
        try:
            async def _synth():
                comm = edge_tts.Communicate(text, VOICE_NAME)
                mp3_data = b""
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        mp3_data += chunk["data"]
                return mp3_data

            mp3_data = asyncio.run(_synth())
            in_buf = io.BytesIO(mp3_data)
            container = av.open(in_buf)
            resampler = av.AudioResampler(format="s16", layout="mono", rate=24000)
            pcm_chunks = []
            for frame in container.decode(audio=0):
                res = resampler.resample(frame)
                if res:
                    for r in res:
                        pcm_chunks.append(r.to_ndarray().tobytes())
            pcm_bytes = b"".join(pcm_chunks)
            subprocess.run(
                ["pacat", "--playback", "--format=s16le", "--rate=24000", "--channels=1"],
                input=pcm_bytes,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return
        except Exception as e:
            print(f"[Neural TTS]: Note ({e}), falling back to local TTS.")

    # Fallback if offline or synthesis fails
    speak_offline(text)

def play_chime():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    chime_path = os.path.join(base_dir, "chime.wav")
    if not os.path.exists(chime_path):
        chime_path = os.path.expanduser("~/chime.wav")
    if os.path.exists(chime_path):
        subprocess.run(["paplay", chime_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def is_online():
    """Quick 100ms check to verify internet connectivity."""
    try:
        socket.setdefaulttimeout(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False

# --- Helper Functions ---
def get_battery_info():
    try:
        cap = "unknown"
        status = "discharging"
        for bat in ["BAT0", "BAT1"]:
            cap_path = f"/sys/class/power_supply/{bat}/capacity"
            stat_path = f"/sys/class/power_supply/{bat}/status"
            if os.path.exists(cap_path):
                with open(cap_path) as f:
                    cap = f.read().strip()
                if os.path.exists(stat_path):
                    with open(stat_path) as f:
                        status = f.read().strip()
                break
        return f"Battery is at {cap} percent and is currently {status.lower()}."
    except Exception:
        return "Unable to check battery status."

def get_weather_info():
    try:
        req = urllib.request.Request("https://wttr.in/?format=3", headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read().decode("utf-8").strip()
            return f"The current weather is: {data}"
    except Exception:
        return "Could not retrieve weather information at the moment."

def get_now_playing():
    try:
        res = subprocess.run(
            ["playerctl", "metadata", "--format", "{{ title }} by {{ artist }}"],
            capture_output=True, text=True, timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            return f"Currently playing {res.stdout.strip()}"
        return "Nothing is currently playing."
    except Exception:
        return "Could not determine what is playing."

# --- Spotify Setup ---
sp = None
client_id = config.get("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIPY_CLIENT_ID")
client_secret = config.get("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = "http://127.0.0.1:8888/callback"
scope = "playlist-read-private playlist-read-collaborative user-library-read user-read-playback-state user-modify-playback-state"
cache_path = os.path.expanduser("~/.cache/spotipy_token.json")

if client_id and client_secret:
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
        from spotipy.cache_handler import CacheFileHandler

        auth_mgr = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            cache_handler=CacheFileHandler(cache_path=cache_path),
            open_browser=False
        )
        token_info = auth_mgr.cache_handler.get_cached_token()
        if token_info and auth_mgr.validate_token(token_info):
            sp = spotipy.Spotify(auth_manager=auth_mgr)
            print("[Spotify]: Connected with linked user account.")
        else:
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
                cache_handler=CacheFileHandler(cache_path=cache_path)
            ))
            print("[Spotify]: Connected with app credentials.")
    except Exception as e:
        print(f"[Spotify]: Initialization error: {e}")

def play_spotify_track(song_name, artist="", media_type="auto"):
    # Ensure Spotify desktop app is open
    subprocess.Popen(["spotify"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)

    raw_query = f"{song_name} {artist}".strip() if artist else song_name.strip()
    is_playlist_query = ("playlist" in raw_query.lower() or media_type == "playlist")

    clean_query = raw_query
    for p in ["my playlist", "the playlist", "playlist"]:
        clean_query = clean_query.replace(p, "").strip()

    if sp and (clean_query or raw_query):
        search_term = clean_query if clean_query else raw_query
        try:
            # 1. If user asked for a playlist or personal library, check user's playlists first
            if is_playlist_query:
                try:
                    user_playlists = sp.current_user_playlists(limit=50)
                    for pl in user_playlists.get("items", []):
                        if pl and (search_term.lower() in pl["name"].lower() or pl["name"].lower() in search_term.lower()):
                            speak(f"Playing your playlist {pl['name']}")
                            subprocess.run(["playerctl", "-p", "spotify", "open", pl["uri"]], timeout=2)
                            time.sleep(0.5)
                            subprocess.run(["playerctl", "-p", "spotify", "play"], timeout=1)
                            return "media_played"
                except Exception:
                    pass

                # If not found in personal playlists, search public playlists
                res_pl = sp.search(q=search_term, limit=1, type="playlist")
                pl_items = [p for p in res_pl.get("playlists", {}).get("items", []) if p]
                if pl_items:
                    pl = pl_items[0]
                    speak(f"Playing playlist {pl['name']}")
                    subprocess.run(["playerctl", "-p", "spotify", "open", pl["uri"]], timeout=2)
                    time.sleep(0.5)
                    subprocess.run(["playerctl", "-p", "spotify", "play"], timeout=1)
                    return "media_played"

            # 2. Track search (default)
            results = sp.search(q=search_term, limit=1, type="track")
            items = results.get("tracks", {}).get("items", [])
            if items:
                track = items[0]
                t_name = track["name"]
                track_uri = track["uri"]
                speak(f"Playing {t_name}")
                subprocess.run(["playerctl", "-p", "spotify", "open", track_uri], timeout=2)
                return "media_played"
        except Exception as e:
            print(f"[Spotify]: API search error: {e}")

    # Fallback via direct Spotify URI
    fallback_q = clean_query if clean_query else raw_query
    if fallback_q:
        speak(f"Playing {fallback_q}")
        subprocess.Popen(["spotify", f"spotify:search:{fallback_q}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
        subprocess.run(["playerctl", "-p", "spotify", "play"])
    else:
        speak("Resuming Spotify")
        subprocess.run(["playerctl", "-p", "spotify", "play"])
    return "media_played"

# --- Gemini Tool Declarations ---
GEMINI_TOOLS = [{
    "function_declarations": [
        {
            "name": "play_music",
            "description": "Play a specific song, artist, playlist, or genre on Spotify.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "song_name": {"type": "STRING", "description": "The song title, playlist name, or search description."},
                    "artist": {"type": "STRING", "description": "Artist name if mentioned."},
                    "media_type": {"type": "STRING", "enum": ["track", "playlist", "album", "auto"], "description": "Type of media to play."}
                },
                "required": ["song_name"]
            }
        },
        {
            "name": "media_control",
            "description": "Control playback for media players (pause, resume, skip, previous, what is playing).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "enum": ["pause", "resume", "next", "previous", "what_playing"],
                        "description": "The media playback action."
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "volume_control",
            "description": "Adjust system audio volume up, down, mute, or unmute.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "enum": ["up", "down", "mute", "unmute"], "description": "Volume action to perform."}
                },
                "required": ["action"]
            }
        },
        {
            "name": "system_info",
            "description": "Query local system information like battery level, time, date, or weather.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "info_type": {"type": "STRING", "enum": ["battery", "time", "date", "weather"]}
                },
                "required": ["info_type"]
            }
        },
        {
            "name": "open_application",
            "description": "Open an application or lock the screen on this laptop.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "enum": ["spotify", "chrome", "terminal", "files", "lock_screen"]}
                },
                "required": ["app_name"]
            }
        }
    ]
}]

def execute_gemini_tool(func_name, args):
    print(f"\n[Gemini Tool Execution]: {func_name}({args})")
    
    if func_name == "play_music":
        song = args.get("song_name", "")
        artist = args.get("artist", "")
        media_type = args.get("media_type", "auto")
        return play_spotify_track(song, artist, media_type)
        
    elif func_name == "media_control":
        action = args.get("action", "")
        if action == "pause":
            subprocess.run(["playerctl", "pause"])
            speak("Paused.")
            return "media_paused"
        elif action == "resume":
            subprocess.run(["playerctl", "play"])
            speak("Resuming playback.")
            return "media_played"
        elif action == "next":
            subprocess.run(["playerctl", "next"])
            speak("Skipping track.")
            return "media_played"
        elif action == "previous":
            subprocess.run(["playerctl", "previous"])
            speak("Previous track.")
            return "media_played"
        elif action == "what_playing":
            speak(get_now_playing())
            return "informational"

    elif func_name == "volume_control":
        action = args.get("action", "")
        if action == "up":
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"])
            speak("Volume up.")
        elif action == "down":
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"])
            speak("Volume down.")
        elif action == "mute":
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
            speak("Muted.")
        elif action == "unmute":
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
            speak("Unmuted.")
        return "informational"

    elif func_name == "system_info":
        info_type = args.get("info_type", "")
        if info_type == "battery":
            speak(get_battery_info())
        elif info_type == "time":
            now = datetime.datetime.now()
            speak(f"It is {now.strftime('%I:%M %p')}.")
        elif info_type == "date":
            now = datetime.datetime.now()
            speak(f"Today is {now.strftime('%A, %B %d')}.")
        elif info_type == "weather":
            speak(get_weather_info())
        return "informational"

    elif func_name == "open_application":
        app = args.get("app_name", "")
        if app == "spotify":
            subprocess.Popen(["spotify"])
            speak("Opening Spotify.")
        elif app == "chrome":
            subprocess.Popen(["google-chrome"])
            speak("Opening Chrome.")
        elif app == "terminal":
            subprocess.Popen(["gnome-terminal"])
            speak("Opening terminal.")
        elif app == "files":
            subprocess.Popen(["nautilus"])
            speak("Opening files.")
        elif app == "lock_screen":
            speak("Locking screen.")
            subprocess.run(["loginctl", "lock-session"])
        return "action"

    return "informational"

# --- Online Gemini Processor (Direct Audio + Tools) ---
def process_audio_with_gemini(wav_bytes):
    b64_audio = base64.b64encode(wav_bytes).decode('utf-8')
    models_to_try = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
    
    system_instruction = (
        "You are Kaz, an ultra-fast, helpful voice assistant running on the user's laptop. "
        "The user will speak to you in audio. "
        "Listen to the user's spoken voice carefully. "
        "When the user mentions a song, music, artist, or asks to play something, ALWAYS call the play_music tool. "
        "When they want to control playback, volume, or system settings, USE THE PROVIDED TOOLS. "
        "CRITICAL RULES: "
        "1. NEVER ask follow-up questions (e.g. NEVER ask 'Is there anything else?', 'How else can I help?', 'Would you like to play another song?'). "
        "2. Do not offer unwanted commentary or follow-ups when playing music. "
        "3. For general knowledge queries, give a direct, friendly answer in 1-2 spoken sentences only."
    )

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
                ]
            }],
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "tools": GEMINI_TOOLS
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read().decode())
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                
                # Check for Function Call first
                for part in parts:
                    if "functionCall" in part:
                        fn_name = part["functionCall"].get("name")
                        fn_args = part["functionCall"].get("args", {})
                        return execute_gemini_tool(fn_name, fn_args)
                
                # If no function call, speak conversational text response (without follow-ups)
                for part in parts:
                    text_resp = part.get("text", "").strip()
                    if text_resp:
                        for junk in ["Is there anything else I can help you with?", "Is there anything else?", "Anything else?"]:
                            text_resp = text_resp.replace(junk, "").strip()
                        if text_resp:
                            speak(text_resp)
                            return "informational"
                return "none"
        except Exception as e:
            # Fall through to next model if model is busy
            continue
            
    print("[Gemini]: API call unsuccessful, falling back to local engine.")
    return None

# --- Offline Fallback Dispatcher ---
def handle_local_command(text):
    text = text.lower().strip().rstrip(".!?")
    if not text:
        return "none"
    print(f"\n[Local Offline Command]: \"{text}\"")

    if text.startswith("play ") or "play " in text:
        song_query = text
        for p in ["open spotify and play ", "play on spotify ", "play the song ", "play song ", "play "]:
            song_query = song_query.replace(p, "")
        return play_spotify_track(song_query.strip())
    elif text in ["pause", "stop"]:
        subprocess.run(["playerctl", "pause"])
        speak("Paused.")
        return "media_paused"
    elif text in ["resume", "play"]:
        subprocess.run(["playerctl", "play"])
        speak("Resuming.")
        return "media_played"
    elif "next" in text:
        subprocess.run(["playerctl", "next"])
        speak("Next track.")
        return "media_played"
    elif "previous" in text or "back" in text:
        subprocess.run(["playerctl", "previous"])
        speak("Previous track.")
        return "media_played"
    elif "volume up" in text:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"])
        speak("Volume up.")
        return "informational"
    elif "volume down" in text:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"])
        speak("Volume down.")
        return "informational"
    elif "time" in text:
        now = datetime.datetime.now()
        speak(f"It is {now.strftime('%I:%M %p')}.")
        return "informational"
    elif "battery" in text:
        speak(get_battery_info())
        return "informational"
    else:
        speak("I am currently offline and can only perform basic local media and volume controls.")
        return "informational"

# --- Initialize Models & Audio ---
print("\n[1/3] Loading Wake Word Engine ('Hey Kaz' & 'Hey Jarvis')...")
from vosk import Model as VoskModel, KaldiRecognizer
vosk_path = os.path.expanduser("~/voice_assistant_models/vosk-model-small-en-us-0.15")
vosk_model = VoskModel(vosk_path)
kaz_grammar = '["hey kaz", "kaz", "hey cas", "cas", "hey cos", "[unk]"]'
kaz_recognizer = KaldiRecognizer(vosk_model, 16000, kaz_grammar)

from openwakeword.model import Model
oww_model = Model()
print("[Wake Word]: Ready. Wake words active: 'Hey Kaz' & 'Hey Jarvis'")

# Local Faster-Whisper (Kept in memory for instant offline fallback)
print("\n[2/3] Loading Offline Fallback Engine (Faster-Whisper)...")
from faster_whisper import WhisperModel
local_whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
print("[Offline Engine]: Ready.")

# PyAudio Setup
import pyaudio

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1280

# Silence ALSA / JACK initialization output
devnull = os.open(os.devnull, os.O_WRONLY)
old_stderr = os.dup(2)
sys.stderr.flush()
os.dup2(devnull, 2)
os.close(devnull)

try:
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
finally:
    os.dup2(old_stderr, 2)
    os.close(old_stderr)

print("\n" + "="*55)
print("  🚀 Hybrid AI Assistant (KAZ) is ONLINE!")
print("  Online: Gemini Native Audio Understanding + Tool Calling")
print("  Offline: Instant fallback to local Faster-Whisper")
print("  Wake word: 'Hey Kaz'")
print("="*55 + "\n")

cooldown_until = 0
trigger_immediately = any(arg in sys.argv for arg in ["now", "--now", "-n", "listen", "--listen"])

try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)

        if time.time() < cooldown_until:
            continue

        chunk_arr = np.frombuffer(data, dtype=np.int16)

        # 1. Check for immediate command-line trigger or "Hey Kaz"
        kaz_detected = False
        if trigger_immediately:
            kaz_detected = True
            trigger_immediately = False
        elif kaz_recognizer.AcceptWaveform(data):
            res = json.loads(kaz_recognizer.Result())
            text = res.get("text", "")
            if any(w in text for w in ["hey kaz", "kaz", "hey cas", "cas"]):
                kaz_detected = True

        # 2. Check for "Hey Jarvis"
        prediction = oww_model.predict(chunk_arr)
        jarvis_detected = prediction.get("hey_jarvis", 0) > 0.70

        if kaz_detected or jarvis_detected:
            detected_word = "Hey Kaz" if kaz_detected else "Hey Jarvis"
            print(f"\n[⚡ Wake Word: {detected_word}!]")

            oww_model.reset()
            kaz_recognizer = KaldiRecognizer(vosk_model, 16000, kaz_grammar)

            # Auto-pause media so mic does not hear speaker output
            was_playing = False
            try:
                res = subprocess.run(["playerctl", "status"], capture_output=True, text=True, timeout=1)
                if "Playing" in res.stdout:
                    was_playing = True
                    subprocess.run(["playerctl", "pause"], timeout=1)
            except Exception:
                pass

            play_chime()

            # Flush mic buffer
            while stream.get_read_available() > 0:
                stream.read(stream.get_read_available(), exception_on_overflow=False)

            print("[Listening for command...]")

            # Record user's voice command (extended input time & natural pauses)
            audio_frames = []
            speech_started = False
            silence_counter = 0
            initial_wait_chunks = int(RATE / CHUNK * 3.0)   # Up to 3.0s to begin speaking after chime
            max_chunks = int(RATE / CHUNK * 7.0)            # Up to 7.0s total recording window
            silence_cutoff = 22                             # ~1.8s of sustained silence needed to finish

            chunks_recorded = 0
            while chunks_recorded < max_chunks:
                cmd_data = stream.read(CHUNK, exception_on_overflow=False)
                audio_frames.append(cmd_data)
                chunks_recorded += 1

                samples = np.frombuffer(cmd_data, dtype=np.int16)
                rms = np.sqrt(np.mean(samples.astype(np.float32)**2))

                if rms > 180:
                    speech_started = True
                    silence_counter = 0
                elif speech_started:
                    silence_counter += 1
                    if silence_counter > silence_cutoff:  # ~1.8s silence after user spoke
                        break
                elif not speech_started and chunks_recorded >= initial_wait_chunks:
                    # User hasn't started speaking within 4 seconds of chime
                    break

            # If user said nothing at all, silently resume music if it was playing
            if not speech_started:
                print("[No speech detected - going back to sleep]")
                if was_playing:
                    time.sleep(0.2)
                    subprocess.run(["playerctl", "play"], timeout=1)
                cooldown_until = time.time() + 1.0
                continue

            # Convert raw audio chunks to clean 16kHz WAV in memory
            raw_pcm = b"".join(audio_frames)
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                wf.writeframes(raw_pcm)
            wav_bytes = wav_buffer.getvalue()

            action_type = None

            # --- ROUTING: Online Gemini vs Offline Local Whisper ---
            if GEMINI_API_KEY and is_online():
                print("[Processing]: Routing audio directly to Gemini Cloud...")
                action_type = process_audio_with_gemini(wav_bytes)

            # Offline Fallback (or if Gemini request failed)
            if action_type is None:
                print("[Processing]: Routing to Local Offline Whisper...")
                audio_np = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                segments, _ = local_whisper.transcribe(audio_np, language="en", beam_size=1)
                local_text = " ".join(s.text for s in segments).strip()
                action_type = handle_local_command(local_text)

            # Smart Resume if music was playing and user asked an informational question
            if was_playing and action_type in ["none", "informational"]:
                time.sleep(0.3)
                subprocess.run(["playerctl", "play"], timeout=1)

            # Cooldown buffer
            if action_type == "media_played":
                cooldown_until = time.time() + 2.5
            else:
                cooldown_until = time.time() + 1.2

            while stream.get_read_available() > 0:
                stream.read(stream.get_read_available(), exception_on_overflow=False)

except KeyboardInterrupt:
    print("\nStopping assistant gracefully...")
    stream.stop_stream()
    stream.close()
    p.terminate()
