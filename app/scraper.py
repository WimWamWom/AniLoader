"""
AniLoader – HTML-Scraper für aniworld.to und s.to.

Extrahiert Serien-Titel, Staffeln, Episoden und verfügbare Sprachen.
Nutzt niquests mit DNS-over-HTTPS, mit automatischem Fallback auf System-DNS
falls DoH im Netzwerk blockiert ist (z.B. Firmennetz).
"""

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from niquests import Session

from .logger import log

# ──────────────────────── HTTP Session ────────────────────────

_session: Optional[Session] = None
_dns_mode: str = "doh"  # 'doh' | 'system'

# Harter Wall-Clock-Timeout für jeden HTTP-Request (inkl. DNS-Auflösung).
# niquests' timeout= greift nicht für die interne DoH-DNS-Phase –
# daher sichern wir jeden Request zusätzlich via ThreadPoolExecutor ab.
_HTTP_HARD_TIMEOUT: int = 30  # Sekunden


def _get_session(force_new: bool = False) -> Session:
    """Lazy-Init einer niquests-Session. Versucht DoH, fällt auf System-DNS zurück."""
    global _session, _dns_mode
    if _session is not None and not force_new:
        return _session

    resolver = ["doh+google://"] if _dns_mode == "doh" else None
    _session = Session(
        resolver=resolver,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": "https://aniworld.to/",
        },
    )
    return _session


def _fetch(url: str) -> str:
    """Fetch HTML für eine URL. Fällt auf System-DNS zurück, wenn DoH fehlschlägt.

    Nutzt einen Hard-Timeout via ThreadPoolExecutor, da niquests' timeout=-Parameter
    die interne DNS-Resolver-Phase (DoH) nicht abdeckt und dort endlos hängen kann.
    """
    global _dns_mode, _session

    def _do_fetch() -> str:
        try:
            resp = _get_session().get(url, timeout=15)
            resp.raise_for_status()
            return str(resp.text)
        except Exception as e:
            if _dns_mode == "doh":
                log(f"[SCRAPER] DoH fehlgeschlagen, wechsle auf System-DNS: {e}")
                _dns_mode = "system"
                _session = None  # Session neu erstellen
                resp = _get_session(force_new=True).get(url, timeout=15)
                resp.raise_for_status()
                return str(resp.text)
            raise

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_fetch)
        try:
            return future.result(timeout=_HTTP_HARD_TIMEOUT)
        except FutureTimeoutError:
            log(f"[SCRAPER] Hard-Timeout ({_HTTP_HARD_TIMEOUT}s) für {url} – DNS hängt, wechsle auf System-DNS")
            _dns_mode = "system"
            _session = None
            # Direkter Versuch mit System-DNS, ohne doH
            resp = _get_session(force_new=True).get(url, timeout=15)
            resp.raise_for_status()
            return str(resp.text)


def _post(url: str, **kwargs):
    """POST-Request mit DNS-Fallback."""
    global _dns_mode, _session
    kwargs.setdefault("timeout", 15)

    def _do_post():
        try:
            return _get_session().post(url, **kwargs)
        except Exception as e:
            if _dns_mode == "doh":
                log(f"[SCRAPER] DoH fehlgeschlagen, wechsle auf System-DNS: {e}")
                _dns_mode = "system"
                _session = None
                return _get_session(force_new=True).post(url, **kwargs)
            raise

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_post)
        try:
            return future.result(timeout=_HTTP_HARD_TIMEOUT)
        except FutureTimeoutError:
            log(f"[SCRAPER] Hard-Timeout ({_HTTP_HARD_TIMEOUT}s) für POST {url} – DNS hängt, wechsle auf System-DNS")
            _dns_mode = "system"
            _session = None
            return _get_session(force_new=True).post(url, **kwargs)


# ──────────────────────── URL-Hilfsfunktionen ────────────────────────


def get_base_url(url: str) -> str:
    """Extrahiert die Serien-Basis-URL (ohne Staffel/Episode)."""
    if "aniworld.to" in url:
        m = re.match(r"(https://aniworld\.to/anime/stream/[^/]+)", url)
        return m.group(1) if m else url
    if "s.to" in url:
        m = re.match(r"(https://s\.to/serie/stream/[^/]+)", url)
        return m.group(1) if m else url
    return url


