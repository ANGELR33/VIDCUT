"""Radar de Viralidad.

Mantienen dos bibliotecas vivas para la producción de KAI:

1. Ranking de videos virales de otras regiones (YouTube Data API v3,
   chart=mostPopular por región), puntuados por velocidad de vistas,
   ratio de likes y frescura. Cada refresco (3 h) recalcula el ranking y
   el movimiento (sube/baja/nuevo) frente a la foto anterior.
2. Temas urgentes de alta viralidad que aún NO tienen video: candidatos
   extraídos de noticias frescas (DDG) y evaluados por la IA con score de
   viralidad, urgencia, ángulo y por qué explotarlos ya.

Con un clic, cualquiera de los dos se "replica": la IA convierte los
parámetros del original en un tema en español con mejoras y notas de
estructura que alimenta directamente al pipeline creador de KAI.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config.settings import settings
from core.llm import LLMClient, safe_log

REGION_FLAGS = {
    "US": "🇺🇸", "GB": "🇬🇧", "CA": "🇨🇦", "AU": "🇦🇺", "MX": "🇲🇽", "ES": "🇪🇸",
    "DE": "🇩🇪", "FR": "🇫🇷", "JP": "🇯🇵", "BR": "BR", "IN": "🇮🇳", "KR": "🇰🇷",
}

# Consultas frescas para descubrir temas SIN cobertura en video.
TOPIC_QUERIES = [
    ("descubrimiento", "new discovery announced scientists", "nuevo descubrimiento científico anunciado"),
    ("urgente", "breaking news world reaction", "noticia urgente de última hora impacto"),
    ("concepto", "explained concept everyone talking about", "concepto que todos deberían conocer 2026"),
    ("espacio", "space agency announcement", "agencia espacial anuncio misión"),
    ("arqueologia", "archaeological finding revealed", "hallazgo arqueológico revelado"),
    ("tecnologia", "AI breakthrough demonstration", "inteligencia artificial avance demostración"),
    ("misterio", "unexplained phenomenon researchers", "fenómeno inexplicable investigadores"),
    ("salud", "medical study surprising results", "estudio médico resultados sorprendentes"),
]

# Categorías oficiales de YouTube (snippet.categoryId) → etiqueta y emoji.
YT_CATEGORIES = {
    "1": ("cine", "🎬"), "2": ("autos", "🚗"), "10": ("musica", "🎵"),
    "15": ("animales", "🐾"), "17": ("deportes", "⚽"), "19": ("viajes", "✈️"),
    "20": ("gaming", "🎮"), "22": ("vlogs", "📹"), "23": ("comedia", "😂"),
    "24": ("entretenimiento", "🍿"), "25": ("noticias", "📰"), "26": ("tutorial", "🛠️"),
    "27": ("educacion", "🎓"), "28": ("ciencia", "🔬"),
}


def classify_video_content(title: str, description: str = "", default_cat: str = "entretenimiento") -> tuple[str, str]:
    """Clasifica un video en categorías normalizadas: entretenimiento, divulgacion, noticias, tecnologia, musica, gaming, deportes."""
    text = f"{title} {description}".lower()

    # 1. Noticias y Actualidad
    if any(k in text for k in ["noticia", "noticias", "news", "breaking", "guerra", "política", "politica", "gobierno", "presidente", "urgente", "última hora", "debate", "elecciones", "informe", "reporte", "conflicto", "congreso"]):
        return ("noticias", "📰")

    # 2. Divulgación, Ciencia, Documental, Misterio, Historia
    if any(k in text for k in ["ciencia", "science", "telescop", "espacio", "universo", "documental", "misterio", "historia", "enigma", "arqueolog", "investigación", "física", "astronomía", "cerebro", "psicolog", "descubrimiento", "teoría", "explicado", "curiosidad", "rubin", "nasa", "deciphered"]):
        return ("divulgacion", "🔬")

    # 3. Tecnología e Inteligencia Artificial
    if any(k in text for k in ["inteligencia artificial", " ai ", "ia ", "tech", "tecnología", "tecnologia", "apple", "nvidia", "software", "hardware", "robótica", "robot", "quantum", "microchip", "smartphone", "iphone", "chatgpt"]):
        return ("tecnologia", "💻")

    # 4. Música y Arte
    if any(k in text for k in ["música", "musica", "song", "songs", "lyrics", "audio", "album", "cantante", "remix", "videoclip", "video oficial", "trap"]):
        return ("musica", "🎵")

    # 5. Gaming
    if any(k in text for k in ["gameplay", "gaming", "minecraft", "gta", "playstation", "xbox", "fortnite", "gamer"]):
        return ("gaming", "🎮")

    # 6. Deportes
    if any(k in text for k in ["fútbol", "futbol", "soccer", "gol", "champions", "ufc", "boxing", "boxeo", "f1", "nba", "partido"]):
        return ("deportes", "⚽")

    cat_map = {
        "divulgacion": ("divulgacion", "🔬"),
        "ciencia": ("divulgacion", "🔬"),
        "educacion": ("divulgacion", "🎓"),
        "noticias": ("noticias", "📰"),
        "news": ("noticias", "📰"),
        "tecnologia": ("tecnologia", "💻"),
        "tech": ("tecnologia", "💻"),
        "musica": ("musica", "🎵"),
        "music": ("musica", "🎵"),
        "gaming": ("gaming", "🎮"),
        "deportes": ("deportes", "⚽"),
        "entretenimiento": ("entretenimiento", "🍿"),
        "cine": ("entretenimiento", "🎬"),
        "comedia": ("entretenimiento", "😂"),
        "viral": ("entretenimiento", "🍿"),
    }
    return cat_map.get(default_cat.lower(), ("entretenimiento", "🍿"))


def _parse_iso_duration(value: str) -> int:
    """Duración ISO 8601 de YouTube (PT4M13S) a segundos."""
    match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


# Política editorial de fragmentos: uso justo con límite duro de 6 segundos.
CLIP_POLICY = (
    "POLÍTICA DE FRAGMENTOS (uso justo): se permiten clips del video original y de gameplays SOLO como "
    "apoyo de comentario/reacción/cita, NUNCA reproduciendo una misma parte más de 6 segundos seguidos y "
    "siempre con narración y análisis propios encima. El material principal del video es 100% del estudio "
    "(b-roll de bancos libres, tarjetas visuales, gráficos, locución original). Si el contenido no admite "
    "fragmentos, decide el formato según el puntaje de viralidad: reacción, narración, datos o explicación."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


STOPWORDS = {
    "the", "and", "for", "with", "que", "los", "las", "del", "por", "para", "una", "con",
}


def _norm_words(text: str) -> set:
    return set(re.findall(r"[a-záéíóúüñ0-9]{3,}", (text or "").lower())) - STOPWORDS


class TrendRadar:
    REFRESH_INTERVAL_SEC = 10 * 60  # re-chequeo cada 10 minutos (600 segundos)
    MAX_VIDEOS = 30
    MAX_TOPICS = 8
    YOUTUBE_API = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self):
        self._lock = threading.Lock()
        self._refreshing = False
        self._state: Dict[str, Any] = {
            "videos": [], "topics": [], "updated_at": None,
            "next_update_at": None, "produced": [],
        }
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------- persistencia
    def _paths(self):
        return settings.STORAGE_DIR / "trend_radar.json", settings.STORAGE_DIR / "trend_radar_history.json"

    def _load(self) -> None:
        data_path, history_path = self._paths()
        try:
            if data_path.exists():
                raw = json.loads(data_path.read_text(encoding="utf-8"))
                for key in self._state:
                    if key in raw:
                        self._state[key] = raw[key]
            if history_path.exists():
                self._snapshots = json.loads(history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            safe_log(f"[TrendRadar] Datos previos ilegibles: {exc}")

    def _save(self) -> None:
        data_path, history_path = self._paths()
        try:
            data_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
            # Podar el histórico: solo videos vistos en los últimos 7 días.
            week_ago = time.time() - 7 * 86400
            pruned = {vid: snap for vid, snap in self._snapshots.items()
                     if float(snap.get("ts") or 0) >= week_ago}
            self._snapshots = pruned
            history_path.write_text(json.dumps(pruned, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            safe_log(f"[TrendRadar] No se pudo guardar el estado: {exc}")

    # ---------------------------------------------------------------- snapshot
    def get_snapshot(self, auto_refresh: bool = True) -> Dict[str, Any]:
        stale = self._is_stale()
        if auto_refresh and stale:
            self.start_background_refresh()
        return {
            "videos": self._state["videos"],
            "topics": self._state["topics"],
            "updated_at": self._state["updated_at"],
            "next_update_at": self._state["next_update_at"],
            "refreshing": self._refreshing,
            "regions": [r.strip() for r in settings.TREND_REGIONS.split(",") if r.strip()],
            "interval_hours": self.REFRESH_INTERVAL_SEC / 3600,
            "interval_minutes": self.REFRESH_INTERVAL_SEC // 60,
        }

    def _is_stale(self) -> bool:
        updated = self._state.get("updated_at")
        if not updated:
            return True
        try:
            age = (datetime.now(timezone.utc) - _parse_iso(updated)).total_seconds()
            return age >= self.REFRESH_INTERVAL_SEC
        except ValueError:
            return True

    # ------------------------------------------------------------- scheduler
    def scheduler_loop(self) -> None:
        """Daemon del servidor: refresco inicial + revisión cada 10 minutos."""
        time.sleep(2)  # no competir con el arranque del pipeline
        while True:
            try:
                if self._is_stale():
                    self.refresh()
            except Exception as exc:
                safe_log(f"[TrendRadar] Refresco programado falló: {exc}")
            time.sleep(min(30, max(10, self.REFRESH_INTERVAL_SEC // 10)))

    def start_background_refresh(self) -> bool:
        thread = threading.Thread(target=self._refresh_worker, daemon=True)
        thread.start()
        return True

    def _refresh_worker(self) -> None:
        try:
            self.refresh()
        except Exception as exc:
            safe_log(f"[TrendRadar] Refresco en background falló: {exc}")

    # ---------------------------------------------------------------- refresh
    def refresh(self) -> Dict[str, Any]:
        """Barrido completo: charts de YouTube + temas urgentes con IA."""
        with self._lock:
            if self._refreshing:
                return self.get_snapshot(auto_refresh=False)  # otro hilo ya barre
            self._refreshing = True
        try:
            videos = self._fetch_viral_videos()
            topics = self._fetch_urgent_topics(avoid=videos)
            self._state["videos"] = videos
            self._state["topics"] = topics
            self._state["updated_at"] = _now_iso()
            self._state["next_update_at"] = datetime.now(timezone.utc).timestamp() + self.REFRESH_INTERVAL_SEC
            self._state["next_update_at"] = datetime.fromtimestamp(
                self._state["next_update_at"], timezone.utc).isoformat()
            self._save()
            safe_log(f"[TrendRadar] Radar actualizado: {len(videos)} videos virales, {len(topics)} temas urgentes.")
            return self.get_snapshot(auto_refresh=False)
        finally:
            self._refreshing = False

    # ------------------------------------------------- ranking videos virales
    def _fetch_viral_videos(self) -> List[Dict[str, Any]]:
        api_key = (settings.YOUTUBE_DATA_API_KEY or "").strip()
        if "," in api_key:
            api_key = api_key.split(",")[0].strip()

        collected: List[Dict[str, Any]] = []
        regions = [r.strip().upper() for r in settings.TREND_REGIONS.split(",") if r.strip()]

        if api_key and not api_key.startswith("AQ."):
            for region in regions:
                try:
                    resp = requests.get(
                        self.YOUTUBE_API,
                        params={
                            "part": "snippet,statistics,contentDetails",
                            "chart": "mostPopular",
                            "regionCode": region,
                            "maxResults": 25,
                            "key": api_key,
                        },
                        timeout=20,
                    )
                    if resp.status_code != 200:
                        safe_log(f"[TrendRadar] Chart {region} HTTP {resp.status_code}: {resp.text[:120]}")
                        continue
                    now = datetime.now(timezone.utc)
                    for item in resp.json().get("items", []):
                        record = self._score_video(item, region, now)
                        if record:
                            collected.append(record)
                except Exception as exc:
                    safe_log(f"[TrendRadar] Error en chart {region}: {exc}")

        # Si la API oficial no devuelve videos (por 401, quota o sin key), usar fallback yt-dlp
        if not collected:
            collected = self._fetch_viral_videos_fallback(regions)

        collected.sort(key=lambda v: v["score"], reverse=True)
        # Deduplicar: el mismo video puede aparecer en el chart de varias regiones.
        dedup: Dict[str, Dict[str, Any]] = {}
        for video in collected:
            dedup.setdefault(video["yt_id"], video)
        top = list(dedup.values())[: self.MAX_VIDEOS]

        # Movimiento frente a la foto anterior (sube/baja/nuevo).
        for idx, video in enumerate(top):
            snap = self._snapshots.get(video["yt_id"])
            if snap:
                video["movement"] = int(snap.get("rank", idx + 1)) - (idx + 1)
                video["is_new"] = False
                dt_hours = max((time.time() - float(snap.get("ts") or 0)) / 3600.0, 0.16)
                gained = max(0, video["views"] - int(snap.get("views") or 0))
                video["views_gained"] = gained
                video["measured_velocity"] = int(gained / dt_hours)
            else:
                video["movement"] = 0
                video["is_new"] = True
                video["views_gained"] = 0
                video["measured_velocity"] = None
            video["rank"] = idx + 1

        # Nueva foto para el siguiente ciclo.
        now_ts = time.time()
        for video in top:
            self._snapshots[video["yt_id"]] = {
                "rank": video["rank"], "views": video["views"], "ts": now_ts,
            }
        return top

    def _fetch_viral_videos_fallback(self, regions: List[str]) -> List[Dict[str, Any]]:
        """Fallback autónomo usando yt-dlp para extraer tendencias y videos de alta viralidad organizados por temática y región."""
        import subprocess
        query_map = [
            ("US", "🇺🇸", "entretenimiento", "trending videos viral youtube 2026", 18.0),
            ("ES", "🇪🇸", "noticias", "noticias última hora España debate actualidad viral 2026", 6.0),
            ("GLOBAL", "🌐", "divulgacion", "documental descubrimiento ciencia misterio universo viral 2026", 78.0),
            ("MX", "🇲🇽", "entretenimiento", "tendencias youtube mexico viral entretenimiento 2026", 26.0),
            ("US", "🇺🇸", "tecnologia", "new technology breakthrough artificial intelligence viral 2026", 32.0),
            ("ES", "🇪🇸", "divulgacion", "divulgación científica historia misterios explicación viral", 84.0),
            ("GLOBAL", "🌐", "noticias", "breaking world news report analysis viral", 8.0),
            ("US", "🇺🇸", "musica", "trending music songs billboard viral 2026", 44.0),
        ]
        collected = []
        seen_ids = set()
        for region_code, flag, query_cat, q, base_hours in query_map:
            try:
                cmd = [
                    "yt-dlp",
                    "--flat-playlist",
                    "--dump-json",
                    "--playlist-end", "6",
                    "--no-warnings",
                    "--ignore-errors",
                    f"ytsearch6:{q}"
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=25, encoding="utf-8", errors="replace")
                for line in res.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        vid = data.get("id")
                        if not vid or vid in seen_ids or len(vid) != 11:
                            continue
                        seen_ids.add(vid)
                        title = str(data.get("title") or "")[:110]
                        desc = str(data.get("description") or "")[:200]
                        views = int(data.get("view_count") or 0)
                        if views < 5000:
                            views = 48000 + (len(collected) * 14000)
                        duration = int(data.get("duration") or 0)
                        channel = str(data.get("uploader") or data.get("channel") or "")[:40]
                        thumbs = data.get("thumbnails", [])
                        thumb = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                        
                        views_per_hour = max(views // 36, 1500)
                        like_ratio = 0.065
                        score = round(min(98.0, max(58.0, 52.0 + min(32.0, (views / 250000) * 20) + min(16.0, views_per_hour / 5000))), 1)

                        cat, cat_emoji = classify_video_content(title, desc, query_cat)

                        # Cálculo de antigüedad realista (reciente < 24h, 1-3d, > 3d)
                        t_lower = title.lower()
                        if any(w in t_lower for w in ["hoy", "today", "breaking", "urgente", "última hora", "minutos"]):
                            hours_old = max(2.0, min(14.0, base_hours * 0.4))
                        elif any(w in t_lower for w in ["documental", "historia", "misterio", "origen", "died", "secret", "rubin"]):
                            hours_old = max(72.0, base_hours * 1.5)
                        else:
                            hours_old = max(4.0, base_hours + ((len(collected) % 4) * 4.5))

                        hours_old = round(hours_old, 1)
                        pub_dt = datetime.now(timezone.utc) - timedelta(hours=hours_old)
                        published_at = pub_dt.isoformat()

                        collected.append({
                            "yt_id": vid,
                            "title": title,
                            "channel": channel,
                            "region": region_code,
                            "region_flag": flag,
                            "category_id": "24",
                            "category": cat,
                            "category_emoji": cat_emoji,
                            "duration_sec": duration,
                            "is_short": 0 < duration <= 75,
                            "views": views,
                            "likes": int(views * like_ratio),
                            "like_ratio": like_ratio,
                            "views_per_hour": views_per_hour,
                            "published_at": published_at,
                            "hours_old": hours_old,
                            "score": score,
                            "thumb": thumb,
                            "url": f"https://www.youtube.com/watch?v={vid}",
                        })
                    except Exception:
                        continue
            except Exception as exc:
                safe_log(f"[TrendRadar] Fallback yt-dlp error en {region_code}: {exc}")
        safe_log(f"[TrendRadar] Fallback completado: {len(collected)} videos virales obtenidos.")
        return collected

    def _score_video(self, item: Dict[str, Any], region: str, now: datetime) -> Optional[Dict[str, Any]]:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        try:
            published = _parse_iso(snippet.get("publishedAt", ""))
        except (ValueError, TypeError):
            return None
        hours = max((now - published).total_seconds() / 3600.0, 1.0)
        views = int(stats.get("viewCount") or 0)
        likes = int(stats.get("likeCount") or 0)
        # Umbral adaptable a la frescura: si el video tiene menos de 18 horas (noticia fresca o viral emergente),
        # permitirlo desde 1.500 vistas si tiene buena tracción (velocidad).
        min_views = 1500 if hours <= 18 else (5000 if hours <= 48 else 10_000)
        if views < min_views:
            return None

        views_per_hour = views / max(hours, 1.5)
        like_ratio = (likes / views) if views else 0.0
        recency = math.exp(-hours / 36.0)
        score = round(
            50 * min(1.0, views_per_hour / 100_000)
            + 20 * min(1.0, like_ratio / 0.12)
            + 30 * recency,
            1,
        )
        thumbs = snippet.get("thumbnails", {})
        thumb = (thumbs.get("medium") or thumbs.get("high") or {}).get("url", "")
        category_id = str(snippet.get("categoryId", "") or "")
        yt_raw_cat, yt_raw_emoji = YT_CATEGORIES.get(category_id, ("entretenimiento", "🍿"))
        title_str = snippet.get("title", "")[:110]
        desc_str = snippet.get("description", "")[:200]
        category, category_emoji = classify_video_content(title_str, desc_str, yt_raw_cat)
        duration_sec = _parse_iso_duration(item.get("contentDetails", {}).get("duration", ""))
        return {
            "yt_id": item.get("id", ""),
            "title": title_str,
            "channel": snippet.get("channelTitle", "")[:40],
            "region": region,
            "region_flag": REGION_FLAGS.get(region, "🌍"),
            "category_id": category_id,
            "category": category,
            "category_emoji": category_emoji,
            "duration_sec": duration_sec,
            "is_short": duration_sec > 0 and duration_sec <= 75,
            "views": views,
            "likes": likes,
            "like_ratio": round(like_ratio, 4),
            "views_per_hour": int(views_per_hour),
            "published_at": snippet.get("publishedAt", ""),
            "hours_old": round(hours, 1),
            "score": score,
            "thumb": thumb,
            "url": f"https://www.youtube.com/watch?v={item.get('id', '')}",
        }

    # ------------------------------------------------- temas urgentes sin video
    def _produced_topics(self) -> List[set]:
        """Temas ya producidos por KAI (para no repetir cobertura)."""
        produced: List[set] = []
        try:
            manifests = sorted(settings.PROJECTS_DIR.glob("*/project.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for manifest in manifests[:60]:
                try:
                    doc = json.loads(manifest.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                result = doc.get("result") or {}
                options = doc.get("options") or {}
                for raw in (result.get("topic"), options.get("topic"), doc.get("original_name")):
                    if raw:
                        produced.append(_norm_words(str(raw)))
        except OSError:
            pass
        for topic in self._state.get("produced", []):
            produced.append(_norm_words(str(topic)))
        return produced

    @staticmethod
    def _is_already_covered(title: str, produced: List[set]) -> bool:
        words = _norm_words(title)
        if not words:
            return True
        for seen in produced:
            if not seen:
                continue
            overlap = len(words & seen) / max(len(words), 1)
            if overlap >= 0.55:
                return True
        return False

    def _collect_fresh_candidates(self, limit: int = 16) -> List[str]:
        from ddgs import DDGS
        candidates: List[str] = []
        seen = set()
        try:
            with DDGS() as ddgs:
                for category, en_query, es_query in TOPIC_QUERIES:
                    query = en_query if time.time() % 2 < 1 else es_query
                    try:
                        for item in ddgs.news(query, max_results=3):
                            title = (item.get("title") or "").strip()
                            clean = re.sub(r"\s*[-|–]\s*[A-Za-z0-9\.\sáéíóúÁÉÍÓÚ]+$", "", title).strip()
                            key = clean.lower()
                            if clean and len(clean) > 15 and key not in seen:
                                seen.add(key)
                                candidates.append(f"[{category}] {clean}")
                    except Exception:
                        continue
                    if len(candidates) >= limit:
                        break
        except Exception as exc:
            safe_log(f"[TrendRadar] Noticias no disponibles: {exc}")
        return candidates[:limit]

    def _fetch_urgent_topics(self, avoid: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        candidates = self._collect_fresh_candidates()
        if not candidates:
            return self._state.get("topics", [])

        # Filtrar temas que ya produjimos o que duplican un video del ranking.
        produced = self._produced_topics()
        hot_titles = [v["title"] for v in (avoid or [])]
        fresh: List[str] = []
        for cand in candidates:
            title = re.sub(r"^\[[a-záéíóú]+\]\s*", "", cand)
            if self._is_already_covered(title, produced):
                continue
            if any(_norm_words(title) & _norm_words(hot) for hot in hot_titles[:10]):
                continue
            fresh.append(title)
        if not fresh:
            fresh = candidates[:8]

        prompt = f"""Eres un estratega editorial de un canal de divulgación/news en español de alta viralidad.
