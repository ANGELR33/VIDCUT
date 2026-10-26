"""Módulo Exclusivo y Aislado para Núcleo Ideológico (Geopolítica & Historia).

Aislamiento Estricto:
1. Nicho 100% Geopolítica, Historia Universal, Estrategia Militar y Dilemas de Poder.
2. Visuales: Archivo histórico de prensa, mapas geopolíticos, documentos desclasificados, fotos editoriales.
3. Prohibido TERMINANTEMENTE: Anime, ficción, o contenido no histórico.
4. Subtítulos Karaoke seguros y marca de agua 'Núcleo Ideológico'.
5. Publicación directa a Facebook 'Núcleo Ideológico' (ID: 1018230678031599) y YouTube 'the Deep dife'.
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

logger = logging.getLogger("aethercut.geopolitics")

BASE_URL = "http://127.0.0.1:8000"
PAGE_ID = "1018230678031599"
YT_CHANNEL_ID = "UC_8-TffWIAoiUMMDfiMUm2Q"  # the Deep dife (YouTube)
PERMANENT_PAGES_FILE = settings.STORAGE_DIR / "facebook_permanent_pages.json"

GEOPOLITICAL_TOPICS = [
    {
        "title": "La Muerte de Alejandro Magno: El Misterio del Veneno que Cambió el Mundo",
        "hook": "A los 32 años conquistó el mundo conocido. Días después, murió sin dejar un heredero claro.",
        "desc": "La evidencia histórica y toxicológica que desafía la versión oficial sobre el fin del mayor conquistador de la antigüedad. 🏛️"
    },
    {
        "title": "La Crisis de los Misiles en Cuba: Los 13 Días en que el Reloj del Fin del Mundo casi se Detiene",
        "hook": "Un solo oficial soviético se negó a presionar el botón rojo. Esa decisión nos salvó a todos.",
        "desc": "El momento más tenso de la Guerra Fría y la diplomacia secreta que evitó una guerra nuclear total. 🌍"
    },
    {
        "title": "El Estrecho de Malaca: El Cuello de Botella que Controla la Economía Mundial",
        "hook": "Por aquí pasa el 80% del petróleo de Asia. Si se bloquea 48 horas, colapsa el comercio global.",
        "desc": "El punto geográfico más codiciado del planeta y la pugna silenciosa de las superpotencias. 🚢"
    },
    {
        "title": "La Caída de Constantinopla: El Cañón Gigante que Destruyó Murallas de Mil Años",
        "hook": "Nadie creía que los muros más resistentes de la cristiandad pudieran caer. Hasta que llegó Orbón.",
        "desc": "El asedio de 1453 que marcó el final de la Edad Media y el inicio de una nueva era geopolítica. ⚔️"
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


class GeopoliticsHistoryProducer:
    """Productor especializado y aislado para Núcleo Ideológico (Geopolítica & Historia)."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.OUTPUTS_DIR

    def produce_and_publish(self, topic_override: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        safe_log("\n[GeopoliticsProducer] 🏛️ Iniciando producción aislada de Geopolítica & Historia para Núcleo Ideológico...")
        token = _get_page_token()
        if not token:
            raise RuntimeError("Token permanente de Facebook para Núcleo Ideológico no encontrado.")

        # Tema geopolítico de alto impacto (rotativo o especificado)
        if topic_override:
            chosen = topic_override
        else:
            candidates = [t for t in GEOPOLITICAL_TOPICS if "Malaca" not in t["title"]]
            chosen = random.choice(candidates) if candidates else random.choice(GEOPOLITICAL_TOPICS)

        payload = {
            "topic": f"Geopolítica e Historia: {chosen['title']}",
            "style": "divulgacion",
            "duration_sec": 48,
            "aspect_ratio": "9:16",
            "voice": "speechify:alejandro",
            "flash_audit": True,
            "origin": "geopolitics_nucleo",
            "enable_avatar": False,
            "burn_subtitles": True,
            "sub_style": "hormozi",
            "auto_publish": False,
            "extra_notes": (
                "INVESTIGACIÓN Y GEOPOLÍTICA DE ÉLITE (EDICIÓN AVANZADA ESTILO VOX / MAGNATES MEDIA / JOHNNY HARRIS):\n"
                "- CERO AVATAR / CERO DIBUJO ANIMADO: Formato 100% metraje documental cinematográfico a pantalla completa con voz en off de alta autoridad.\n"
                "- CERO PLANTILLAS GENÉRICAS / CERO CAJAS CENTRADAS: Prohibido colocar cajas opacas, diapositivas de texto o cards de PowerPoint tapando el video. El metraje 4K y el mapa satelital son los protagonistas absolutos.\n"
                "- TIPOGRAFÍA CINÉTICA DIRECTA ('free_title'): Letras gigantes con sombreado multicapa directamente sobre la imagen, sin fondo ni contenedor.\n"
                "- INSIGNIAS FLOTANTES ESCALONADAS ('chips'): Banderas y nombres de países ('China', 'Estados Unidos', 'Japón') en el tercio inferior seguro.\n"
                "- NARRATIVA PERIODÍSTICA CRUDA: Arranca con máxima tensión y apuestas reales ('En este instante, noventa mil buques cisterna...'). Cero muletillas de IA ('alguna vez te has preguntado', 'miren este dato')."
            ),
        }

        created = requests.post(f"{BASE_URL}/api/streamer/create", json=payload, timeout=60).json()
        project_id = created.get("project_id")
        if not project_id:
            raise RuntimeError(f"No se pudo crear proyecto para Núcleo Ideológico: {created}")

        safe_log(f"[GeopoliticsProducer] Proyecto creado con éxito ({project_id}). Esperando renderización 9:16...")
        master_file = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"

        for _ in range(120):
            time.sleep(15)
            if master_file.exists() and master_file.stat().st_size > 1_000_000:
                break

        if not master_file.exists():
            raise TimeoutError("Render de Núcleo Ideológico agotó el tiempo de espera.")

        title = f"{chosen['title'][:80]}"
        desc = (
            f"{chosen['hook']}\n\n"
            f"{chosen['desc']}\n\n"
            f"#Historia #Geopolítica #Mundo #Poder #Documental #Estrategia"
        )

        # Control de Calidad Visual Autónomo con Gemini Vision (0% Anime / 0% Contaminación)
        from core.vision_qa import vision_qa
        qa = vision_qa.audit_video(
            video_path=master_file,
            expected_niche="Historia universal, geopolítica, archivo histórico, mapas y documentos",
            forbidden_elements=["anime", "videojuegos", "caricaturas", "ciencia ficción infantil"],
            channel_name="Núcleo Ideológico (Historia & Geopolítica)"
        )
        if not qa.get("approved", True):
            safe_log(f"[GeopoliticsProducer] 🛑 Publicación abortada por Vision QA: {qa.get('critique')}")
            return {
                "success": False,
                "project_id": project_id,
                "reason": f"Rechazado por Vision QA: {qa.get('critique')}",
                "qa_details": qa
            }

        safe_log(f"[GeopoliticsProducer] 📤 Publicando Reel a Facebook Page (ID: {PAGE_ID})...")
        pub = publish_video_to_facebook(
            video_path=master_file,
            title=title,
            description=desc,
            page_id=PAGE_ID,
            access_token=token,
            is_reel=True,
        )

        # Sindicación Multi-Plataforma: Publicación simultánea en YouTube Shorts (the Deep dife)
        yt_pub = None
        try:
            from core.youtube_oauth import upload_video
            safe_log(f"[GeopoliticsProducer] 📺 Sindicando simultáneamente a YouTube Shorts (the Deep dife)...")
            yt_tags = ["historia", "geopolitica", "documental", "mundo", "datos", "shorts"]
            yt_pub = upload_video(
                video_path=master_file,
                title=f"{title[:85]} #Shorts",
                description=f"{desc}\n\n#Shorts #Historia #Geopolitica",
                tags=yt_tags,
                privacy="public",
                channel_id=YT_CHANNEL_ID
            )
            safe_log(f"[GeopoliticsProducer] ✓ Publicado en YouTube Shorts: {yt_pub.get('video_url')}")
        except Exception as yt_exc:
            safe_log(f"[GeopoliticsProducer] Aviso en sindicación de YouTube Shorts: {yt_exc}")

        # Sembrar comentario inicial de reflexión histórica
        vid_id = pub.get("video_id")
        if vid_id:
            try:
                from core.facebook_community_manager import facebook_community_manager
                facebook_community_manager.post_seed_comment(
                    video_id=vid_id,
                    page_id=PAGE_ID,
                    access_token=token,
                    video_title=title,
                    debate_question="¿Crees que este acontecimiento histórico pudo haberse evitado o era el curso inevitable del poder? Déjame tu punto de vista. 👇"
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