def is_aniworld(url: str) -> bool:
    return "aniworld.to" in url


def is_sto(url: str) -> bool:
    return "s.to" in url


def build_season_url(base_url: str, season: int) -> str:
    """Baut die URL für eine Staffel."""
    return f"{base_url}/staffel-{season}"


def build_film_url(base_url: str) -> str:
    """Baut die URL für die Filme-Seite."""
    if is_sto(base_url):
        return f"{base_url}/staffel-0"
    return f"{base_url}/filme"


def build_episode_url(base_url: str, season: int, episode: int) -> str:
    """Baut die URL für eine einzelne Episode."""
    if season == 0:
        if is_sto(base_url):
            return f"{base_url}/staffel-0/episode-{episode}"
        else:  # ANiworld
            return f"{base_url}/filme/film-{episode}"
    return f"{base_url}/staffel-{season}/episode-{episode}"


# ──────────────────────── Serien-Titel ────────────────────────


def get_series_title(url: str) -> Optional[str]:
    """Extrahiert den Serien-Titel von der Serien-Seite."""
    base_url = get_base_url(url)
    try:
        html = _fetch(base_url)
        soup = BeautifulSoup(html, "lxml")

        if is_aniworld(url):
            # <div class="series-title"><h1><span>Title</span></h1></div>
            title_div = soup.find("div", class_="series-title")
            if title_div:
                h1 = title_div.find("h1")
                if h1:
                    span = h1.find("span")
                    return span.get_text(strip=True) if span else h1.get_text(strip=True)
            # Fallback
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(strip=True)

        elif is_sto(url):
            # <h1 itemprop="name">Title</h1>
            h1 = soup.find("h1", attrs={"itemprop": "name"})
            if h1:
                return h1.get_text(strip=True)
            # Fallback: series-title Div (s.to nutzt ähnliche Struktur)
            title_div = soup.find("div", class_="series-title")
            if title_div:
                h1 = title_div.find("h1")
                if h1:
                    span = h1.find("span")
                    return span.get_text(strip=True) if span else h1.get_text(strip=True)
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(strip=True)

    except Exception as e:
        log(f"[SCRAPER] Titel-Fehler für {url}: {e}")

    return None


# ──────────────────────── Poster / Cover-Bild ────────────────────────


def get_poster_url(url: str) -> Optional[str]:
    """Extrahiert die Cover-Bild-URL (Poster) von der Serien-Seite."""
    base_url = get_base_url(url)
    try:
        html = _fetch(base_url)
        soup = BeautifulSoup(html, "lxml")

        # Methode 1: .seriesCoverBox (Standard für beide Plattformen)
        cover_div = soup.find("div", class_="seriesCoverBox")
        if cover_div:
            img = cover_div.find("img")
            if img:
                src = img.get("data-src") or img.get("src", "")
                if src and not src.startswith("data:"):
                    if src.startswith("http"):
                        return src
                    # Relative URL → absolute
                    domain = "https://aniworld.to" if is_aniworld(url) else "https://s.to"
                    return f"{domain}{src}"

        # Methode 2: Spezifisch für S.to - .backdrop oder .poster-image
        if is_sto(url):
            # S.to nutzt oft .backdrop für große Bilder
            backdrop = soup.find("div", class_="backdrop")
            if backdrop:
                img = backdrop.find("img")
                if img:
                    src = img.get("data-src") or img.get("src", "")
                    if src and not src.startswith("data:"):
                        if src.startswith("http"):
                            return src
                        return f"https://s.to{src}"

            # Alternative: .poster-image oder ähnliche Klassen
            for class_name in ["poster-image", "series-poster", "cover-image"]:
                poster_img = soup.find("img", class_=class_name)
                if poster_img:
                    src = poster_img.get("data-src") or poster_img.get("src", "")
                    if src and not src.startswith("data:"):
                        if src.startswith("http"):
                            return src
                        return f"https://s.to{src}"

        # Methode 3: Fallback - alle <img> nach cover/poster durchsuchen
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src", "")
            if src and any(k in src for k in ("/cover/", "/poster/", "stream-cover", "/backdrop/")):
                if src.startswith("data:"):
                    continue
                if src.startswith("http"):
                    return src
                domain = "https://aniworld.to" if is_aniworld(url) else "https://s.to"
                return f"{domain}{src}"

    except Exception as e:
        log(f"[SCRAPER] Poster-Fehler für {url}: {e}")

    return None


