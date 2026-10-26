"""Módulo Exclusivo y Aislado para Contrapunto & PixelGrama (Tecnología & IA).

Aislamiento Estricto:
1. Nicho 100% Inteligencia Artificial, Software, Hardware y Futuro.
2. Visuales: Capturas de código, interfaces de IA, chips de silicio, datacenters y keynotes reales.
3. Prohibido TERMINANTEMENTE: Anime, religión o personajes de ficción.
4. Subtítulos Karaoke seguros y marca de agua 'Contrapunto'.
5. Publicación directa a Facebook 'Contrapunto' (ID: 1039337485919543) y YouTube 'PixelGrama'.
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
import requests

from config.settings import settings
from core.llm import safe_log
from core.facebook_publisher import publish_video_to_facebook

logger = logging.getLogger("aethercut.tech_ai")

BASE_URL = "http://127.0.0.1:8000"
PAGE_ID = "1039337485919543"
YT_CHANNEL_ID = "UChQZ2TvHifQBrDzbZRjGDkA"  # PixelGrama (YouTube)
PERMANENT_PAGES_FILE = settings.STORAGE_DIR / "facebook_permanent_pages.json"

TECH_TOPICS = [
    {
        "title": "El Día que ChatGPT Casi Muere: Los 10 Días de Caos en OpenAI",
        "hook": "Sam Altman fue despedido un viernes por la tarde. El lunes, casi destruye la IA moderna.",
        "desc": "La verdadera historia detrás de la crisis que casi acaba con la mayor empresa de inteligencia artificial del planeta. 🤖"
    },
    {
        "title": "La Revolución Silenciosa de los Chips Cuánticos: ¿El Fin del Cifrado?",
        "hook": "Las contraseñas que usas hoy podrían romperse en segundos. Así cambiará todo.",
        "desc": "El salto de la computación cuántica y la carrera tecnológica global entre gigantes informáticos. 💻"
    },
    {
        "title": "Robots Humanoides en Fábricas Reales: Lo Que Nadie Te Cuenta de la Automatización",
        "hook": "Ya no son prototipos de laboratorio. Ya están ensamblando coches sin intervención humana.",
        "desc": "¿Estamos preparados para la sustitución de empleo físico por robots con visión artificial? Déjame tu opinión. ⚙️"
    },
    {
        "title": "Modelos de Razonamiento vs Lenguaje: Por Qué la IA ya no solo Predice Palabras",
        "hook": "Antes adivinaba la siguiente palabra. Ahora piensa antes de responder. Este es el salto.",
        "desc": "Cómo funcionan los nuevos modelos de pensamiento paso a paso que están superando exámenes de doctorado. 🧠"
    }
]


def _get_page_token() -> Optional[str]:
    if PERMANENT_PAGES_FILE.exists():
        try:
            data = json.loads(PERMANENT_PAGES_FILE.read_text(encoding="utf-8"))
            for p in data.get("pages", []):
                if p.get("id") == PAGE_ID:
                    return p.get("access_token")
        except Exception:
            pass
    return None


class TechAIProducer:
    """Productor especializado y aislado para Contrapunto (Tecnología & IA)."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.OUTPUTS_DIR

    def produce_and_publish(self) -> Dict[str, Any]:
        safe_log("\n[TechAIProducer] 🤖 Iniciando producción aislada de Tecnología & IA para Contrapunto...")
        token = _get_page_token()
        if not token:
            raise RuntimeError("Token permanente de Facebook para Contrapunto no encontrado.")

        # Intentar obtener tema caliente de tendencia de YouTube; si no, usar lista curada
        chosen = None
        try:
            from core.realtime_trend_radar import realtime_trend_radar
            chosen = realtime_trend_radar.get_trending_tech_topic()
        except Exception as exc:
            safe_log(f"[TechAIProducer] Aviso consultando TrendRadar Tech: {exc}")

        if not chosen:
            chosen = random.choice(TECH_TOPICS)

        payload = {
            "topic": f"Tecnología e Inteligencia Artificial: {chosen['title']}",
            "style": "divulgacion",
            "duration_sec": 50,
            "aspect_ratio": "9:16",
            "voice": "speechify:alejandro",
            "bgm_track": "upbeat",
            "flash_audit": True,
            "origin": "tech_contrapunto",
            "auto_publish": False,
            "extra_notes": (
                "TECNOLOGÍA, SOFTWARE E INTELIGENCIA ARTIFICIAL EXCLUSIVAMENTE:\n"
                "- Visuales: Servidores, datacenters, chips, conferencias de tecnología (OpenAI, NVIDIA, Google), código y gráficos limpios.\n"
                "- PROHIBIDO TERMINANTEMENTE: Anime, caricaturas, religión o metraje irrelevante."
            ),
        }

        created = requests.post(f"{BASE_URL}/api/streamer/create", json=payload, timeout=60).json()
        project_id = created.get("project_id")
        if not project_id:
            raise RuntimeError(f"No se pudo crear proyecto para Contrapunto: {created}")

        safe_log(f"[TechAIProducer] Proyecto creado con éxito ({project_id}). Esperando renderización 9:16...")
        master_file = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"

        for _ in range(120):
            time.sleep(15)
            if master_file.exists() and master_file.stat().st_size > 1_000_000:
                break

        if not master_file.exists():
            raise TimeoutError("Render de Contrapunto agotó el tiempo de espera.")

        title = f"{chosen['title'][:80]}"
        desc = (
            f"{chosen['hook']}\n\n"
            f"{chosen['desc']}\n\n"
            f"#Tecnología #IA #InteligenciaArtificial #OpenAI #Futuro #Innovación"
        )

        # Control de Calidad Visual Autónomo con Gemini Vision (0% Anime / 0% Contaminación)
        from core.vision_qa import vision_qa
        qa = vision_qa.audit_video(
            video_path=master_file,
            expected_niche="Tecnología, servidores, microchips, inteligencia artificial, robótica y gráficos técnicos",
            forbidden_elements=["anime", "religión", "política partidista", "videojuegos", "caricaturas"],
            channel_name="Contrapunto (Tech & IA)"
        )
        if not qa.get("approved", True):
            safe_log(f"[TechAIProducer] 🛑 Publicación abortada por Vision QA: {qa.get('critique')}")
            return {
                "success": False,
                "project_id": project_id,
                "reason": f"Rechazado por Vision QA: {qa.get('critique')}",
                "qa_details": qa
            }

        safe_log(f"[TechAIProducer] 📤 Publicando Reel a Facebook Page (ID: {PAGE_ID})...")
        pub = publish_video_to_facebook(
            video_path=master_file,
            title=title,
            description=desc,
            page_id=PAGE_ID,
            access_token=token,
            is_reel=True,
        )

        # Sindicación Multi-Plataforma: Publicación simultánea en YouTube Shorts (PixelGrama)
        yt_pub = None
        try:
            from core.youtube_oauth import upload_video
            safe_log(f"[TechAIProducer] 📺 Sindicando simultáneamente a YouTube Shorts (PixelGrama)...")
            yt_tags = ["tecnologia", "ia", "inteligencia artificial", "innovacion", "shorts", "software"]
            yt_pub = upload_video(
                video_path=master_file,
                title=f"{title[:85]} #Shorts",
                description=f"{desc}\n\n#Shorts #Tecnologia #IA",
                tags=yt_tags,
                privacy="public",
                channel_id=YT_CHANNEL_ID
            )
            safe_log(f"[TechAIProducer] ✓ Publicado en YouTube Shorts: {yt_pub.get('video_url')}")
        except Exception as yt_exc:
            safe_log(f"[TechAIProducer] Aviso en sindicación de YouTube Shorts: {yt_exc}")

        # Sembrar comentario inicial de debate tecnológico
        vid_id = pub.get("video_id")
        if vid_id:
            try:
                from core.facebook_community_manager import facebook_community_manager
                facebook_community_manager.post_seed_comment(
                    video_id=vid_id,
                    page_id=PAGE_ID,
                    access_token=token,
                    video_title=title,
                    debate_question="¿Crees que este avance acelerará el cambio más rápido de lo que esperamos? Los leo abajo. 👇"
                )
            except Exception:
                pass

        return {
            "success": True,
            "project_id": project_id,
            "title": title,
            "post_url": pub.get("post_url"),
            "youtube_url": yt_pub.get("video_url") if yt_pub else None,
        }
