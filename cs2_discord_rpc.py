"""
cs2_discord_rpc.py
------------------
Shows a custom Discord "Rich Presence" while you play Counter-Strike 2:
which map you're on, which round you're in, and which game mode you're
playing (Competitive / Premier, Wingman, Casual, Deathmatch, Arms Race,
Demolition, etc.).

How it works:
    1) CS2 can send its in-game state to a local HTTP address via Valve's
       "Game State Integration" (GSI) feature. To enable this, copy
       `gamestate_integration_discordrpc.cfg` into CS2's config folder
       (see README.md).
    2) This script opens a small local HTTP server to receive that data
       (default: http://127.0.0.1:3000).
    3) It reads the incoming data (map, mode, round, score, bomb status,
       etc.) and forwards it to the Discord desktop app via `pypresence`.

Install:
    pip install cs2-discord-rpc
    (or, from a clone of this repo: pip install -r requirements.txt)

Usage:
    DISCORD_CLIENT_ID=xxxxxxxxxxxxxxxxxx cs2-discord-rpc

    Alternative (handy for autostart on Windows):
    Copy `config.example.json` to `config.json` and put your Client ID in
    it; the script reads this file instead of requiring an environment
    variable. Use windows_autostart/install_autostart.ps1 to start it
    automatically when you log in to Windows.

    You can also choose the display language of the Discord status text
    with RPC_LANGUAGE (or the "language" key in config.json): "en"
    (default) or "tr". See README.md.

How to get a Discord Client ID, where the GSI file goes -> README.md
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

try:
    from pypresence import Presence
    from pypresence.exceptions import DiscordNotFound, PipeClosed
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The pypresence library was not found. Install it with:\n"
        "    pip install cs2-discord-rpc"
    ) from exc


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cs2-discord-rpc")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
PLACEHOLDER_CLIENT_ID = "PUT_YOUR_DISCORD_CLIENT_ID_HERE"


def _read_config_file() -> dict:
    """Reads `config.json` (returns an empty dict if missing/invalid)."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read config.json, falling back to defaults: %s", exc)
        return {}


_CONFIG = _read_config_file()


def _setting(env_var: str, config_key: str, default: Optional[str]) -> Optional[str]:
    """Reads a setting from the environment first, then config.json, then
    falls back to the given default.

    config.json is especially handy for Windows autostart (Task
    Scheduler): instead of re-setting an environment variable every
    session, you write the setting to a file once (see windows_autostart/
    and README.md).
    """
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value
    config_value = _CONFIG.get(config_key)
    if config_value:
        return str(config_value)
    return default


def load_client_id() -> str:
    return _setting("DISCORD_CLIENT_ID", "discord_client_id", PLACEHOLDER_CLIENT_ID)


# Client ID of the application you created in the Discord Developer Portal.
# https://discord.com/developers/applications -> New Application -> General
# Can be set via an environment variable (DISCORD_CLIENT_ID) or config.json.
DISCORD_CLIENT_ID = load_client_id()

# Local address/port CS2's GSI data will be sent to.
# Must match the "uri" in gamestate_integration_discordrpc.cfg.
GSI_HOST = "127.0.0.1"
GSI_PORT = 3000

# Updates are sent to Discord at most this often while the state is
# unchanged (to avoid hammering the Discord IPC).
MIN_UPDATE_INTERVAL_SECONDS = 4.0

# If no data arrives from the player for this long, the status is cleared
# (interpreted as the game having been closed / CS2 exited).
STALE_TIMEOUT_SECONDS = 20.0


# --------------------------------------------------------------------------
# Display language
#
# The text shown on Discord (mode names, status text) can be shown in
# English (default) or Turkish. Set it via the RPC_LANGUAGE environment
# variable or the "language" key in config.json, e.g. RPC_LANGUAGE=tr.
# --------------------------------------------------------------------------

DEFAULT_LANGUAGE = "en"