# ──────────────────────── Staffel-Nummern ────────────────────────


def get_season_numbers(url: str) -> List[int]:
    """
    Gibt eine Liste der verfügbaren Staffel-Nummern zurück.
    0 wird für Filme verwendet (falls vorhanden).
    """
    base_url = get_base_url(url)
    try:
        html = _fetch(base_url)
        soup = BeautifulSoup(html, "lxml")
        seasons: List[int] = []

        if is_aniworld(base_url):
            nav = soup.find("div", class_="hosterSiteDirectNav")
            scope = nav if nav else soup
            for ul in scope.find_all("ul"):
                text = ul.get_text(" ", strip=True)
                if "Staffeln" in text or "Staffel" in text:
                    for a in ul.find_all("a"):
                        num = a.get_text(strip=True)
                        if num.isdigit():
                            seasons.append(int(num))
            # Filme prüfen: href endet mit /filme (mit oder ohne Slash)
            for a in soup.find_all("a"):
                href = str(a.get("href", "")).rstrip("/")
                if href.endswith("/filme") and 0 not in seasons:
                    seasons.insert(0, 0)
                    break

        elif is_sto(base_url):
            nav = soup.find("nav", id="season-nav")
            scope = nav if nav else soup
            for a in scope.find_all("a", attrs={"data-season-pill": True}):
                num_str = str(a.get("data-season-pill", "")).strip()
                if num_str.isdigit():
                    seasons.append(int(num_str))
            
            # S.to: Filme sind unter /staffel-0 oder separate Filme-Section
            # Prüfe auf Filme-Link oder Staffel-0
            for a in scope.find_all("a"):
                href = a.get("href", "")
                href = str(href)
                if "/staffel-0" in href and 0 not in seasons:
                    seasons.insert(0, 0)
                    break

        return sorted(set(seasons))

    except Exception as e:
        log(f"[SCRAPER] Staffeln-Fehler für {url}: {e}")
        return []


# ──────────────────────── Hat Filme? ────────────────────────


def has_movies(url: str) -> bool:
    """Prüft ob die Serie Filme hat."""
    seasons = get_season_numbers(url)
    return 0 in seasons


# ──────────────── Episoden pro Staffel (mit Sprachen) ──────────────────


def get_episodes_for_season(
    base_url: str, season: int
) -> List[Dict]:
    """
    Gibt für eine Staffel alle Episoden mit verfügbaren Sprachen zurück.

    Returns:
        Liste von Dicts: [
            {
                "episode": 1,
                "title_de": "...",
                "title_en": "...",
                "url": "https://...",
                "languages": ["German Dub", "German Sub", "English Sub"],
            },
            ...
        ]
    """
    if season == 0:
        season_url = build_film_url(base_url)
    else:
        season_url = build_season_url(base_url, season)

    try:
        html = _fetch(season_url)
    except Exception as e:
        log(f"[SCRAPER] Episoden-Fehler für {season_url}: {e}")
        return []

    soup = BeautifulSoup(html, "lxml")

    if is_aniworld(base_url):
        return _parse_aniworld_season(soup, base_url, season)
    elif is_sto(base_url):
        return _parse_sto_season(soup, base_url, season)
    return []


