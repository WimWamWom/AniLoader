import os
import subprocess
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import sqlite3
import json
import sys
import shutil
import threading
from flask import Flask, render_template_string, jsonify, request

# -------------------- Konfiguration --------------------
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "Download.txt"
DOWNLOAD_DIR = BASE_DIR / "Downloads"
DB_PATH = BASE_DIR / "download.db"
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]

# -------------------- Logging-System --------------------
log_buffer = []
log_lock = threading.Lock()

def log(msg):
    ts = time.strftime("[%H:%M:%S]")
    line = f"{ts} {msg}"
    with log_lock:
        log_buffer.append(line)
        if len(log_buffer) > 1500:
            # größerer Puffer, aber gedeckelt
            del log_buffer[:500]
    print(line)

# -------------------- Webserver --------------------
app = Flask(__name__)

DASHBOARD_HTML = """
<!doctype html>
<html lang="de" data-bs-theme="dark">
<head>
  <meta charset="utf-8">
  <title>Anime Downloader • Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link
    href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
    rel="stylesheet"
    integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH"
    crossorigin="anonymous">
  <style>
    body { background:#0b0e13; }
    .card { border-radius: 1rem; }
    .badge-lang { font-size: .75rem; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
    .log-box {
        background:#000;
        color:#ddd;
        border-radius:.75rem;
        padding:1rem;
        max-height:70vh;
        overflow:auto;
        white-space:pre-wrap;
        border:1px solid #222;
    }
    .sticky-toolbar { position: sticky; top: 0; z-index: 100; background: rgba(11,14,19,.85); backdrop-filter: blur(6px); }
    .progress { height: .5rem; }
    summary { cursor: pointer; }
    .filename { word-break: break-all; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg border-bottom sticky-toolbar">
  <div class="container-fluid">
    <span class="navbar-brand">Anime Downloader</span>
    <div class="ms-auto d-flex gap-2">
      <span id="lastUpdated" class="text-secondary small"></span>
      <button id="refreshBtn" class="btn btn-sm btn-outline-light">Jetzt aktualisieren</button>
    </div>
  </div>
</nav>

<div class="container py-3">
  <ul class="nav nav-tabs" id="tabs" role="tablist">
    <li class="nav-item" role="presentation">
      <button class="nav-link active" id="overview-tab" data-bs-toggle="tab" data-bs-target="#overview" type="button" role="tab">Übersicht</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="log-tab" data-bs-toggle="tab" data-bs-target="#logs" type="button" role="tab">Live-Log</button>
    </li>
  </ul>

  <div class="tab-content pt-3">
    <div class="tab-pane fade show active" id="overview" role="tabpanel" aria-labelledby="overview-tab">
      <div id="overviewContainer" class="row g-3">
        <!-- Cards werden via JS gefüllt -->
      </div>
    </div>

    <div class="tab-pane fade" id="logs" role="tabpanel" aria-labelledby="log-tab">
      <div class="d-flex align-items-center gap-2 mb-2">
        <input id="logFilter" class="form-control form-control-sm" placeholder="Log filtern (Regex, z.B. SUCCESS|FEHLER)">
        <button id="clearFilter" class="btn btn-sm btn-outline-secondary">Filter löschen</button>
      </div>
      <div id="logBox" class="log-box mono"></div>
    </div>
  </div>
</div>

<script>
  const overviewEl = document.getElementById('overviewContainer');
  const logBox = document.getElementById('logBox');
  const lastUpdated = document.getElementById('lastUpdated');
  const refreshBtn = document.getElementById('refreshBtn');
  const logFilter = document.getElementById('logFilter');
  const clearFilter = document.getElementById('clearFilter');

  function fmt(n) { return new Intl.NumberFormat('de-DE').format(n); }

  function renderOverview(data){
    overviewEl.innerHTML = '';
    if(!data || !Array.isArray(data.items)) return;

    data.items.forEach(item => {
      const progressKnown = item.estimated_total_episodes && item.estimated_total_episodes > 0;
      const progressEpisodes = Math.min(item.count_episodes, item.estimated_total_episodes || item.count_episodes);
      const pct = progressKnown ? Math.round((progressEpisodes / item.estimated_total_episodes) * 100) : 0;

      const filesList = (arr) => {
        if (!arr || arr.length === 0) return '<span class="text-secondary">Keine Dateien gefunden</span>';
        const items = arr.map(fn => `<li class="list-group-item d-flex gap-2 align-items-start py-1"><span class="badge text-bg-secondary">mp4</span><span class="filename">${fn}</span></li>`).join('');
        return `<ul class="list-group list-group-flush">${items}</ul>`;
      };

      const card = document.createElement('div');
      card.className = 'col-12';
      card.innerHTML = `
        <div class="card">
          <div class="card-body">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
              <div>
                <h5 class="card-title mb-0">${item.title || '(kein Titel)'}</h5>
                <div class="small text-secondary">ID: ${item.id} • URL: ${item.url || '-'}</div>
              </div>
              <div class="d-flex align-items-center gap-2">
                ${item.complete ? '<span class="badge text-bg-success">Komplett</span>' : '<span class="badge text-bg-warning">Läuft</span>'}
                ${item.deutsch_komplett ? '<span class="badge text-bg-primary">Deutsch komplett</span>' : '<span class="badge text-bg-secondary">Deutsch unvollständig</span>'}
              </div>
            </div>

            <div class="mt-3">
              <div class="d-flex justify-content-between small">
                <span>Episoden: <strong>${fmt(item.count_episodes)}</strong>${progressKnown ? ` / ${fmt(item.estimated_total_episodes)}` : ''}</span>
                <span>Filme: <strong>${fmt(item.count_films)}</strong></span>
              </div>
              <div class="progress mt-1">
                ${progressKnown
                  ? `<div class="progress-bar" role="progressbar" style="width:${pct}%;" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"></div>`
                  : `<div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width:100%;"></div>`
                }
              </div>
            </div>

            <div class="row g-3 mt-3">
              <div class="col-12 col-lg-6">
                <details>
                  <summary class="mb-2">Episoden-Dateien anzeigen (${fmt(item.episodes.length)})</summary>
                  ${filesList(item.episodes)}
                </details>
              </div>
              <div class="col-12 col-lg-6">
                <details>
                  <summary class="mb-2">Film-Dateien anzeigen (${fmt(item.films.length)})</summary>
                  ${filesList(item.films)}
                </details>
              </div>
            </div>

            <div class="mt-3 small text-secondary">
              Zuletzt bekannt: Staffel ${item.last_season || 0}, Episode ${item.last_episode || 0}, Film ${item.last_film || 0}
            </div>
          </div>
        </div>
      `;
      overviewEl.appendChild(card);
    });
  }

  async function fetchOverview(){
    try{
      const res = await fetch('/api/state');
      const data = await res.json();
      renderOverview(data);
      const dt = new Date();
      lastUpdated.textContent = 'Stand: ' + dt.toLocaleTimeString('de-DE');
    }catch(e){
      console.error(e);
    }
  }

  async function fetchLogs(){
    try{
      const res = await fetch('/logs');
      let txt = await res.text();
      const filterVal = logFilter.value.trim();
      if(filterVal){
        try{
          const rx = new RegExp(filterVal, 'i');
          txt = txt.split('\\n').filter(line => rx.test(line)).join('\\n');
        }catch(e){}
      }
      const shouldStick = (logBox.scrollTop + logBox.clientHeight) >= (logBox.scrollHeight - 20);
      logBox.textContent = txt;
      if(shouldStick){ logBox.scrollTop = logBox.scrollHeight; }
    }catch(e){
      // ignore
    }
  }

  refreshBtn.addEventListener('click', fetchOverview);
  clearFilter.addEventListener('click', ()=>{ logFilter.value=''; });

  fetchOverview();
  fetchLogs();
  setInterval(fetchOverview, 2000);
  setInterval(fetchLogs, 1000);
</script>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz"
        crossorigin="anonymous"></script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route("/logs")
def http_logs():
    with log_lock:
        return "\n".join(log_buffer), 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/state")
def api_state():
    # Liefert strukturierte Übersicht pro Anime
    items = []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, title, url, complete, deutsch_komplett, fehlende_deutsch_folgen,
               last_film, last_episode, last_season
        FROM anime ORDER BY id
    """)
    rows = c.fetchall()
    conn.close()

    for row in rows:
        item = {
            "id": row[0],
            "title": row[1],
            "url": row[2],
            "complete": bool(row[3]),
            "deutsch_komplett": bool(row[4]),
            "fehlende_deutsch_folgen": [],
            "last_film": row[6],
            "last_episode": row[7],
            "last_season": row[8],
        }
        try:
            item["fehlende_deutsch_folgen"] = json.loads(row[5] or "[]")
        except Exception:
            item["fehlende_deutsch_folgen"] = []

        # Datei-Scan der Serie
        series_folder = Path(DOWNLOAD_DIR) / (item["title"] or "")
        episodes, films = [], []
        count_episodes, count_films = 0, 0

        if series_folder.exists():
            # Episoden: unter Staffeln
            for f in series_folder.rglob("*.mp4"):
                rel = f.relative_to(series_folder).as_posix()
                # Erkennen, ob Film oder Episode
                if re.search(r"(?:^|/)Filme/", rel, flags=re.I) or re.search(r"/Film\\s*\\d{2}", rel, flags=re.I):
                    films.append(rel)
                else:
                    # Sicherer: Muster SxxExxx
                    if re.search(r"S\\d{2}E\\d{3}", f.name, flags=re.I):
                        episodes.append(rel)
                    else:
                        # Falls falsch einsortiert, nach Namen raten
                        if re.search(r"film\\s*\\d{2}", f.name, flags=re.I):
                            films.append(rel)
                        else:
                            episodes.append(rel)

            count_episodes = len(episodes)
            count_films = len(films)

        # Schätzung Gesamtfolgen: nutze last_season * last_episode als grobe obere Schranke
        # Wenn nichts bekannt, 0 -> Balken animiert
        estimated_total = 0
        if item["last_season"] and item["last_episode"]:
            estimated_total = max(item["last_episode"], count_episodes)

        items.append({
            **item,
            "count_episodes": count_episodes,
            "count_films": count_films,
            "episodes": sorted(episodes),
            "films": sorted(films),
            "estimated_total_episodes": estimated_total
        })

    return jsonify({"items": items})