STRINGS: dict[str, dict] = {
    "en": {
        "mode_labels": {
            "competitive": "Competitive",
            "scrimcomp5v5": "Premier",
            "scrimcomp2v2": "Wingman",
            "casual": "Casual",
            "deathmatch": "Deathmatch",
            "gungameprogressive": "Arms Race",
            "gungametrbomb": "Demolition",
            "skirmish": "Skirmish",
            "cooperative": "Co-op Strike",
            "training": "Training",
            "custom": "Custom Game",
            "survival": "Danger Zone",
        },
        "unknown_mode": "Unknown Mode",
        "unknown_map": "Unknown Map",
        "main_menu_details": "Browsing main menu",
        "warmup": "Warmup",
        "gameover": "Match over",
        "frags_deaths": "{kills} kills / {deaths} deaths",
        "bomb_planted": "Bomb planted",
    },
    "tr": {
        "mode_labels": {
            "competitive": "Rekabetçi",
            "scrimcomp5v5": "Premier",
            "scrimcomp2v2": "Yoldaş (Wingman)",
            "casual": "Basit",
            "deathmatch": "Deathmatch",
            "gungameprogressive": "Silah Yarışı",
            "gungametrbomb": "Yıkım",
            "skirmish": "Uçan Keşif Nişancısı",
            "cooperative": "Ko-op Görev",
            "training": "Antrenman",
            "custom": "Özel Oyun",
            "survival": "Tehlike Bölgesi",
        },
        "unknown_mode": "Bilinmeyen Mod",
        "unknown_map": "Bilinmeyen Harita",
        "main_menu_details": "Ana menüde geziniyor",
        "warmup": "Isınma turu",
        "gameover": "Maç bitti",
        "frags_deaths": "{kills} frag / {deaths} ölüm",
        "bomb_planted": "Bomba döşendi",
    },
}


def load_language() -> str:
    lang = (_setting("RPC_LANGUAGE", "language", DEFAULT_LANGUAGE) or DEFAULT_LANGUAGE).lower()
    if lang not in STRINGS:
        log.warning("Unknown RPC_LANGUAGE '%s', falling back to '%s'.", lang, DEFAULT_LANGUAGE)
        lang = DEFAULT_LANGUAGE
    return lang


LANGUAGE = load_language()
STR = STRINGS[LANGUAGE]


# --------------------------------------------------------------------------
# CS2 game modes
#
# The "map.mode" field in CS2's GSI output varies by the game mode the
# player is in. The table below maps every known mode key to its
# mode-specific behavior (whether rounds are counted, default max rounds).
# Display labels themselves live in STRINGS above so they can be
# translated.
#
# Note: "max_rounds" values are the defaults for CS2's standard
# matchmaking settings (e.g. Competitive/Premier MR12 -> 24 rounds,
# Wingman MR8 -> 16 rounds). These limits can differ on custom/community
# servers; if unknown, only the current round is shown.
# --------------------------------------------------------------------------

@dataclass
class ModeInfo:
    has_rounds: bool     # Does this mode have the concept of "rounds"?
    max_rounds: Optional[int] = None  # Default max rounds (if known)


MODE_INFO: dict[str, ModeInfo] = {
    # Competitive / Premier (both may come from GSI as "competitive")
    "competitive":        ModeInfo(True, 24),
    "scrimcomp5v5":       ModeInfo(True, 24),
    # Wingman 2v2
    "scrimcomp2v2":       ModeInfo(True, 16),
    # Casual
    "casual":             ModeInfo(True, None),
    # Deathmatch: no rounds, continuous respawn + scoreboard
    "deathmatch":         ModeInfo(False),
    # Arms Race
    "gungameprogressive": ModeInfo(False),
    # Demolition
    "gungametrbomb":      ModeInfo(True, None),
    # Skirmish and other "skirmish"-type modes
    "skirmish":           ModeInfo(True, None),
    # Co-op Strike / Guardian and similar cooperative modes
    "cooperative":        ModeInfo(False),
    # Training
    "training":           ModeInfo(False),
    # Custom game / community servers
    "custom":             ModeInfo(True, None),
    # Danger Zone (battle royale, legacy CS:GO mode)
    "survival":           ModeInfo(False),
}

DEFAULT_MODE = ModeInfo(True, None)


def mode_info_for(mode_key: Optional[str]) -> ModeInfo:
    if not mode_key:
        return DEFAULT_MODE
    return MODE_INFO.get(mode_key, DEFAULT_MODE)


def mode_label(mode_key: Optional[str]) -> str:
    if not mode_key:
        return STR["unknown_mode"]
    return STR["mode_labels"].get(mode_key, STR["unknown_mode"])


# --------------------------------------------------------------------------
# Map names
#
# GSI sends the map name as a technical code like "de_dust2". We translate
# these into more readable names; if an unlisted map comes in, we strip
# the prefix and title-case the rest (e.g. "de_newmap" -> "Newmap").
# --------------------------------------------------------------------------

MAP_DISPLAY_NAMES = {
    "de_dust2": "Dust II",
    "de_mirage": "Mirage",
    "de_inferno": "Inferno",
    "de_nuke": "Nuke",
    "de_overpass": "Overpass",
    "de_vertigo": "Vertigo",
    "de_ancient": "Ancient",
    "de_anubis": "Anubis",
    "de_train": "Train",
    "de_cache": "Cache",
    "cs_office": "Office",
    "cs_italy": "Italy",
    "cs_agency": "Agency",
    "de_shortdust": "Short Dust (Wingman)",
    "de_lake": "Lake (Wingman)",
    "de_stmarc": "St. Marc (Wingman)",
    "de_grail": "Grail (Wingman)",
    "aim_map": "Aim Map",
}