def _parse_aniworld_season(
    soup: BeautifulSoup, base_url: str, season: int
) -> List[Dict]:
    """
    Parst eine AniWorld-Staffelseite.
    Die Sprach-Flags sind direkt in der Episoden-Tabelle sichtbar.
    """
    episodes = []

    # Suche tbody mit id="seasonN" oder "seasonFilme" etc.
    if season == 0:
        # Filme: verschiedene IDs möglich
        tbody = None
        for candidate_id in ["seasonFilme", "season0", "seasonFilms"]:
            tbody = soup.find("tbody", id=candidate_id)
            if tbody:
                break
        if not tbody:
            # Fallback: erste tbody die Episoden-Rows enthält
            for tb in soup.find_all("tbody"):
                if tb.find("tr", attrs={"data-episode-id": True}):
                    tbody = tb
                    break
    else:
        tbody = soup.find("tbody", id=f"season{season}")
        if not tbody:
            log(f"[SCRAPER] Kein tbody id=season{season} gefunden – versuche Fallback")
            tbody = soup.find("tbody")

    if not tbody:
        log(f"[SCRAPER] Kein tbody gefunden auf Staffel-{season}-Seite")
        return []

    rows = tbody.find_all("tr", attrs={"data-episode-id": True})
    if not rows:
        # Fallback 1: Film-Seiten haben manchmal keine data-episode-id, aber itemprop="url"
        rows = [tr for tr in tbody.find_all("tr") if tr.find("a", attrs={"itemprop": "url"})]
        if rows:
            log(f"[SCRAPER] Fallback-1: {len(rows)} Rows mit itemprop=url gefunden")
    if not rows and season == 0:
        # Fallback 2: Jede <tr> mit einem Link die /filme/film- enthält
        rows = [
            tr for tr in tbody.find_all("tr")
            if tr.find("a", href=lambda h: h and "/filme/film-" in h)
        ]
        if rows:
            log(f"[SCRAPER] Fallback-2: {len(rows)} Film-Rows via /filme/film- gefunden")
    if not rows and season == 0:
        # Fallback 3: Jede <tr> mit irgendeinem <a href> — debug alle Rows
        all_rows = tbody.find_all("tr")
        log(f"[SCRAPER] DEBUG: {len(all_rows)} Rows in tbody gefunden")
        for i, tr in enumerate(all_rows[:5]):
            log(f"[SCRAPER] DEBUG Row {i}: {str(tr)[:300]}")
        rows = [tr for tr in all_rows if tr.find("a", href=True)]
        if rows:
            log(f"[SCRAPER] Fallback-3: {len(rows)} Rows mit beliebigem <a href>")
    if not rows:
        log(f"[SCRAPER] Keine Rows in tbody gefunden (season={season})")

    for tr in rows:
        ep_data: Dict = {"languages": []}

        # Episode-Nummer
        meta = tr.find("meta", attrs={"itemprop": "episodeNumber"})
        if meta:
            data = meta.get("content", "0")
            try:
                ep_data["episode"] = int(data)
            except (ValueError, TypeError):
                ep_data["episode"] = 0
        else:
            # Fallback: aus Link-Text oder href
            a = tr.find("a", attrs={"itemprop": "url"}) or tr.find("a", href=True)
            if a:
                text = a.get_text(strip=True)
                m = re.search(r"(\d+)", text)
                if not m:
                    href = a.get("href", "")
                    m = re.search(r"film-(\d+)", href)
                ep_data["episode"] = int(m.group(1)) if m else 0
            else:
                continue

        # Titel (deutsch + englisch)
        title_td = tr.find("td", class_="seasonEpisodeTitle")
        if title_td:
            strong = title_td.find("strong")
            ep_data["title_de"] = strong.get_text(strip=True) if strong else ""
            span = title_td.find("span")
            ep_data["title_en"] = span.get_text(strip=True) if span else ""
        else:
            ep_data["title_de"] = ""
            ep_data["title_en"] = ""

        # URL
        a = tr.find("a", attrs={"itemprop": "url"}) or tr.find("a", href=True)
        if a and a.get("href"):
            href = str(a["href"])
            if not href.startswith("http"):
                href = f"https://aniworld.to{href}"
            ep_data["url"] = href
        else:
            episode = int(ep_data["episode"])
            ep_data["url"] = build_episode_url(base_url, season, episode)

        # Sprachen aus Flag-Images
        langs = _extract_aniworld_languages(tr)
        ep_data["languages"] = langs

        episodes.append(ep_data)

    return episodes


