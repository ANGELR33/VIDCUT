"""Módulo Exclusivo y Aislado para Huellas Sagradas (Cine Bíblico & Fe).

Aislamiento Estricto:
1. Nicho 100% Espiritual y Bíblico: Películas cristianas (Hacksaw Ridge, La Pasión, Ben-Hur),
   versículos de consuelo y milagros de fe.
2. Cero mezcla con Anime, Política o Tecnología.
3. Subtítulos Karaoke seguros y marca de agua 'Huellas Sagradas'.
4. Publicación directa a la página de Facebook 'Huellas Sagradas' (ID: 1375932688939134).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
import requests

from config.settings import settings
from core.llm import safe_log
from core.facebook_publisher import publish_video_to_facebook

logger = logging.getLogger("aethercut.huellas_sagradas")

BASE_URL = "http://127.0.0.1:8000"
PAGE_ID = "1375932688939134"
PERMANENT_PAGES_FILE = settings.STORAGE_DIR / "facebook_permanent_pages.json"

CHRISTIAN_TOPICS = [
    {
        "title": "Hasta el Último Hombre (Hacksaw Ridge): La oración de Desmond Doss bajo fuego enemigo",
        "hook": "Le dijeron que moriría en el primer minuto. Pero él solo pidió salvar a uno más.",
        "desc": "Una lección conmovedora de convicción y fe que desafió al mundo entero. 🙏 Comparte esta reflexión."
    },
    {
        "title": "El perdón inquebrantable que salvó una vida en medio de la guerra",
        "hook": "Cuando todos pedían venganza, él eligió perdonar. Y el milagro ocurrió.",
        "desc": "El perdón no cambia el pasado, pero abre las puertas del futuro. 🙏 Reflexión de fe."
    },
    {
        "title": "La fe del Centurión: 'Tan solo di la palabra y mi siervo sanará'",
        "hook": "No pidió que fuera a su casa. Solo creyó en una palabra de poder.",
        "desc": "La fe que asombró a Jesús. Una reflexión para cuando sientas que tus fuerzas se acaban. ✝️"
    },
    {
        "title": "El milagro de la tormenta en el mar: '¿Por qué teméis, hombres de poca fe?'",
        "hook": "Las olas cubrían la barca, pero el Creador dormía en paz.",
        "desc": "Si Dios está en tu barca, ninguna tormenta podrá hundir tu propósito. 🙏 Reflexión de esperanza."
    },
    {
        "title": "El juicio de Salomón: El verdadero amor de una madre dispuesto a renunciar",
        "hook": "Prefería perder a su hijo antes de verlo morir. Así descubrió la verdad.",
        "desc": "La sabiduría de Dios revelada en el amor más puro. Una historia milenaria que conmueve hoy. ✝️"
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


class HuellasSagradasProducer:
    """Productor especializado y aislado para Huellas Sagradas."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.OUTPUTS_DIR

    def produce_and_publish(self) -> Dict[str, Any]:
        safe_log("\n[HuellasSagradas] ✝️ Iniciando producción aislada de Cine Bíblico & Fe...")
        token = _get_page_token()
        if not token:
            raise RuntimeError("Token permanente de Facebook para Huellas Sagradas no encontrado.")

        import random
        chosen = random.choice(CHRISTIAN_TOPICS)

        payload = {
            "topic": f"Reflexión cristiana y cine bíblico: {chosen['title']}",
            "style": "divulgacion",
            "duration_sec": 52,
            "aspect_ratio": "9:16",
            "voice": "speechify:alejandro",
            "flash_audit": True,
            "origin": "universal_tour_huellas",
            "auto_publish": False,
            "extra_notes": (
                "CINE CRISTIANO, FE Y ESPERANZA EXCLUSIVAMENTE:\n"
                "- Voz solemne, emotiva, respetuosa y reflexiva.\n"
                "- Visuales: Cine bíblico, paisajes sagrados, pinturas al óleo clásicas y luz cálida.\n"
                "- PROHIBIDO: Anime, tecnología, política, videojuegos o metraje de stock genérico."
            ),
        }

        created = requests.post(f"{BASE_URL}/api/streamer/create", json=payload, timeout=60).json()
        project_id = created.get("project_id")
        if not project_id:
            raise RuntimeError(f"No se pudo crear proyecto para Huellas Sagradas: {created}")

        safe_log(f"[HuellasSagradas] Proyecto creado con éxito ({project_id}). Esperando renderización 9:16...")
        master_file = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"

        for _ in range(120):
            time.sleep(15)
            if master_file.exists() and master_file.stat().st_size > 1_000_000:
                break

        if not master_file.exists():
            raise TimeoutError("Render de Huellas Sagradas agotó el tiempo de espera.")

        title = f"{chosen['title'][:80]}"
        desc = (
            f"{chosen['hook']}\n\n"
            f"{chosen['desc']}\n\n"
            f"#Fe #Dios #CineCristiano #Reflexión #Esperanza #Amor #Paz"
        )

        # Control de Calidad Visual Autónomo con Gemini Vision (0% Anime / 0% Contaminación)
        from core.vision_qa import vision_qa
        qa = vision_qa.audit_video(
            video_path=master_file,
            expected_niche="Cine bíblico, paisajes sagrados, pinturas al óleo y relatos de fe cristiana",
            forbidden_elements=["anime", "tecnología", "política", "videojuegos", "caricaturas"],
            channel_name="Huellas Sagradas"
        )
        if not qa.get("approved", True):
            safe_log(f"[HuellasSagradas] 🛑 Publicación abortada por Vision QA: {qa.get('critique')}")
            return {
                "success": False,
                "project_id": project_id,
                "reason": f"Rechazado por Vision QA: {qa.get('critique')}",
                "qa_details": qa
            }

        safe_log(f"[HuellasSagradas] 📤 Publicando Reel a Facebook Page (ID: {PAGE_ID})...")
        pub = publish_video_to_facebook(
            video_path=master_file,
            title=title,
            description=desc,
            page_id=PAGE_ID,
            access_token=token,
            is_reel=True,
        )

        # Sembrar comentario inicial de reflexión para activar el algoritmo de comentarios
        vid_id = pub.get("video_id")
        if vid_id:
            try:
                from core.facebook_community_manager import facebook_community_manager
                facebook_community_manager.post_seed_comment(
                    video_id=vid_id,
                    page_id=PAGE_ID,
                    access_token=token,
                    video_title=title,
                    debate_question="¿Qué parte de esta historia de fe te tocó más el corazón? Deja tu reflexión o petición de oración aquí abajo. 🙏👇"
                )
            except Exception:
                pass

        return {
            "success": True,
            "project_id": project_id,
            "title": title,
            "post_url": pub.get("post_url"),
        }