def display_map_name(raw_name: Optional[str]) -> str:
    if not raw_name:
        return STR["unknown_map"]
    if raw_name in MAP_DISPLAY_NAMES:
        return MAP_DISPLAY_NAMES[raw_name]
    # Strip prefixes like "de_", "cs_", "aim_" for a nicer display name.
    for prefix in ("de_", "cs_", "aim_", "gd_", "ar_"):
        if raw_name.startswith(prefix):
            return raw_name[len(prefix):].replace("_", " ").title()
    return raw_name.replace("_", " ").title()


# --------------------------------------------------------------------------
# Map images
#
# We use the KEY names of the images you uploaded to the "Rich Presence ->
# Art Assets" section of your application in the Discord Developer Portal
# (not an external URL). This is the most reliable method with classic
# desktop Rich Presence (local IPC). Upload one asset per map with these
# names (no extension, all lowercase):
#
#   cs2_logo, de_dust2, de_mirage, de_inferno, de_nuke, de_overpass,
#   de_vertigo, de_ancient, de_anubis, de_train, de_cache, cs_office,
#   cs_italy, cs_agency, de_shortdust, de_lake, de_stmarc, de_grail, aim_map
#
# (The images themselves are already in this repo under
# cs2-discord-rpc/assets/maps/ — you can download them from there and
# upload them to the Developer Portal.)
# --------------------------------------------------------------------------

FALLBACK_MAP_IMAGE_KEY = "cs2_logo"


def map_image_key(raw_name: Optional[str]) -> str:
    """Produces the Art Asset key corresponding to the GSI map code.

    Falls back to the generic CS2 logo if we don't have a ready image for
    a map (a newly released map, a community server map, etc.).
    """
    return raw_name if raw_name in MAP_DISPLAY_NAMES else FALLBACK_MAP_IMAGE_KEY


# Discord Rich Presence has two image slots: a large main image
# (large_image) and a small badge in its bottom-right corner
# (small_image). While in a match, the large image shows the map you're
# currently playing (more visually interesting since it's a real
# screenshot), and the small badge is always the CS2 logo. In the main
# menu (no map yet), the large image falls back to the CS2 logo.
CS2_LOGO_IMAGE_KEY = FALLBACK_MAP_IMAGE_KEY


# --------------------------------------------------------------------------
# Shared state: the GSI server updates this object, and the presence loop
# reads from it to send updates to Discord.
# --------------------------------------------------------------------------

@dataclass
class SharedState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    payload: Optional[dict] = None
    last_seen: float = 0.0

    def update(self, payload: dict) -> None:
        with self.lock:
            self.payload = payload
            self.last_seen = time.monotonic()

    def snapshot(self) -> tuple[Optional[dict], float]:
        with self.lock:
            return self.payload, self.last_seen


state = SharedState()


# --------------------------------------------------------------------------
# GSI HTTP server: handles POST requests coming from CS2.
# --------------------------------------------------------------------------

class GSIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - BaseHTTPRequestHandler API
        # Silence the default noisy access logs.
        pass

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b""
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except (ValueError, json.JSONDecodeError) as exc:
            log.warning("Received invalid GSI data: %s", exc)
            self.send_response(400)
            self.end_headers()
            return

        state.update(payload)
        self.send_response(200)
        self.end_headers()


