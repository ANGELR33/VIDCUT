"""Endpoints para ingesta y procesamiento de video (archivo local o URL remota)."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
import aiohttp
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import HttpUrl

from config.settings import settings
from api.schemas import ApiResponse, VideoProcessResponse, VideoProcessUrlRequest
from api.security import verify_api_key
from api.state import api_state
from api.webhook import dispatch_task_webhook
from core.pipeline import PipelineOptions
from core.project_store import ProjectStore

router = APIRouter(prefix="/videos", tags=["Video Ingestion & Processing"])

ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
MAX_UPLOAD_MB = 2048


async def _download_remote_video(video_url: str, output_path: Path, max_mb: int = MAX_UPLOAD_MB) -> Path:
    """Descarga un video desde una URL remota (enlace directo o plataforma como YouTube)."""
    clean_url = video_url.strip()
    is_youtube_or_social = any(domain in clean_url.lower() for domain in [
        "youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com", "vimeo.com"
    ])

    if is_youtube_or_social:
        import yt_dlp
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(output_path.with_suffix(".%(ext)s")),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "max_filesize": max_mb * 1024 * 1024,
        }
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([clean_url]))
        # Verificar archivo descargado
        for candidate in [output_path, output_path.with_suffix(".mp4"), output_path.with_suffix(".mkv")]:
            if candidate.exists() and candidate.stat().st_size > 1024:
                return candidate
        raise RuntimeError("No se pudo descargar el video desde la plataforma social indicada.")

    # Descarga directa vía HTTP/HTTPS con aiohttp
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(clean_url) as resp:
            if resp.status >= 400:
                raise HTTPException(status_code=400, detail=f"No se pudo acceder a la URL del video (HTTP {resp.status}).")
            
            written, limit = 0, max_mb * 1024 * 1024
            async with aiofiles.open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(4 * 1024 * 1024):
                    written += len(chunk)
                    if written > limit:
                        output_path.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail=f"El video supera el límite de {max_mb} MB.")
                    await f.write(chunk)

    if not output_path.exists() or output_path.stat().st_size < 1024:
        raise HTTPException(status_code=400, detail="El archivo descargado está vacío o no es un video válido.")
    return output_path


async def _run_pipeline_with_webhook(task_id: str, saved_path: Path, options: PipelineOptions, webhook_url: Optional[str]) -> None:
    """Ejecuta el pipeline de edición y dispara el webhook al terminar o fallar."""
    try:
        if api_state.run_pipeline_task_fn:
            await api_state.run_pipeline_task_fn(task_id, saved_path, options)
        else:
            raise RuntimeError("Motor de pipeline no inicializado en el servidor.")
    finally:
        # Despachar webhook si fue provisto
        if webhook_url:
            state = api_state.tasks_progress.get(task_id, {})
            status_val = "completed" if state.get("completed") else ("cancelled" if state.get("cancelled") else "failed")
            event_type = f"video.{status_val}"
            await dispatch_task_webhook(task_id, webhook_url, event_type)


@router.post("/process", response_model=ApiResponse[VideoProcessResponse], status_code=status.HTTP_202_ACCEPTED)
async def process_uploaded_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(..., description="Archivo de video binario (MP4, MOV, MKV, etc.)"),
    silence_threshold: float = Form(1.5, description="Umbral de silencio en segundos"),
    enable_broll: bool = Form(True, description="Activar inserción de B-Roll"),
    enable_captions: bool = Form(True, description="Activar subtítulos dinámicos"),
    enable_shorts: bool = Form(True, description="Extraer Shorts verticales 9:16"),
    enable_cards: bool = Form(True, description="Generar tarjetas de contexto"),
    voice: str = Form("es-MX-JorgeNeural", description="Voz neuronal para locución"),
    webhook_url: Optional[str] = Form(None, description="URL de webhook para notificación al finalizar"),
    _auth: bool = Depends(verify_api_key),
):
    """Carga un archivo de video mediante multipart/form-data e inicia la edición con IA."""
    ext = Path(video.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado ({ext or 'sin extensión'}). Formatos admitidos: {', '.join(sorted(ALLOWED_EXT))}",
        )

    task_id = uuid.uuid4().hex[:8]
    clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(video.filename or "video").stem)[:60]
    saved = settings.INPUTS_DIR / f"{task_id}_{clean_stem}{ext}"

    written, limit = 0, MAX_UPLOAD_MB * 1024 * 1024
    async with aiofiles.open(saved, "wb") as out:
        while chunk := await video.read(4 * 1024 * 1024):
            written += len(chunk)
            if written > limit:
                await out.close()
                saved.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"El archivo supera {MAX_UPLOAD_MB} MB.")
            await out.write(chunk)

    now = datetime.now(timezone.utc).isoformat()
    with api_state.state_lock:
        api_state.tasks_progress[task_id] = {
            "step": "init", "progress": 5.0, "message": "Archivo recibido. Iniciando análisis...",
            "completed": False, "error": None, "result": None, "cancel_supported": True,
            "file_name": Path(video.filename or "video").name,
            "created_at": now, "updated_at": now, "step_started_at": now,
            "events": [{"step": "init", "progress": 5.0, "message": "Archivo recibido. Iniciando...", "at": now}],
        }

    options = PipelineOptions(
        silence_threshold=max(0.5, min(5.0, silence_threshold)),
        broll=enable_broll,
        captions=enable_captions,
        shorts=enable_shorts,
        cards=enable_cards,
        voice=voice,
    )

    ProjectStore(task_id).create(
        source_file=saved,
        original_name=Path(video.filename or "video").name,
        options={
            "silence_threshold": options.silence_threshold,
            "broll": options.broll,
            "cards": options.cards,
            "captions": options.captions,
            "shorts": options.shorts,
            "voice": voice,
            "webhook_url": webhook_url,
        },
    )

    import threading
    api_state.task_cancel_events[task_id] = threading.Event()
    if webhook_url:
        api_state.register_webhook(task_id, webhook_url)

    job = asyncio.create_task(_run_pipeline_with_webhook(task_id, saved, options, webhook_url))
    api_state.task_jobs[task_id] = job

    return ApiResponse(
        success=True,
        message="Video cargado correctamente. Tarea de edición iniciada en background.",
        data=VideoProcessResponse(
            task_id=task_id,
            project_id=task_id,
            status="queued",
            message="Edición iniciada.",
        ),
    )


@router.post("/process-url", response_model=ApiResponse[VideoProcessResponse], status_code=status.HTTP_202_ACCEPTED)
async def process_video_by_url(
    payload: VideoProcessUrlRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Descarga un video desde una URL remota (HTTP direct link o YouTube) e inicia la edición."""
    task_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    clean_name = payload.title or f"remote_video_{task_id}"
    dest_path = settings.INPUTS_DIR / f"{task_id}_{clean_name}.mp4"

    with api_state.state_lock:
        api_state.tasks_progress[task_id] = {
            "step": "downloading", "progress": 3.0, "message": f"Descargando video desde {payload.video_url[:60]}...",
            "completed": False, "error": None, "result": None, "cancel_supported": True,
            "file_name": clean_name,
            "created_at": now, "updated_at": now, "step_started_at": now,
            "events": [{"step": "downloading", "progress": 3.0, "message": "Iniciando descarga remota...", "at": now}],
        }

    options = PipelineOptions(
        silence_threshold=max(0.5, min(5.0, payload.silence_threshold)),
        broll=payload.enable_broll,
        captions=payload.enable_captions,
        shorts=payload.enable_shorts,
        cards=payload.enable_cards,
        voice=payload.voice,
    )

    import threading
    api_state.task_cancel_events[task_id] = threading.Event()
    if payload.webhook_url:
        api_state.register_webhook(task_id, payload.webhook_url)

    async def _download_and_run():
        try:
            downloaded = await _download_remote_video(payload.video_url, dest_path)
            ProjectStore(task_id).create(
                source_file=downloaded,
                original_name=clean_name,
                options={
                    "silence_threshold": options.silence_threshold,
                    "broll": options.broll,
                    "cards": options.cards,
                    "captions": options.captions,
                    "shorts": options.shorts,
                    "voice": payload.voice,
                    "source_url": payload.video_url,
                    "webhook_url": payload.webhook_url,
                },
            )
            await _run_pipeline_with_webhook(task_id, downloaded, options, payload.webhook_url)
        except Exception as exc:
            with api_state.state_lock:
                api_state.tasks_progress[task_id].update({
                    "step": "error", "completed": True, "error": str(exc),
                    "message": f"Fallo al procesar el video desde URL: {exc}"
                })
            if payload.webhook_url:
                await dispatch_task_webhook(task_id, payload.webhook_url, "video.failed", {"error": str(exc)})

    job = asyncio.create_task(_download_and_run())
    api_state.task_jobs[task_id] = job

    return ApiResponse(
        success=True,
        message=f"Solicitud aceptada. Descargando video desde URL y encolando edición.",
        data=VideoProcessResponse(
            task_id=task_id,
            project_id=task_id,
            status="downloading",
            message="Descarga remota en curso.",
        ),
    )
