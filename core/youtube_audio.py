"""Gestor de la Biblioteca de Audio de YouTube (YouTube Audio Library).

Permite utilizar pistas de música de fondo (BGM) y efectos de sonido (SFX)
100% libres de derechos y reclamos de Content ID de YouTube.

Estructura de almacenamiento:
assets/audio/youtube_library/
├── bgm/
│   ├── cinematic/
│   ├── tension/
│   ├── upbeat/
│   ├── ambient/
│   └── lofi/
└── sfx/
    ├── transitions/  (whooshes, swooshes, wipes)
    ├── impacts/      (booms, sub-drops, hits)
    ├── alerts/       (notificaciones, breaking news stingers)
    ├── chimes/       (campanadas, aciertos, dings)
    └── ui/           (clicks, pops, badges)
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from core.llm import safe_log

# Extensiones de audio soportadas
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}

YOUTUBE_LIBRARY_DIR = settings.BASE_DIR / "assets" / "audio" / "youtube_library"
LIB_DIR = YOUTUBE_LIBRARY_DIR
YOUTUBE_BGM_DIR = YOUTUBE_LIBRARY_DIR / "bgm"
YOUTUBE_SFX_DIR = YOUTUBE_LIBRARY_DIR / "sfx"
ORIGINAL_AUDIO_DIR = settings.BASE_DIR / "assets" / "audio" / "original"
ORIGINAL_BGM_DIR = ORIGINAL_AUDIO_DIR / "bgm"

# Mapeo de sinónimos de moods/categorías de YouTube Studio
MOOD_ALIASES: Dict[str, List[str]] = {
    "tension": ["tension", "suspense", "dark", "dramatic", "breaking", "thriller", "news"],
    "cinematic": ["cinematic", "epic", "orchestral", "documentary", "movie", "soundtrack"],
    "upbeat": ["upbeat", "energetic", "happy", "electronic", "dance", "bright", "action"],
    "ambient": ["ambient", "calm", "chill", "relaxing", "atmospheric", "meditation"],
    "lofi": ["lofi", "lo-fi", "chillhop", "beat", "study"],
    "spiritual": ["spiritual", "fe", "faith", "esperanza", "hope", "dios", "god", "religioso", "worship", "oracion", "oración", "biblia", "cristiano", "christian", "emotivo"],
}

# Mapeo de categorías de SFX
SFX_CATEGORY_MAP: Dict[str, List[str]] = {
    "whoosh": ["transitions", "whoosh", "swoosh", "wipe"],
    "transition": ["transitions", "whoosh", "swoosh"],
    "impact": ["impacts", "impact", "boom", "hit", "thud"],
    "boom": ["impacts", "boom"],
    "riser": ["impacts", "riser", "transitions"],
    "alert": ["alerts", "alert", "stinger", "news"],
    "chime": ["chimes", "chime", "ding", "bell", "success"],
    "pop": ["ui", "pop", "click", "tap"],
    "paper": ["ui", "paper"],
    "marker": ["ui", "marker"],
}


def _search_original_bgm(key: str) -> Optional[Path]:
    """Busca música ORIGINAL del canal en assets/audio/original/bgm."""
    if not ORIGINAL_BGM_DIR.exists():
        return None
    for ext in AUDIO_EXTENSIONS:
        direct = ORIGINAL_BGM_DIR / f"{key}{ext}"
        if direct.is_file():
            return direct
    target_dirs = [key]
    for canon, aliases in MOOD_ALIASES.items():
        if key == canon or key in aliases:
            target_dirs.extend([canon, *aliases])
    for dir_name in dict.fromkeys(target_dirs):
        sub = ORIGINAL_BGM_DIR / dir_name
        if sub.is_dir():
            candidates = sorted(
                p for p in sub.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
            )
            if candidates:
                return candidates[0]
    for p in ORIGINAL_BGM_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and key in p.stem.lower():
            return p
    return None


def get_youtube_bgm_track(mood_or_name: str) -> Optional[Path]:
    """Busca una pista BGM de la Biblioteca de YouTube según el estado de ánimo o nombre.
    
    Si se encuentra una pista en la carpeta correspondiente, se retorna su ruta Path.
    Si la biblioteca está vacía o no existe para esa categoría, retorna None para
    que el pipeline continúe fluidamente con el fallback predeterminado.
    """
    if not mood_or_name or not isinstance(mood_or_name, str):
        return None
    
    key = mood_or_name.lower().strip()
    if key.startswith("youtube:"):
        key = key[len("youtube:"):].strip()
    
    if key in ("silent", "none", ""):
        return None

    original = _search_original_bgm(key)
    if original:
        safe_log(f"[OriginalAudio] Pista original seleccionada: {original.name}")
        return original

    if not YOUTUBE_BGM_DIR.exists():
        return None

    # 1. Búsqueda directa por nombre de archivo exacto
    for ext in AUDIO_EXTENSIONS:
        direct_file = YOUTUBE_BGM_DIR / f"{key}{ext}"
        if direct_file.is_file():
            return direct_file

    # 2. Búsqueda por subdirectorio de categoría/mood
    # Revisar si coincide con la clave o alguno de sus alias
    target_dirs: List[str] = [key]
    for canon_mood, aliases in MOOD_ALIASES.items():
        if key == canon_mood or key in aliases:
            if canon_mood not in target_dirs:
                target_dirs.append(canon_mood)
            for a in aliases:
                if a not in target_dirs:
                    target_dirs.append(a)

    for dir_name in target_dirs:
        sub = YOUTUBE_BGM_DIR / dir_name
        if sub.is_dir():
            candidates = [p for p in sub.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
            if candidates:
                # Determinista o rotativo si hay varias pistas
                chosen = sorted(candidates)[0]
                safe_log(f"[YouTubeAudio] Pista BGM seleccionada ({dir_name}): {chosen.name}")
                return chosen

    # 3. Búsqueda recursiva por coincidencia parcial en nombre de archivo
    for p in YOUTUBE_BGM_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
            if key in p.stem.lower():
                safe_log(f"[YouTubeAudio] Pista BGM coincidente encontrada: {p.name}")
                return p

    return None


def get_youtube_sfx_path(sfx_name: str) -> Optional[Path]:
    """Busca un efecto de sonido (SFX) en la Biblioteca de YouTube.
    
    Retorna la ruta Path si existe un SFX dedicado de la biblioteca,
    o None si no existe para recurrir al SFX base del sistema.
    """
    if not sfx_name or not isinstance(sfx_name, str):
        return None
    
    key = sfx_name.lower().strip()
    if key.startswith("youtube:"):
        key = key[len("youtube:"):].strip()
    
    if key in ("none", "silent", ""):
        return None

    if not YOUTUBE_SFX_DIR.exists():
        return None

    # 1. Coincidencia directa por nombre de archivo
    for ext in AUDIO_EXTENSIONS:
        direct_file = YOUTUBE_SFX_DIR / f"{key}{ext}"
        if direct_file.is_file():
            return direct_file

    # 2. Búsqueda en carpetas de categorías de SFX
    possible_folders = SFX_CATEGORY_MAP.get(key, [key])
    for folder in possible_folders:
        cat_dir = YOUTUBE_SFX_DIR / folder
        if cat_dir.is_dir():
            # Buscar archivo con el nombre o primer archivo disponible
            for ext in AUDIO_EXTENSIONS:
                candidate = cat_dir / f"{key}{ext}"
                if candidate.is_file():
                    return candidate
            files = [p for p in cat_dir.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
            if files:
                chosen = sorted(files)[0]
                return chosen

    # 3. Búsqueda recursiva por coincidencia de subcadena
    for p in YOUTUBE_SFX_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
            if key in p.stem.lower():
                return p

    return None


def list_youtube_library_summary() -> Dict[str, Any]:
    """Genera un resumen estructurado del contenido disponible en la Biblioteca de YouTube."""
    summary: Dict[str, Any] = {
        "bgm": {},
        "sfx": {},
        "total_bgm": 0,
        "total_sfx": 0,
    }

    if YOUTUBE_BGM_DIR.exists():
        for item in YOUTUBE_BGM_DIR.iterdir():
            if item.is_dir():
                tracks = [p.name for p in item.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
                summary["bgm"][item.name] = tracks
                summary["total_bgm"] += len(tracks)
            elif item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
                summary["bgm"].setdefault("root", []).append(item.name)
                summary["total_bgm"] += 1

    if YOUTUBE_SFX_DIR.exists():
        for item in YOUTUBE_SFX_DIR.iterdir():
            if item.is_dir():
                sfx_files = [p.name for p in item.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
                summary["sfx"][item.name] = sfx_files
                summary["total_sfx"] += len(sfx_files)
            elif item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
                summary["sfx"].setdefault("root", []).append(item.name)
                summary["total_sfx"] += 1

    return summary


def infer_audio_mood(topic: str, style: str = "") -> str:
    """Infiere el tono/mood musical más adecuado según el tema del video."""
    t = f"{topic} {style}".lower()

    # 0. Espiritual / Fe / Versículos Bíblicos / Películas Cristianas / Dios
    spiritual_keywords = [
        "dios", "jesus", "jesucristo", "cristo", "cristiano", "cristiana",
        "biblia", "biblico", "biblica", "versiculo", "salmo", "fe", "oracion",
        "esperanza", "milagro", "adoracion", "evangelio", "pelicula cristiana",
        "redencion", "perdon", "paz de dios", "espiritu santo", "proverbios"
    ]
    if any(k in t for k in spiritual_keywords):
        return "spiritual"

    # 0.1 Épico Motivacional / Estoicismo / Disciplina / Frases de Impacto
    epic_motivation_keywords = [
        "estoicismo", "estoico", "marco aurelio", "seneca", "epicteto",
        "disciplina", "foco mental", "mentalidad imparable", "frase motivacional",
        "frases motivacionales", "motivacion corta", "superacion personal",
        "fuerza mental", "guerrero interior", "habitos atomicos", "resiliencia"
    ]
    if any(k in t for k in epic_motivation_keywords):
        return "epic_motivation"

    # 1. Tensión / Noticias urgentes / Política / Presidentes / Conflicto
    tension_keywords = [
        "presidente", "gobierno", "ministro", "guerra", "crisis", "conflicto",
        "elecciones", "onu", "juicio", "escandalo", "noticia", "breaking",
        "alerta", "milei", "trump", "biden", "putin", "politica", "urgente",
        "denuncia", "fraude", "militar", "ataque", "tension", "geopolitica", "discurso"
    ]
    if any(k in t for k in tension_keywords):
        return "tension"

    # 2. Cinemático / Historia / Misterio / Catástrofe / Documental
    cinematic_keywords = [
        "misterio", "universo", "historia", "espacio", "arqueologia", "secreto",
        "peligro", "catastrofe", "tierra", "oceano", "volcan", "documental",
        "civilizacion", "antiguo", "enigma", "extraterrestre", "cosmos"
    ]
    if any(k in t for k in cinematic_keywords):
        return "cinematic"

    # 3. Upbeat / Éxito / Viral / Consejos / Dinero / Motivación
    upbeat_keywords = [
        "dinero", "exito", "viral", "top 10", "consejos", "hacks", "finanzas",
        "emprendimiento", "motivacion", "habitos", "millonario", "negocios",
        "crecimiento", "productividad", "marketing"
    ]
    if any(k in t for k in upbeat_keywords):
        return "upbeat"

    # 4. Lo-Fi / Filosofía / Educación profunda / Estudio
    lofi_keywords = [
        "filosofia", "reflexion", "psicologia", "estoicismo", "meditacion",
        "mente", "estudio", "habito de lectura", "pensamiento", "aprender"
    ]
    if any(k in t for k in lofi_keywords):
        return "lofi"

    # 5. Ambient / Tecnología / Ciencia / IA
    ambient_keywords = [
        "tecnologia", "ia", "inteligencia artificial", "robot", "chip", "software",
        "ciencia", "futuro", "computadora", "cuantica", "algoritmo", "innovacion"
    ]
    if any(k in t for k in ambient_keywords):
        return "ambient"

    # Fallback predeterminado según el estilo del compositor
    if style in ("divulgacion", "periodistico", "streamer"):
        return "tension"
    return "cinematic"


def download_best_audio_for_topic(
    topic: str,
    style: str = "",
    preferred_mood: Optional[str] = None,
    force_download: bool = False
) -> Optional[Path]:
    """Descarga de forma automática la pista de la Biblioteca de Audio de YouTube
    que mejor se adapte al video, según el análisis semántico del tema y estilo.
    """
    import re
    mood = (preferred_mood or infer_audio_mood(topic, style)).strip().lower()
    target_dir = YOUTUBE_BGM_DIR / mood
    target_dir.mkdir(parents=True, exist_ok=True)

    # Si ya tenemos pistas en esa categoría y no se fuerza la descarga, usar la existente
    if not force_download:
        existing = [p for p in target_dir.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
        if existing:
            chosen = sorted(existing)[0]
            safe_log(f"[YouTubeAudioAuto] Pista adaptada existente: {chosen.name}")
            return chosen

    # Construir query dirigida para música instrumental libre de derechos
    mood_search_tags = {
        "spiritual": "cinematic worship piano strings inspiring emotional peaceful instrumental no copyright",
        "epic_motivation": "epic cinematic motivation orchestral trailer powerful inspiring dramatic instrumental no copyright",
        "tension": "tension dramatic breaking news suspense documentary",
        "cinematic": "dramatic cinematic trailer orchestral film",
        "upbeat": "upbeat energetic electronic happy motivational",
        "ambient": "ambient chill documentary technology atmospheric",
        "lofi": "lofi chill study relaxing beat",
    }
    tags = mood_search_tags.get(mood, "cinematic documentary")
    query = f'ytsearch5:"Audio Library" "No Copyright Music" {tags} instrumental'

    safe_log(f"[YouTubeAudioAuto] Buscando pista óptima para «{topic}» (Mood: {mood})...")

    try:
        import yt_dlp

        ydl_opts_search = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            search_res = ydl.extract_info(query, download=False)

        entries = search_res.get("entries", [])
        if not entries:
            safe_log("[YouTubeAudioAuto] No se obtuvieron resultados en la búsqueda")
            return None

        # Filtrar candidatos: descartar compilaciones largas o canciones de < 45 seg
        best_candidate = None
        for entry in entries:
            title = entry.get("title", "")
            title_lower = title.lower()
            dur = entry.get("duration") or 180

            if any(bad in title_lower for bad in ["1 hour", "10 hour", "compilation", "top 50", "top 100", "remix"]):
                continue
            if dur < 45 or dur > 550:
                continue

            best_candidate = entry
            break

        if not best_candidate:
            best_candidate = entries[0]

        video_id = best_candidate.get("id")
        video_title = best_candidate.get("title", "yt_audio")
        clean_title = re.sub(r'[\/:*?"<>|]', '_', video_title)[:60].strip()
        out_path = target_dir / f"{clean_title}.mp3"

        if out_path.exists():
            safe_log(f"[YouTubeAudioAuto] Pista previamente descargada: {out_path.name}")
            return out_path

        safe_log(f"[YouTubeAudioAuto] Descargando «{video_title}» ({video_id})...")
        download_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts_download = {
            "format": "bestaudio/best",
            "outtmpl": str(target_dir / f"{clean_title}.%(ext)s"),
            "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
        }
        for c_cand in [settings.STORAGE_DIR / "cookies.txt", settings.BASE_DIR / "cookies.txt", settings.BASE_DIR / "assets" / "cookies.txt"]:
            if c_cand.is_file() and c_cand.stat().st_size > 10:
                ydl_opts_download["cookiefile"] = str(c_cand.resolve())
                break

        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            ydl.download([download_url])

        if out_path.exists():
            safe_log(f"[YouTubeAudioAuto] ¡Pista descargada con éxito!: {out_path.name}")
            return out_path

        for p in target_dir.glob(f"{clean_title}.*"):
            if p.suffix.lower() in AUDIO_EXTENSIONS:
                return p

    except Exception as exc:
        safe_log(f"[YouTubeAudioAuto] Error descargando audio adaptativo: {exc}")

    return None


async def async_download_best_audio_for_topic(
    topic: str,
    style: str = "",
    preferred_mood: Optional[str] = None,
    force_download: bool = False
) -> Optional[Path]:
    """Versión asíncrona no bloqueante de download_best_audio_for_topic."""
    import asyncio
    return await asyncio.to_thread(
        download_best_audio_for_topic,
        topic=topic,
        style=style,
        preferred_mood=preferred_mood,
        force_download=force_download
    )