def run_gsi_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((GSI_HOST, GSI_PORT), GSIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("GSI server listening on http://%s:%d", GSI_HOST, GSI_PORT)
    return server


# --------------------------------------------------------------------------
# Logic that builds the "details" / "state" text shown on Discord from the
# GSI data.
# --------------------------------------------------------------------------

def build_presence_fields(payload: dict) -> Optional[dict]:
    """Builds the Discord Rich Presence fields from a GSI payload.

    Returns None if the player is in the main menu or data is missing (in
    which case the presence is cleared).
    """
    player = payload.get("player") or {}
    map_info = payload.get("map") or {}
    round_info = payload.get("round") or {}

    activity = player.get("activity")
    if activity is not None and activity != "playing":
        # In the main menu / typing text -> no map yet, only the large
        # CS2 logo is shown (no small map badge).
        return {
            "details": STR["main_menu_details"],
            "state": "Counter-Strike 2",
            "large_image": CS2_LOGO_IMAGE_KEY,
            "large_text": "Counter-Strike 2",
        }

    map_name_raw = map_info.get("name")
    mode_key = map_info.get("mode")
    mode = mode_info_for(mode_key)
    map_name = display_map_name(map_name_raw)
    label = mode_label(mode_key)

    phase = map_info.get("phase")  # warmup / live / intermission / gameover
    if phase == "warmup":
        details = f"🗺️ {map_name} · {label}"
        state_text = STR["warmup"]
    elif phase == "gameover":
        details = f"🗺️ {map_name} · {label}"
        state_text = STR["gameover"]
    else:
        team_ct = map_info.get("team_ct") or {}
        team_t = map_info.get("team_t") or {}
        ct_score = team_ct.get("score", 0)
        t_score = team_t.get("score", 0)

        details = f"🗺️ {map_name} · {label}"

        if mode.has_rounds:
            current_round = map_info.get("round")
            # GSI round numbers start at 0; +1 for humans.
            round_display = (current_round + 1) if isinstance(current_round, int) else None
            round_text = f"Round {round_display}" if round_display else "Round -"
            if mode.max_rounds:
                round_text += f"/{mode.max_rounds}"
            state_text = f"{round_text} · CT {ct_score} - {t_score} T"
        else:
            # Modes without rounds (Deathmatch, Arms Race, etc.): show
            # personal kill/death stats instead of a round number.
            match_stats = player.get("match_stats") or {}
            kills = match_stats.get("kills", 0)
            deaths = match_stats.get("deaths", 0)
            state_text = STR["frags_deaths"].format(kills=kills, deaths=deaths)

        if round_info.get("bomb") == "planted":
            state_text += f" · 💣 {STR['bomb_planted']}"

    return {
        "details": details,
        "state": state_text,
        "large_image": map_image_key(map_name_raw),
        "large_text": map_name,
        "small_image": CS2_LOGO_IMAGE_KEY,
        "small_text": "Counter-Strike 2",
    }


def state_key(fields: Optional[dict]) -> tuple:
    if fields is None:
        return ()
    return (
        fields.get("details"),
        fields.get("state"),
        fields.get("large_image"),
        fields.get("small_image"),
    )


# --------------------------------------------------------------------------
# Main loop: establishes/keeps alive the Discord IPC connection and
# reflects changes in GSI state to Discord.
# --------------------------------------------------------------------------

def connect_discord() -> Presence:
    if DISCORD_CLIENT_ID == "PUT_YOUR_DISCORD_CLIENT_ID_HERE":
        raise SystemExit(
            "DISCORD_CLIENT_ID is not set. Follow the steps in README.md to\n"
            "create your own Discord application and give this script its\n"
            "Client ID (environment variable: DISCORD_CLIENT_ID)."
        )
    rpc = Presence(DISCORD_CLIENT_ID)
    rpc.connect()
    log.info("Connected to Discord (client_id=%s).", DISCORD_CLIENT_ID)
    return rpc


def main() -> None:
    run_gsi_server()

    rpc: Optional[Presence] = None
    last_sent_key: tuple = ("__init__",)
    last_sent_time = 0.0
    cleared_for_stale = True
    start_time = time.time()

    while True:
        try:
            if rpc is None:
                rpc = connect_discord()

            payload, last_seen = state.snapshot()
            now = time.monotonic()
            is_stale = payload is None or (now - last_seen) > STALE_TIMEOUT_SECONDS

            if is_stale:
                if not cleared_for_stale:
                    rpc.clear()
                    log.info("No data from CS2, Discord status cleared.")
                    cleared_for_stale = True
                    last_sent_key = ()
                time.sleep(1.0)
                continue

            cleared_for_stale = False
            fields = build_presence_fields(payload)
            key = state_key(fields)

            enough_time_passed = (time.time() - last_sent_time) >= MIN_UPDATE_INTERVAL_SECONDS
            if fields and key != last_sent_key and enough_time_passed:
                rpc.update(
                    details=fields["details"],
                    state=fields["state"],
                    large_image=fields.get("large_image") or CS2_LOGO_IMAGE_KEY,
                    large_text=fields.get("large_text") or "Counter-Strike 2",
                    small_image=fields.get("small_image"),
                    small_text=fields.get("small_text"),
                    start=int(start_time),
                )
                log.info("Status updated: %s | %s", fields["details"], fields["state"])
                last_sent_key = key
                last_sent_time = time.time()

            time.sleep(1.0)

        except (DiscordNotFound, PipeClosed) as exc:
            log.warning("Could not connect to Discord (%s). Make sure the Discord "
                        "desktop app is running. Retrying in 5s.", exc)
            rpc = None
            time.sleep(5.0)
        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as exc:  # noqa: BLE001 - don't want the script to die on a one-off error
            log.exception("Unexpected error: %s", exc)
            time.sleep(3.0)

    if rpc is not None:
        try:
            rpc.clear()
            rpc.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