def _extract_aniworld_languages(element) -> List[str]:
    """Extrahiert Sprachen aus AniWorld Flag-Images."""
    langs = []
    seen = set()

    for img in element.find_all("img", class_="flag"):
        src = img.get("src", "")
        title = img.get("title", "").lower()

        lang = None
        # WICHTIG: Genauere Checks zuerst (specifische Dateien)
        if src.endswith("japanese-german.svg"):
            lang = "German Sub"
        elif src.endswith("japanese-english.svg"):
            lang = "English Sub"
        elif src.endswith("german.svg"):
            lang = "German Dub"
        elif src.endswith("english.svg"):
            lang = "English Dub"
        # Fallback: Title-Attribute
        elif "deutschem untertitel" in title:
            lang = "German Sub"
        elif "englische untertitel" in title or "englischen untertitel" in title:
            lang = "English Sub"
        elif "deutsch/german" in title or "deutsch" in title:
            lang = "German Dub"
        elif "english" in title:
            lang = "English Dub"

        if lang and lang not in seen:
            seen.add(lang)
            langs.append(lang)

    return langs


def _parse_sto_season(
    soup: BeautifulSoup, base_url: str, season: int
) -> List[Dict]:
    """
    Parst eine S.to-Staffelseite.
    Sprachen sind in SVG-Icons in jeder Episode verfügbar (watch-language Icons).
    """
    episodes = []

    # Moderne S.to Struktur: <table class="episode-table">
    episode_table = soup.find("table", class_="episode-table")
    if not episode_table:
        # Fallback: Suche nach Episode-Links im HTML
        log(f"[SCRAPER] episode-table nicht gefunden, nutze Regex-Fallback")
        pattern = re.compile(
            r'href="(?:https?://(?:serienstream|s)\.to)?/serie/[^"]+/staffel-'
            + str(season)
            + r'/episode-(\d+)"'
        )
        seen = set()
        for m in pattern.finditer(str(soup)):
            ep_num = int(m.group(1))
            if ep_num not in seen:
                seen.add(ep_num)
                episodes.append({
                    "episode": ep_num,
                    "title_de": "",
                    "title_en": "",
                    "url": build_episode_url(base_url, season, ep_num),
                    "languages": [],
                })
        return sorted(episodes, key=lambda x: x["episode"])

    # Alle Reihen in der Tabelle
    tbody = episode_table.find("tbody")
    rows = tbody.find_all("tr") if tbody else episode_table.find_all("tr")[1:]  # Skip header

    for row in rows:
        ep_data: Dict = {"languages": []}

        # Episode-Nummer: first <th> in row (z.B. <th class="text-center">1</th>)
        th = row.find("th")
        if th:
            num_text = th.get_text(strip=True)
            try:
                ep_data["episode"] = int(num_text)
            except (ValueError, TypeError):
                continue
        else:
            continue

        # Titel: Kombiniere Deutsche + Englische Titel
        # S.to: zweite <td> (nach Episode-Nr)
        tds = row.find_all("td")
        if len(tds) >= 1:
            title_td = tds[0]
            # Titel kann mehrere Spans enthalten (deutsch + englisch)
            texts = []
            for el in title_td.find_all(["strong", "span"]):
                text = el.get_text(strip=True)
                if text:
                    texts.append(text)
            # Erste ist meist deutsch
            ep_data["title_de"] = texts[0] if texts else ""
            ep_data["title_en"] = texts[1] if len(texts) > 1 else ""
        else:
            ep_data["title_de"] = ""
            ep_data["title_en"] = ""

        # URL konstruieren
        episode = ep_data["episode"]
        ep_data["url"] = build_episode_url(base_url, season, episode)

        # Sprachen aus der Sprach-Cell (letzte <td> mit class="episode-language-cell")
        lang_cell = row.find("td", class_="episode-language-cell")
        if lang_cell:
            langs = _extract_sto_languages(lang_cell)
            ep_data["languages"] = langs
        else:
            ep_data["languages"] = []

        episodes.append(ep_data)

    return episodes


