"""Módulo de publicación automática y cross-posting en Páginas de Facebook (Meta Graph API).

Permite correlacionar cada canal de YouTube con su 'Página Hermana' en Facebook,
publicando automáticamente los videos (como Facebook Reels o videos estándar)
sin duplicar trabajo ni mezclar nichos.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.facebook_publisher")

GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
GRAPH_VIDEO_URL = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"

CORRELATIONS_FILE = settings.STORAGE_DIR / "channel_correlations.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[FacebookPublisher] Error leyendo {path.name}: {exc}")
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_channel_correlations() -> Dict[str, Any]:
    """Obtiene la configuración de canales de YouTube y sus páginas hermanas de Facebook."""
    # Inicializar con los canales existentes si no existe el archivo
    correlations = _read_json(CORRELATIONS_FILE, {})
    from core.channel_intelligence import ANALYTICS_FILE
    yt_accounts_path = settings.STORAGE_DIR / "youtube_accounts.json"
    yt_accounts = _read_json(yt_accounts_path, [])

    updated = False
    for acc in yt_accounts:
        cid = acc.get("channel_id")
        if cid and cid not in correlations:
            correlations[cid] = {
                "channel_id": cid,
                "channel_title": acc.get("title", "Canal"),
                "channel_tag": acc.get("tag", ""),
                "facebook_page": {
                    "enabled": False,
                    "page_name": f"{acc.get('title', 'Canal')} (Página Facebook)",
                    "page_id": "",
                    "access_token": "",
                    "auto_cross_post": False,
                    "last_publish_at": None,
                },
            }
            updated = True

    if updated:
        _write_json(CORRELATIONS_FILE, correlations)

    return correlations


def update_facebook_correlation(channel_id: str, fb_config: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza la página hermana de Facebook asociada a un canal de YouTube."""
    correlations = get_channel_correlations()
    if channel_id not in correlations:
        correlations[channel_id] = {
            "channel_id": channel_id,
            "channel_title": "Canal",
            "facebook_page": {},
        }

    correlations[channel_id]["facebook_page"].update(fb_config)
    _write_json(CORRELATIONS_FILE, correlations)
    safe_log(f"[FacebookPublisher] Correlación actualizada para canal {channel_id}: {fb_config.get('page_name')}")
    return correlations[channel_id]


def test_facebook_page_connection(page_id: str, access_token: str) -> Dict[str, Any]:
    """Verifica si el Page ID y el Page Access Token son válidos consultando Meta Graph API."""
    if not page_id or not access_token:
        return {"success": False, "error": "Falta el Page ID o el Page Access Token."}

    try:
        resp = requests.get(
            f"{GRAPH_URL}/{page_id}",
            params={"fields": "id,name,link,fan_count,verification_status", "access_token": access_token},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and "id" in data:
            return {
                "success": True,
                "page_id": data.get("id"),
                "name": data.get("name"),
                "link": data.get("link"),
                "followers": data.get("fan_count", 0),
            }
        else:
            err_msg = data.get("error", {}).get("message", "Token o Page ID inválido.")
            return {"success": False, "error": err_msg}
    except Exception as exc:
        return {"success": False, "error": f"Error de red al conectar con Facebook: {exc}"}


def fetch_facebook_pages_from_user_token(user_access_token: str) -> Dict[str, Any]:
    """Consulta Meta Graph API (/me/accounts) con un User Access Token y devuelve todas las páginas gestionadas con sus tokens."""
    token = (user_access_token or "").strip()
    if not token:
        return {"success": False, "error": "Token vacío o no proporcionado.", "pages": []}

    try:
        url = f"{GRAPH_URL}/me/accounts"
        resp = requests.get(url, params={"access_token": token, "limit": 50}, timeout=15)
        data = resp.json()
        if resp.status_code != 200 or "data" not in data:
            err = data.get("error", {}).get("message", "Token de usuario inválido o expirado.")
            return {"success": False, "error": err, "pages": []}

        pages = []
        for item in data.get("data", []):
            pages.append({
                "id": str(item.get("id")),
                "name": item.get("name", "Página sin nombre"),
                "category": item.get("category", ""),
                "access_token": item.get("access_token", ""),
                "tasks": item.get("tasks", []),
            })
        return {"success": True, "count": len(pages), "pages": pages}
    except Exception as exc:
        return {"success": False, "error": f"Error consultando cuentas de Facebook: {exc}", "pages": []}


def generate_permanent_page_tokens(app_id: str, app_secret: str, user_token: str) -> Dict[str, Any]:
    """Intercambia un User Token temporal por un Token de Larga Duración (60 días)
    y obtiene los Tokens de Página PERMANENTES (que nunca expiran) para todas las páginas."""
    app_id = (app_id or "").strip()
    app_secret = (app_secret or "").strip()
    user_token = (user_token or "").strip()

    if not app_id or not app_secret or not user_token:
        return {"success": False, "error": "Falta App ID, App Secret o User Token."}

    try:
        # Paso 1: Intercambio por Long-Lived User Token (60 días)
        exchange_url = f"{GRAPH_URL}/oauth/access_token"
        resp = requests.get(
            exchange_url,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": user_token,
            },
            timeout=15,
        )
        data = resp.json()
        long_lived_token = data.get("access_token")
        if not long_lived_token:
            err = data.get("error", {}).get("message", "Error al intercambiar token con Meta.")
            return {"success": False, "error": err}

        # Paso 2: Consultar /me/accounts con el Long-Lived Token -> Genera Page Tokens PERMANENTES
        accounts_res = fetch_facebook_pages_from_user_token(long_lived_token)
        if not accounts_res.get("success"):
            return accounts_res

        return {
            "success": True,
            "message": "Tokens permanentes generados con éxito para todas tus páginas.",
            "long_lived_user_token": long_lived_token,
            "count": accounts_res.get("count", 0),
            "pages": accounts_res.get("pages", []),
        }
    except Exception as exc:
        return {"success": False, "error": f"Error generando tokens permanentes: {exc}"}


