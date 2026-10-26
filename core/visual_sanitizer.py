"""Saneamiento de búsquedas visuales y aislamiento temático.

Problema real detectado en producción: el director puede contaminar las
consultas con títulos de anime ("Black Clover") aunque el tema sea tecnología.
Eso hace que el buscador descargue wallpapers de anime en un canal de IA.

Este módulo garantiza, antes del render:
- Ninguna consulta visual contiene términos de anime/manga/wallpapers.
- Las consultas de tecnología buscan metraje/fotografía REAL y añaden
  exclusiones explícitas (-anime, -manga, -illustration).
- Si una consulta era basura, se sustituye por una consulta técnica segura
  derivada de la escena.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, List

ANIME_TERMS = (
    "anime", "manga", "otaku", "waifu", "shonen", "shounen", "isekai", "fanart",
    "black clover", "naruto", "one piece", "dragon ball", "demon slayer",
    "jujutsu kaisen", "my hero academia", "attack on titan", "sailor moon",
    "moewalls", "pixiv", "danbooru", "gelbooru", "konachan", "zerochan",
    "deviantart", "live wallpaper", "wallpaper anime",
)

TECH_TERMS = (
    "tecnolog", "inteligencia artificial", " ia ", "software", "hardware",
    "microchip", "chip", "servidor", "datacenter", "data center", "openai",
    "nvidia", "google", "microsoft", "robot", "algoritmo", "modelo de lenguaje",
)

TECH_HINTS = (
    "ai", "artificial", "intelligence", "server", "datacenter", "data center",
    "chip", "semiconductor", "software", "code", "technology", "robot", "model",
    "cloud", "gpu", "computer", "cyber", "network", "quantum", "keynote",
    "developer", "algorithm", "openai", "nvidia", "microsoft", "google",
)

TECH_QUERIES = (
    "data center server racks artificial intelligence 4k real footage",
    "silicon microchip wafer closeup real photograph",
    "software engineer code screen office real footage",
    "technology keynote conference stage real footage",
    "cloud computing servers night real footage",
)

GENERIC_QUERIES = (
    "documentary real footage 4k",
    "archive news report real footage",
    "press conference real footage",
    "historical archive photograph documentary",
)

_NEGATIVE = "-anime -manga -illustration -cartoon -wallpaper -fanart -stock -vector -clipart"
_STOP = {
    "el", "la", "los", "las", "un", "una", "de", "del", "al", "en", "y", "o", "que",
    "por", "para", "con", "sin", "sobre", "entre", "es", "son", "fue", "como", "su",
    "sus", "se", "lo", "le", "les", "no", "mas", "pero", "cuando", "donde", "esta",
    "este", "estos", "estas", "muy", "ya", "the", "and", "of", "to", "in", "on",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def is_anime_query(query: str) -> bool:
    low = _norm(query)
    # Ignorar las exclusiones negativas (-anime, -wallpaper, ...) al detectar.
    low = re.sub(
        r"-(anime|manga|illustration|cartoon|wallpaper|fanart|stock|vector|clipart|otaku)",
        " ",
        low,
    )
    return any(term in low for term in ANIME_TERMS)


def _is_tech(topic: str, origin: str) -> bool:
    low = f" {_norm(topic)} {_norm(origin)} "
    return any(term in low for term in TECH_TERMS)


def _scene_terms(scene: Any, limit: int = 4) -> str:
    speech = _norm(getattr(scene, "speech", "") or "")
    name = _norm(getattr(scene, "name", "") or "")
    words: List[str] = []
    for token in re.findall(r"[a-z0-9áéíóúñ]{4,}", f"{name} {speech}"):
        if token in _STOP or token in words:
            continue
        words.append(token)
        if len(words) >= limit:
            break
    return " ".join(words)


def _fallback_query(scene: Any, index: int, tech: bool) -> str:
    terms = _scene_terms(scene)
    if tech:
        base = TECH_QUERIES[index % len(TECH_QUERIES)]
        return f"{base} {_NEGATIVE}".strip()
    base = GENERIC_QUERIES[index % len(GENERIC_QUERIES)]
    return f"{terms} {base} {_NEGATIVE}".strip()


def _harden(query: str, tech: bool) -> str:
    clean = re.sub(r"\s+", " ", str(query or "")).strip()
    low = clean.lower()
    if "-anime" not in low:
        clean = f"{clean} real footage {_NEGATIVE}"
    elif tech and "real" not in low:
        clean = f"{clean} real footage"
    return clean


def _clean_beats(beats: Iterable[Any]) -> int:
    changed = 0
    for beat in beats or []:
        if not isinstance(beat, dict):
            continue
        query = str(beat.get("query", "") or "")
        if is_anime_query(query):
            # Sin consulta we no podemos inventar el tema: se elimina el beat.
            beat["query"] = ""
            changed += 1
    return changed


def sanitize_plan_visuals(plan: Any, topic: str = "", origin: str = "") -> int:
    """Limpia las consultas del plan. Devuelve cuántas se corrigieron."""
    tech = _is_tech(topic, origin)
    changed = 0
    for index, scene in enumerate(getattr(plan, "scenes", []) or []):
        for attr in ("visual_query", "visual_query2"):
            query = str(getattr(scene, attr, "") or "")
            if not query:
                continue
            if is_anime_query(query):
                setattr(scene, attr, _fallback_query(scene, index, tech))
                changed += 1
            elif tech and not any(hint in _norm(query) for hint in TECH_HINTS):
                setattr(scene, attr, _fallback_query(scene, index, tech))
                changed += 1
            else:
                hardened = _harden(query, tech)
                if hardened != query:
                    setattr(scene, attr, hardened)
                    changed += 1
        changed += _clean_beats(getattr(scene, "visual_beats", None) or [])
    return changed
