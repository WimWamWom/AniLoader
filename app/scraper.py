"""
AniLoader – Metadaten-Scraper auf Basis des `aniworld`-Moduls.

Ersetzt das frühere eigene HTML-Scraping für aniworld.to/serienstream.to
VOLLSTÄNDIG durch die Python-API des `aniworld`-Moduls
(AniworldSeries/Season/Episode, SerienstreamSeries/Season/Episode,
aniworld.search). Es gibt keinen direkten HTTP-/BeautifulSoup-Code mehr für
aniworld.to/serienstream.to in AniLoader.

Reine URL-Helfer (ohne HTTP) bleiben erhalten – sie sind kein Scraping.

HTTP/Session: Alle Modul-Requests laufen über die modulglobale Session. AniLoaders
DoH+System-DNS-Fallback wird via aniworld_session.install_session() injiziert
(siehe app/aniworld_session.py – notwendig, weil die Modelle GLOBAL_SESSION per
Namen importieren und ein bloßes Rebind nicht greifen würde). Dieselbe Session
steht Nicht-Scraper-Aufrufern als scraper.get_shared_session() zur Verfügung –
pro Aufruf eine neue niquests-Session zu bauen würde deren Pool-Threads lecken.

Effizienz/Requests: get_episodes_for_season enumeriert Episoden mit genau EINEM
Fetch (Staffelseite) und holt KEINE Sprachen pro Episode. Die Sprach-Verfügbarkeit
wird erst dann pro Episode geladen (provider_data, 1 Fetch), wenn eine
Download-Entscheidung sie tatsächlich braucht (get_episode_languages /
is_episode_available). Das minimiert Requests im Sinne des Projektziels.
"""

import html as _html
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

from aniworld import (
    AniworldSeries,
    AniworldSeason,
    AniworldEpisode,
    SerienstreamSeries,
    SerienstreamSeason,
    SerienstreamEpisode,
)
from aniworld import search as _aw_search

from .logger import debug, log
from .aniworld_session import (  # noqa: F401 – get_shared_session bewusst re-exportiert
    install_session,
    available_labels,
    get_shared_session,
    is_available,
)
from .domains import (  # noqa: F401 – bewusst re-exportiert für bestehende Aufrufer
    ANIWORLD,
    SERIENSTREAM,
    canonical_host,
    canonical_origin,
    get_base_url,
    get_series_key,
    is_aniworld,
    is_known,
    is_serienstream,
    normalize_series_url,
)

# Session-Injektion beim Import sicherstellen (idempotent, einmalig pro Prozess).
try:
    install_session()
except Exception as _e:  # pragma: no cover - Injektion darf den Import nie hart failen
    log(f"[SCRAPER] Session-Injektion beim Import fehlgeschlagen: {_e}")


# ──────────────────────── URL-Hilfsfunktionen (rein, kein HTTP) ────────────────────────


# URL-Logik liegt zentral in app/domains.py – dort steht auch die konfigurierbare
# Domainliste. Hier nur re-exportiert, damit alle bestehenden Aufrufer
# (scraper.normalize_series_url, scraper.is_sto, …) unverändert funktionieren.
def is_sto(url: str) -> bool:
    """True für serienstream (Name historisch: früher 's.to')."""
    return is_serienstream(url)


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
        else:  # aniworld
            return f"{base_url}/filme/film-{episode}"
    return f"{base_url}/staffel-{season}/episode-{episode}"


# ──────────────────────── Modul-Fabriken ────────────────────────


def _sto_series_url(url: str) -> str:
    """serienstream-Serien-URL in eine modulakzeptierte /serie/<slug>-Form bringen."""
    base = get_base_url(normalize_series_url(url))
    return base.replace("/serie/stream/", "/serie/", 1)


def _sto_episode_url(url: str) -> str:
    """serienstream-Episoden-URL auf /serie/<slug>/staffel-N/episode-M normalisieren."""
    return str(url or "").replace("/serie/stream/", "/serie/", 1)


