"""Endpoints para el Estudio de Publicación, Miniaturas IA y YouTube Multi-Canal."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from config.settings import settings
from api.schemas import (
    ApiResponse,
    ChannelSchema,
    PublishPrepareRequest,
    PublishThumbnailRequest,
    YouTubeUploadRequest,
)
from api.security import verify_api_key
from core.channel_manager import ChannelManager
from core.project_store import ProjectStore
from core.publish_studio import PublishStudio
import core.youtube_oauth as yt

router = APIRouter(prefix="/publish", tags=["Publishing & Multi-Channel Studio"])


@router.post("/prepare", response_model=ApiResponse[Dict[str, Any]])
async def prepare_publication_metadata(
    payload: PublishPrepareRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Genera títulos de alto CTR, descripción optimizada para SEO y etiquetas con IA."""
    store = ProjectStore(payload.project_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    res = doc.get("result") or {}
    title = res.get("title") or doc.get("original_name") or "Video AetherCut"
    topic = res.get("topic") or (doc.get("options") or {}).get("topic", "")

    studio = PublishStudio(payload.project_id)
    loop = asyncio.get_running_loop()
    metadata = await loop.run_in_executor(
        None,
        lambda: studio.prepare_metadata(title=title, topic=topic, instructions=payload.custom_instructions)
    )

    return ApiResponse(
        success=True,
        message="Metadatos de publicación generados con éxito.",
        data=metadata,
    )


@router.post("/thumbnail", response_model=ApiResponse[Dict[str, Any]])
async def generate_project_thumbnail(
    payload: PublishThumbnailRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Genera una miniatura profesional optimizada para alta tasa de clics (CTR)."""
    studio = PublishStudio(payload.project_id)
    loop = asyncio.get_running_loop()
    thumb_res = await loop.run_in_executor(
        None,
        lambda: studio.generate_studio_thumbnail_fast(title=payload.title, topic=payload.topic or payload.title)
    )

    return ApiResponse(
        success=True,
        message="Miniatura de alta resolución generada.",
        data=thumb_res,
    )


@router.get("/youtube/status", response_model=ApiResponse[Dict[str, Any]])
async def check_youtube_connection(_auth: bool = Depends(verify_api_key)):
    """Verifica si el servidor tiene un canal de YouTube vinculado por OAuth 2.0."""
    connected = yt.is_connected()
    channel_info = yt.get_channel_info() if connected else None
    return ApiResponse(
        success=True,
        message="Estado de conexión con YouTube obtenido",
        data={"connected": connected, "channel": channel_info},
    )


@router.post("/youtube/upload", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_202_ACCEPTED)
async def upload_to_youtube(
    payload: YouTubeUploadRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Sube el video producido directamente a la cuenta conectada de YouTube."""
    if not yt.is_connected():
        raise HTTPException(status_code=400, detail="YouTube no está conectado. Vincula el canal en el servidor primero.")

    store = ProjectStore(payload.project_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    video_path = settings.OUTPUTS_DIR / f"{payload.project_id}_master.mp4"
    if not video_path.exists():
        cand = next(settings.OUTPUTS_DIR.glob(f"{payload.project_id}_edit_*.mp4"), None)
        if cand: video_path = cand
        else: raise HTTPException(status_code=400, detail="No se encontró el archivo de video final para subir.")

    thumb_path = settings.OUTPUTS_DIR / f"{payload.project_id}_thumbnail.jpg"
    thumb = thumb_path if thumb_path.exists() else None

    loop = asyncio.get_running_loop()
    upload_res = await loop.run_in_executor(
        None,
        lambda: yt.upload_video(
            video_path=video_path,
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            privacy=payload.privacy,
            category_id=payload.category_id,
            made_for_kids=payload.made_for_kids,
        )
    )
    if thumb:
        await loop.run_in_executor(None, lambda: yt.set_thumbnail(upload_res["video_id"], thumb))

    return ApiResponse(
        success=True,
        message="¡Video publicado en YouTube con éxito!",
        data={
            "video_id": upload_res.get("video_id"),
            "url": f"https://youtu.be/{upload_res.get('video_id')}",
            "studio_url": f"https://studio.youtube.com/video/{upload_res.get('video_id')}/edit",
        },
    )


# --- Gestión de Canales ---

@router.get("/channels", response_model=ApiResponse[List[Dict[str, Any]]])
async def list_configured_channels(_auth: bool = Depends(verify_api_key)):
    """Lista todos los canales y nichos configurados en el sistema."""
    channels = ChannelManager.list_channels()
    return ApiResponse(success=True, message=f"{len(channels)} canales encontrados", data=channels)


@router.post("/channels", response_model=ApiResponse[Dict[str, Any]])
async def upsert_channel(channel: ChannelSchema, _auth: bool = Depends(verify_api_key)):
    """Crea o actualiza un canal en la configuración multi-nicho."""
    res = ChannelManager.upsert_channel(channel.model_dump())
    return ApiResponse(success=True, message="Canal guardado con éxito.", data=res)


@router.delete("/channels/{channel_id}", response_model=ApiResponse[Dict[str, Any]])
async def delete_channel(channel_id: str, _auth: bool = Depends(verify_api_key)):
    """Elimina un canal configurado."""
    ok = ChannelManager.delete_channel(channel_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
    return ApiResponse(success=True, message="Canal eliminado.", data={"deleted": True})
