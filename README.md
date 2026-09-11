# CS2 Discord Rich Presence

[![CI](https://github.com/openl32dll/cs2-discord-rpc/actions/workflows/ci.yml/badge.svg)](https://github.com/openl32dll/cs2-discord-rpc/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/openl32dll/cs2-discord-rpc)](https://github.com/openl32dll/cs2-discord-rpc/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/cs2-discord-rpc)](https://pypi.org/project/cs2-discord-rpc/)

🇬🇧 English | [🇹🇷 Türkçe](README.tr.md)

A tool that shows more than just "Playing Counter-Strike 2" on your Discord
profile: **which map** you're on, **which game mode** you're playing
(Competitive/Premier, Wingman, Casual, Deathmatch, Arms Race, Demolition,
Co-op, Training, Custom Game, etc.) and **which round** you're in.

In modes without the concept of rounds (Deathmatch, Arms Race, etc.), your
current kill/death count is shown instead of a round.

## How it works

Thanks to Valve's **Game State Integration (GSI)** feature, CS2 can send
its in-game state (map, mode, round, score, bomb status...) to a local HTTP
address at regular intervals. This script:

1. Opens a small local server at `http://127.0.0.1:3000`.
2. Reads the incoming data from CS2.
3. Forwards it to the Discord desktop app via the `pypresence` library.

## Installation

### 1) Create a Discord Application

Discord requires third-party scripts to create an application (Client ID)
in order to show a "Rich Presence":

1. Go to https://discord.com/developers/applications.
2. Create a new application with **New Application** — name it
   `Counter-Strike 2` if you like.
3. Copy the **Application ID** (Client ID) shown on the **OAuth2 / General**
   page in the left menu.

**Also upload the map images at this step.** On the same page, go to
**Rich Presence → Art Assets** in the left menu and upload every PNG from
the `assets/maps/` folder using the **exact same** key name as its
filename (no extension, all lowercase):

```
cs2_logo, de_dust2, de_mirage, de_inferno, de_nuke, de_overpass,
de_vertigo, de_ancient, de_anubis, de_train, de_cache, cs_office,
cs_italy, cs_agency, de_shortdust, de_lake, de_stmarc, de_grail, aim_map
```

For maps you don't have a real screenshot for (Wingman maps, Agency, Aim
Map, etc.) you can skip this — the script automatically falls back to
`cs2_logo`. To add or change an image later, just **re-upload it** under
the same key name and restart the script.

### 2) Point CS2 to the GSI config file

Copy `gamestate_integration_discordrpc.cfg` into CS2's config folder:

```
<Steam install directory>\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg\
```

(The folder is still named `csgo` since CS2 is the successor to CS:GO.)

Restart CS2 (if it's running) after copying the file.

### 3) Install

From PyPI (recommended — this makes the `cs2-discord-rpc` command
available):

```bash
pip install cs2-discord-rpc
```

Or, if you'd rather clone this repo and install dependencies manually:

```bash
pip install -r requirements.txt
```

### 4) Set your Client ID

You have two options:

**a) One-off / for testing — environment variable:**
```bash
# Windows (PowerShell)
$env:DISCORD_CLIENT_ID="YOUR_CLIENT_ID"; cs2-discord-rpc

# Linux / macOS
DISCORD_CLIENT_ID=YOUR_CLIENT_ID cs2-discord-rpc
```

**b) Persistent / for autostart — config.json (recommended):**
```bash
cp config.example.json config.json     # Windows: copy config.example.json config.json
```
Open `config.json` and put your Client ID in the `discord_client_id` field.
This file is in `.gitignore` so it never gets committed. The script reads
it automatically every time it runs — no need to set an environment
variable, which makes it ideal for Windows autostart (see below).

### 5) Run it

Make sure the Discord desktop app is running, then — if you installed via
PyPI:

```bash
cs2-discord-rpc
```

If you installed by cloning the repo:

```bash
python cs2_discord_rpc.py
```

Once you join a match in CS2, your Discord profile will automatically show
the map, mode, and round. The status updates/clears automatically when
you're in the main menu or exit the game.

## Display language

By default, the text shown on Discord (mode names, status text like
"Warmup" or "Bomb planted") is in **English**. If you'd rather see it in
**Turkish**, set the `RPC_LANGUAGE` environment variable or the
`"language"` key in `config.json` to `tr`:

```bash
RPC_LANGUAGE=tr cs2-discord-rpc
```

or in `config.json`:
```json
{
  "discord_client_id": "YOUR_DISCORD_CLIENT_ID_HERE",
  "language": "tr"
}
```