def start_webserver():
    # Host 0.0.0.0 für LAN-Zugriff; Port 8081
    app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False)

# -------------------- Datenbankfunktionen --------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            complete BOOLEAN DEFAULT 0,
            deutsch_komplett BOOLEAN DEFAULT 0,
            fehlende_deutsch_folgen TEXT DEFAULT '[]',
            last_film INTEGER DEFAULT 0,
            last_episode INTEGER DEFAULT 0,
            last_season INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def import_anime_txt():
    if not ANIME_TXT.exists():
        log(f"[FEHLER] Anime-Datei nicht gefunden: {ANIME_TXT}")
        return
    with open(ANIME_TXT, "r", encoding="utf-8") as f:
        anime_links = [line.strip() for line in f if line.strip()]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for url in anime_links:
        try:
            title = get_series_title(url)
            c.execute("INSERT OR IGNORE INTO anime (url, title) VALUES (?, ?)", (url, title))
        except Exception as e:
            log(f"[FEHLER] DB Insert: {e}")
    conn.commit()
    conn.close()

def load_anime():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, url, complete, deutsch_komplett, fehlende_deutsch_folgen, last_film, last_episode, last_season FROM anime ORDER BY id")
    rows = c.fetchall()
    conn.close()
    anime_list = []
    for row in rows:
        entry = {
            "id": row[0],
            "title": row[1],
            "url": row[2],
            "complete": bool(row[3]),
            "deutsch_komplett": bool(row[4]),
            "fehlende_deutsch_folgen": json.loads(row[5]),
            "last_film": row[6],
            "last_episode": row[7],
            "last_season": row[8]
        }
        if not entry["title"]:
            new_title = get_series_title(entry["url"])
            if new_title:
                update_anime(entry["id"], title=new_title)
                entry["title"] = new_title
        anime_list.append(entry)
    return anime_list

