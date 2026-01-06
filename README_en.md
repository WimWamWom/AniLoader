<a id="readme-top"></a>

[German README](README.md) — deutsche Version

# <img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png" width="32" align="center"> AniLoader

<ins><strong>In development, already usable</strong></ins><br/>
This downloader is based on <a href="https://github.com/phoenixthrush/AniWorld-Downloader" target="_blank" rel="noreferrer">AniWorld-Downloader</a> by <a href="https://github.com/phoenixthrush" target="_blank" rel="noreferrer">phoenixthrush</a> and uses its CLI <code>aniworld</code> for the actual downloads.

AniLoader is a Python tool with an optional web interface to automatically download anime from <a href="https://aniworld.to/" target="_blank" rel="noreferrer">AniWorld</a> and series from <a href="https://s.to/" target="_blank" rel="noreferrer">SerienStream (s.to)</a>. It focuses on German versions (German Dub). A SQLite database tracks progress, detects missing German episodes, and prevents duplicates. Files are renamed and sorted into a clean folder structure.

## Contents

- [Function](#function)
- [Installation](#installation)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Clone repository](#2-clone-repository)
  - [3. Install dependencies](#3-install-dependencies)
  - [4. Create download list](#4-create-download-list)
- [Usage](#usage)
  - [CLI (no web interface)](#cli-no-web-interface)
  - [Web interface (Flask/Waitress)](#web-interface-flaskwaitress)
  - [Directory structure](#directory-structure)
- [Configuration](#configuration)
- [Web-UI Features](#web-ui-features)
- [Unraid Integration & Automation](#unraid-integration--automation)
- [Log System](#log-system)
- [API](#api)
  - [Start Download](#start-download)
  - [Status](#status)
  - [Logs](#logs)
  - [Last Run](#last-run)
  - [Disk](#disk)
  - [Config](#config)
  - [Database](#database)
  - [Counts](#counts)
  - [Export](#export)
  - [Check](#check)
  - [Queue](#queue)
- [Tampermonkey](#tampermonkey)
- [Notes](#notes)
- [Examples](#examples)
- [Debugging & Troubleshooting](#debugging--troubleshooting)
- [License](#license)

## Function

### Features
- Import series links from <code>AniLoader.txt</code>
- Track progress in SQLite (loaded seasons/episodes/movies, missing German episodes, “complete”, etc.)
- Language priority (configurable):
  1. German Dub
  2. German Sub
  3. English Dub
  4. English Sub
- Skips already downloaded episodes
- Deletes older non-dub versions once German Dub is available
- Renames files like <code>S01E023 - Title [English Sub].mp4</code> or <code>Film01 - Title.mp4</code>
- Folder layout: <code>Downloads/Series/Staffel N/*.mp4</code> and <code>Downloads/Series/Filme/*.mp4</code>
- Modes: full run, check only new content, German-only catch-up, and check-missing
- Web UI: progress, logs, DB view, disk space, queue (“Next”)

## Installation

### 1. Prerequisites
- Python 3.9 or newer (tested with 3.13)
- OS: Windows, Linux, or macOS (Windows shown with Waitress)

### 2. Clone repository
```bash
git clone https://github.com/WimWamWom/AniLoader
```

### 3. Install dependencies
Install everything in one command:
```bash
pip install requests beautifulsoup4 flask flask_cors aniworld waitress
```

Optional (to use Cloudflare DNS 1.1.1.1 for title lookups):
```bash
pip install dnspython
```

Verify that the downloader CLI is present:
```bash
aniworld --help
```

### 4. Create download list
Create <code>AniLoader.txt</code> in the project folder. Put exactly one series base URL per line (not an episode URL), for example:

```
https://aniworld.to/anime/stream/naruto
https://s.to/serie/stream/the-rookie
```

## Usage

### CLI (no web interface)
CLI script: <code>downloader.py</code>

```bash
py downloader.py [mode]
```

Modes:
- <code>default</code>: full run across movies and seasons; loads content according to language priority; may mark complete
- <code>german</code>: retries entries from “fehlende_deutsch_folgen” in German Dub only
- <code>new</code>: checks for new movies/seasons/episodes starting from stored <code>last_*</code> values
- <code>check-missing</code>: attempts to re-download missing files using DB and filesystem info
- <code>full-check</code>: exhaustive check from the beginning (movies from 1, seasons from 1/episode 1) for all series; existing files are skipped

Examples:
```bash
py downloader.py
py downloader.py german
py downloader.py new
py downloader.py check-missing
py downloader.py full-check
```

Notes:
- <code>Downloads/</code> is created automatically
- Minimum free space is configurable (default 2 GB); below that the run stops
- <code>aniworld</code> must be on PATH

### Web interface (Flask/Waitress)

- Development (local):
```bash
py AniLoader.py
```

- Production on Windows (recommended):
```bash
python -m waitress --host=0.0.0.0 --port=5050 AniLoader:app
```

Open: http://localhost:5050

### Directory structure

```
AniLoader/
├─ AniLoader.py             # Web server + logic
├─ downloader.py            # CLI variant (no web server)
├─ AniLoader.txt            # Import list of series URLs
├─ data/
│  ├─ AniLoader.db         # SQLite database
│  └─ config.json          # Config (languages, min_free_gb, download_path, port, autostart_mode)
├─ Downloads/
│  └─ <Series>/Filme/ and Staffel 1/, Staffel 2/, ...
├─ templates/
├─ static/
└─ README_en.md
```

## Configuration

The configuration file is located at <code>data/config.json</code>. Missing keys are added automatically on startup and the file is written with pretty formatting.

Important keys:
- <code>languages</code>: order of languages to attempt (default: German Dub → German Sub → English Dub → English Sub)
- <code>min_free_gb</code>: minimum free disk space in GB; below this threshold downloads stop (default: 2.0)
- <code>download_path</code>: destination root folder for all downloads (default: <code>./Downloads</code>); created automatically if missing
- <code>port</code>: web server port (configurable only via file; no effect in CLI-only runs)
- <code>autostart_mode</code>: optional autostart mode for the web interface (<code>default</code>|<code>german</code>|<code>new</code>|<code>check-missing</code>|<code>full-check</code>)
- <code>refresh_titles</code>: refresh series titles on startup (default: <code>true</code>). Applies to both the web interface and <code>downloader.py</code>.

Notes:
- For the CLI (<code>downloader.py</code>) only <code>download_path</code> is used; <code>port</code> has no effect.
- On the first run, <code>download_path</code> is set if missing and the folder is created.

### DNS for title lookups (optional)
- AniLoader can resolve only the HTML title lookups (<code>get_series_title</code>/<code>get_episode_title</code>) via Cloudflare DNS <code>1.1.1.1</code>.
- This is enabled when <code>dnspython</code> is installed. If not installed, it gracefully falls back to your system DNS (no errors).
- No system- or router-level settings are changed. The DNS override applies only to these lookups and keeps TLS/SNI intact (connections still use the hostname).

Enable optionally:
```bash
pip install dnspython
```
Note: If you want absolutely everything (including the external <code>aniworld</code> CLI) to use 1.1.1.1, change DNS globally on your OS/router.

## Web-UI Features
- Start buttons for all modes (including “Full Check”); disabled while a run is active
- Status indicator incl. out-of-space (unit auto TB/GB/MB)
- Live logs with filter and copy
  - **Log view toggle**: Radio buttons to switch between "All Logs" (since server start) and "Last Run" (current run only)
- Database tab: filter/sort, list of missing German URLs, "Next" button (Queue)
- Queue table with clear/remove entries
- Settings: set download storage path directly or use the convenient "Choose folder…" button (native file chooser); port is configurable only via <code>config.json</code>
  - Toggle: "Refresh titles on startup"

## Unraid Integration & Automation

AniLoader can run fully automated on Unraid servers and notify you via Discord about new episodes.

### User Scripts Setup

**Prerequisite:** Install Unraid plugin "User Scripts"

Two ready-to-use Bash scripts are included in the repository:

#### check-german.sh
Checks **weekly** for new German dubs of existing episodes.

**Recommended schedule:** Sundays 5:00 AM
```
0 5 * * 0
```

#### check-new.sh
Checks **daily** for completely new episodes across all tracked series.

**Recommended schedule:** Daily 6:00 AM
```
0 6 * * *
```

### Script Features

- **API Integration**: Communicates with your AniLoader server via REST API
- **Basic Auth**: Supports password-protected domains
- **Wait Logic**: Waits up to 120 minutes if another job is still running (prevents conflicts)
- **Discord Webhooks**: Automatic notifications with all found episodes
- **Multi-Embed Support**: Automatically splits long lists into multiple Discord embeds (2048 character limit)
- **Multiple Webhooks**: Send notifications simultaneously to multiple Discord channels
- **Smart Filtering**: Only notifies when new episodes are actually found

### Discord Webhooks

#### Creating a Webhook
1. Discord Server → Server Settings → Integrations
2. "Create Webhook" → Select channel
3. Copy webhook URL

**Note:** Webhooks only work on Discord servers, not in group chats or DMs!

#### Configuration in Scripts

Both scripts have a configuration section at the top:

```bash
# API Endpoint
API_ENDPOINT="https://your-domain.example.com"
API_AUTH="username:password"

# Discord Webhooks (multiple possible)
DISCORD_WEBHOOK_URLS=(
    "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
    "https://discord.com/api/webhooks/SECOND_WEBHOOK_URL"  # Optional
)
```

#### Discord Embed Colors

The scripts use color codes for Discord embeds:
- `3066993` = Green (Success)
- `15158332` = Red (Error)
- `3447003` = Blue (Info)

### Schedule & Cron

**Cron Format:** `Minute Hour Day Month Weekday`

```
┌─── Minute (0-59)
│ ┌─── Hour (0-23)
│ │ ┌─── Day of Month (1-31)
│ │ │ ┌─── Month (1-12)
│ │ │ │ ┌─── Day of Week (0-7, 0&7=Sunday)
│ │ │ │ │
* * * * *
```

**Examples:**
- `0 6 * * *` = Daily at 6:00 AM
- `0 5 * * 0` = Every Sunday at 5:00 AM
- `*/30 * * * *` = Every 30 minutes
- `0 8,20 * * *` = Daily at 8:00 AM and 8:00 PM
- `0 12 * * 1-5` = Monday to Friday at 12:00 PM

**Why 1 hour gap?**
The German check runs Sundays at 5:00 AM, the New check runs daily at 6:00 AM. This allows the German check to finish before the New check starts. The wait logic ensures that overlaps are handled gracefully (waits up to 2 hours).

### Customizing Scripts for Your Environment

1. **API_ENDPOINT**: Your AniLoader domain or IP
2. **API_AUTH**: If Basic Auth is enabled, format `"username:password"`
3. **DISCORD_WEBHOOK_URLS**: One or more webhook URLs

Example:
```bash
API_ENDPOINT="https://aniloader.mydomain.com"
API_AUTH="admin:myPassword123"
DISCORD_WEBHOOK_URLS=(
    "https://discord.com/api/webhooks/123456789/abcdefghijk"
    "https://discord.com/api/webhooks/987654321/zyxwvutsrqp"
)
```

**Important:** The scripts use the `/last_run` endpoint, which is only available in newer AniLoader versions. Make sure your server is updated!

## Log System

AniLoader uses a two-tier file-based logging system.

### File-based Logs

**Advantages:**
- No RAM consumption during long server uptime
- Logs survive server restarts
- Perfect for automated scripts

#### all_logs.txt
- Location: `data/all_logs.txt`
- Content: **Complete log history** since installation
- Continuously appended (no automatic deletion)
- API Endpoint: `/logs`

#### last_run.txt
- Location: `data/last_run.txt`
- Content: **Only the last run**
- Cleared and rewritten on each new run
- API Endpoint: `/last_run`
- Ideal for scripts: Prevents duplicates when counting episodes

### Web-UI Log View

In the web interface, you can switch between both log sources:

- **"All Logs"**: Shows `all_logs.txt` (complete history)
- **"Last Run"**: Shows `last_run.txt` (current run only)

Switching happens live without page reload via radio buttons above the log display.

### For Script Developers

**Important:** Always use `/last_run` instead of `/logs` when counting episodes!

```bash
# ❌ WRONG - counts historical logs multiple times
LOG_CONTENT=$(curl -s "http://localhost:5050/logs")

# ✅ CORRECT - only the current run
LOG_CONTENT=$(curl -s "http://localhost:5050/last_run")
```

## API

Base URL: <code>http://localhost:5050</code>

### Start Download
- URL: <code>/start_download</code>
- Method: GET or POST
- Param: <code>mode</code> = <code>default</code> | <code>german</code> | <code>new</code> | <code>check-missing</code> | <code>full-check</code>
- Response: <code>{"status":"started","mode":"..."}</code> or <code>409 already_running</code>

Examples:
```bash
curl "http://localhost:5050/start_download"
curl "http://localhost:5050/start_download?mode=german"
curl "http://localhost:5050/start_download?mode=new"
curl "http://localhost:5050/start_download?mode=check-missing"
```

### Status
- URL: <code>/status</code>
- Method: GET
- Returns: <code>status</code> (idle|running|finished|kein-speicher), <code>mode</code>, <code>current_index</code>, <code>current_title</code>, <code>started_at</code>, and during a run <code>current_season</code>/<code>current_episode</code>/<code>current_is_film</code>

Example:
```json
{"status":"running","mode":"new","current_index":1,"current_title":"Naruto","started_at":1725300000.0}
```

### Logs
- URL: <code>/logs</code>
- Method: GET
- Returns **all logs since server start** from `all_logs.txt` as JSON array
- Use this endpoint for the complete history in the Web-UI

Example:
```json
[
  "[2026-01-06 10:30:15] [INFO] Server started",
  "[2026-01-06 10:31:20] [SUCCESS] Naruto: Episode 5 downloaded",
  "[2026-01-06 11:45:00] [GERMAN] One Piece: Episode 10 now available in German"
]
```

### Last Run
- URL: <code>/last_run</code>
- Method: GET
- Returns **only logs from the last run** from `last_run.txt` as JSON array
- Ideal for automated scripts: Prevents duplicates when counting episodes
- Cleared on each new run

**Important for scripts:** Always use `/last_run` instead of `/logs` when counting new episodes!

Example:
```json
[
  "[2026-01-06 12:00:00] [INFO] Starting New-Check...",
  "[2026-01-06 12:05:30] [SUCCESS] Demon Slayer: Episode 23 downloaded",
  "[2026-01-06 12:10:15] [INFO] Run completed"
]
```

### Disk
- URL: <code>/disk</code>
- Method: GET
- Returns: free space in GB, e.g. <code>{"free_gb": 512.3}</code>

### Config
- URL: <code>/config</code>
- Methods: GET | POST
- GET example:
```json
{"languages":["German Dub","German Sub","English Dub","English Sub"],"min_free_gb":2.0,"download_path":"C:\\Path\\to\\Downloads","port":5050,"autostart_mode":null}
```
- POST body example:
```json
{"download_path":"D:\\Media\\Anime"}
```
Notes:
- <code>download_path</code> can be changed via POST; the folder is created if needed.
- <code>port</code> is only configurable via the file <code>data/config.json</code> and is picked up on server start.

### Database
- URL: <code>/database</code>
- Method: GET
- Params: <code>q</code>, <code>complete</code> (0|1), <code>deleted</code> (0|1), <code>deutsch</code> (0|1), <code>sort_by</code> (id|title|last_film|last_episode|last_season), <code>order</code> (asc|desc), <code>limit</code>, <code>offset</code>

### Counts
- URL: <code>/counts</code>
- Method: GET
- Params: <code>id</code> (DB ID) or <code>title</code> (series folder)
- Response: <code>{ per_season: {"1":12,...}, total_seasons, total_episodes, films, title }</code>

### Export
- URL: <code>/export</code>
- Method: POST
- Body: <code>{ "url": "https://..." }</code>

### Check
- URL: <code>/check</code>
- Method: GET
- Param: <code>url</code>
- Checks if URL exists in DB (and not deleted)

### Queue
- URL: <code>/queue</code>
- Methods:
  - GET: returns queue entries
  - POST: <code>{"anime_id": 42}</code> → enqueue series
  - DELETE: clear all, or with <code>?id=QID</code> / <code>?anime_id=AID</code> remove specific

## Tampermonkey
User script: https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js

Config in the script:
```js
const SERVER_IP = "localhost"; // set to your AniLoader server host/IP if not local
```

Behavior:
- On load, checks DB/status and adjusts button state
- If not present, adds entry via <code>POST /export</code>
- Starts <code>/start_download</code> if no run is active
- Disables button if already present or currently downloading

## Notes
- Windows MAX_PATH is considered; very long titles are shortened automatically
- When German Dub is found, older sub/English versions for the same episode are removed
- Deleted series (folder removed) are tracked and can be reactivated by exporting the same URL again
- Autostart mode can be set via <code>/config</code> (<code>default</code>|<code>german</code>|<code>new</code>|<code>check-missing</code>)

## Examples

Filenames after download:
```
S01E005 - The Ninja Test.mp4
S01E006 - Clash of Blades [Sub].mp4
Film01 - Naruto Movie.mp4
```

Example <code>AniLoader.txt</code> entries:
```
https://aniworld.to/anime/stream/a-certain-magical-index
https://s.to/serie/stream/family-guy
```

## Debugging & Troubleshooting
- “aniworld: command not found”: the CLI is missing or not on PATH
- No logs in UI: open <code>/logs</code> in the browser
- “kein-speicher”: check <code>/disk</code> and adjust <code>min_free_gb</code> via <code>/config</code>
- Remote access: with <code>host=0.0.0.0</code> the server is reachable from outside; use a WSGI server (Waitress) and secure it behind a proxy/auth if exposing it

## License

MIT License (see LICENSE). Third-party copyrights remain with their authors.

<p align="right">(<a href="#readme-top">Back to top</a>)</p>