An unrecognized value falls back to English. Only `en` and `tr` are
supported today; contributions adding more languages are welcome (see
`STRINGS` in `cs2_discord_rpc.py`).

## Autostart on Windows (at PC/login)

If you don't want to run it by hand every time, you can set up a Task
Scheduler task that starts the script in the background (no console
window) as soon as you log in to Windows:

1. First complete **step 4b) config.json** above (the script won't run
   without a saved Client ID).
2. Open PowerShell from inside this repo's folder. Task Scheduler may not
   allow creating a new task as a regular user on some Windows setups — if
   you get an "Access denied" error, reopen PowerShell **as Administrator**
   (right-click → "Run as Administrator"):
   ```powershell
   powershell -ExecutionPolicy Bypass -File windows_autostart\install_autostart.ps1
   ```
3. That's it. The script will start automatically on your next login. To
   try it right away:
   ```powershell
   Start-ScheduledTask -TaskName "CS2DiscordRPC"
   ```

To remove it:
```powershell
powershell -ExecutionPolicy Bypass -File windows_autostart\uninstall_autostart.ps1
```

> **Note:** The task triggers "at logon" (`AtLogOn`), not "at system
> startup" — because the Discord desktop app the script talks to also only
> runs within your session, not at system boot. The script automatically
> retries every few seconds even if Discord hasn't fully started yet, so
> you don't need to worry about ordering. The task is also configured to
> restart itself a few times if the script crashes.

## Map images

Discord Rich Presence has two image slots: a **large main image** and a
**small badge** in its bottom-right corner. In this script:

- The **large image** shows the map you're currently in
  (`assets/maps/<map_code>.png`).
- The **small badge** is always `assets/maps/cs2_logo.png` — a fixed CS2
  logo.
- In the main menu (not yet in a match), only the large CS2 logo is
  shown, with no small badge.

The `assets/maps/` folder contains a small PNG badge for every major map
(Dust II, Mirage, Inferno, Nuke, Overpass, Vertigo, Ancient, Anubis,
Train, Cache, Office, Italy, Agency, the Wingman maps, Aim Map) plus a
generic `cs2_logo.png`. These are currently simple icons generated for
this repo (see "Using real screenshots" below — you can easily replace
them with your own).

- The script sends the map name it gets from GSI (e.g. `de_dust2`)
  directly as the **Art Asset key** you uploaded to the Discord Developer
  Portal — see "1) Create a Discord Application" above. No external URL is
  used; this is the most reliable method with classic desktop Rich
  Presence.
- If a map comes in that we don't have an icon for (a newly released map
  or a community server map), the large image also automatically falls
  back to `cs2_logo`.
- To add a new map / regenerate the icons: edit and rerun
  `assets/generate_map_icons.py` (requires Pillow).

### Using real screenshots

We don't ship Valve's actual in-game screenshots in this repo (copyrighted
content). But using **your own** screenshots is entirely up to you and
very easy:

1. Join a match in CS2, take a screenshot with `F12` (Steam screenshot).
2. Save it as `assets/screenshots_raw/<map_code>.jpg` (e.g.
   `assets/screenshots_raw/de_mirage.jpg`; valid map codes are listed
   above).
3. Run `python assets/import_screenshots.py`.

The script automatically center-crops the image to 1024x576 (16:9) and
saves it as `assets/maps/<map_code>.png`; the new image is used
immediately, with no changes needed in `cs2_discord_rpc.py`.

## Supported modes

| GSI mode key            | Displayed name (English) | Round display    |
|--------------------------|---------------------------|-------------------|
| `competitive`            | Competitive                | Round X/24        |
| `scrimcomp5v5`           | Premier                    | Round X/24        |
| `scrimcomp2v2`           | Wingman                    | Round X/16        |
| `casual`                 | Casual                      | Round X           |
| `deathmatch`             | Deathmatch                  | Kills / deaths    |
| `gungameprogressive`     | Arms Race                   | Kills / deaths    |
| `gungametrbomb`          | Demolition                  | Round X           |
| `skirmish`               | Skirmish                    | Round X           |
| `cooperative`            | Co-op Strike                | Kills / deaths    |
| `training`               | Training                    | Kills / deaths    |
| `custom`                 | Custom Game                 | Round X           |

If a new, unlisted mode is added, the script displays "Unknown Mode"; it's
easy to extend by adding a new entry to the `MODE_INFO` dictionary (and a
label in `STRINGS`) in `cs2_discord_rpc.py`.

> **Note:** The 24 rounds for `competitive`/`scrimcomp5v5` and 16 rounds
> for `scrimcomp2v2` are based on the default matchmaking settings (MR12 /
> MR8). If this limit differs on a community server, only the current
> round number is shown.