def update_anime(anime_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    values = []
    for key, val in kwargs.items():
        if key == "fehlende_deutsch_folgen":
            val = json.dumps(val)
        fields.append(f"{key} = ?")
        values.append(val)
    values.append(anime_id)
    c.execute(f"UPDATE anime SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()

# -------------------- Hilfsfunktionen --------------------
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', ' ', name)

def get_episode_title(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        german_title = soup.select_one("span.episodeGermanTitle")
        if german_title and german_title.text.strip():
            return german_title.text.strip()
        english_title = soup.select_one("small.episodeEnglishTitle")
        if english_title and english_title.text.strip():
            return english_title.text.strip()
    except Exception as e:
        log(f"[FEHLER] Konnte Episodentitel nicht abrufen ({url}): {e}")
    return None

def get_series_title(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.select_one("div.series-title h1 span")
        if title and title.text.strip():
            return sanitize_filename(title.text.strip())
    except Exception as e:
        log(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({url}): {e}")
    return None

def episode_already_downloaded(series_folder, season, episode):
    if not os.path.exists(series_folder):
        return False
    pattern = f"S{season:02d}E{episode:03d}" if season > 0 else f"Film{episode:02d}"
    for file in Path(series_folder).rglob("*.mp4"):
        if pattern.lower() in file.name.lower():
            return True
    return False

def delete_old_non_german_versions(series_folder, season, episode):
    pattern = f"S{season:02d}E{episode:03d}" if season > 0 else f"Film{episode:02d}"
    for file in Path(series_folder).rglob("*.mp4"):
        if pattern.lower() in file.name.lower() and "dub" not in file.name.lower():
            try:
                os.remove(file)
                log(f"[DEL] Alte Version gelöscht: {file.name}")
            except Exception as e:
                log(f"[FEHLER] Konnte Datei nicht löschen: {file.name} → {e}")

def rename_downloaded_file(series_folder, season, episode, title, language):
    """
    Benennt heruntergeladene Dateien sauber um:
    - Staffeln: SXXEXXX - Titel [Sprache].mp4
    - Filme: Movie XXX → FilmXX - Titel [Sprache].mp4
    """
    lang_suffix = {
        "German Dub": "Dub",
        "German Sub": "Sub",
        "English Dub": "English Dub",
        "English Sub": "English Sub"
    }.get(language, "")

    # Dateien suchen
    if season > 0:
        # Staffel
        pattern = f"S{season:02d}E{episode:03d}"
        matching_files = [f for f in Path(series_folder).rglob("*.mp4") if pattern.lower() in f.name.lower()]
        if not matching_files:
            print(f"[WARN] Keine Datei gefunden für {pattern}")
            return False
        file_to_rename = matching_files[0]
    else:
        # Filme: alle Movie XXX-Dateien
        pattern = f"Movie {episode:03d}"
        matching_files = [f for f in Path(series_folder).rglob("*.mp4") if pattern.lower() in f.name.lower()]
        if not matching_files:
            print(f"[WARN] Keine Datei gefunden für Film {episode}")
            return False
        file_to_rename = matching_files[0]
        pattern = f"Film{episode:02d}"  # Neuer Name

    # Titel sichern
    safe_title = sanitize_filename(title) if title else ""
    new_name = f"{pattern}"
    if safe_title:
        new_name += f" - {safe_title}"
    if lang_suffix:
        new_name += f" [{lang_suffix}]"
    new_name += ".mp4"

    # Zielordner
    dest_folder = Path(series_folder) / ("Filme" if season == 0 else f"Staffel {season}")
    dest_folder.mkdir(parents=True, exist_ok=True)
    new_path = dest_folder / new_name

    try:
        shutil.move(file_to_rename, new_path)
        print(f"[OK] Umbenannt: {file_to_rename.name} → {new_name}")
        return True
    except Exception as e:
        print(f"[FEHLER] Umbenennen fehlgeschlagen: {e}")
        return False


def run_download(cmd):
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        out = process.stdout + process.stderr
        if "No streams available for episode" in out:
            return "NO_STREAMS"
        if "No provider found for language" in out:
            return "LANGUAGE_ERROR"
        return "OK" if process.returncode == 0 else "FAILED"
    except Exception as e:
        log(f"[FEHLER] {e}")
        return "FAILED"

# -------------------- Downloadfunktionen --------------------
def download_episode(series_title, episode_url, season, episode, anime_id, german_only=False):
    series_folder = os.path.join(DOWNLOAD_DIR, series_title)
    if episode_already_downloaded(series_folder, season, episode):
        log(f"[SKIP] Episode bereits vorhanden: {series_title} - " + (f"S{season}E{episode}" if season > 0 else f"Film {episode}"))
        return "SKIPPED"
    langs_to_try = ["German Dub"] if german_only else LANGUAGES
    for lang in langs_to_try:
        log(f"[DOWNLOAD] Versuche {lang} → {episode_url}")
        cmd = ["aniworld", "--language", lang, "-o", DOWNLOAD_DIR, "--episode", episode_url]
        result = run_download(cmd)
        if result == "NO_STREAMS":
            log(f"[INFO] Kein Stream verfügbar: {episode_url} → Abbruch")
            return "NO_STREAMS"
        elif result == "OK":
            title = get_episode_title(episode_url)
            rename_downloaded_file(series_folder, season, episode, title, lang)
            if lang == "German Dub":
                delete_old_non_german_versions(series_folder, season, episode)
            log(f"[SUCCESS] {lang} erfolgreich geladen: {episode_url}")
            return "OK"
        elif result == "LANGUAGE_ERROR":
            continue
    log(f"[FAILED] Download fehlgeschlagen: {episode_url}")
    return "FAILED"

def download_films(series_title, base_url, anime_id, german_only=False, start_film=1):
    film_num = start_film
    log(f"[INFO] Starte Filmprüfung ab Film {start_film}")
    while True:
        film_url = f"{base_url}/filme/film-{film_num}"
        result = download_episode(series_title, film_url, 0, film_num, anime_id, german_only)
        if result in ["NO_STREAMS", "FAILED"]:
            log(f"[INFO] Keine weiteren Filme gefunden bei Film {film_num}.")
            break
        update_anime(anime_id, last_film=film_num)
        film_num += 1
        time.sleep(1)

def download_seasons(series_title, base_url, anime_id, german_only=False, start_season=1, start_episode=1):
    season = start_season if start_season > 0 else 1
    while True:
        episode = start_episode
        found_episode_in_season = False
        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            result = download_episode(series_title, episode_url, season, episode, anime_id, german_only)
            if result in ["NO_STREAMS", "FAILED"]:
                if episode == start_episode:
                    log(f"[INFO] Keine Episoden gefunden in Staffel {season}. Anime abgeschlossen.")
                    update_anime(anime_id, complete=True)
                    return
                else:
                    log(f"[INFO] Staffel {season} beendet nach {episode-1} Episoden.")
                    break
            found_episode_in_season = True
            update_anime(anime_id, last_episode=episode, last_season=season)
            episode += 1
            time.sleep(1)
        season += 1
        start_episode = 1

def check_deutsch_komplett(anime):
    series_folder = os.path.join(DOWNLOAD_DIR, anime["title"])
    all_episodes = list(Path(series_folder).rglob("*.mp4"))
    german_missing = any("Dub" not in f.name for f in all_episodes if "Film" not in f.name)
    if not german_missing:
        update_anime(anime["id"], deutsch_komplett=True)
        log(f"[INFO] Serie komplett auf Deutsch: {anime['title']}")

# -------------------- Hauptprogramm --------------------
def main():
    init_db()
    import_anime_txt()
    anime_list = load_anime()
    mode = str(sys.argv[1].lower() if len(sys.argv) > 1 else "default")
    log(f"[INFO] Gewählter Modus: {mode}")
    if mode == "german":
        log("\n=== Modus: Prüfe auf neue deutsche Synchro ===")
        for anime in anime_list:
            fehlende = anime.get("fehlende_deutsch_folgen", [])
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            if not fehlende:
                log(f"[GERMAN] '{series_title}': Keine neuen deutschen Folgen")
                continue
            log(f"[GERMAN] '{series_title}': {len(fehlende)} neue deutsche Folgen gefunden")
            verbleibend = fehlende.copy()
            for url in fehlende:
                match = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                season = int(match.group(1)) if match else 0
                episode = int(match.group(2)) if match else int(re.search(r"/film-(\d+)", url).group(1))
                result = download_episode(series_title, url, season, episode, anime_id, german_only=True)
                if result == "OK" and url in verbleibend:
                    verbleibend.remove(url)
                    update_anime(anime_id, fehlende_deutsch_folgen=verbleibend)
            if not verbleibend:
                update_anime(anime_id, deutsch_komplett=True)
                log(f"[GERMAN] Serie jetzt komplett auf Deutsch: {series_title}")
    elif mode == "new":
        log("\n=== Modus: Prüfe auf neue Episoden & Filme ===")
        for anime in anime_list:
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            base_url = anime["url"]
            start_film = anime["last_film"] + 1
            start_season = anime["last_season"]
            start_episode = anime["last_episode"] + 1 if start_season > 0 else 1
            log(f"\n[NEW] Prüfe '{series_title}' ab Film {start_film} und Staffel {start_season}, Episode {start_episode}")
            download_films(series_title, base_url, anime_id, start_film=start_film)
            download_seasons(series_title, base_url, anime_id, start_season=start_season, start_episode=start_episode)
    else:
        log("\n=== Modus: Standard  ===")
        for anime in anime_list:
            if anime["complete"]:
                log(f"[SKIP] '{anime['title']}' bereits komplett.")
                continue
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            base_url = anime["url"]
            start_film = anime["last_film"] + 1
            start_season = anime["last_season"]
            start_episode = anime["last_episode"] + 1 if start_season > 0 else 1
            log(f"\n[START] Starte Download für: '{series_title}' ab Film {start_film} / Staffel {start_season}, Episode {start_episode}")
            download_films(series_title, base_url, anime_id, start_film=start_film)
            download_seasons(series_title, base_url, anime_id, start_season=max(1, start_season), start_episode=start_episode)
            check_deutsch_komplett(anime)
            update_anime(anime_id, complete=True)
            log(f"[COMPLETE] Download abgeschlossen für: '{series_title}'")
    input("\n[FERTIG] Alle Aufgaben abgeschlossen, drücke eine beliebige Taste zum Beenden.")

if __name__ == "__main__":
    threading.Thread(target=start_webserver, daemon=True).start()
    main()
