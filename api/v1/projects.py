"""Endpoints RESTful para la gestión integral de proyectos y descargas."""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse

from config.settings import settings
from api.schemas import (
    ApiResponse,
    ProjectListResponse,
    ProjectSummary,
    TimelineUpdateRequest,
)
from api.security import verify_api_key
from api.state import api_state
from api.webhook import dispatch_task_webhook
from core.project_store import ProjectStore, editor_snapshot
from core.silence_detector import SilenceDetector

router = APIRouter(prefix="/projects", tags=["Project Management & Exports"])


@router.get("", response_model=ApiResponse[ProjectListResponse])
async def list_projects(
    limit: int = Query(20, ge=1, le=100, description="Límite de resultados a retornar"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    search: Optional[str] = Query(None, description="Filtro de búsqueda por nombre o tema"),
    status_filter: Optional[str] = Query(None, description="Filtro por estado (done, running, error, queued)"),
    _auth: bool = Depends(verify_api_key),
):
    """Lista todos los proyectos guardados con soporte de paginación y búsqueda."""
    all_projects: List[ProjectSummary] = []
    
    for manifest in settings.PROJECTS_DIR.glob("*/project.json"):
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            pid = doc.get("id") or manifest.parent.name
            res = doc.get("result") or {}
            st = doc.get("status", "unknown")

            if status_filter and st.lower() != status_filter.lower():
                continue

            name = doc.get("original_name") or res.get("title") or "Video sin nombre"
            topic = res.get("topic") or (doc.get("options") or {}).get("topic") or ""

            if search:
                term = search.lower()
                if term not in name.lower() and term not in topic.lower() and term not in str(pid).lower():
                    continue

            # Detectar thumbnail si existe
            thumbnail_url = None
            thumb_path = settings.OUTPUTS_DIR / f"{pid}_thumbnail.jpg"
            if thumb_path.exists():
                thumbnail_url = f"/media/{pid}_thumbnail.jpg"
            else:
                work_thumb = settings.PROJECTS_DIR / pid / "work" / "streamer_card_0.png"
                if work_thumb.exists():
                    thumbnail_url = f"/storage/projects/{pid}/work/streamer_card_0.png"

            all_projects.append(ProjectSummary(
                id=pid,
                name=name,
                status=st,
                duration=float(res.get("duration") or 0.0),
                topic=topic or None,
                thumbnail_url=thumbnail_url,
                master_video_url=res.get("master_video_url") or res.get("media_url"),
                has_plan=bool(doc.get("plan")),
                has_result=bool(doc.get("result")),
                updated_at=doc.get("updated_at"),
            ))
        except Exception:
            continue

    all_projects.sort(key=lambda p: p.updated_at or "", reverse=True)
    total = len(all_projects)
    paged = all_projects[offset : offset + limit]

    return ApiResponse(
        success=True,
        message=f"{total} proyectos encontrados",
        data=ProjectListResponse(projects=paged, total=total),
    )


@router.get("/{project_id}", response_model=ApiResponse[Dict[str, Any]])
async def get_project_details(project_id: str, _auth: bool = Depends(verify_api_key)):
    """Obtiene el manifiesto completo, plan editorial y resultados de un proyecto."""
    store = ProjectStore(project_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No se encontró el proyecto '{project_id}'.")

    # Enriquecer con artefactos locales
    master_path = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"
    if not master_path.exists():
        cand = next(settings.OUTPUTS_DIR.glob(f"{project_id}_edit_*.mp4"), None)
        if cand:
            master_path = cand

    thumb_path = settings.OUTPUTS_DIR / f"{project_id}_thumbnail.jpg"
    sub_path = settings.OUTPUTS_DIR / f"{project_id}_subtitles.srt"

    doc["artifacts"] = {
        "master_video_exists": master_path.exists(),
        "master_video_url": f"/media/{master_path.name}" if master_path.exists() else None,
        "thumbnail_exists": thumb_path.exists(),
        "thumbnail_url": f"/media/{thumb_path.name}" if thumb_path.exists() else None,
        "subtitles_exists": sub_path.exists(),
        "subtitles_url": f"/api/v1/projects/{project_id}/download/subtitles" if sub_path.exists() else None,
    }

    return ApiResponse(
        success=True,
        message="Detalles del proyecto obtenidos",
        data=doc,
    )


@router.post("/{project_id}/detect-silence", response_model=ApiResponse[Dict[str, Any]])
async def detect_project_silence(
    project_id: str,
    min_silence_sec: float = Query(0.8, ge=0.2, le=5.0, description="Duración mínima de silencio en segundos"),
    noise_db: float = Query(-32.0, le=-10.0, ge=-60.0, description="Umbral de ruido en dB"),
    _auth: bool = Depends(verify_api_key),
):
    """Detecta intervalos de silencio y pausas muertas en el audio del proyecto."""
    store = ProjectStore(project_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    target_path = None
    if doc.get("source_file") and Path(doc["source_file"]).exists():
        target_path = Path(doc["source_file"])
    else:
        master = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"
        if master.exists():
            target_path = master
        else:
            cand = next(settings.OUTPUTS_DIR.glob(f"{project_id}_edit_*.mp4"), None)
            if cand and cand.exists():
                target_path = cand
            else:
                audio_cand = store.workdir / "voice.mp3"
                if audio_cand.exists():
                    target_path = audio_cand

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=400, detail="No se encontró archivo de video o audio en el proyecto para analizar.")

    detector = SilenceDetector(noise_db=noise_db, padding_sec=0.12)
    loop = asyncio.get_running_loop()
    silences = await loop.run_in_executor(
        None,
        lambda: detector.detect(target_path, min_silence_sec=min_silence_sec)
    )

    if silences is None:
        silences = []

    clean_silences = [
        {"start": round(s, 2), "end": round(e, 2), "duration": round(e - s, 2)}
        for s, e in silences if e != float("inf") and (e - s) >= min_silence_sec
    ]
    total_saved_sec = sum(item["duration"] for item in clean_silences)

    return ApiResponse(
        success=True,
        message=f"Se detectaron {len(clean_silences)} pausas de silencio ({round(total_saved_sec, 2)}s eliminables).",
        data={
            "project_id": project_id,
            "silence_intervals": clean_silences,
            "count": len(clean_silences),
            "total_saved_sec": round(total_saved_sec, 2),
            "min_silence_sec": min_silence_sec,
        },
    )


@router.delete("/{project_id}", response_model=ApiResponse[Dict[str, Any]])
async def delete_project(project_id: str, _auth: bool = Depends(verify_api_key)):
    """Elimina permanentemente un proyecto y libera el espacio ocupado en disco."""
    if project_id in api_state.task_jobs:
        raise HTTPException(status_code=409, detail="No se puede eliminar un proyecto en ejecución. Cancélalo primero.")

    store = ProjectStore(project_id)
    if not store.root.exists() and not store.manifest_path.exists():
        raise HTTPException(status_code=404, detail="No se encontró el proyecto a eliminar.")

    report = store.delete(include_source=True, include_outputs=True)
    with api_state.state_lock:
        api_state.tasks_progress.pop(project_id, None)

    freed_mb = round(report["freed_bytes"] / (1024 * 1024), 2)
    return ApiResponse(
        success=True,
        message=f"Proyecto '{project_id}' eliminado con éxito.",
        data={"freed_mb": freed_mb},
    )


@router.get("/{project_id}/timeline", response_model=ApiResponse[Dict[str, Any]])
async def get_project_timeline(project_id: str, _auth: bool = Depends(verify_api_key)):
    """Obtiene la línea de tiempo, cortes, tarjetas y material de apoyo del plan."""
    store = ProjectStore(project_id)
    try:
        plan = store.load_plan()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No se pudo cargar el plan editorial: {exc}")

    return ApiResponse(
        success=True,
        message="Línea de tiempo obtenida",
        data=editor_snapshot(plan),
    )


@router.put("/{project_id}/timeline", response_model=ApiResponse[Dict[str, Any]])
async def update_project_timeline(
    project_id: str,
    payload: TimelineUpdateRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Guarda modificaciones en la línea de tiempo (activar/desactivar cortes, mover tarjetas, etc.)."""
    store = ProjectStore(project_id)
    try:
        plan = store.load_plan()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No se encontró el plan de edición: {exc}")

    if payload.cards:
        card_map = {c.id: c for c in payload.cards}
        for card in plan.info_cards:
            if card.card_id in card_map:
                up = card_map[card.card_id]
                if up.enabled is not None: card.enabled = up.enabled
                if up.start is not None: card.start_sec = max(0.0, up.start)
                if up.duration is not None: card.display_duration_sec = max(2.0, min(15.0, up.duration))
                if up.position: card.screen_position = up.position
                if up.avatar_spoken_text is not None: card.avatar_spoken_text = up.avatar_spoken_text
                if up.avatar_enabled is not None: card.avatar_enabled = up.avatar_enabled

    if payload.brolls:
        broll_map = {b.id: b for b in payload.brolls}
        for b in plan.b_rolls:
            if b.cue_id in broll_map:
                up = broll_map[b.cue_id]
                if up.enabled is not None: b.enabled = up.enabled
                if up.start is not None: b.start_sec = max(0.0, up.start)
                if up.end is not None: b.end_sec = max(b.start_sec + 1.0, up.end)

    store.save_plan(plan, status="ready_for_export")
    return ApiResponse(
        success=True,
        message="Ajustes de la línea de tiempo guardados. Listo para reexportar.",
        data={"editor": editor_snapshot(plan)},
    )


@router.post("/{project_id}/export", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_202_ACCEPTED)
async def export_project_revision(project_id: str, _auth: bool = Depends(verify_api_key)):
    """Inicia una reexportación renderizada a partir de los cambios guardados."""
    if project_id in api_state.task_jobs:
        raise HTTPException(status_code=409, detail="Este proyecto ya tiene una tarea en ejecución.")

    import threading
    api_state.task_cancel_events[project_id] = threading.Event()
    now = datetime.now(timezone.utc).isoformat()

    with api_state.state_lock:
        api_state.tasks_progress[project_id] = {
            "step": "render", "progress": 5.0, "message": "Iniciando reexportación de la línea de tiempo...",
            "completed": False, "error": None, "result": None, "cancel_supported": True,
            "created_at": now, "updated_at": now, "step_started_at": now,
            "events": [{"step": "render", "progress": 5.0, "message": "Iniciando render de nueva versión...", "at": now}],
        }

    if not api_state.run_export_task_fn:
        raise HTTPException(status_code=500, detail="El motor de exportación no está disponible.")

    job = asyncio.create_task(api_state.run_export_task_fn(project_id))
    api_state.task_jobs[project_id] = job

    return ApiResponse(
        success=True,
        message="Render de nueva versión iniciado en background.",
        data={"task_id": project_id, "status": "render"},
    )


@router.get("/{project_id}/download/{asset_type}")
async def download_project_asset(project_id: str, asset_type: str):
    """Descarga directa de artefactos: master, short, subtitles, transcript, thumbnail o archivo por nombre."""
    store = ProjectStore(project_id)
    doc = store.read()
    res = doc.get("result") or {}

    target_file: Optional[Path] = None
    media_type = "application/octet-stream"

    if asset_type == "master":
        target_file = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"
        if not target_file.exists():
            target_file = next(settings.OUTPUTS_DIR.glob(f"{project_id}_edit_*.mp4"), None)
        media_type = "video/mp4"

    elif asset_type == "short":
        target_file = next(settings.OUTPUTS_DIR.glob(f"short_{project_id}_*.mp4"), None)
        if not target_file:
            cand = settings.OUTPUTS_DIR / f"{project_id}_short.mp4"
            if cand.exists(): target_file = cand
        media_type = "video/mp4"

    elif asset_type == "subtitles":
        target_file = settings.OUTPUTS_DIR / f"{project_id}_subtitles.srt"
        if not target_file.exists():
            target_file = store.workdir / "captions.srt"
        media_type = "text/plain"

    elif asset_type == "transcript":
        target_file = store.workdir / "transcript.json"
        if not target_file.exists():
            target_file = store.workdir / "transcript.txt"
        media_type = "application/json" if (target_file and target_file.suffix == ".json") else "text/plain"

    elif asset_type == "thumbnail":
        target_file = settings.OUTPUTS_DIR / f"{project_id}_thumbnail.jpg"
        media_type = "image/jpeg"

    else:
        # Búsqueda por nombre de archivo exacto en outputs o workdir
        cand = settings.OUTPUTS_DIR / asset_type
        if cand.exists() and cand.is_file():
            target_file = cand
        else:
            cand_work = store.workdir / asset_type
            if cand_work.exists() and cand_work.is_file():
                target_file = cand_work

    if not target_file or not target_file.exists():
        raise HTTPException(status_code=404, detail=f"Artefacto '{asset_type}' no encontrado para este proyecto.")

    return FileResponse(
        str(target_file),
        media_type=media_type,
        filename=target_file.name,
    )


@router.get("/{project_id}/materials/download")
async def download_materials_zip(project_id: str):
    """Empaqueta todos los materiales (audio, b-rolls, cards, subtítulos) en un archivo ZIP."""
    store = ProjectStore(project_id)
    if not store.workdir.exists():
        raise HTTPException(status_code=404, detail="El proyecto no posee materiales de trabajo.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in store.workdir.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith(".tmp"):
                rel_path = file_path.relative_to(store.workdir)
                zip_file.write(file_path, arcname=str(rel_path))

    buffer.seek(0)
    filename = f"materials_{project_id}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/{project_id}/webhook", response_model=ApiResponse[Dict[str, Any]])
async def test_project_webhook(
    project_id: str,
    payload: Dict[str, Any],
    _auth: bool = Depends(verify_api_key),
):
    """Despacha manualmente el resumen y artefactos del proyecto a la URL de webhook provista."""
    webhook_url = str(payload.get("webhook_url", "")).strip()
    if not webhook_url or not webhook_url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL de webhook inválida. Debe comenzar con http o https.")

    success = await dispatch_task_webhook(project_id, webhook_url, "project.manual_dispatch")
    if not success:
        raise HTTPException(status_code=502, detail="No se pudo despachar el webhook a la URL indicada.")

    return ApiResponse(
        success=True,
        message="Webhook despachado correctamente.",
        data={"project_id": project_id, "webhook_url": webhook_url},
    )
