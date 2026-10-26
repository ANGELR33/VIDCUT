"""Motor de Recomendación y Difusión Multi-Canal (AetherCut Multi-Channel Publisher & AI Matcher).

Permite publicar con 1 clic en múltiples canales de YouTube y páginas de Facebook,
analizando semánticamente el guion y el tema para sugerir con precisión de IA
cuál es el destino más rentable y afín para la audiencia.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.multichannel")

YOUTUBE_ACCOUNTS_FILE = settings.STORAGE_DIR / "youtube_accounts.json"
PERMANENT_PAGES_FILE = settings.STORAGE_DIR / "facebook_permanent_pages.json"
CORRELATIONS_FILE = settings.STORAGE_DIR / "channel_correlations.json"


# ============================================================================
# Perfiles de Nicho de Canales y Páginas
# ============================================================================

CHANNEL_PROFILES: Dict[str, Dict[str, Any]] = {
    # YOUTUBE
    "UC_8-TffWIAoiUMMDfiMUm2Q": {
        "name": "the Deep dife",
        "platform": "youtube",
        "tag": "Historia, ciencia y datos reveladores",
        "category": "Historia & Filosofía",
        "avatar": "https://yt3.ggpht.com/5zTM2koSnupIwEuC0Tx9goj9Uem_sChwSaYxSh7_qj0_un03uXf_vfw6IY46rI2mXsw4SHE9Sw=s88-c-k-c0x00ffffff-no-rj",
        "positive_keywords": [
            "historia", "roma", "griego", "filosofia", "filosofía", "estoicismo", "estoico",
            "marco aurelio", "seneca", "epicteto", "ciencia", "misterio", "datos", "procrastinacion",
            "procrastinación", "habito", "hábito", "disciplina", "psicologia", "psicología",
            "mente", "cerebro", "humano", "documental", "revelacion", "revelación", "origen",
            "antiguo", "emperador", "imperio", "filosofo", "filósofo", "meditaciones", "tiempo"
        ],
        "negative_keywords": ["python", "software", "codigo", "código", "anime", "biblia", "jesus", "cristo", "musica"],
        "base_affinity": 45,
        "default_reason": "Audiencia cautivada por biografías históricas, datos científicos poco conocidos y lecciones de filosofía práctica estoica."
    },
    "UChQZ2TvHifQBrDzbZRjGDkA": {
        "name": "PixelGrama",
        "platform": "youtube",
        "tag": "Tecnología, IA, innovación y herramientas",
        "category": "Tecnología & IA",
        "avatar": "https://yt3.ggpht.com/K6uhNf8Lf1yWHpaDqXPqyj8ODISR2p1kblEeAny7u_b2RBe66ewtS1MAXyfc5aQlmoAk0PqbAg=s88-c-k-c0x00ffffff-no-rj",
        "positive_keywords": [
            "tecnologia", "tecnología", "inteligencia artificial", "ia", "ai", "software", "hardware",
            "herramienta", "herramientas", "innovacion", "innovación", "lanzamiento", "deepseek",
            "chatgpt", "openai", "gemini", "robot", "robotica", "robótica", "futuro", "digital",
            "gadget", "algoritmo", "modelo", "automatizacion", "automatización", "programacion",
            "programación", "computadora", "tech", "chip", "nvidia"
        ],
        "negative_keywords": ["marco aurelio", "roma", "imperio", "biblia", "cristianismo", "fe", "oracion", "anime"],
        "base_affinity": 30,
        "default_reason": "Canal especializado en vanguardia tecnológica, nuevos modelos de Inteligencia Artificial y tutoriales de software digital."
    },
    # FACEBOOK PAGES
    "1018230678031599": {
        "name": "Núcleo Ideológico",
        "platform": "facebook",
        "tag": "Historia y filosofía universal",
        "category": "Geopolítica & Filosofía",
        "avatar": "",
        "positive_keywords": [
            "historia", "filosofia", "filosofía", "geopolitica", "geopolítica", "estoicismo",
            "marco aurelio", "imperio", "guerra", "estrategia", "doctrina", "liderazgo",
            "pensamiento", "sociedad", "poder", "roma", "grecia", "politica", "política",
            "disciplina", "moral", "nacion", "nación", "soberania", "soberanía"
        ],
        "negative_keywords": ["python", "tutorial", "anime", "otaku", "música", "cancion"],
        "base_affinity": 40,
        "default_reason": "Comunidad de Facebook de alto análisis crítico que debate sobre historia universal, estrategia y filosofía de vida."
    },
    "1039337485919543": {
        "name": "Contrapunto",
        "platform": "facebook",
        "tag": "Podcast, tecnología, IA y debate",
        "category": "Debate Tech & IA",
        "avatar": "",
        "positive_keywords": [
            "tecnologia", "tecnología", "ia", "inteligencia artificial", "debate", "controversia",
            "futuro", "innovacion", "innovación", "computacion", "computación", "robot", "sociedad digital",
            "polemica", "polémica", "opinion", "opinión", "algoritmo", "trabajo del futuro"
        ],
        "negative_keywords": ["marco aurelio", "roma clásica", "biblia", "fe", "espiritualidad"],
        "base_affinity": 35,
        "default_reason": "Página de debate activo en Facebook enfocada en el impacto de la Inteligencia Artificial, dilemas del futuro y tecnología."
    },
    "1352345044630476": {
        "name": "Palabras con Peso",
        "platform": "facebook",
        "tag": "Psicología, frases y reflexión",
        "category": "Desarrollo Personal",
        "avatar": "",
        "positive_keywords": [
            "habito", "hábito", "habitos", "hábitos", "psicologia", "psicología", "procrastinacion",
            "procrastinación", "motivacion", "motivación", "disciplina", "consejo", "mente", "superacion",
            "superación", "dolor", "exito", "éxito", "frase", "reflexion", "reflexión", "vida", "vida diaria",
            "estoicismo", "marco aurelio", "emocion", "emoción"
        ],
        "negative_keywords": ["software", "codigo", "deepseek", "gpu", "anime"],
        "base_affinity": 40,
        "default_reason": "Público masivo en Facebook que consume píldoras de psicología práctica, cambios de mentalidad y frases de impacto."
    },
    "1375932688939134": {
        "name": "Huellas Sagradas",
        "platform": "facebook",
        "tag": "Fe, cine bíblico y espiritualidad",
        "category": "Espiritualidad & Fe",
        "avatar": "",
        "positive_keywords": [
            "fe", "dios", "biblia", "biblico", "bíblico", "jesus", "jesús", "cristo", "esperanza",
            "paz", "oracion", "oración", "versiculo", "versículo", "sagrado", "alma", "milagro",
            "perdon", "perdón", "amor de dios", "creyente"
        ],
        "negative_keywords": ["tecnologia", "ia", "deepseek", "computadora", "anime", "ateismo"],
        "base_affinity": 15,
        "default_reason": "Comunidad de fe orientada a citas bíblicas, cine sacro y mensajes edificantes para el espíritu."
    },
    "972321959300050": {
        "name": "Black Clover T 4",
        "platform": "facebook",
        "tag": "Anime, manga y acción",
        "category": "Anime & Ficción",
        "avatar": "",
        "positive_keywords": [
            "anime", "manga", "black clover", "asta", "magia", "otaku", "capitulo", "capítulo",
            "temporada", "pelea", "shonen", "animacion", "animación", "japones", "japonés"
        ],
        "negative_keywords": ["marco aurelio", "roma", "tecnologia", "fe", "biblia", "procrastinacion"],
        "base_affinity": 10,
        "default_reason": "Canal dedicado a la serie de anime, resúmenes cronológicos de episodios y momentos de acción."
    },
    "880043901851712": {
        "name": "FizzB",
        "platform": "facebook",
        "tag": "Música, cultura y clips visuales",
        "category": "Música & Cultura",
        "avatar": "",
        "positive_keywords": ["musica", "música", "cancion", "canción", "ritmo", "soundtrack", "artista", "beat"],
        "negative_keywords": ["marco aurelio", "estoicismo", "deepseek", "ia", "biblia"],
        "base_affinity": 20,
        "default_reason": "Comunidad de entretenimiento ligero y contenidos musicales o curiosidades sonoras."
    },
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[MultiChannel] Error leyendo {path.name}: {exc}")
    return default


def get_all_distribution_targets() -> List[Dict[str, Any]]:
    """Devuelve la lista unificada y normalizada de todos los canales y páginas conectadas."""
    targets: List[Dict[str, Any]] = []

    # 1. YouTube Accounts
    yt_accounts = _read_json(YOUTUBE_ACCOUNTS_FILE, [])
    for acc in yt_accounts:
        cid = acc.get("channel_id")
        if not cid:
            continue
        profile = CHANNEL_PROFILES.get(cid, {})
        targets.append({
            "id": cid,
            "target_key": f"yt:{cid}",
            "platform": "youtube",
            "name": acc.get("title") or profile.get("name") or "Canal YouTube",
            "tag": acc.get("tag") or profile.get("tag") or "Canal de YouTube",
            "category": profile.get("category", "General"),
            "subscribers": f"{acc.get('subscribers', '0')} subs",
            "avatar": acc.get("thumbnail") or profile.get("avatar") or "",
            "connected": bool(acc.get("refresh_token") or acc.get("access_token")),
            "badge": "YouTube",
        })

    # 2. Facebook Pages
    fb_pages_doc = _read_json(PERMANENT_PAGES_FILE, {})
    fb_pages = fb_pages_doc.get("pages", [])
    seen_ids = set()
    for page in fb_pages:
        pid = str(page.get("id") or "").strip()
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        profile = CHANNEL_PROFILES.get(pid, {})
        targets.append({
            "id": pid,
            "target_key": f"fb:{pid}",
            "platform": "facebook",
            "name": page.get("name") or profile.get("name") or "Página Facebook",
            "tag": profile.get("tag") or page.get("category") or "Página de Facebook",
            "category": profile.get("category", page.get("category", "Comunidad")),
            "subscribers": "Página Oficial",
            "avatar": "",
            "connected": bool(page.get("access_token")),
            "badge": "Facebook Page",
            "has_token": bool(page.get("access_token")),
        })

    return targets


def evaluate_channel_recommendations(
    topic: str,
    title: str = "",
    extra_text: str = "",
) -> Dict[str, Any]:
    """Evalúa la afinidad estratégica del video contra cada canal y genera la recomendación de IA."""
    targets = get_all_distribution_targets()
    combined_corpus = f"{title} {topic} {extra_text}".lower()

    scored_targets: List[Dict[str, Any]] = []

    for t in targets:
        cid = t["id"]
        profile = CHANNEL_PROFILES.get(cid, {})

        pos_kw = profile.get("positive_keywords", [])
        neg_kw = profile.get("negative_keywords", [])
        base_score = profile.get("base_affinity", 40)

        # Contar aciertos positivos
        pos_matches = []
        for kw in pos_kw:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined_corpus):
                pos_matches.append(kw)

        # Contar discrepancias negativas
        neg_matches = []
        for kw in neg_kw:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined_corpus):
                neg_matches.append(kw)

        # Cálculo de puntaje
        score = base_score + (len(pos_matches) * 12) - (len(neg_matches) * 15)
        score = max(18, min(99, score))

        # Generar justificación de la IA personalizada
        channel_name = t["name"]
        if score >= 85:
            reason = (
                f"Máxima afinidad de nicho: Tu contenido sobre «{title[:40] or topic[:40]}...» "
                f"encaja a la perfección con la audiencia de {channel_name} ({t['category']}). "
                f"Términos clave detectados: {', '.join(pos_matches[:4]) or 'interés orgánico directo'}."
            )
            is_recommended = True
        elif score >= 65:
            reason = (
                f"Buena opción de difusión: {channel_name} puede amplificar este contenido gracias a su "
                f"comunidad interesada en {t['category']}."
            )
            is_recommended = True
        else:
            reason = (
                f"Afinidad moderada o baja ({score}%): La audiencia habitual de {channel_name} "
                f"espera contenido de {profile.get('category', t['category'])}; publicar aquí podría tener "
                f"menor retención inicial."
            )
            is_recommended = False

        item = dict(t)
        item["affinity_pct"] = score
        item["is_recommended"] = is_recommended
        item["recommendation_reason"] = reason
        item["matched_keywords"] = pos_matches[:5]
        scored_targets.append(item)

    # Ordenar rigurosamente de mayor a menor afinidad
    scored_targets.sort(key=lambda x: x["affinity_pct"], reverse=True)

    # Asegurar que al menos el canal top 1 y 2 sean marcados como recomendados
    if scored_targets and not any(x["is_recommended"] for x in scored_targets):
        scored_targets[0]["is_recommended"] = True

    top_channel = scored_targets[0] if scored_targets else None
    ai_summary = ""
    if top_channel:
        ai_summary = (
            f"La IA sugiere prioritariamente publicar en «{top_channel['name']}» ({top_channel['affinity_pct']}% afinidad) "
            f"debido a su fuerte alineación temática con {top_channel['category']}."
        )

    return {
        "ai_summary": ai_summary,
        "top_recommendation": top_channel["name"] if top_channel else "",
        "channels": scored_targets,
    }


def publish_to_selected_channels(
    task_id: str,
    channel_keys: List[str],
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    is_reel: bool = True,
    privacy: str = "public",
) -> Dict[str, Any]:
    """Publica el video master a cada uno de los canales o páginas seleccionadas."""
    from core.project_store import ProjectStore
    store = ProjectStore(task_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Proyecto {task_id} no encontrado")

    result = doc.get("result") or {}
    master_file = (
        Path(result.get("output_file") or "")
        if result.get("output_file")
        else settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
    )

    if not master_file.exists():
        # Buscar en storage/outputs
        candidate = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
        if candidate.exists():
            master_file = candidate
        else:
            raise FileNotFoundError(f"No existe el archivo de video final para {task_id}")

    # Resolver miniatura del video
    thumbnail_file: Optional[Path] = None
    thumb_candidates = [
        settings.OUTPUTS_DIR / f"{task_id}_thumbnail.jpg",
        settings.OUTPUTS_DIR / f"{task_id}_thumbnail.png",
        settings.PROJECTS_DIR / task_id / "thumbnail.jpg",
        settings.PROJECTS_DIR / task_id / "thumbnail.png",
    ]
    for cand in thumb_candidates:
        if cand.is_file():
            thumbnail_file = cand
            break

    # Lista de páginas de Facebook para buscar tokens
    fb_pages_doc = _read_json(PERMANENT_PAGES_FILE, {})
    fb_pages_map = {str(p.get("id")): p for p in fb_pages_doc.get("pages", [])}

    clean_tags = tags or ["AetherCut", "Documental", "IA"]
    reports: List[Dict[str, Any]] = []

    safe_log(f"\n[MultiChannel] Iniciando difusión de «{title}» a {len(channel_keys)} canales...")

    for key in channel_keys:
        # Formatos de key: "yt:UC_..." o "fb:1018..." o raw ID
        if key.startswith("yt:"):
            platform = "youtube"
            target_id = key[3:]
        elif key.startswith("fb:"):
            platform = "facebook"
            target_id = key[3:]
        elif key.startswith("UC"):
            platform = "youtube"
            target_id = key
        else:
            platform = "facebook"
            target_id = key

        profile = CHANNEL_PROFILES.get(target_id, {})
        channel_name = profile.get("name") or target_id

        if platform == "youtube":
            try:
                import core.youtube_oauth as yt
                safe_log(f"[MultiChannel] Subiendo a YouTube: {channel_name} ({target_id})...")
                up_res = yt.upload_video(
                    video_path=master_file,
                    title=title[:100],
                    description=description,
                    tags=clean_tags,
                    privacy=privacy,
                    channel_id=target_id,
                )
                video_id = up_res.get("video_id", "")
                vid_url = up_res.get("video_url") or f"https://youtu.be/{video_id}"

                # Asignar miniatura oficial si existe
                thumbnail_applied = False
                if video_id and thumbnail_file and thumbnail_file.exists():
                    try:
                        safe_log(f"[MultiChannel] Asignando miniatura {thumbnail_file.name} a YouTube {video_id}...")
                        thumbnail_applied = yt.set_thumbnail(video_id, thumbnail_file, channel_id=target_id)
                        if thumbnail_applied:
                            safe_log(f"[MultiChannel] Miniatura oficial asignada con éxito a {video_id}")
                        else:
                            safe_log(f"[MultiChannel] Aviso: YouTube no aceptó miniatura externa (requiere canal verificado)")
                    except Exception as th_err:
                        safe_log(f"[MultiChannel] Error asignando miniatura: {th_err}")

                msg = "Publicado exitosamente en YouTube."
                if thumbnail_file and not thumbnail_applied:
                    msg += " (Nota: Miniatura requiere canal verificado por teléfono en YouTube Studio)"
                elif thumbnail_applied:
                    msg += " (Miniatura oficial vinculada)"

                reports.append({
                    "channel_key": key,
                    "name": channel_name,
                    "platform": "youtube",
                    "success": True,
                    "url": vid_url,
                    "thumbnail_applied": thumbnail_applied,
                    "message": msg,
                })
                safe_log(f"[MultiChannel] YouTube {channel_name} publicado: {vid_url}")
            except Exception as yt_err:
                safe_log(f"[MultiChannel] ⚠️ Error en YouTube {channel_name}: {yt_err}")
                reports.append({
                    "channel_key": key,
                    "name": channel_name,
                    "platform": "youtube",
                    "success": False,
                    "url": None,
                    "error": str(yt_err),
                    "message": f"Fallo al subir a YouTube: {yt_err}",
                })

        elif platform == "facebook":
            page_info = fb_pages_map.get(target_id) or {}
            access_token = page_info.get("access_token", "")
            if not access_token:
                # Buscar en correlaciones
                corrs = _read_json(CORRELATIONS_FILE, {})
                for c in corrs.values():
                    fbp = c.get("facebook_page", {})
                    if str(fbp.get("page_id")) == target_id and fbp.get("access_token"):
                        access_token = fbp.get("access_token")
                        break

            if not access_token:
                reports.append({
                    "channel_key": key,
                    "name": channel_name,
                    "platform": "facebook",
                    "success": False,
                    "url": None,
                    "error": "No se encontró el token de acceso permanente para esta página de Facebook.",
                })
                continue

            try:
                from core.facebook_publisher import publish_video_to_facebook
                safe_log(f"[MultiChannel] 📱 Publicando Reel en Facebook: {channel_name} ({target_id})...")
                fb_res = publish_video_to_facebook(
                    video_path=master_file,
                    title=title,
                    description=description,
                    page_id=target_id,
                    access_token=access_token,
                    is_reel=is_reel,
                )
                reel_url = fb_res.get("url") or fb_res.get("reel_url") or f"https://facebook.com/{target_id}"
                reports.append({
                    "channel_key": key,
                    "name": channel_name,
                    "platform": "facebook",
                    "success": True,
                    "url": reel_url,
                    "message": f"Reel publicado exitosamente en Facebook: {channel_name}",
                })
                safe_log(f"[MultiChannel] ✓ Facebook {channel_name} publicado: {reel_url}")
            except Exception as fb_err:
                safe_log(f"[MultiChannel] ⚠️ Error en Facebook {channel_name}: {fb_err}")
                reports.append({
                    "channel_key": key,
                    "name": channel_name,
                    "platform": "facebook",
                    "success": False,
                    "url": None,
                    "error": str(fb_err),
                    "message": f"Fallo al publicar en Facebook: {fb_err}",
                })

    # Guardar registro en el proyecto para auditoría histórica
    try:
        current_publishes = doc.get("multichannel_publishes", [])
        current_publishes.append({
            "timestamp": store._now(),
            "title": title,
            "reports": reports,
        })
        doc["multichannel_publishes"] = current_publishes
        store.write(doc)
    except Exception:
        pass

    success_count = sum(1 for r in reports if r.get("success"))
    return {
        "success": success_count > 0,
        "total_targets": len(channel_keys),
        "published_count": success_count,
        "reports": reports,
    }
