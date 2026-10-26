"""Endpoints para listar y extraer Clips y Shorts verticales (9:16) de alto impacto."""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from config.settings import settings
from api.schemas import ApiResponse, ClipExtractRequest, ClipSummary
from api.security import verify_api_key
from core.project_store import ProjectStore
from core.llm import safe_log
from utils.file_manager import FileManager

router = APIRouter(prefix="/clips", tags=["Shorts & Viral Clips Studio"])


@router.get("/{project_id}", response_model=ApiResponse[List[ClipSummary]])
async def list_project_clips(project_id: str, _auth: bool = Depends(verify_api_key)):
    """Lista todos los clips y Shorts 9:16 generados para un proyecto."""
    clips: List[ClipSummary] = []
    pattern = f"short_{project_id}_*.mp4"
    for p in sorted(settings.OUTPUTS_DIR.glob(pattern)):
        try:
            stat = p.stat()
            clip_name = p.stem.replace(f"short_{project_id}_", "").replace("_", " ").title()
            clips.append(ClipSummary(
                filename=p.name,
                name=clip_name,
                url=f"/outputs/{p.name}",
                size_mb=round(stat.st_size / (1024 * 1024), 2),
                created_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            ))
        except OSError:
            continue

    return ApiResponse(
        success=True,
        message=f"{len(clips)} clips encontrados para el proyecto '{project_id}'.",
        data=clips,
    )


@router.post("/{project_id}/extract", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_202_ACCEPTED)
async def extract_clip_from_project(
    project_id: str,
    payload: Optional[ClipExtractRequest] = None,
    _auth: bool = Depends(verify_api_key),
):
    """Extrae un Short vertical 9:16 personalizado o automático con gancho dinámico."""
    store = ProjectStore(project_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No se encontró el proyecto '{project_id}'.")

    master_file = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"
    if not master_file.exists():
        cand = next(settings.OUTPUTS_DIR.glob(f"{project_id}_edit_*.mp4"), None)
        if cand and cand.exists():
            master_file = cand
        else:
            raise HTTPException(status_code=400, detail="El video master debe estar completado para extraer clips.")

    # Duración total con ffprobe
    total_dur = 60.0
    try:
        p_res = await asyncio.to_thread(
            subprocess.run,
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(master_file)],
            capture_output=True, text=True, check=True
        )
        total_dur = float(p_res.stdout.strip())
    except Exception:
        pass

    start_sec = 0.0
    dur_sec = min(35.0, total_dur)
    clip_title = "Clip Viral"

    if payload:
        if payload.start_sec is not None:
            start_sec = max(0.0, payload.start_sec)
        if payload.end_sec is not None:
            dur_sec = max(5.0, payload.end_sec - start_sec)
        if payload.title:
            clip_title = payload.title

    clean_slug = clip_title.lower().replace(" ", "_")[:30]
    out_filename = f"short_{project_id}_{clean_slug}_{int(start_sec)}s.mp4"
    out_file = settings.OUTPUTS_DIR / out_filename

    # Extraer vertical en background thread
    def _render_vertical_clip():
        crop_filter = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:flags=lanczos"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-i", str(master_file),
            "-t", str(dur_sec),
            "-vf", crop_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(out_file)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(None, _render_vertical_clip)

    def _log_render_error(fut):
        exc = fut.exception()
        if exc:
            safe_log(f"[API Clips] Fallo renderizando {out_filename}: {exc}")

    future.add_done_callback(_log_render_error)

    return ApiResponse(
        success=True,
        message=f"Extracción de clip iniciada: {out_filename}",
        data={
            "filename": out_filename,
            "url": f"/outputs/{out_filename}",
            "start_sec": start_sec,
            "duration_sec": dur_sec,
        },
    )
