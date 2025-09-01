<a id="readme-top"></a>

# AniLoader

NOTE: Work in progress. Functional.

This project is a Python script with an optional web interface that automates downloading anime from AniWorld (aniworld.to) and series from SerienStream (s.to). The focus is on German dubbed versions. The script uses a **SQLite database** to track downloads and automatically detect missing German episodes. Downloaded files are renamed and organized by seasons, episodes and movies. A lightweight web interface lets you manage downloads and monitor progress.

## Contents
- Features
- Installation
- Usage (CLI)
- Web interface
- API
- Tampermonkey
- Notes
- Examples
- License

## Features
- Import anime/series URLs from a text file (`AniLoader.txt`)
- Track download status in a SQLite database (`AniLoader.db`)
- Language priority (default):
  1. German Dub
  2. German Sub
  3. English Dub
  4. English Sub
- Detect already downloaded episodes automatically
- Remove old subtitle versions except German Dub
- Clean renaming of files by season/episode/title/language
- Download full seasons and movies
- Automatic folder structure:
  - Movies → `Filme`
  - Seasons → `Staffel 1`, `Staffel 2`, …
- Modes: download all, only missing German episodes (`german`), or only new episodes (`new`)
- Web interface for controlling downloads, viewing logs and querying the database

## Installation
Clone the repo:

```
git clone https://github.com/WimWamWom/AniLoader
```

Install dependencies:

```
pip install requests beautifulsoup4 flask flask_cors aniworld
```

Create `AniLoader.txt` with one URL per line (link to the series, not to a single episode), for example:

```
https://aniworld.to/serie/naruto
https://s.to/serie/stream/the-rookie
```

## Usage (command line)
Download everything:

```
py downloader.py
```

Download only missing German episodes:

```
py downloader.py german
```

Check and download new episodes since last run:

```
py downloader.py new
```

## Web interface
Start a development server:

```
py AniLoader.py
```

Note: Flask's built-in server is for development only. For production, use a WSGI server like `waitress`:

```
pip install waitress
python -m waitress --host=0.0.0.0 --port=5050 AniLoader:app
```

The UI will be available at http://localhost:5050 by default.

## API (selected endpoints)
- /start_download — start background runner (modes: default|german|new)
- /status — current status (idle|running|finished)
- /logs — recent logs
- /config — get/set languages and min free space
- /database — query database entries
- /export — add URL from Tampermonkey
- /check — check if URL exists in database

See the German README for full examples and cURL snippets.

## Tampermonkey
The included `Tampermonkey.user.js` adds a button on AniWorld / S.to pages to send the current series URL to your AniLoader server. Update SERVER_IP in the script if your server is not running on `localhost`.

## Notes
- The script expects AniWorld / SerienStream URL structures
- Old subtitle versions (except German Dub) will be removed automatically

## Examples
Filename examples after download:

```
S01E005 - The Ninja Test [Dub].mp4
S01E006 - Clash of Blades [Sub].mp4
Film01 - Naruto Movie [Dub].mp4
```

## License
See `LICENSE` file.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
