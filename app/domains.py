"""
AniLoader – Domain-Registry.

Alle bekannten Domains der unterstützten Plattformen an EINER Stelle. Die Seiten
ziehen regelmäßig um; ein Umzug soll deshalb eine Konfigurationsänderung sein und
keine Code-Suche quer durchs Projekt.

Konfigurierbar über ``data/config.yaml``:

    domains:
      aniworld:
        canonical: aniworld.to
        aliases: []
      serienstream:
        canonical: serienstream.to
        aliases:
          - serienstream.cx
          - 186.2.175.5
          - s.to

Regeln:
  * ``canonical`` ist die EINZIGE Domain, die je ausgegeben oder gespeichert wird.
  * ``aliases`` werden ausschließlich als Eingabe akzeptiert und sofort auf die
    kanonische Domain normalisiert (alte Links, Mirrors, IP-Adressen).
  * Ein neuer Mirror wird einfach unter ``aliases`` ergänzt – kein Code-Eingriff.

⚠ ``canonical`` kann NICHT frei gewählt werden – die aniworld-Library kennt ihre
  Hosts hartkodiert, und zwar an drei Stellen mit unterschiedlicher Wirkung:

  * ``aniworld/config.py`` → ``_STO_HOST`` / ``ANIWORLD_*_PATTERN``: die Modelle
    VALIDIEREN jede URL im Konstruktor. Ein hier eingetragener Host, den die
    Library nicht kennt, führt zu ``ValueError: Invalid ... URL`` – die Serie
    lässt sich dann gar nicht mehr laden.
  * ``aniworld/models/s_to/http.py`` → ``STO_DOMAINS``/``STO_IP``: serienstream-
    Requests laufen über ``sto_get()``, das JEDE serienstream-URL auf den
    aktiven Host umschreibt. Die hier konfigurierte Domain bestimmt also NICHT,
    welcher Host tatsächlich abgefragt wird – die Library probiert immer erst
    serienstream.to, dann serienstream.cx, und die IP nur als letzten Ausweg.
    (AniWorld verhält sich anders: dort geht der Request an die URL, die wir
    übergeben.)
  * ``aniworld/cf_bypass.py`` → ``_CF_BYPASS_DOMAINS``: nur ``s.to`` und
    ``serienstream.to`` bekommen den Cloudflare-Bypass.

  Kurz: ``aliases`` erfüllen ihren Zweck (Eingabe-Normalisierung alter Links),
  ``canonical`` muss aber ein Host bleiben, den die Library bereits kennt.
"""

import re
from typing import Dict, List, Optional

from .logger import log

# Plattform-Bezeichner. Bewusst domain-unabhängig: sie stecken auch im
# series_key, der einen Domain-Wechsel überleben muss.
ANIWORLD = "aniworld"
SERIENSTREAM = "serienstream"

# Standard-Registry – über config.yaml überschreibbar.
DEFAULT_DOMAINS: Dict[str, Dict] = {
    ANIWORLD: {
        "canonical": "aniworld.to",
        "aliases": [],
    },
    SERIENSTREAM: {
        "canonical": "serienstream.to",
        # Reine Eingabe-Aliase. s.to steht hier nur, damit alte Links und
        # Alt-Einträge weiter funktionieren – ausgegeben wird es nie.
        "aliases": ["serienstream.cx", "186.2.175.5", "s.to"],
    },
}

# Pfadform je Plattform: (kanonischer Pfad, akzeptierte Pfad-Varianten als Regex)
_PLATFORM_PATHS: Dict[str, tuple] = {
    ANIWORLD: ("anime/stream", r"anime/stream"),
    SERIENSTREAM: ("serie", r"serie(?:/stream)?"),
}

_cache: Optional[Dict[str, Dict]] = None
_loading = False  # Schutz gegen Re-Entrance über load_config()


def _clean_hosts(entry: Dict) -> List[str]:
    """canonical + aliases als deduplizierte Hostliste (Reihenfolge bleibt)."""
    canonical = str(entry.get("canonical") or "").strip()
    aliases = [str(a).strip() for a in (entry.get("aliases") or []) if str(a).strip()]

    hosts: List[str] = []
    seen: set = set()
    for host in [canonical] + aliases:
        key = host.lower()
        if host and key not in seen:
            seen.add(key)
            hosts.append(host)
    return hosts