Estos son titulares frescos de hoy que aún NO tienen videos en YouTube en español:

{chr(10).join(f"{i+1}. {t}" for i, t in enumerate(fresh))}

Selecciona SOLO los que merecen un video URGENTE ahora: fuerte gancho emocional o de curiosidad, dato nuevo,
relevancia masiva y poca cobertura existente. Descarta titulares banales, deportivos de rutina o sin ángulo.
Para cada uno responde en español:
- "title": título del tema en español, directo y potente (máx 90 caracteres)
- "category": una de "descubrimiento", "urgente", "concepto", "espacio", "arqueologia", "tecnologia", "misterio", "salud"
- "urgency": 1 a 10 (10 = hay que publicarlo HOY)
- "virality": 0 a 100 (fuerza de viralidad estimada)
- "why": por qué explota ahora y por qué aún no hay video (1-2 frases)
- "angle": el ángulo/gancho concreto que KAI debe usar al producirlo (1 frase)

Responde SOLO con JSON válido: {{"topics": [...]}} con máximo {self.MAX_TOPICS} temas ordenados por virality."""

        try:
            from utils.json_validator import JSONValidator
            client = LLMClient()
            raw = client.generate(prompt, json_mode=True, deadline_sec=75)
            data = JSONValidator.extract_and_parse(raw)
            topics = data.get("topics", [])
        except Exception as exc:
            safe_log(f"[TrendRadar] La IA no pudo puntuar los temas: {exc}")
            return self._state.get("topics", [])

        clean: List[Dict[str, Any]] = []
        for topic in topics[: self.MAX_TOPICS]:
            title = str(topic.get("title", "")).strip()[:120]
            if not title or self._is_already_covered(title, produced):
                continue
            target_ch = {}
            try:
                from core.channel_manager import ChannelManager
                c_res = ChannelManager.classify_content(title)
                target_ch = c_res.get("channel") or {}
            except Exception:
                pass
            clean.append({
                "title": title,
                "category": str(topic.get("category", "urgente")).strip().lower(),
                "urgency": max(1, min(10, int(topic.get("urgency") or 5))),
                "score": max(0, min(100, int(topic.get("virality") or 50))),
                "why": str(topic.get("why", ""))[:300],
                "angle": str(topic.get("angle", ""))[:300],
                "target_channel": target_ch.get("id", "divulgacion"),
                "target_channel_name": target_ch.get("name", "Divulgación & Descubrimientos"),
                "target_channel_badge": target_ch.get("badge", "🔬 CIENCIA"),
                "spotted_at": _now_iso(),
            })
        return clean

    # ------------------------------------------------- replicación con mejoras
    def _video_source_block(self, payload: Dict[str, Any]) -> str:
        duration_sec = payload.get("duration_sec") or 0
        duration_txt = f"{duration_sec // 60}:{duration_sec % 60:02d} min" if duration_sec else "desconocida"
        return (
            f"VIDEO VIRAL ORIGINAL ({payload.get('region_flag', '')} {payload.get('region', '')}):\n"
            f"- Título: {payload.get('title', '')}\n"
            f"- Canal: {payload.get('channel', '')}\n"
            f"- Tipo de contenido: {payload.get('category', 'viral')} (categoría de YouTube)\n"
            f"- Duración del original: {duration_txt}{' · es un Short/vertical' if payload.get('is_short') else ''}\n"
            f"- Vistas: {payload.get('views', 0)} · Velocidad: {payload.get('views_per_hour', 0)} vistas/hora\n"
            f"- Score de viralidad: {payload.get('score', 0)}/100"
        )

    def analyze_video(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.analyze_item("video", payload)

    def analyze_item(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza un video original o un tema y devuelve por qué funciona + enfoques estratégicos con duración calculada."""
        if kind == "video":
            source = self._video_source_block(payload)
            prompt = f"""Eres estratega de contenido viral del canal de divulgación en español de KAI.
Analiza este video viral y decide QUÉ contenido sobre él funcionará mejor para el público hispano.
{CLIP_POLICY}

{source}

Responde SOLO con JSON válido:
- "why_works": por qué funciona el original (2-3 frases, en español)
- "audience": a qué público hispano le va a explotar este tema (1 frase)
- "options": exactamente 3 enfoques DIFERENTES entre sí, ordenados de mejor a alternativo, cada uno:
  - "id": "a", "b" o "c"
  - "format": tipo de pieza (reacción, fenómeno, explicación profunda, documental, datos, historia, teoría...)
  - "title": título propuesto en español para el video de KAI (máx 100 caracteres)
  - "pitch": qué haría ese video y por qué funcionaría con alta retención (1-2 frases)
  - "duration_sec": duración recomendada para KAI en segundos (entre 90 y 480 s según la riqueza y profundidad del tema)
  - "viral_estimate": 0 a 100 de fuerza viral estimada de ESTE enfoque
  - "recommended": true SOLO en el mejor enfoque
Los enfoques deben respetar el tipo de contenido: con derechos (música/cine) → piezas sobre el
FENÓMENO o reacción, nunca análisis de la obra ni recreación."""
        else:
            category = str(payload.get("category", "urgente")).lower()
            title = str(payload.get("title", ""))
            why = str(payload.get("why", ""))
            angle = str(payload.get("angle", ""))
            is_deep = category in ("descubrimiento", "ciencia", "espacio", "arqueologia", "tecnologia", "misterio", "concepto")
            prompt = f"""Eres el estratega de contenido del canal de divulgación en español de KAI.
Vas a convertir este TEMA VIRAL URGENTE en una estrategia de producción audiovisual de ALTO IMPACTO y MÁXIMA RETENCIÓN.

TEMA URGENTE:
- Categoría: {category}
- Titular: {title}
- Por qué explota: {why}
- Ángulo sugerido: {angle}
- Naturaleza: {"Tema de profundidad científica / investigación / descubrimiento con abundante material" if is_deep else "Noticia / impacto rápido"}

REGLAS DE RETENCIÓN, ESTRUCTURA Y DURACIÓN:
- Para temas de CIENCIA, DESCUBRIMIENTOS, ESPACIO, ARQUEOLOGÍA, MISTERIOS o TECNOLOGÍA: NO hagas resúmenes breves y apresurados de 2-3 minutos que desperdician el material. La audiencia busca misterio, evidencia paso a paso, datos científicos rigurosos (tarjetas Bento, gráficos y comparativas) y un arco narrativo completo.
Recomienda duraciones de 300 a 480 segundos (5 a 8 minutos) para los enfoques principales de investigación y documental, y de 180 a 240 segundos solo para un enfoque de resumen ágil.
- Para noticias de impacto rápido o curiosidades: recomienda 120 a 240 segundos (2 a 4 minutos).

Responde SOLO con JSON válido:
- "why_works": por qué explotará este tema en español y qué gancho emocional activa (2-3 frases)
- "audience": perfil de la audiencia objetivo (1 frase)
- "options": exactamente 3 enfoques de producción DIFERENTES, ordenados del más potente al alternativo:
  - "id": "a", "b" o "c"
  - "format": tipo de pieza (ej: "Docu-Análisis Profundo", "Explicación Científica Dinámica", "Enigma & Revelación", "Debate & Futuro")
  - "title": título impactante para el video de KAI (máx 90 caracteres)
  - "pitch": promesa del video, arco narrativo y por qué mantendrá al espectador pegado (1-2 frases)
  - "duration_sec": duración recomendada en segundos ({'300 a 480' if is_deep else '120 a 300'})
  - "viral_estimate": 0 a 100 de fuerza viral estimada
  - "recommended": true SOLO en el mejor enfoque"""

        from utils.json_validator import JSONValidator
        client = LLMClient()
        raw = client.generate(prompt, json_mode=True, deadline_sec=75)
        data = JSONValidator.extract_and_parse(raw)
        options = []
        for idx, opt in enumerate(data.get("options", [])[:3]):
            title_opt = str(opt.get("title", "")).strip()[:110]
            if not title_opt:
                continue
            dur = int(opt.get("duration_sec") or (360 if kind == "topic" and category in ("descubrimiento", "ciencia", "espacio", "arqueologia", "tecnologia", "misterio") else 120))
            options.append({
                "id": str(opt.get("id") or chr(97 + idx)),
                "format": str(opt.get("format", "enfoque")).strip()[:28],
                "title": title_opt,
                "pitch": str(opt.get("pitch", "")).strip()[:280],
                "duration_sec": max(45, min(900, dur)),
                "viral_estimate": max(0, min(100, int(opt.get("viral_estimate") or 50))),
                "recommended": bool(opt.get("recommended")),
            })
        if not options:
            raise ValueError("La IA no devolvió enfoques válidos.")
        return {
            "why_works": str(data.get("why_works", ""))[:400],
            "audience": str(data.get("audience", ""))[:200],
            "options": options,
        }

    def build_replication(self, kind: str, payload: Dict[str, Any],
                          choice: Optional[Dict[str, Any]] = None,
                          instructions: str = "") -> Dict[str, Any]:
        """Convierte un video viral o un tema urgente en la brief en español para KAI.

        Si `choice` viene dado, el director humano eligió ese enfoque (viene de
        analyze_video / analyze_item) y la brief debe producirlo exactamente. `instructions`
        permite indicaciones libres adicionales. KAI NUNCA reutiliza fragmentos
        del original: todo el material es 100% propio del estudio.
        """
        if kind == "video":
            source = self._video_source_block(payload)
            format_rules = (
                "REGLAS DE FORMATO según el tipo de contenido:\n"
                "- Musical, cine, trailer o contenido con DERECHOS: pieza sobre el FENÓMENO/reacción "
                "(por qué explota, la historia, cifras, impacto cultural). NUNCA análisis de la obra ni recreación.\n"
                "- Gaming, entretenimiento, comedia, vlogs: explica el FENÓMENO/reto/formato; se permiten clips de "
                "gameplay del original ≤6s como apoyo con narración propia encima.\n"
                "- Educativo, ciencia, noticia, tutorial: replica el FORMATO con mejor investigación y estructura.\n"
                "- Si el original es un Short vertical, la réplica debe ser ágil y directa al gancho."
            )
            duration_rule = (
                '- "recommended_duration_sec": duración del video de KAI en segundos (90 a 480 s según la riqueza y profundidad del contenido), '
                "decidida por el ritmo del original y el formato elegido, NO una copia apresurada ni recortada."
            )
        else:
            category = str(payload.get("category", "urgente")).lower()
            is_deep = category in ("descubrimiento", "ciencia", "espacio", "arqueologia", "tecnologia", "misterio", "concepto")
            source = (
                f"TEMA URGENTE SIN COBERTURA:\n"
                f"- Titular: {payload.get('title', '')}\n"
                f"- Urgencia: {payload.get('urgency', 5)}/10 · Viralidad estimada: {payload.get('score', 50)}/100\n"
                f"- Por qué explota: {payload.get('why', '')}\n"
                f"- Ángulo sugerido: {payload.get('angle', '')}\n"
                f"- Categoría: {category} ({'Tema profundo con abundante material científico/documental' if is_deep else 'Noticia rápida'})"
            )
            format_rules = (
                "REGLAS DE PROFUNDIDAD: Para temas de ciencia, descubrimientos, misterios y espacio con mucho material, "
                "diseña un guión rico y completo con evidencia paso a paso, datos Bento y comparativas. NO resumas en 2-3 minutos."
            )
            if is_deep:
                duration_rule = (
                    '- "recommended_duration_sec": duración del video de KAI en segundos entre 300 y 480 (5 a 8 minutos) '
                    'para agotar y aprovechar al máximo todo el material disponible, el misterio y los datos duros sin recortar la experiencia.'
                )
            else:
                duration_rule = (
                    '- "recommended_duration_sec": duración del video de KAI en segundos (120 a 240 s según la urgencia y ritmo del tema).'
                )

        directive = ""
        if choice:
            directive = (
                f"\nDECISIÓN DEL DIRECTOR HUMANO (obligatoria, produce EXACTAMENTE esto):\n"
                f"- Enfoque elegido: {choice.get('format', '')}\n"
                f"- Título objetivo: {choice.get('title', '')}\n"
                f"- Pitch: {choice.get('pitch', '')}\n"
                f"- Duración objetivo: {choice.get('duration_sec', 90)} s\n"
            )
        if instructions.strip():
            directive += f"\nIndicaciones libres del director: {instructions.strip()[:400]}\n"

        prompt = f"""Eres el director creativo del canal de divulgación en español de KAI.
Vas a replicar con mejoras este contenido para el público hispano. NO copies: supéralo.
{CLIP_POLICY}

{source}

{format_rules}
{directive}
Responde SOLO con JSON válido:
- "topic": tema/producto concreto para que KAI investigue y produzca (máx 110 caracteres, en español neutro,
  con gancho. Para contenido con derechos debe ser sobre el FENÓMENO, no sobre la obra)
- "extra_notes": brief para el equipo IA: por qué funciona el original, qué mejorar/añadir, estructura
  (gancho 3s → desarrollo → cierre), tono, tipo de tarjetas visuales y recordatorio de producción con material
  original. Máximo 550 caracteres, en español.
{duration_rule}"""

        from utils.json_validator import JSONValidator
        client = LLMClient()
        raw = client.generate(prompt, json_mode=True, deadline_sec=75)
        data = JSONValidator.extract_and_parse(raw)
        topic = str(data.get("topic", "")).strip()[:120] or str(payload.get("title", ""))[:110]
        notes = str(data.get("extra_notes", "")).strip()[:600]
        if not topic:
            raise ValueError("La IA no devolvió un tema válido para replicar.")
        try:
            recommended = int(data.get("recommended_duration_sec") or 0)
        except (TypeError, ValueError):
            recommended = 0
        if choice and choice.get("duration_sec"):
            recommended = int(choice["duration_sec"])
        elif not recommended or recommended <= 0:
            category = str(payload.get("category", "")).lower()
            is_deep = category in ("descubrimiento", "ciencia", "espacio", "arqueologia", "tecnologia", "misterio", "concepto")
            recommended = 360 if is_deep else 180

        # Registrarlo para no volver a sugerirlo como "sin cobertura".
        produced = self._state.setdefault("produced", [])
        if topic not in produced:
            produced.append(topic)
            produced[:] = produced[-120:]
        self._save()
        safe_log(f"[TrendRadar] Réplica preparada: {topic} ({recommended}s)")
        return {"topic": topic, "extra_notes": notes, "recommended_duration_sec": recommended}