def _series_obj(url: str):
    """Baut das passende Serien-Modell (ohne Fetch – Properties laden lazy)."""
    normalized = normalize_series_url(url)
    if is_aniworld(normalized):
        return AniworldSeries(get_base_url(normalized))
    if is_sto(normalized):
        return SerienstreamSeries(_sto_series_url(normalized))
    return None


def _episode_obj(episode_url: str):
    """Baut das passende Episoden-Modell."""
    if is_aniworld(episode_url):
        return AniworldEpisode(url=episode_url)
    if is_sto(episode_url):
        return SerienstreamEpisode(_sto_episode_url(episode_url))
    # Fallback: normalisieren und erneut prüfen (z.B. s.to-Domain ohne 'serienstream')
    norm = normalize_series_url(episode_url)
    if is_sto(norm):
        return SerienstreamEpisode(_sto_episode_url(episode_url))
    return None


def _clean_text(text: Optional[str]) -> str:
    r"""Normalisiert jeden Titel-/Beschreibungstext aus dem `aniworld`-Modul.

    Das Modul entschärft HTML-Entities nur an EINIGEN Stellen: AniWorlds
    Serientitel laufen durch ``html.unescape`` (models/aniworld_to/series.py:233),
    serienstreams Serientitel (models/s_to/series.py:188), AniWorlds
    Episodentitel (models/aniworld_to/season.py:272/281/287) und die Suchtreffer
    (search.py:349) dagegen NICHT. Dadurch kam z.B. "Widow&#039;s Bay" statt
    "Widow's Bay" in der Datenbank und im Ordnernamen an.

    Deshalb wird hier – an der einzigen Stelle, an der Modultexte in AniLoader
    eintreten – einheitlich aufgeräumt:
      1. ``<em>``-Markup der Suchtreffer entfernen (vor dem Entschärfen, damit
         echte ``&lt;em&gt;``-Texte nicht nachträglich zu Markup werden),
      2. HTML-Entities auflösen ("&#039;" → "'", "&amp;" → "&"),
      3. Whitespace normalisieren – ``&nbsp;`` wird beim Entschärfen zu U+00A0
         und landet sonst unsichtbar in Ordner- und Dateinamen (``\s`` deckt
         das mit ab), ebenso Tabs/Zeilenumbrüche aus dem HTML.
    """
    value = str(text or "").replace("<em>", "").replace("</em>", "")
    value = _html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _num_from_url(url: str) -> Optional[int]:
    """Extrahiert die Episoden-/Filmnummer aus einer URL (rein, kein HTTP)."""
    m = re.search(r"/staffel-\d+/episode-(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"/filme/film-(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"/episode-(\d+)", url)
    if m:
        return int(m.group(1))
    return None


# ──────────────────────── Serien-Titel / Poster ────────────────────────


def get_series_title(url: str) -> Optional[str]:
    """Extrahiert den Serien-Titel."""
    try:
        series = _series_obj(url)
        if series is None:
            return None
        title = _clean_text(series.title) or None
        debug(f"[SCRAPER] Titel für {url}: {title!r}")
        return title
    except Exception as e:
        log(f"[SCRAPER] Titel-Fehler für {url}: {e}")
        return None


def get_poster_url(url: str) -> Optional[str]:
    """Extrahiert die Cover-Bild-URL (Poster)."""
    try:
        series = _series_obj(url)
        if series is None:
            return None
        poster = series.poster_url
        if not poster:
            return None
        poster = str(poster)
        if not poster.startswith("http"):
            # Relative Poster-URL → gegen die kanonische Domain der Plattform auflösen
            poster = urljoin(canonical_origin(normalize_series_url(url)), poster)
        return poster
    except Exception as e:
        log(f"[SCRAPER] Poster-Fehler für {url}: {e}")
        return None


# ──────────────────────── Staffel-Nummern ────────────────────────


def get_season_numbers(url: str) -> List[int]:
    """
    Gibt eine Liste der verfügbaren Staffel-Nummern zurück.
    0 wird für Filme verwendet (falls vorhanden).
    """
    try:
        series = _series_obj(url)
        if series is None:
            return []
        numbers = set()
        for season in series.seasons:
            try:
                numbers.add(int(season.season_number))
            except Exception:
                continue
        # AniWorld: Filme werden als season_number 0 geführt; absichern über has_movies.
        if is_aniworld(normalize_series_url(url)):
            try:
                if getattr(series, "has_movies", False):
                    numbers.add(0)
            except Exception:
                pass
        found = sorted(numbers)
        debug(f"[SCRAPER] Staffeln für {url}: {found}")
        return found
    except Exception as e:
        log(f"[SCRAPER] Staffeln-Fehler für {url}: {e}")
        return []


def has_movies(url: str) -> bool:
    """Prüft ob die Serie Filme hat."""
    return 0 in get_season_numbers(url)


# ──────────────── Episoden pro Staffel ──────────────────


def get_episodes_for_season(base_url: str, season: int) -> List[Dict]:
    """
    Gibt für eine Staffel alle Episoden zurück – mit genau EINEM HTTP-Fetch
    (Staffelseite). Die Sprach-Verfügbarkeit ("languages") wird hier bewusst
    NICHT geladen (leer), sondern erst bei Bedarf pro Episode über
    get_episode_languages/is_episode_available (je 1 Fetch).

    Returns:
        Liste von Dicts: {"episode": int, "title_de": str, "title_en": str,
                          "url": str, "languages": []}
    """
    base = base_url if (is_aniworld(base_url) or is_sto(base_url)) else get_base_url(base_url)

    if season == 0:
        season_url = build_film_url(base)
    else:
        season_url = build_season_url(base, season)

    try:
        if is_aniworld(base):
            season_obj = AniworldSeason(season_url)
            episodes = season_obj.episodes  # 1 Fetch; Nr.+Titel kommen von der Staffelseite
            result: List[Dict] = []
            for ep in episodes:
                num = ep.episode_number
                if num is None:
                    num = _num_from_url(ep.url)
                result.append({
                    "episode": int(num) if num is not None else 0,
                    "title_de": _clean_text(ep.title_de),
                    "title_en": _clean_text(ep.title_en),
                    "url": ep.url,
                    "languages": [],
                })
            return result

        if is_sto(base):
            # Serie explizit übergeben, um die fragile interne Serien-URL-Ableitung
            # des Moduls zu umgehen.
            series_obj = SerienstreamSeries(_sto_series_url(base))
            season_obj = SerienstreamSeason(season_url, series=series_obj)
            episodes = season_obj.episodes  # 1 Fetch; nur URLs
            result = []
            for ep in episodes:
                num = _num_from_url(ep.url)
                result.append({
                    "episode": num if num is not None else 0,
                    # serienstream liefert Titel nur pro Episoden-Fetch – hier bewusst
                    # leer, um Request-Explosion beim Enumerieren zu vermeiden.
                    "title_de": "",
                    "title_en": "",
                    "url": ep.url,
                    "languages": [],
                })
            return sorted(result, key=lambda x: x["episode"])

    except Exception as e:
        label = "Filme" if season == 0 else f"Staffel {season}"
        log(f"[SCRAPER] Episoden-Fehler für {base} {label}: {e}")
        return []

    return []


# ──────────────────────── Episode-Titel ────────────────────────


def get_episode_title(episode_url: str) -> Optional[str]:
    """Extrahiert den (deutschen) Episoden-Titel. Löst 1 Fetch aus."""
    try:
        ep = _episode_obj(episode_url)
        if ep is None:
            return None
        title = _clean_text(ep.title_de) or None
        debug(f"[SCRAPER] Episodentitel für {episode_url}: {title!r}")
        return title
    except Exception as e:
        log(f"[SCRAPER] Episodentitel-Fehler für {episode_url}: {e}")
        return None


# ──────────────── Sprachen / Verfügbarkeit (je 1 Fetch pro Episode) ────────────────


def get_episode_languages(episode_url: str) -> List[str]:
    """
    Verfügbare Sprachen einer Episode als AniLoader-Labels
    ("German Dub"/"German Sub"/"English Sub"/"English Dub").
    Löst genau 1 HTTP-Fetch (Episoden-Seite) aus.
    """
    try:
        ep = _episode_obj(episode_url)
        if ep is None:
            return []
        labels = available_labels(ep.provider_data)
        debug(f"[SCRAPER] Sprachen für {episode_url}: {labels}")
        return labels
    except Exception as e:
        log(f"[SCRAPER] Sprachen-Fehler für {episode_url}: {e}")
        return []


def is_episode_available(episode_url: str) -> bool:
    """
    Prüft, ob eine Episode echte Streams hat (kein Ankündigungs-Placeholder).
    Verfügbar ⇔ provider_data enthält mindestens einen Hoster/eine Sprache.
    Im Fehlerfall True (im Zweifel nicht überspringen). Löst 1 Fetch aus.
    """
    try:
        ep = _episode_obj(episode_url)
        if ep is None:
            return True
        return is_available(ep.provider_data)
    except Exception as e:
        log(f"[SCRAPER] Verfügbarkeits-Check fehlgeschlagen für {episode_url}: {e}")
        return True


# ──────────────────────── Suche ────────────────────────


def search_anime(query: str, platform: str = "both", log_search: bool = False) -> List[Dict]:
    """
    Sucht nach Serien/Animes über die Modul-Suchfunktionen (aniworld.search).

    Args:
        query: Suchbegriff
        platform: "aniworld" | "sto" | "both"
        log_search: Loggt bei aktiver Suche die Ergebnisanzahlen

    Returns:
        Liste von Dicts: [{"title","url","description","platform"}]
    """
    aniworld_results: List[Dict] = []
    sto_results: List[Dict] = []

    if platform in ("aniworld", "both"):
        try:
            data = _aw_search.query(query) or []
            for item in data:
                link = item.get("link", "") or ""
                if "/anime/stream/" in link:
                    full_url = link if link.startswith("http") else f"{canonical_origin(ANIWORLD)}{link}"
                    aniworld_results.append({
                        "title": _clean_text(item.get("title")),
                        "url": full_url,
                        "description": _clean_text(item.get("description")),
                        "platform": "AniWorld",
                    })
        except Exception as e:
            log(f"[SUCHE] AniWorld-Fehler: {e}")

    if platform in ("sto", "both"):
        try:
            shows = _aw_search.query_s_to(query) or []
            for show in shows:
                link = show.get("link", "") or ""  # bereits normalisiert: /serie/<slug>
                if not link:
                    continue
                full_url = f"{canonical_origin(SERIENSTREAM)}{link}" if link.startswith("/") else link
                sto_results.append({
                    "title": _clean_text(show.get("title")),
                    "url": full_url,
                    "description": "",
                    "platform": canonical_host(SERIENSTREAM),
                })
        except Exception as e:
            log(f"[SUCHE] serienstream.to-Fehler: {e}")

    # Ergebnisse abwechselnd mischen (AniWorld, serienstream.to, …)
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
        log(f"[SUCHE] AniWorld: {len(aniworld_results)}, serienstream.to: {len(sto_results)}")

    return results


# ──────────────────────── Komplette Serien-Info ────────────────────────


def get_series_info(url: str) -> Dict:
    """Sammelt alle Informationen zu einer Serie in einem Aufruf."""
    base_url = get_base_url(url)
    title = get_series_title(url)
    season_numbers = get_season_numbers(url)

    info: Dict = {
        "title": title,
        "url": base_url,
        "has_movies": 0 in season_numbers,
        "seasons": {},
    }

    for s_num in season_numbers:
        info["seasons"][s_num] = get_episodes_for_season(base_url, s_num)

    return info
