"""
AniLoader – Session-Injektion & Sprach-Adapter für das `aniworld`-Modul.

Hintergrund
-----------
Das `aniworld`-Modul führt ALLE HTTP-Requests über eine modul-globale
niquests-Session aus: ``aniworld.config.GLOBAL_SESSION`` (config.py:96),
fest verdrahtet auf ``resolver=["doh+google://"]`` – OHNE System-DNS-Fallback.

WICHTIG (verifiziert am Modul-Quellcode): Die Modelle importieren die Session
per ``from ...config import GLOBAL_SESSION`` auf MODULEBENE, z. B.
``models/aniworld_to/series.py:4`` und nutzen sie als ``GLOBAL_SESSION.get(url)``
(series.py:94, season.py:79, episode.py:347; analog s_to). Dadurch hält jedes
Modell eine EIGENE Namensbindung an das ursprüngliche Session-Objekt.
Ein bloßes Neuzuweisen von ``aniworld.config.GLOBAL_SESSION = neu`` wirkt daher
NICHT auf die bereits importierten Modelle – sie würden weiter die alte
DoH-only-Session verwenden.

Lösung: ``install_session`` patcht ``GLOBAL_SESSION`` in ALLEN geladenen
``aniworld``-Modulen (via ``sys.modules``) UND in ``config`` (für später lazy
importierte Module). Damit greift AniLoaders DoH+System-DNS-Fallback-Session
tatsächlich für die Modell-Requests.
"""

import sys
import threading
from typing import List, Optional

from niquests import Session

from aniworld import config as _aw_config
from aniworld.config import (  # verifiziert: config.py:161/181/201/208/225
    LANG_KEY_MAP,
    LANG_LABELS,
    INVERSE_LANG_KEY_MAP,
)

from .logger import log

# ──────────────────────── Session-Bau & Injektion ────────────────────────

# Die zuletzt injizierte Session. Wird über get_shared_session() auch von
# Aufrufern ausserhalb des Scrapers genutzt (Poster-Proxy, Discord-Webhook):
# niquests.get()/post() auf Modulebene bauen pro Aufruf eine NEUE Session mit
# eigenem Resolver-Pool auf. Jeder urllib3-future ConnectionPool hält dabei einen
# Background-Monitoring-Thread, der ausschliesslich über close() endet –
# wiederholte Aufrufe lassen also dauerhaft Threads zurück, bis der Container
# keine neuen mehr starten kann ("RuntimeError: can't start new thread").
_installed_session: Optional[Session] = None
_session_lock = threading.Lock()


def _close_session_quietly(session: Optional[Session]) -> None:
    """Gibt die Pools einer verworfenen Session frei.

    Eine Session einfach zu dereferenzieren lässt ihre Pool-Monitoring-Threads
    für die restliche Prozesslaufzeit zurück – nur close() beendet sie.
    """
    if session is None:
        return
    try:
        session.close()
    except Exception as exc:  # noqa: BLE001 – Aufräumen darf nie hart failen
        log(f"[ANIWORLD] Session-Close fehlgeschlagen: {exc}")


def build_session() -> Session:
    """Baut eine niquests-Session mit DoH und System-DNS-Fallback.

    niquests akzeptiert eine Resolver-Liste; Ziel ist DoH (Anti-Sperre) mit
    automatischem Rückfall auf System-DNS in restriktiven Netzen (AniLoaders
    dokumentierter Anwendungsfall). Falls die Resolver-Liste vom installierten
    niquests nicht akzeptiert wird, fällt der Bau auf eine reine System-DNS-
    Session zurück (Robustheit vor Anti-Sperre).

    [unsicher] Das exakte Failover-Verhalten der niquests-Resolver-Liste
    (DoH → System) ist noch nicht gegen einen echten DNS-Ausfall verifiziert;
    die Konstruktion selbst wird im Smoke-Test geprüft.
    """
    try:
        session = Session(resolver=["doh+google://", "system://"])
        log("[ANIWORLD] Session gebaut: DoH+System-DNS-Fallback (Resolver-Liste)")
        return session
    except Exception as exc:  # noqa: BLE001 – bewusst breit: Bau darf nie hart failen
        log(f"[ANIWORLD] Resolver-Liste nicht akzeptiert ({exc}) – nutze System-DNS")
        return Session()


def install_session(session: Optional[Session] = None) -> Session:
    """Injiziert ``session`` als ``GLOBAL_SESSION`` in alle aniworld-Module.

    Muss aufgerufen werden, NACHDEM ``aniworld`` (inkl. Modelle) importiert ist.
    Patcht sowohl ``aniworld.config`` (für später lazy importierte Module) als
    auch jedes bereits geladene ``aniworld.*``-Modul, das ``GLOBAL_SESSION``
    per Namen gebunden hat.

    Returns:
        die injizierte Session.
    """
    global _installed_session

    if session is None:
        session = build_session()

    _aw_config.GLOBAL_SESSION = session

    patched: List[str] = []
    for name, mod in list(sys.modules.items()):
        if name != "aniworld" and not name.startswith("aniworld."):
            continue
        if mod is None:
            continue
        if hasattr(mod, "GLOBAL_SESSION"):
            setattr(mod, "GLOBAL_SESSION", session)
            patched.append(name)

    with _session_lock:
        previous, _installed_session = _installed_session, session

    # Die abgeloeste Session schliessen – sonst bleiben ihre Pool-Threads liegen.
    if previous is not None and previous is not session:
        _close_session_quietly(previous)

    log(f"[ANIWORLD] GLOBAL_SESSION injiziert in {len(patched)} Modul(e)")
    return session


