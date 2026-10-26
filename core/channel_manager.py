"""
Multi-Channel Manager & Content Classifier (AetherCut Pro).

Permite gestionar múltiples canales de YouTube (Divulgación, Curiosidades, Reacciones, etc.),
almacenar sus credenciales y perfiles de marca, y clasificar automáticamente el contenido
generado por la IA hacia el canal óptimo para publicación asistida o automática.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger("aethercut.channel_manager")

CHANNELS_FILE = settings.STORAGE_DIR / "channels.json"

# Canales iniciales predeterminados que coinciden con los nichos solicitados
DEFAULT_CHANNELS: List[Dict[str, Any]] = [
    {
        "id": "divulgacion",
        "name": "Divulgación & Descubrimientos",
        "category_name": "Divulgación Científica e Histórica",
        "category_id": "28",  # Ciencia y Tecnología en YouTube
        "badge": "🔬 CIENCIA & HALLAZGOS",
        "color": "#ff9436",
        "description": "Descubrimientos arqueológicos, misiones espaciales, avances de la ciencia y fenómenos naturales.",
        "tags_seed": ["ciencia", "descubrimientos", "divulgacion", "arqueologia", "universo", "documental"],
        "tone": "documental, analítico, fascinante y riguroso",
        "studio_url": "https://studio.youtube.com/channel/UC/videos/upload?d=pt",
        "youtube_channel_id": "",
        "is_oauth_connected": False,
    },
    {
        "id": "curiosidades",
        "name": "Curiosidades & Tops",
        "category_name": "Curiosidades y Datos Asombrosos",
        "category_id": "24",  # Entretenimiento en YouTube
        "badge": "💡 CURIOSIDADES & TOPS",
        "color": "#00f5a0",
        "description": "Preguntas insólitas, rankings, récords mundiales, cosas que no sabías y misterios cotidianos.",
        "tags_seed": ["curiosidades", "top 10", "datos curiosos", "sabias que", "increible", "entretenimiento"],
        "tone": "dinámico, ágil, lleno de sorpresas y ritmo rápido",
        "studio_url": "https://studio.youtube.com/channel/UC/videos/upload?d=pt",
        "youtube_channel_id": "",
        "is_oauth_connected": False,
    },
    {
        "id": "reacciones",
        "name": "Reacciones & Casos Virales",
        "category_name": "Reacciones y Análisis de Casos",
        "category_id": "24",  # Entretenimiento
        "badge": "🎙️ REACCIONES & OPINIÓN",
        "color": "#00e5ff",
        "description": "Reacción en vivo de KAI Streamer a videos de la comunidad, noticias virales y debates candentes.",
        "tags_seed": ["reaccion", "streamer", "analisis", "en vivo", "debate", "viral"],
        "tone": "conversacional, espontáneo, enfocado en interacción y debate",
        "studio_url": "https://studio.youtube.com/channel/UC/videos/upload?d=pt",
        "youtube_channel_id": "",
        "is_oauth_connected": False,
    },
    {
        "id": "tecnologia",
        "name": "Tecnología & Futuro IA",
        "category_name": "Tecnología e Inteligencia Artificial",
        "category_id": "28",  # Ciencia y Tecnología
        "badge": "⚡ TECH & FUTURO IA",
        "color": "#a855f7",
        "description": "Modelos de IA, automatización, herramientas digitales, robots y futuro tecnológico.",
        "tags_seed": ["tecnologia", "inteligencia artificial", "ia", "futuro", "software", "innovacion"],
        "tone": "vanguardista, técnico accesible, visión de futuro",
        "studio_url": "https://studio.youtube.com/channel/UC/videos/upload?d=pt",
        "youtube_channel_id": "",
        "is_oauth_connected": False,
    },
]


class ChannelManager:
    """Administrador centralizado de canales de YouTube para publicación multi-nicho."""

    @classmethod
    def get_channels_file(cls) -> Path:
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        return CHANNELS_FILE

    @classmethod
    def list_channels(cls) -> List[Dict[str, Any]]:
        file_path = cls.get_channels_file()
        if not file_path.exists():
            cls.save_channels(DEFAULT_CHANNELS)
            return DEFAULT_CHANNELS

        try:
            channels = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(channels, list) or len(channels) == 0:
                cls.save_channels(DEFAULT_CHANNELS)
                return DEFAULT_CHANNELS
            return channels
        except Exception as exc:
            logger.warning(f"Error leyendo canales guardados: {exc}")
            return DEFAULT_CHANNELS

    @classmethod
    def save_channels(cls, channels: List[Dict[str, Any]]) -> None:
        file_path = cls.get_channels_file()
        file_path.write_text(json.dumps(channels, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def get_channel(cls, channel_id: str) -> Optional[Dict[str, Any]]:
        channels = cls.list_channels()
        for ch in channels:
            if ch.get("id") == channel_id:
                return ch
        return None

    @classmethod
    def upsert_channel(cls, channel_data: Dict[str, Any]) -> Dict[str, Any]:
        channels = cls.list_channels()
        ch_id = channel_data.get("id", "").strip()
        if not ch_id:
            import uuid
            ch_id = f"ch_{uuid.uuid4().hex[:6]}"
            channel_data["id"] = ch_id

        found = False
        updated_list = []
        for ch in channels:
            if ch.get("id") == ch_id:
                merged = {**ch, **channel_data}
                updated_list.append(merged)
                found = True
            else:
                updated_list.append(ch)

        if not found:
            updated_list.append(channel_data)

        cls.save_channels(updated_list)
        return channel_data

    @classmethod
    def delete_channel(cls, channel_id: str) -> bool:
        channels = cls.list_channels()
        filtered = [ch for ch in channels if ch.get("id") != channel_id]
        if len(filtered) < len(channels):
            cls.save_channels(filtered)
            return True
        return False

    @classmethod
    def classify_content(cls, topic: str, speech_excerpt: str = "") -> Dict[str, Any]:
        """
        Clasifica automáticamente una temática o guion hacia el canal más idóneo.
        Evalúa coincidencia temática mediante IA o análisis semántico de palabras clave.
        """
        channels = cls.list_channels()
        full_text = f"{topic} {speech_excerpt}".lower()

        # Palabras clave de clasificación directa
        scores: Dict[str, float] = {ch["id"]: 0.1 for ch in channels}

        # Reglas para Divulgación
        div_kw = ["científic", "descubri", "arqueolog", "océan", "nasa", "universo", "historia", "fósil", "planeta", "tierra", "especie", "investigad"]
        for kw in div_kw:
            if kw in full_text:
                scores["divulgacion"] = scores.get("divulgacion", 0) + 1.2

        # Reglas para Curiosidades
        cur_kw = ["sabías", "sabias", "top", "curiosidad", "récord", "record", "increíble", "increible", "extrañ", "asombros", "número 1", "por qué", "por que"]
        for kw in cur_kw:
            if kw in full_text:
                scores["curiosidades"] = scores.get("curiosidades", 0) + 1.2

        # Reglas para Reacciones
        reac_kw = ["reacción", "reaccion", "streamer", "opinión", "opinion", "debate", "caso", "video de", "polemica", "polémica", "youtuber", "twitch"]
        for kw in reac_kw:
            if kw in full_text:
                scores["reacciones"] = scores.get("reacciones", 0) + 1.5

        # Reglas para Tecnología
        tech_kw = ["ia", "inteligencia artificial", "gemini", "chatgpt", "deepseek", "robot", "código", "software", "algoritmo", "chip", "nvidia", "quantum"]
        for kw in tech_kw:
            if kw in full_text:
                scores["tecnologia"] = scores.get("tecnologia", 0) + 1.3

        # Intentar clasificación fina con LLM si hay API Key
        try:
            from core.llm import LLMClient
            client = LLMClient()
            channel_options_str = "\n".join([f"- {c['id']}: {c['name']} ({c['description']})" for c in channels])
            prompt = f"""Clasifica este tema de video en el canal de YouTube más adecuado entre las opciones disponibles:

Tema: {topic}
Extracto: {speech_excerpt[:300]}

Canales disponibles:
{channel_options_str}

Responde SOLO en formato JSON válido:
{{
  "recommended_channel_id": "uno_de_los_ids_arriba",
  "confidence": 0.95,
  "reason": "Explicación breve de por qué encaja en este canal"
}}"""
            from utils.json_validator import JSONValidator
            raw_res = client.generate(prompt, json_mode=True, deadline_sec=15)
            parsed = JSONValidator.extract_and_parse(raw_res)
            best_id = parsed.get("recommended_channel_id")
            if any(c["id"] == best_id for c in channels):
                best_channel = cls.get_channel(best_id)
                return {
                    "channel": best_channel,
                    "confidence": float(parsed.get("confidence", 0.90)),
                    "reason": parsed.get("reason", "Clasificado por análisis contextual de la IA"),
                    "all_scores": scores,
                }
        except Exception:
            pass

        # Fallback a heurística de scores
        best_id = max(scores, key=scores.get)
        best_channel = cls.get_channel(best_id) or channels[0]
        return {
            "channel": best_channel,
            "confidence": 0.85,
            "reason": f"Clasificado por coincidencia temática con {best_channel.get('name')}",
            "all_scores": scores,
        }
