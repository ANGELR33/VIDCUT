"""Radar de Tendencias en Tiempo Real (RealtimeTrendRadar).

Conexión directa con YouTube Data API v3 y Gemini Flash Lite para:
1. Descubrir clips virales y momentos cumbre de podcasts en español (The Wild Project, Creativo, Date un Vlog, Gusgri).
2. Detectar noticias y avances de IA y tecnología que están explotando en las últimas 24 horas.
3. Extraer temas de geopolítica e historia con alta tracción social.
4. Convertir tendencias en conceptos de video con hooks magnéticos de 50 segundos.
"""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, Dict, List, Optional, Set

import requests

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.realtime_trend_radar")


def _parse_iso_duration(duration_str: str) -> float:
    """Convierte formato ISO 8601 de YouTube (ej: PT1M30S o PT45S) a segundos."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str or "")
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return float(hours * 3600 + minutes * 60 + seconds)


class RealtimeTrendRadar:
    """Radar de Tendencias en Tiempo Real impulsado por YouTube Data API y Gemini."""

    def __init__(self):
        self.api_key = settings.YOUTUBE_DATA_API_KEY
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def get_trending_podcast_candidates(self, used_ids: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """Busca clips y momentos cumbre de podcasts virales en español con alta retención."""
        if not self.api_key:
            return []

        used = used_ids or set()
        queries = [
            ("The Wild Project clip reflexion debate", "The Wild Project", "Debate y Ciencia"),
            ("Javier Santaolalla explicacion fisica universo", "Date un Vlog", "Ciencia y Cosmos"),
            ("Creativo Roberto Martinez mejor momento reflexion", "Creativo", "Mentalidad y Criterio"),
            ("Gusgri podcast momento revelacion", "Gusgri Podcast", "Verdades Incómodas"),
            ("Filosofia de la calle debate dilema moral", "Filosofía", "Dilema Humano"),
        ]
        random.shuffle(queries)

        candidates: List[Dict[str, Any]] = []

        for q, channel_name, topic in queries[:3]:
            try:
                safe_log(f"[TrendRadar] 📡 Escaneando tendencias en YouTube: «{q}»...")
                s_res = requests.get(
                    f"{self.base_url}/search",
                    params={
                        "part": "snippet",
                        "q": q,
                        "order": "viewCount",
                        "type": "video",
                        "relevanceLanguage": "es",
                        "maxResults": 6,
                        "key": self.api_key,
                    },
                    timeout=10,
                )

                if s_res.status_code != 200:
                    safe_log(f"[TrendRadar] Aviso YouTube Search API ({s_res.status_code}): {s_res.text[:120]}")
                    continue

                items = s_res.json().get("items", [])
                video_ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId") and it["id"]["videoId"] not in used]

                if not video_ids:
                    continue

                # Consultar duraciones exactas
                v_res = requests.get(
                    f"{self.base_url}/videos",
                    params={
                        "part": "snippet,contentDetails,statistics",
                        "id": ",".join(video_ids[:10]),
                        "key": self.api_key,
                    },
                    timeout=10,
                )

                if v_res.status_code != 200:
                    continue

                for v_item in v_res.json().get("items", []):
                    vid = v_item["id"]
                    if vid in used:
                        continue

                    duration_str = v_item.get("contentDetails", {}).get("duration", "")
                    dur_sec = _parse_iso_duration(duration_str)
                    snippet = v_item.get("snippet", {})
                    title = snippet.get("title", "")
                    views = int(v_item.get("statistics", {}).get("viewCount", 0))

                    # Filtrar por duración manejable (25s a 240s) o clips cortos
                    if 25.0 <= dur_sec <= 260.0 or (dur_sec == 0 and ("clip" in title.lower() or "short" in title.lower())):
                        candidates.append({
                            "id": vid,
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "title": title,
                            "duration": dur_sec,
                            "views": views,
                            "channel": channel_name,
                            "topic": topic,
                        })

                if candidates:
                    break

            except Exception as exc:
                safe_log(f"[TrendRadar] Error buscando tendencias de podcast: {exc}")

        # Ordenar por visualizaciones
        candidates.sort(key=lambda x: x.get("views", 0), reverse=True)
        return candidates

    def get_trending_tech_topic(self) -> Optional[Dict[str, Any]]:
        """Descubre un tema de tecnología o IA en tendencia y genera un concepto de Reel de 50s."""
        if not self.api_key:
            return None

        try:
            safe_log("[TrendRadar] 📡 Rastreando tendencias de IA y Tecnología en español...")
            s_res = requests.get(
                f"{self.base_url}/search",
                params={
                    "part": "snippet",
                    "q": "inteligencia artificial avance tecnologia OpenAI Google Nvidia",
                    "order": "viewCount",
                    "type": "video",
                    "relevanceLanguage": "es",
                    "maxResults": 3,
                    "key": self.api_key,
                },
                timeout=10,
            )

            if s_res.status_code == 200:
                items = s_res.json().get("items", [])
                if items:
                    chosen_sn = random.choice(items)["snippet"]
                    trend_title = chosen_sn.get("title", "")
                    trend_desc = chosen_sn.get("description", "")

                    # Destilar con Gemini
                    from google import genai
                    from google.genai import types

                    gemini_key = settings.GEMINI_API_KEY.split(",")[0].strip()
                    client = genai.Client(api_key=gemini_key)
                    prompt = (
                        f"A partir de este tema tecnológico en tendencia en español: '{trend_title}' ({trend_desc}), "
                        f"crea un concepto de Reel de 50 segundos para el canal 'Contrapunto'. "
                        f"Devuelve estrictamente en JSON con claves: "
                        f"'title': título potente en español (máx 10 palabras), "
                        f"'hook': gancho inicial de impacto (máx 15 palabras), "
                        f"'desc': descripción persuasiva para Facebook (con 4 hashtags)."
                    )
                    res = client.models.generate_content(
                        model="gemini-flash-lite-latest",
                        contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    if res.text:
                        data = json.loads(res.text)
                        safe_log(f"[TrendRadar] 🚀 Tendencia Tech Detectada: «{data.get('title')}»")
                        return data

        except Exception as exc:
            safe_log(f"[TrendRadar] Aviso extrayendo tendencia Tech: {exc}")

        return None

    def get_trending_geopolitics_topic(self) -> Optional[Dict[str, Any]]:
        """Descubre un tema de geopolítica o historia en tendencia y genera un concepto de Reel de 52s."""
        if not self.api_key:
            return None

        try:
            safe_log("[TrendRadar] 📡 Rastreando tendencias de Historia y Geopolítica en español...")
            s_res = requests.get(
                f"{self.base_url}/search",
                params={
                    "part": "snippet",
                    "q": "geopolitica historia documental poder mundial conflicto estrategia",
                    "order": "viewCount",
                    "type": "video",
                    "relevanceLanguage": "es",
                    "maxResults": 3,
                    "key": self.api_key,
                },
                timeout=10,
            )

            if s_res.status_code == 200:
                items = s_res.json().get("items", [])
                if items:
                    chosen_sn = random.choice(items)["snippet"]
                    trend_title = chosen_sn.get("title", "")
                    trend_desc = chosen_sn.get("description", "")

                    from google import genai
                    from google.genai import types

                    gemini_key = settings.GEMINI_API_KEY.split(",")[0].strip()
                    client = genai.Client(api_key=gemini_key)
                    prompt = (
                        f"A partir de este tema histórico/geopolítico en tendencia: '{trend_title}' ({trend_desc}), "
                        f"crea un concepto de Reel de 52 segundos para el canal 'Núcleo Ideológico'. "
                        f"Devuelve estrictamente en JSON con claves: "
                        f"'title': título solemne y documental (máx 10 palabras), "
                        f"'hook': gancho de revelación histórica (máx 15 palabras), "
                        f"'desc': descripción para Facebook con 4 hashtags."
                    )
                    res = client.models.generate_content(
                        model="gemini-flash-lite-latest",
                        contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    if res.text:
                        data = json.loads(res.text)
                        safe_log(f"[TrendRadar] 🏛️ Tendencia Geopolítica Detectada: «{data.get('title')}»")
                        return data

        except Exception as exc:
            safe_log(f"[TrendRadar] Aviso extrayendo tendencia Geopolítica: {exc}")

        return None


# Singleton
realtime_trend_radar = RealtimeTrendRadar()