def get_shared_session() -> Session:
    """Gemeinsame HTTP-Session für Aufrufer ausserhalb des `aniworld`-Moduls.

    Wichtig für alles, was wiederholt HTTP macht (Poster-Proxy, Discord-Webhook):
    statt pro Aufruf eine neue niquests-Session samt Resolver-Pool aufzubauen,
    deren Monitoring-Threads nie freigegeben werden, teilen sich alle Aufrufer
    dieselbe – bereits in die aniworld-Module injizierte – Session.
    """
    with _session_lock:
        if _installed_session is not None:
            return _installed_session

    # Noch nicht injiziert (z.B. Import-Reihenfolge) – jetzt nachholen.
    return install_session()


# ──────────────────────── Sprach-Adapter ────────────────────────
# AniLoader spricht in Labels ("German Dub"/"German Sub"/"English Sub"/
# "English Dub"). Das Modul kodiert Sprachen als (Audio, Subtitles)-Enum-Tupel
# und liefert verfügbare Sprachen als Keys von ProviderData._data.


# ⚠ Das Modul hat ZWEI unterschiedliche Enum-Paare für denselben Zweck:
#   * ``aniworld.config.Audio/Subtitles``            – Basis von LANG_KEY_MAP und
#                                                      von AniWorlds ProviderData
#   * ``aniworld.models.s_to.episode.Audio/Subtitles`` – lokal definierte Enums,
#                                                      die serienstream in seine
#                                                      provider_data-Keys legt
# Enum-Member verschiedener Klassen sind NIE gleich (Enum.__eq__ vergleicht die
# Identität, nicht den Wert). Ein Lookup eines serienstream-Tupels in
# INVERSE_LANG_KEY_MAP liefert deshalb immer None – für serienstream käme sonst
# eine leere Sprachliste zurück und jede Episode gälte als "nicht verfügbar".
# Darum wird zusätzlich über die Enum-WERTE ("German"/"None") aufgelöst; das ist
# klassenunabhängig und deckt beide Varianten ab.


def _lang_values(lang_tuple) -> Optional[tuple]:
    """(Audio, Subtitles)-Tupel → reines Wertepaar, z.B. ``("German", "None")``."""
    if not isinstance(lang_tuple, (tuple, list)) or len(lang_tuple) != 2:
        return None
    return tuple(getattr(part, "value", part) for part in lang_tuple)


# Wertebasierte Umkehrung von LANG_KEY_MAP – die vier Wertepaare sind eindeutig.
_VALUES_TO_KEY = {_lang_values(tpl): key for key, tpl in LANG_KEY_MAP.items()}


def tuple_to_label(lang_tuple) -> Optional[str]:
    """(Audio, Subtitles)-Tupel → AniLoader-Label, oder None.

    Akzeptiert sowohl die config-Enums (AniWorld) als auch die lokalen
    s_to-Enums (serienstream) – siehe Erklärung oben.
    """
    try:
        key = INVERSE_LANG_KEY_MAP.get(lang_tuple)
    except TypeError:  # nicht hashbar (z.B. Liste statt Tupel)
        key = None
    if key is None:
        key = _VALUES_TO_KEY.get(_lang_values(lang_tuple))
    return LANG_LABELS.get(key) if key else None


def label_to_tuple(label: str):
    """AniLoader-Label → (Audio, Subtitles)-Tupel, oder None."""
    key = None
    for k, lbl in LANG_LABELS.items():
        if lbl == label:
            key = k
            break
    return LANG_KEY_MAP.get(key) if key else None


def _provider_dict(provider_data) -> dict:
    """Liefert das zugrundeliegende ``{(Audio,Subtitles): {provider: url}}``-Dict.

    Robust gegen beide Modul-Varianten: AniWorld liefert ein ``ProviderData``-
    Objekt (Attribut ``_data``), serienstream.to liefert ein rohes ``dict``.
    """
    data = getattr(provider_data, "_data", None)
    if isinstance(data, dict):
        return data
    if isinstance(provider_data, dict):
        return provider_data
    return {}


def available_labels(provider_data) -> List[str]:
    """AniLoader-Labels aller in einem provider_data verfügbaren Sprachen.

    Verfügbare Sprachen = Keys des Provider-Dicts (leer ⇒ Episode ist eine
    Ankündigung ohne Streams).
    """
    labels: List[str] = []
    for lang_tuple in _provider_dict(provider_data).keys():
        lbl = tuple_to_label(lang_tuple)
        if lbl and lbl not in labels:
            labels.append(lbl)
    return labels


def is_available(provider_data) -> bool:
    """True, wenn mindestens ein Hoster/eine Sprache verfügbar ist."""
    return bool(_provider_dict(provider_data))