def _extract_sto_languages(element) -> List[str]:
    """Extrahiert Sprachen aus S.to SVG-Icons oder Flag-Images."""
    langs = []
    seen = set()

    # Methode 1: SVG-Icons mit watch-language Klasse (moderne S.to-Struktur)
    for svg in element.find_all("svg", class_="watch-language"):
        svg_classes = " ".join(svg.get("class", []))
        use = svg.find("use")
        href = str(use.get("href") or use.get("xlink:href") or "") if use else ""
        combined = (href + " " + svg_classes).lower()

        lang = None
        # Auf s.to: german-flag = German Dub, english-flag = English Dub
        # Sub-Varianten haben explizit '-sub' im Icon-Namen/Klasse
        if "german-sub" in combined or "deutsch-sub" in combined:
            lang = "German Sub"
        elif "english-sub" in combined:
            lang = "English Sub"
        elif "german" in combined:
            lang = "German Dub"
        elif "english" in combined:
            lang = "English Dub"

        if lang and lang not in seen:
            seen.add(lang)
            langs.append(lang)

    # Methode 2: Fallback für Flag-Images (ältere S.to-Struktur)
    if not langs:
        for img in element.find_all("img", class_="flag"):
            src = img.get("src", "") or img.get("data-src", "")
            
            lang = None
            if src.endswith("german-sub.svg") or src.endswith("deutsch-sub.svg"):
                lang = "German Sub"
            elif src.endswith("english-sub.svg"):
                lang = "English Sub"
            elif src.endswith("german.svg"):
                lang = "German Dub"
            elif src.endswith("english.svg"):
                lang = "English Dub"
            
            if lang and lang not in seen:
                seen.add(lang)
                langs.append(lang)

    return langs


# ──────────────────────── Stream-Verfügbarkeit ────────────────────────


def is_episode_available(episode_url: str) -> bool:
    """
    Prüft ob eine Episode tatsächlich Streams hat (kein Ankündigungs-Placeholder).

    Zuverlässigstes Merkmal auf aniworld.to:
    - Episoden MIT Streams:    <ul class="row"> enthält <li class="episodeLink..."> Elemente
    - Episoden OHNE Streams:   <ul class="row"> ist leer ODER fehlt komplett

    Fallback: Prüft ob changeLanguageBox Flag-Images enthält.

    Gibt True zurück wenn mindestens ein Hoster-Link gefunden wurde.
    Gibt True zurück wenn die Seite nicht aniworld.to ist (S.to hat eigene Logik).
    """
    if not is_aniworld(episode_url):
        return True  # Nur für aniworld.to relevant

    try:
        html = _fetch(episode_url)
        soup = BeautifulSoup(html, "lxml")

        # Primärcheck: <ul class="row"> mit Hoster-<li> Einträgen
        for ul in soup.find_all("ul", class_="row"):
            li_items = ul.find_all("li", class_=lambda c: bool(c and "episodeLink" in c))
            if li_items:
                return True

        # Fallback: Flag-Images in changeLanguageBox
        lang_box = soup.find("div", class_="changeLanguageBox")
        if lang_box and lang_box.find("img"):
            return True

        # Weiterer Fallback: data-link-target Attribute (Redirect-Links)
        if soup.find(attrs={"data-link-target": True}):
            return True

        return False

    except Exception as e:
        log(f"[SCRAPER] Verfügbarkeits-Check fehlgeschlagen für {episode_url}: {e}")
        return True  # Im Zweifel: nicht überspringen


# ──────────────────────── Episode-Sprachen (Fallback) ────────────────────────


def get_episode_languages(episode_url: str) -> List[str]:
    """
    Holt die verfügbaren Sprachen direkt von der Episoden-Seite.
    Dies wird verwendet, wenn die Staffelseite keine Sprach-Info pro Episode hat (z.B. S.to).
    """
    try:
        html = _fetch(episode_url)
        soup = BeautifulSoup(html, "lxml")

        if is_aniworld(episode_url):
            # ANiworld: Sprachen aus Player-Bereich
            return _extract_aniworld_episode_languages(soup)
        elif is_sto(episode_url):
            # S.to: Sprachen aus Hosters/Provider-Bereich
            return _extract_sto_episode_languages(soup)
    except Exception as e:
        log(f"[SCRAPER] Sprachen-Fehler für {episode_url}: {e}")

    return []


