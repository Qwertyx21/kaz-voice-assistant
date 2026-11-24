#!/usr/bin/env python3
import os
import sys
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler

CONFIG_FILE = os.path.expanduser("~/.assistant_config.json")
local_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
if not os.path.exists(CONFIG_FILE) and os.path.exists(local_config):
    CONFIG_FILE = local_config
CACHE_FILE = os.path.expanduser("~/.cache/spotipy_token.json")

if not os.path.exists(CONFIG_FILE):
    print(f"Error: {CONFIG_FILE} not found. Please create it or copy config.example.json.")
    sys.exit(1)

with open(CONFIG_FILE) as f:
    config = json.load(f)

client_id = config.get("SPOTIPY_CLIENT_ID")
client_secret = config.get("SPOTIPY_CLIENT_SECRET")
redirect_uri = "http://127.0.0.1:8888/callback"

if not client_id or not client_secret:
    print("Error: SPOTIPY_CLIENT_ID or SPOTIPY_CLIENT_SECRET missing in config.")
    sys.exit(1)

scope = "playlist-read-private playlist-read-collaborative user-library-read user-read-playback-state user-modify-playback-state"

print("\n" + "="*50)
print("  🔗 Linking your personal Spotify account to Kaz")
print("="*50)
print(f"\nMake sure '{redirect_uri}' is added to Redirect URIs in your Spotify Developer Dashboard:\n")
print("  1. Go to: https://developer.spotify.com/dashboard")
print("  2. Click your App -> Settings")
print(f"  3. In 'Redirect URIs', add: {redirect_uri}")
print("  4. Click 'Save' at the bottom.\n")
print("Opening browser for authorization now...\n")

auth_manager = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=CacheFileHandler(cache_path=CACHE_FILE),
    open_browser=True
)

try:
    sp = spotipy.Spotify(auth_manager=auth_manager)
    user = sp.current_user()
    print(f"\n🎉 Successfully linked Spotify account: {user.get('display_name')} ({user.get('id')})")
    
    # List user's playlists
    playlists = sp.current_user_playlists(limit=10)
    items = playlists.get("items", [])
    print(f"\nFound {len(items)} personal playlists:")
    for idx, p in enumerate(items, 1):
        print(f"  {idx}. {p['name']} ({p['tracks']['total']} tracks) -> {p['uri']}")
        
    print("\n✅ Authorization complete! Kaz can now access all your personal playlists.\n")
except Exception as e:
    print(f"\n❌ Authorization failed: {e}\n")
