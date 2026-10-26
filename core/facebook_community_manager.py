"""Gestor de Comunidad y Respuestas Automáticas para Páginas de Facebook (FacebookCommunityManager).

Propósito Algorítmico (Multiplicador Viral de Meta):
1. 'Comentario Semilla' (Seed Comment): Inmediatamente tras publicar un Reel, la página fija
   o publica una pregunta provocativa para 'romper el hielo' y disparar los comentarios orgánicos.
2. Detección y Respuesta Inteligente con IA: Escanea comentarios recientes de seguidores reales
   y responde en menos de 30 minutos con una réplica natural que genere un 'hilo de debate'.
3. Blindaje Antispam:
   - Cero autorepuestas a la propia página.
   - Registro permanente de comentarios respondidos (storage/facebook_replied_comments.json).
   - Límite de 3 respuestas por página por ciclo para mantener naturalidad y proteger la cuenta.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.facebook_community")

GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
REPLIED_COMMENTS_FILE = settings.STORAGE_DIR / "facebook_replied_comments.json"
PERMANENT_PAGES_FILE = settings.STORAGE_DIR / "facebook_permanent_pages.json"

PAGE_NICHE_PROFILES = {
    "1352345044630476": {
        "name": "Palabras con Peso",
        "style": "profundo, analítico, reflexivo, cuestionador y cercano sin sonar a bot",
        "focus": "filosofía, ciencia, debates humanos y psicología",
    },
    "1375932688939134": {
        "name": "Huellas Sagradas",
        "style": "solemne, cálido, respetuoso, espiritual y edificante",
        "focus": "cine bíblico, versículos de paz, fe en Dios y esperanza",
    },
    "1039337485919543": {
        "name": "Contrapunto",
        "style": "tecnológico, innovador, curioso y con visión de futuro",
        "focus": "inteligencia artificial, computación, robótica e ingeniería",
    },
    "1018230678031599": {
        "name": "Núcleo Ideológico",
        "style": "documental, riguroso, histórico y de análisis geopolítico",
        "focus": "historia universal, tratados, estrategia y diplomacia",
    },
}


def _read_replied_comments() -> Dict[str, Any]:
    if REPLIED_COMMENTS_FILE.exists():
        try:
            return json.loads(REPLIED_COMMENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"replied_ids": {}, "seed_comments": {}}


def _save_replied_comments(data: Dict[str, Any]) -> None:
    REPLIED_COMMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPLIED_COMMENTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(REPLIED_COMMENTS_FILE)


class FacebookCommunityManager:
    """Agente de Engagement y Gestión Comunitaria en Facebook."""

    def __init__(self):
        pass

    def post_seed_comment(
        self,
        video_id: str,
        page_id: str,
        access_token: str,
        video_title: str,
        debate_question: Optional[str] = None,
    ) -> Optional[str]:
        """Publica el primer comentario de la página en el Reel para romper el hielo e incentivar debate."""
        if not video_id or not access_token:
            return None

        state = _read_replied_comments()
        if video_id in state.get("seed_comments", {}):
            return state["seed_comments"][video_id]

        profile = PAGE_NICHE_PROFILES.get(page_id, {"name": "Página", "focus": "general"})
        page_name = profile["name"]

        message = (debate_question or "¿Tú qué opinas sobre esto? ¿Estás de acuerdo o crees que la realidad es muy distinta? Los leo a todos aquí abajo. 👇").strip()

        safe_log(f"[CommunityManager] 💬 Publicando comentario semilla en '{page_name}' [Video: {video_id}]...")
        url = f"{GRAPH_URL}/{video_id}/comments"
        try:
            resp = requests.post(
                url,
                data={
                    "message": message,
                    "access_token": access_token,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                cid = resp.json().get("id")
                safe_log(f"[CommunityManager] ✓ Comentario semilla publicado con éxito (ID: {cid})")
                state.setdefault("seed_comments", {})[video_id] = cid
                _save_replied_comments(state)
                return cid
            else:
                safe_log(f"[CommunityManager] Aviso publicando comentario semilla ({resp.status_code}): {resp.text[:120]}")
        except Exception as exc:
            safe_log(f"[CommunityManager] Error publicando comentario semilla: {exc}")

        return None

    def generate_ai_reply(
        self,
        user_comment: str,
        user_name: str,
        video_title: str,
        page_id: str,
    ) -> str:
        """Genera una respuesta auténtica con Gemini Flash Lite según el nicho de la página."""
        profile = PAGE_NICHE_PROFILES.get(page_id, {
            "name": "Creador de Contenido",
            "style": "cercano, inteligente y conciso",
            "focus": "debate general",
        })

        try:
            from google import genai
            from google.genai import types

            gemini_key = settings.GEMINI_API_KEY.split(",")[0].strip()
            client = genai.Client(api_key=gemini_key)

            prompt = (
                f"Eres el creador de la página de Facebook '{profile['name']}' ({profile['focus']}).\n"
                f"Tu estilo de comunicación es: {profile['style']}.\n"
                f"Un seguidor llamado '{user_name}' comentó en tu video '{video_title}':\n"
                f"Comentario: \"{user_comment}\"\n\n"
                f"Redacta una respuesta cercana, inteligente y de máximo 20 palabras que invite a seguir la conversación.\n"
                f"PROHIBICIONES ESTRICTAS:\n"
                f"- PROHIBIDO sonar a robot corporativo o decir 'gracias por tu comentario'.\n"
                f"- PROHIBIDO sonar condescendiente.\n"
                f"- Debe sonar como un creador de contenido real escribiendo desde su teléfono.\n"
                f"Devuelve solo el texto de la respuesta."
            )

            res = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
            )
            if res.text:
                reply = res.text.strip().replace('"', '')
                return reply
        except Exception as exc:
            safe_log(f"[CommunityManager] Aviso generando respuesta con IA: {exc}")

        return "Totalmente, es un punto que da para mucho debate. ¿Qué opinas tú de cómo evoluciona esto?"

    def scan_and_reply_page(
        self,
        page_id: str,
        page_name: str,
        access_token: str,
        max_replies: int = 3,
    ) -> int:
        """Escanea videos recientes de una página y responde a comentarios no atendidos."""
        state = _read_replied_comments()
        replied_map = state.setdefault("replied_ids", {})

        url = f"{GRAPH_URL}/{page_id}/videos"
        params = {
            "fields": "id,title,description,comments.limit(10){id,message,from,created_time}",
            "limit": 5,
            "access_token": access_token,
        }

        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                return 0

            videos = r.json().get("data", [])
            replies_sent = 0

            for vid in videos:
                if replies_sent >= max_replies:
                    break

                video_id = vid.get("id")
                video_title = vid.get("title") or vid.get("description", "")[:50]
                comments = vid.get("comments", {}).get("data", [])

                for c in comments:
                    if replies_sent >= max_replies:
                        break

                    cid = c.get("id")
                    c_from = c.get("from", {})
                    from_id = c_from.get("id")
                    from_name = c_from.get("name", "Seguidor")
                    msg = (c.get("message") or "").strip()

                    # Omitir si es un comentario propio de la página o si ya fue respondido
                    if from_id == page_id or cid in replied_map or not msg or len(msg) < 3:
                        continue

                    # Generar respuesta con IA
                    reply_text = self.generate_ai_reply(
                        user_comment=msg,
                        user_name=from_name,
                        video_title=video_title,
                        page_id=page_id,
                    )

                    safe_log(f"[CommunityManager] 💬 Respondiendo a '{from_name}' en '{page_name}': «{reply_text}»")

                    # Enviar respuesta al comentario
                    rep_url = f"{GRAPH_URL}/{cid}/comments"
                    rep_res = requests.post(
                        rep_url,
                        data={
                            "message": reply_text,
                            "access_token": access_token,
                        },
                        timeout=15,
                    )

                    if rep_res.status_code == 200:
                        replies_sent += 1
                        replied_map[cid] = {
                            "replied_at": datetime.now(timezone.utc).isoformat(),
                            "user_comment": msg,
                            "reply": reply_text,
                            "video_id": video_id,
                            "page": page_name,
                        }
                        # Dar like al comentario original para generar notificación al usuario
                        try:
                            requests.post(f"{GRAPH_URL}/{cid}/likes", data={"access_token": access_token}, timeout=10)
                        except Exception:
                            pass
                        time.sleep(1.5)  # Breve pausa natural antispam

            if replies_sent > 0:
                _save_replied_comments(state)
                safe_log(f"[CommunityManager] ✓ {replies_sent} respuestas enviadas en '{page_name}'.")

            return replies_sent

        except Exception as exc:
            safe_log(f"[CommunityManager] Aviso escaneando '{page_name}': {exc}")

        return 0

    def run_community_round(self, max_replies_per_page: int = 3) -> Dict[str, Any]:
        """Ronda completa de comunidad por todas las páginas permanentes activas."""
        safe_log("\n[CommunityManager] 🌐 Iniciando ronda de interacción comunitaria en Facebook...")
        if not PERMANENT_PAGES_FILE.exists():
            return {"success": False, "error": "No hay páginas permanentes guardadas."}

        try:
            data = json.loads(PERMANENT_PAGES_FILE.read_text(encoding="utf-8"))
            pages = data.get("pages", [])
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        results = {}
        for p in pages:
            pid = p.get("id")
            pname = p.get("name")
            token = p.get("access_token")
            # Excluir la página de anime inactiva
            if pid == "972321959300050":
                continue

            if pid and token:
                sent = self.scan_and_reply_page(
                    page_id=pid,
                    page_name=pname,
                    access_token=token,
                    max_replies=max_replies_per_page,
                )
                results[pname] = sent

        return {"success": True, "results": results}


# Singleton
facebook_community_manager = FacebookCommunityManager()