def _build(cfg_domains: Optional[Dict]) -> Dict[str, Dict]:
    """Baut die Registry inkl. vorkompilierter Regex-Muster."""
    built: Dict[str, Dict] = {}

    for platform, defaults in DEFAULT_DOMAINS.items():
        entry = {"canonical": defaults["canonical"], "aliases": list(defaults["aliases"])}

        override = (cfg_domains or {}).get(platform) or {}
        if isinstance(override, dict):
            if str(override.get("canonical") or "").strip():
                entry["canonical"] = str(override["canonical"]).strip()
            if isinstance(override.get("aliases"), list):
                entry["aliases"] = [str(a).strip() for a in override["aliases"] if str(a).strip()]

        hosts = _clean_hosts(entry)
        host_re = "|".join(re.escape(h) for h in hosts)
        canonical_path, path_re = _PLATFORM_PATHS[platform]

        built[platform] = {
            "canonical": entry["canonical"],
            "aliases": entry["aliases"],
            "hosts": hosts,
            "canonical_path": canonical_path,
            # https://<host>/<pfad>/<slug>  – Slug ist Gruppe 1
            "series_re": re.compile(
                rf"^https?://(?:www\.)?(?:{host_re})/{path_re}/([^/?#]+)",
                re.IGNORECASE,
            ),
            # Host-Erkennung mit Grenzen, damit kein Teilstring-Treffer entsteht
            "host_re": re.compile(
                rf"(?:^|//)(?:www\.)?(?:{host_re})(?=[:/?#]|$)",
                re.IGNORECASE,
            ),
        }

    return built


def get_domains(force_reload: bool = False) -> Dict[str, Dict]:
    """Gibt die (gecachte) Domain-Registry zurück."""
    global _cache, _loading

    if _cache is not None and not force_reload:
        return _cache

    # Re-Entrance: get_domains() → load_config() → … → get_domains()
    if _loading:
        return _build(None)

    cfg_domains = None
    _loading = True
    try:
        from .config import load_config  # verzögert: config importiert dieses Modul
        cfg_domains = load_config().get("domains")
    except Exception as e:
        log(f"[DOMAINS] Konfiguration nicht lesbar, nutze Standard-Domains: {e}")
    finally:
        _loading = False

    _cache = _build(cfg_domains)
    return _cache


def reload_domains() -> None:
    """Cache verwerfen – nach dem Speichern der Konfiguration aufrufen."""
    get_domains(force_reload=True)
    log(f"[DOMAINS] Registry neu geladen: "
        + " | ".join(f"{p}={', '.join(e['hosts'])}" for p, e in (_cache or {}).items()))


# ──────────────────────── URL-Hilfsfunktionen (rein, kein HTTP) ────────────────────────


def detect_platform(url: str) -> Optional[str]:
    """Ermittelt die Plattform einer URL ('aniworld' | 'serienstream' | None)."""
    text = str(url or "")
    for platform, entry in get_domains().items():
        if entry["host_re"].search(text):
            return platform
    return None


def is_known(url: str) -> bool:
    """True, wenn die URL zu einer der konfigurierten Plattformen gehört."""
    return detect_platform(url) is not None


def is_aniworld(url: str) -> bool:
    return detect_platform(url) == ANIWORLD


def is_serienstream(url: str) -> bool:
    return detect_platform(url) == SERIENSTREAM


def canonical_host(platform: str) -> str:
    """Kanonische Domain einer Plattform, z.B. 'serienstream.to'."""
    entry = get_domains().get(platform)
    return entry["canonical"] if entry else ""


def canonical_origin(url_or_platform: str) -> str:
    """
    Gibt 'https://<kanonische Domain>' zurück – für Referer und relative Bild-URLs.

    Akzeptiert einen Plattformnamen oder eine beliebige URL der Plattform.
    """
    platform = url_or_platform if url_or_platform in DEFAULT_DOMAINS else detect_platform(url_or_platform)
    host = canonical_host(platform) if platform else ""
    return f"https://{host}" if host else ""


def canonical_series_url(platform: str, slug: str) -> str:
    """Baut die kanonische Serien-URL aus Plattform und Slug."""
    entry = get_domains()[platform]
    return f"https://{entry['canonical']}/{entry['canonical_path']}/{slug}"


def normalize_series_url(url: str) -> str:
    """
    Normalisiert bekannte Serien-URL-Varianten auf die kanonische Form.

    Aliase (s.to, serienstream.cx, IP-Mirror, /serie/stream/…) werden dabei
    auf die konfigurierte kanonische Domain umgeschrieben.
    """
    value = str(url or "").strip()

    for platform, entry in get_domains().items():
        m = entry["series_re"].match(value)
        if m:
            return canonical_series_url(platform, m.group(1))

    return value


def get_series_key(url: str) -> Optional[str]:
    """
    Stabiler Key pro Serie: '<plattform>:<slug>'.

    Bewusst ohne Domain – so überlebt der Key einen Domain-Wechsel und die
    Duplikaterkennung bleibt intakt.
    """
    value = str(url or "").strip()

    for platform, entry in get_domains().items():
        m = entry["series_re"].match(value)
        if m:
            return f"{platform}:{m.group(1).lower()}"

    return None


def get_base_url(url: str) -> str:
    """Extrahiert die kanonische Serien-Basis-URL (ohne Staffel/Episode)."""
    value = str(url or "").strip()

    for platform, entry in get_domains().items():
        m = entry["series_re"].match(value)
        if m:
            return canonical_series_url(platform, m.group(1))

    return value
