# AniLoader

Currently under development but functional.

This downloader is based on the AniWorld-Downloader by phoenixthrush: https://github.com/phoenixthrush/AniWorld-Downloader

AniLoader is a Python script (optionally with a web UI) that automates downloading anime from AniWorld (aniworld.to) and series from SerienStream (s.to). The focus is on German dub versions. The script uses a SQLite database to track downloads and automatically detects missing German episodes. Downloaded files are renamed and organized by seasons, episodes and movies into a clear folder hierarchy. The web UI provides a convenient way to manage downloads and view progress.

## Contents
- Functionality
- Installation
  - 1. Clone repository
  - 2. Install Python dependencies
  - 3. Create download list
- Usage
  - AniLoader as a local program
  - AniLoader with web interface
- API
- Tampermonkey
- Notes
- Examples
- Debugging & Troubleshooting
- License

## Functionality

### Features
- Import anime/series links from a text file (`AniLoader.txt`)
- Track download status in a SQLite database (`AniLoader.db`)
- Language priority order:
  1. German Dub
  2. German Sub
  3. English Dub
  4. English Sub
- Automatic detection of already downloaded episodes
- Removes old subtitle versions except German Dub
- Clean renaming of episodes by season, episode, title and language
- Downloads seasons and movies
- Automatic sorting into folders:
  - Movies → `Filme` (or `Movies`)
  - Seasons → `Staffel 1`, `Staffel 2`, …
- Option to only check missing German episodes (`german`) or new episodes (`new`)
- Web interface to control downloads, view logs and query the database

## Directory structure

```
AniLoader/
├─ AniLoader.txt # List of anime URLs (one per line)
├─ AniLoader.db # SQLite database for progress and missing episodes
├─ downloader.py # Main script without web interface
├─ AniLoader.py # Main script with web interface
├─ templates/ # HTML templates for the web UI
├─ static/ # CSS/JS for the web UI
├─ README.md # README (German)
├─ README_en.md # README (English)
├─ Downloads/ # Default download folder
```

## Installation

### 1. Clone repository

```
git clone https://github.com/WimWamWom/AniLoader
```

### 2. Install Python dependencies

```
pip install requests beautifulsoup4 flask flask_cors aniworld
```

### 3. Create download list

Add one URL per line to `AniLoader.txt`, e.g.:

```
https://aniworld.to/serie/naruto
https://s.to/serie/stream/the-rookie
```

Each URL should point to the series page, not a single episode.

## Usage

### AniLoader as a local program

Download everything (movies and seasons):

```
py downloader.py
```

Only download missing German episodes:

```
py downloader.py german
```

Check for new episodes and download them:

```
py downloader.py new
```

### AniLoader with web interface

Start the local test server (development only):

```
py AniLoader.py
```

For production, use a WSGI server like `waitress` (recommended on Windows):

```
pip install waitress
python -m waitress --host=0.0.0.0 --port=5050 AniLoader:app
```

Open the web UI at http://localhost:5050

## API (summary)

/ start_download — start background download runner (mode: default | german | new)
/ status — current status (idle | running | finished | no-space)
/ logs — recent in-memory log lines
/ disk — free disk space in GB
/ config — GET/POST languages and minimum free space
/ database — query DB entries (filters: q, complete, deleted, sort_by, order, limit, offset)
/ counts — count episodes and movies per season from filesystem
/ export — add URL to database (used by Tampermonkey)
/ check — verify if a URL already exists in the DB

## Tampermonkey

The repository includes a Tampermonkey user script `Tampermonkey.user.js` that adds a button to AniWorld / S.to pages. Update the SERVER_IP in the script if your server isn't running on `localhost`.

## Notes

Key configuration options are at the top of `AniLoader.py`:
- DOWNLOAD_DIR
- DOWNLOAD_TXT
- LANGUAGES
- DB_PATH

## Examples

Filename examples after download:

```
S01E005 - The Ninja Test [Dub].mp4
S01E006 - Blade Fight [Sub].mp4
Film01 - Naruto Movie [Dub].mp4
```

## License

See the `LICENSE` file in the repository.