def _extract_aniworld_episode_languages(soup: BeautifulSoup) -> List[str]:
    """Extrahiert verfügbare Sprachen von einer AniWorld-Episodenseite."""
    langs = []
    seen = set()

    # Methode 1: Hoster-Liste mit Flag-Images
    for div in soup.find_all("div", class_="hosterSiteDirectNav"):
        for img in div.find_all("img", class_="flag"):
            src = img.get("src", "")
            title = img.get("title", "").lower()
            
            lang = None
            if "german.svg" in src or "deutsch" in title:
                lang = "German Dub"
            elif "deutschem untertitel" in title or "german-sub" in src:
                lang = "German Sub"
            elif "english-sub" in src or "englische untertitel" in title:
                lang = "English Sub"
            elif "english.svg" in src:
                lang = "English Dub"
            
            if lang and lang not in seen:
                seen.add(lang)
                langs.append(lang)
    
    # Methode 2: Voice-Buttons im Player-Bereich
    if not langs:
        for btn in soup.find_all("button", class_=re.compile(r"voice|language")):
            text = btn.get_text(strip=True).lower()
            lang = None
            if "german dub" in text or "deutsch dub" in text:
                lang = "German Dub"
            elif "german sub" in text or "deutsch sub" in text:
                lang = "German Sub"
            elif "english sub" in text:
                lang = "English Sub"
            
            if lang and lang not in seen:
                seen.add(lang)
                langs.append(lang)

    return langs


def _extract_sto_episode_languages(soup: BeautifulSoup) -> List[str]:
    """Extrahiert verfügbare Sprachen von einer S.to-Episodenseite."""
    langs = []
    seen = set()

    def _add_lang(lang: Optional[str]) -> None:
        if lang and lang not in seen:
            seen.add(lang)
            langs.append(lang)

    def _map_text_to_lang(text: str) -> Optional[str]:
        t = (text or "").lower()
        if "german sub" in t or "deutsch sub" in t or "untertitel" in t:
            return "German Sub"
        if "english sub" in t:
            return "English Sub"
        if "german" in t or "deutsch" in t:
            return "German Dub"
        if "english" in t:
            return "English Dub"
        return None

    # Methode 1: Hosters-Bereich .hoster-item mit SVG-Icons
    for hoster_div in soup.find_all("div", class_="hoster-item"):
        # S.to hat .language-badge mit Icons
        for lang_badge in hoster_div.find_all(class_="language-badge"):
            svg = lang_badge.find("svg")
            if not svg:
                lang_text = lang_badge.get_text(strip=True).lower()
            else:
                # SVG-Icon parsen
                use = svg.find("use")
                if not use:
                    continue
                icon_href = str(use.get("href") or use.get("xlink:href") or "")
                if "german" in icon_href:
                    lang_text = "german"
                elif "english" in icon_href:
                    lang_text = "english"
                else:
                    continue
                
            # Bestimme Sprache und Typ (Dub/Sub)
            lang = None
            if "german" in lang_text:
                # German Dub vs German Sub unterscheiden
                parent_text = hoster_div.get_text(strip=True).lower()
                if "untertitel" in parent_text or "sub" in parent_text:
                    lang = "German Sub"
                else:
                    lang = "German Dub"
            elif "english" in lang_text:
                parent_text = hoster_div.get_text(strip=True).lower()
                if "untertitel" in parent_text or "sub" in parent_text:
                    lang = "English Sub"
                else:
                    lang = "English Dub"
            
            _add_lang(lang)

    # Methode 2: Fallback über Flag-Images (ältere S.to-Struktur)
    if not langs:
        for img in soup.find_all("img", class_="flag"):
            src = img.get("src", "") or img.get("data-src", "")
            lang = None
            src_lower = src.lower()
            if "german-sub" in src_lower or "deutsch-sub" in src_lower:
                lang = "German Sub"
            elif "english-sub" in src_lower:
                lang = "English Sub"
            elif "german" in src_lower or "deutsch" in src_lower:
                lang = "German Dub"
            elif "english" in src_lower:
                lang = "English Dub"

            _add_lang(lang)

    return langs


# ──────────────────────── Episode-Titel ────────────────────────


def get_episode_title(episode_url: str) -> Optional[str]:
    """Extrahiert den Episoden-Titel von der Episoden-Seite."""
    try:
        html = _fetch(episode_url)
        soup = BeautifulSoup(html, "lxml")

        if is_aniworld(episode_url):
            span = soup.find("span", class_="episodeGermanTitle")
            if span:
                return span.get_text(strip=True)
            # Fallback
            h2 = soup.find("h2", class_="episodeTitle")
            if h2:
                return h2.get_text(strip=True)

        elif is_sto(episode_url):
            # S.to Episodentitel
            h2 = soup.find("h2", class_="episodeTitle")
            if h2:
                return h2.get_text(strip=True)
            title_span = soup.find("span", class_="episodeGermanTitle")
            if title_span:
                return title_span.get_text(strip=True)

    except Exception as e:
        log(f"[SCRAPER] Episodentitel-Fehler für {episode_url}: {e}")

    return None


