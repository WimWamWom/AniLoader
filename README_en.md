<a id="readme-top"></a>

# AniLoader

_Currently still in development. Functional already._

**This downloader is based on the [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader/tree/next) by [phoenixthrush](https://github.com/phoenixthrush).**

This project is a Python script with an optional web interface that automates downloading anime from [AniWorld](https://aniworld.to/) and series from [SerienStream](https://s.to/). The focus is on German dub versions. The script manages a **SQLite database** where all downloaded content is stored and **missing German episodes** are automatically detected. Downloaded files are neatly renamed and organized by **seasons, episodes and movies**. The web interface provides a convenient way to manage downloads and view current progress.


## Contents
- [Function](#function)
- [Installation](#installation)
  - [1. Clone repository](#1-clone-repository)
  - [2. Install Python dependencies](#2-install-python-dependencies)
  - [3. Create download list](#3-create-download-list)
- [Usage](#usage)
  - [AniLoader as a local program](#aniloader-as-a-local-program)
    - [Download everything](#download-everything)
    - [Only missing German episodes](#only-missing-german-episodes)
    - [Check and download new episodes](#check-and-download-new-episodes)
  - [AniLoader with web interface](#aniloader-with-web-interface)
    - [Start](#start)
    - [Web Interface](#web-interface)
- [API](#api)
  - [Start Download](#start-download)
  - [Status](#status)
  - [Logs](#logs)
  - [Database entries](#database-entries-searchfiltersort)
- [Tampermonkey](#tampermonkey)
- [Notes](#notes)
  - [Good to Know](#good-to-know)
  - [Customization](#customization)
- [Examples](#examples)
- [Debugging & Troubleshooting](#debugging--troubleshooting-common-errors)
- [License](#license)



## Function

### Features
- **Import anime/series links** from a text file (`AniLoader.txt`)
- Track download status in a SQLite database (`AniLoader.db`)
- **Language priority**:
  1. German Dub
  2. German Sub
  3. English Dub
  4. English Sub
- Automatic detection of already downloaded episodes
- **Remove old subtitle versions** except German Dub
- Clean **renaming** of episodes by season, episode, title and language
- **Download seasons and movies**
- Automatic sorting of downloads:
  - Movies → `Filme`
  - Seasons → `Staffel 1`, `Staffel 2`, …
- Option to only check **missing German episodes** (`german`) or **new episodes** (`new`)
- **Web interface** to control downloads, monitor logs and query the database
  - Start buttons are disabled during a running cycle
  - Red stop button to cancel without marking as "complete"
  - Progress card with clickable series link and start time/index
  - Shows "Loaded per season … • Movies: N" based on the filesystem
  - Disk usage display with automatic unit (TB/GB/MB)
  - Smooth updates: existing values remain visible until new data arrives


## Directory structure

```
AniLoader/
├─ AniLoader.txt # List of anime URLs (one per line)
├─ AniLoader.db # SQLite database for progress and missing episodes
├─ downloader.py # Main script without web interface
├─ AniLoader.py # Main script with web interface
├─ templates/ # HTML templates for the web interface
├─ static/ # CSS/JS for the web interface
├─ README.md # README (German)
├─ README_en.md # README (English)
├─ Downloads/ # Default download folder
│ ├─ Naruto/
│ │ ├─ Filme/
│ │ │ ├─ Film01.mp4
│ │ │ └─ ...
│ │ ├─ Staffel 1/
│ │ │ ├─ S01E001 - Title.mp4
│ │ │ └─ ...
│ │ ├─ Staffel 2/
│ │ │ ├─ S02E001 - Title [Sub].mp4
│ │ │ └─ ...

```


<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Installation

### 1. Clone repository
```
git clone https://github.com/WimWamWom/AniLoader
```

### 2. **Install Python dependencies**

```
pip install requests beautifulsoup4 flask flask_cors aniworld
```


### 3. Create download list

The file `AniLoader.txt` contains the links to the anime/series, e.g.:

```
https://aniworld.to/serie/naruto
https://s.to/serie/stream/the-rookie
```
Each URL must be on its own line and should point to the series page, not a specific episode.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

### `downloader.py` (CLI — no web interface)

`downloader.py` is the lightweight CLI-only variant without the web server. It provides the same core functionality as `AniLoader.py` for managing downloads, maintaining the SQLite database, and detecting missing German episodes.

Invocation:

```
py downloader.py [mode]
```

Available modes (argument `mode`):

- `default` (no argument):
  - Full run: checks movies and seasons, downloads missing episodes/movies using the configured language priority, and marks series as complete when no further seasons are found.
  - Updates `last_film`, `last_season`, `last_episode` in the DB and sets `complete=True` when a series is finished.

- `german`:
  - Attempts to download only German Dub versions for entries listed in `fehlende_deutsch_folgen`.
  - When a German version is found, the URL is removed from `fehlende_deutsch_folgen`.

- `new`:
  - Checks each series for new movies or seasons starting from the stored `last_*` values and downloads any new content.

- `check-missing`:
  - Re-checks for missing files: first retries URLs stored in `fehlende_deutsch_folgen` (German-only), then scans the filesystem up to the recorded `last_film` / `last_season` / `last_episode` values and attempts to re-download missing files.

Important configuration points:

- `AniLoader.txt`: series URLs (one URL per line) — imported on start and cleared afterwards.
- `config.json` (auto-created if missing):
  - `languages`: list of languages to try in order (default: `["German Dub","German Sub","English Dub","English Sub"]`).
  - `min_free_gb`: minimum free disk space (in GB) below which downloads are aborted (default: `2.0`).

Examples:

```
py downloader.py
py downloader.py german
py downloader.py new
py downloader.py check-missing
```

Notes:

- The CLI calls the external `aniworld` tool. Ensure `aniworld` is available in your PATH.
- `Downloads/` is created automatically if it doesn't exist.
- `check-missing` can trigger many download attempts for large libraries; adjust `min_free_gb` as needed.


## AniLoader with Web Interface


### Start

### As a local "test" server
Start the program with
```
py AniLoader.py
```
**Warning:**
The built-in Flask server is intended for development and testing only. It is not suitable for production use because it lacks security hardening and may be unstable under load.

### Start with a WSGI server (recommended)

For production use, run AniLoader with a WSGI server like `waitress` (recommended for Windows):

1. Install waitress:
  ```
  pip install waitress
  ```
2. Start AniLoader with waitress:
  ```
  python -m waitress --host=0.0.0.0 --port=5050 AniLoader:app
  ```
  (The `:app` refers to the Flask app object in `AniLoader.py`)

## Web Interface

### Access
The web interface is available at [http://localhost:5050](http://localhost:5050).

See the Debugging & Troubleshooting section for security and remote access notes.

##### Features
- Start and follow downloads
- Monitor logs in real time
- View, filter and sort database entries
- Endpoint for Tampermonkey script

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## API 

### Start Download
URL: /start_download  
Method: GET or POST  
Query / JSON: mode = default | german | new  
Description: starts the background runner in one of the modes. The endpoint starts the background thread function run_mode(mode).  

#### GET, Default mode:
```
curl "http://localhost:5050/start_download"
```

#### GET, German mode:
```
curl "http://localhost:5050/start_download?mode=german"
```
#### GET, Check for new episodes:
```
curl "http://localhost:5050/start_download?mode=new"
```
Checks for new movies, seasons or episodes for completed anime

#### GET, Check for missing episodes:
```
curl "http://localhost:5050/start_download?mode=check-missing"
```
Checks started anime for missing episodes and downloads them.

### Status

URL: /status  
Method: GET  
Description: returns the current status (idle | running | finished | no-space), current mode, index/title of the series, start time.  

#### Call
```
curl http://localhost:5050/status
```

#### Output
```
{"status":"running","mode":"new","current_index":1,"current_title":"Naruto","started_at":1600000000.0}
```



### Logs
### Disk

URL: /disk  
Method: GET  
Description: free disk space as a number in GB (frontend displays TB/GB/MB).  
```
{"free_gb": 512.34}
```

### Config

URL: /config  
Method: GET | POST  
Description: gets/sets language order and minimum free space.  

GET
```
curl http://localhost:5050/config
```
Response
```
{"languages":["German Dub","German Sub","English Dub","English Sub"],"min_free_gb":128}
```

POST
```
curl -X POST http://localhost:5050/config -H "Content-Type: application/json" -d '{"languages":["German Dub","German Sub"],"min_free_gb":256}'
```

URL: /logs  
Method: GET  
Description: returns the in-memory log lines as a JSON array (last MAX_LOG_LINES).  
```
curl http://localhost:5050/logs
```
<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Database entries (Search/Filter/Sort)
URL: `/database`  
Method: GET  
Query parameters:
- q = search term (matches title or url)
- complete = 0 or 1 (filter)
- deleted = 0 or 1 (filter)
- sort_by = id | title | last_film | last_episode | last_season
- order = asc | desc
- limit = number
- offset = number

#### Example call 
```
curl "http://localhost:5050/database?q=naruto&complete=0&sort_by=title&order=asc&limit=50"
```
#### Response
```
{id,title,url,complete,deutsch_komplett,fehlende,last_film,last_episode,last_season}
```

### Counts (Season / Movie counts)

URL: /counts  
Method: GET  
Description: counts episodes and movies per season from the filesystem.  
Parameters: `id` (DB id) or `title` (series folder under Downloads).  

Example
```
curl "http://localhost:5050/counts?id=42"
```
Response
```
{"per_season":{"1":12,"2":12},"total_seasons":2,"total_episodes":24,"films":1,"title":"Naruto"}
```

### Export

URL: /export  
Method: POST  
Description: adds a URL to the database (for Tampermonkey).  
Body: `{ "url": "https://…" }`

### Check

URL: /check  
Method: GET  
Description: checks whether a URL already exists (and is not deleted).  
Query: `url=https://…`
<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Tampermonkey
[User Script](https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js) (JavaScript) adds a button to AniWorld / S.to.  
Change the SERVER_IP in the Tampermonkey script if your server is not `localhost`.
--> If your Flask runs on a different machine, set SERVER_IP to its `IP address` (e.g.: 123.45.67): 
```
const SERVER_IP = "localhost";
or
const SERVER_IP = "123.45.67";
```
Behavior:
- On load the script calls /check?url=… → if present, the button is green and disabled.
- Clicking the button sends POST /export with JSON {url}.
<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Notes
### Good to Know
- The URL structure must match AniWorld or SerienStream formats
- Old subtitle versions (except German Dub) are automatically removed
- Missing streams or language issues show warnings

### Customization

The most important configuration options are at the top of `AniLoader.py`:
- `DOWNLOAD_DIR`: folder for downloads
- `DOWNLOAD_TXT`: path to the download text file
- `LANGUAGES`: order and languages to try when downloading
- `DB_PATH`: location of the SQLite database
- 
<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Examples

### Filename after download


```
S01E005 - Der Ninja-Test [Dub].mp4
S01E006 - Kampf der Klingen [Sub].mp4
Film01 - Naruto Movie [Dub].mp4
```

### Example input links (`AniLoader.txt`)
```
https://aniworld.to/anime/stream/a-certain-magical-index
https://s.to/serie/stream/family-guy
https://aniworld.to/anime/stream/classroom-of-the-elite
https://aniworld.to/anime/stream/highschool-dxd
https://s.to/serie/stream/die-schluempfe
https://s.to/serie/stream/die-abenteuer-des-jungen-marco-polo
```


### Example SQLite database (`AniLoader.db`)
- automatically created, contains per anime:
  - title
  - url
  - complete
  - deutsch_komplett
  - fehlende_deutsch_folgen (JSON array)
  - last_film (Integer)
  - last_episode (Integer)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Debugging & Troubleshooting (common errors)

### No download starts / aniworld: command not found
aniworld not installed or not in PATH. Install it or adjust run_download.

### AniLoader.txt is not read
Ensure `AniLoader.txt` is in the same folder as `AniLoader.py`. On start the database is updated.

### No logs in UI
/logs returns log lines as JSON. Check with `curl http://localhost:5050/logs`. The UI must display these.

### Server restarts on page reload
The script runs as a normal Flask process. If you start in developer mode (debug=True), the reloader can restart threads. In the code debug=False is used — that's good. Threads do not automatically survive page reloads, but here the server is persistent.

### Database inconsistencies
You can open the SQLite file `AniLoader.db` with `sqlite3 AniLoader.db`. Make a backup before making changes.

### Remote access / firewall
By default host="0.0.0.0" means reachable from the outside. Set firewall/router port forwarding as needed. Warning: insecure if publicly exposed — see the security notes.


<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

This project is licensed under the [MIT License](https://github.com/WimWamWom/AniLoader/blob/main/LICENSE).  
More information is in the LICENSE file.