def publish_video_to_facebook(
    video_path: Path,
    title: str,
    description: str,
    page_id: str,
    access_token: str,
    is_reel: bool = True,
) -> Dict[str, Any]:
    """Publica un video directamente a una Página de Facebook usando Meta Graph API.

    - Si is_reel=True: Usa el protocolo de Facebook Video Reels API (9:16 vertical).
    - Si is_reel=False: Usa la subida de video estándar a la Página.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"El video no existe en {video_path}")

    full_description = f"{title}\n\n{description}".strip()

    # Protocolo 1: Facebook Reels API (para videos verticales 9:16)
    if is_reel:
        try:
            # Fase 1: Iniciar subida de Reel
            start_url = f"{GRAPH_URL}/{page_id}/video_reels"
            init_res = requests.post(
                start_url,
                data={
                    "upload_phase": "start",
                    "access_token": access_token,
                },
                timeout=30,
            )
            init_data = init_res.json()
            video_id = init_data.get("video_id")
            upload_url = init_data.get("upload_url")

            if not video_id or not upload_url:
                err = init_data.get("error", {}).get("message", "No se pudo iniciar sesión de Reel.")
                logger.warning(f"[FacebookPublisher] Error iniciando Reel ({init_res.status_code}): {err}")
                # Fallback a subida directa
                return _publish_standard_video(video_path, title, full_description, page_id, access_token)

            # Fase 2: Subir archivo binario
            file_size = video_path.stat().st_size
            with open(video_path, "rb") as f:
                upload_res = requests.post(
                    upload_url,
                    headers={
                        "Authorization": f"OAuth {access_token}",
                        "offset": "0",
                        "file_size": str(file_size),
                    },
                    data=f,
                    timeout=300,
                )

            # Fase 3: Publicar Reel
            finish_res = requests.post(
                start_url,
                data={
                    "upload_phase": "finish",
                    "access_token": access_token,
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": full_description[:5000],
                },
                timeout=30,
            )
            finish_data = finish_res.json()
            if finish_data.get("success"):
                safe_log(f"[FacebookPublisher] Reel publicado con éxito en Facebook (ID: {video_id})")
                return {
                    "success": True,
                    "platform": "facebook",
                    "format": "reel",
                    "video_id": video_id,
                    "page_id": page_id,
                    "post_url": f"https://www.facebook.com/reel/{video_id}",
                }
            else:
                logger.warning(f"[FacebookPublisher] Falló finalización de Reel: {finish_data}")
        except Exception as exc:
            logger.warning(f"[FacebookPublisher] Error en protocolo de Reel, probando estándar: {exc}")

    # Protocolo 2: Subida estándar a la Página de Facebook
    return _publish_standard_video(video_path, title, full_description, page_id, access_token)


def _publish_standard_video(
    video_path: Path,
    title: str,
    description: str,
    page_id: str,
    access_token: str,
) -> Dict[str, Any]:
    """Subida de video a una Página de Facebook con protocolo segmentado (Resumable Upload) para tolerar archivos grandes."""
    file_size = video_path.stat().st_size
    url = f"{GRAPH_VIDEO_URL}/{page_id}/videos"

    # Si el video es pequeño (< 20MB), intentar subida directa rápida
    if file_size < 20 * 1024 * 1024:
        try:
            with open(video_path, "rb") as video_file:
                files = {"source": video_file}
                data = {
                    "title": title[:255],
                    "description": description[:5000],
                    "access_token": access_token,
                }
                res = requests.post(url, files=files, data=data, timeout=120)
            if res.status_code == 200 and res.text:
                res_data = res.json()
                if "id" in res_data:
                    vid = res_data["id"]
                    safe_log(f"[FacebookPublisher] Video subido directamente en Facebook Page {page_id} (ID: {vid})")
                    return {
                        "success": True,
                        "platform": "facebook",
                        "format": "video",
                        "video_id": vid,
                        "page_id": page_id,
                        "post_url": f"https://www.facebook.com/{page_id}/videos/{vid}",
                    }
        except Exception as _e_direct:
            safe_log(f"[FacebookPublisher] Subida directa omitida ({_e_direct}), pasando a protocolo por partes...")

    # Protocolo oficial Resumable Upload de Meta para archivos de cualquier tamaño sin error 413
    safe_log(f"[FacebookPublisher] 📤 Subiendo video ({file_size // (1024*1024)} MB) mediante protocolo por bloques de Meta...")
    
    # Fase 1: Iniciar sesión de subida
    init_res = requests.post(
        url,
        data={
            "upload_phase": "start",
            "file_size": file_size,
            "access_token": access_token,
        },
        timeout=30,
    )
    init_data = init_res.json()
    upload_session_id = init_data.get("upload_session_id")
    video_id = init_data.get("video_id")
    if not upload_session_id or not video_id:
        err = init_data.get("error", {}).get("message", f"HTTP {init_res.status_code}")
        raise RuntimeError(f"Error iniciando subida por partes en Meta: {err}")

    start_offset = int(init_data.get("start_offset", 0))
    end_offset = int(init_data.get("end_offset", file_size))

    # Fase 2: Transferir fragmentos
    with open(video_path, "rb") as f:
        while start_offset < file_size:
            chunk_len = end_offset - start_offset
            f.seek(start_offset)
            chunk_data = f.read(chunk_len)

            transfer_res = requests.post(
                url,
                data={
                    "upload_phase": "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset": str(start_offset),
                    "access_token": access_token,
                },
                files={
                    "video_file_chunk": ("chunk.mp4", chunk_data, "application/octet-stream"),
                },
                timeout=180,
            )
            t_data = transfer_res.json()
            new_start = int(t_data.get("start_offset", file_size))
            new_end = int(t_data.get("end_offset", file_size))
            if new_start == start_offset:
                raise RuntimeError(f"Fallo en transferencia de bloque Meta en offset {start_offset}")
            start_offset = new_start
            end_offset = new_end

    # Fase 3: Finalizar y publicar
    finish_res = requests.post(
        url,
        data={
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "title": title[:255],
            "description": description[:5000],
            "access_token": access_token,
        },
        timeout=60,
    )
    finish_data = finish_res.json()
    if finish_data.get("success") or "id" in finish_data:
        vid = finish_data.get("id") or video_id
        safe_log(f"[FacebookPublisher] ✅ Video publicado exitosamente en Facebook Page {page_id} (ID: {vid})")
        return {
            "success": True,
            "platform": "facebook",
            "format": "video",
            "video_id": vid,
            "page_id": page_id,
            "post_url": f"https://www.facebook.com/{page_id}/videos/{vid}",
        }
    else:
        err = finish_data.get("error", {}).get("message", "Error al finalizar subida en Meta.")
        raise RuntimeError(f"Error finalizando video en Facebook: {err}")


def auto_cross_post_for_channel(channel_id: str, video_path: Path, title: str, description: str, is_reel: bool = True) -> Optional[Dict[str, Any]]:
    """Si el canal de YouTube tiene una página hermana de Facebook activa con cross-posting activado, publica el video."""
    correlations = get_channel_correlations()
    ch_info = correlations.get(channel_id)
    if not ch_info:
        return None

    fb = ch_info.get("facebook_page", {})
    if not fb.get("enabled") or not fb.get("auto_cross_post") or not fb.get("page_id") or not fb.get("access_token"):
        return None

    try:
        safe_log(
            f"[FacebookPublisher] Ruteo por tema: canal '{ch_info.get('channel_title') or channel_id}' "
            f"({ch_info.get('channel_tag', 'sin nicho')}) → página '{fb.get('page_name')}' ({fb.get('page_id')})"
        )
        safe_log(f"[FacebookPublisher] Iniciando cross-posting para página hermana «{fb.get('page_name')}»...")
        try:
            from core.page_registry import validate_channel_page
            route = validate_channel_page(channel_id, str(fb.get("page_id", "")))
            if route.get("mapped"):
                safe_log(
                    f"[FacebookPublisher] Tema de la página: {route.get('theme')} "
                    f"| productor: {route.get('producer')}"
                )
                for warning in route.get("warnings", []):
                    safe_log(f"[FacebookPublisher] AVISO de ruteo: {warning}")
            else:
                safe_log("[FacebookPublisher] AVISO: página sin mapear en page_registry.json")
        except Exception as _route_err:
            safe_log(f"[FacebookPublisher] Aviso validando ruteo: {_route_err}")
        result = publish_video_to_facebook(
            video_path=video_path,
            title=title,
            description=description,
            page_id=fb["page_id"],
            access_token=fb["access_token"],
            is_reel=is_reel,
        )
        fb["last_publish_at"] = result.get("post_url")
        _write_json(CORRELATIONS_FILE, correlations)
        return result
    except Exception as exc:
        safe_log(f"[FacebookPublisher] No se pudo hacer cross-posting en Facebook: {exc}")
        return None