# ──────────────────────── Suche ────────────────────────


def search_anime(query: str, platform: str = "both", log_search: bool = False) -> List[Dict]:
    """
    Sucht nach Serien/Animes.

    Args:
        query: Suchbegriff
        platform: "aniworld" | "sto" | "both"
        log_search: Loggt nur bei aktiv ausgelöster Suche die Ergebnisanzahlen

    Returns:
        Liste von Dicts: [{"title": "...", "url": "...", "description": "...", "platform": "..."}]
    """

    aniworld_results: List[Dict] = []
    sto_results: List[Dict] = []

    if platform in ("aniworld", "both"):
        try:
            resp = _post(
                "https://aniworld.to/ajax/search",
                data={"keyword": query},
                timeout=10,
            )
            data = resp.json() if resp.status_code == 200 else []
            for item in data:
                link = item.get("link", "")
                if "/anime/stream/" in link:
                    full_url = f"https://aniworld.to{link}" if not link.startswith("http") else link
                    aniworld_results.append({
                        "title": item.get("title", "").replace("<em>", "").replace("</em>", ""),
                        "url": full_url,
                        "description": item.get("description", ""),
                        "platform": "AniWorld",
                    })
        except Exception as e:
            log(f"[SUCHE] AniWorld-Fehler: {e}")

    if platform in ("sto", "both"):
        try:
            resp = _get_session().get(
                "https://s.to/api/search/suggest",
                params={"term": query},
                timeout=10,
            )
            data_raw = resp.json() if resp.status_code == 200 else {}
            shows = data_raw.get("shows", []) or []
            for show in shows:
                raw_url = show.get("url", "") or ""
                # Normalize: /serie/<slug> oder /serie/stream/<slug> → /serie/stream/<slug>
                if raw_url.startswith("/serie/stream/"):
                    slug = raw_url[len("/serie/stream/"):].strip("/").split("/")[0]
                elif raw_url.startswith("/serie/"):
                    slug = raw_url[len("/serie/"):].strip("/").split("/")[0]
                else:
                    continue
                if not slug:
                    continue
                full_url = f"https://s.to/serie/stream/{slug}"
                title = (show.get("name", "") or "").replace("<em>", "").replace("</em>", "")
                sto_results.append({
                    "title": title,
                    "url": full_url,
                    "description": "",
                    "platform": "S.to",
                })
        except Exception as e:
            log(f"[SUCHE] S.to-Fehler: {e}")

    # Ergebnisse abwechselnd mischen (AniWorld, S.to, AniWorld, S.to, …)
    results: List[Dict] = []
    i_aw, i_st = 0, 0
    while i_aw < len(aniworld_results) or i_st < len(sto_results):
        if i_aw < len(aniworld_results):
            results.append(aniworld_results[i_aw])
            i_aw += 1
        if i_st < len(sto_results):
            results.append(sto_results[i_st])
            i_st += 1

    if log_search:
        log(f"[SUCHE] AniWorld: {len(aniworld_results)}, S.to: {len(sto_results)}")

    return results


# ──────────────────────── Komplette Serien-Info ────────────────────────


def get_series_info(url: str) -> Dict:
    """
    Sammelt alle Informationen zu einer Serie in einem Aufruf.
    Minimale HTTP-Requests: 1 (Serien-Seite) + N (je eine pro Staffel).

    Returns:
        {
            "title": "...",
            "url": "...",
            "has_movies": True/False,
            "seasons": {
                0: [{"episode": 1, ...}, ...],  # Filme
                1: [{"episode": 1, ...}, ...],   # Staffel 1
                ...
            }
        }
    """
    base_url = get_base_url(url)
    title = get_series_title(url)
    season_numbers = get_season_numbers(url)

    info = {
        "title": title,
        "url": base_url,
        "has_movies": 0 in season_numbers,
        "seasons": {},
    }

    for s_num in season_numbers:
        episodes = get_episodes_for_season(base_url, s_num)
        info["seasons"][s_num] = episodes

    return info
