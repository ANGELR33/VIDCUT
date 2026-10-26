"""Endpoints para la generación autónoma de videos y transmisiones KAI Streamer."""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from config.settings import settings
from api.schemas import ApiResponse, StreamerCreateRequest, StreamerCreateResponse
from api.security import verify_api_key
from api.state import api_state
from api.webhook import dispatch_task_webhook
from core.project_store import ProjectStore
from core.streamer_pipeline import StreamerOptions

router = APIRouter(prefix="/streamer", tags=["Autonomous AI Streamer"])


async def _run_streamer_with_webhook(task_id: str, options: StreamerOptions, webhook_url: str | None) -> None:
    try:
        if api_state.run_streamer_task_fn:
            await api_state.run_streamer_task_fn(task_id, options)
        else:
            raise RuntimeError("Motor KAI Streamer no inicializado en el servidor.")
    finally:
        if webhook_url:
            state = api_state.tasks_progress.get(task_id, {})
            status_val = "completed" if state.get("completed") else ("cancelled" if state.get("cancelled") else "failed")
            await dispatch_task_webhook(task_id, webhook_url, f"streamer.{status_val}")


@router.post("/create", response_model=ApiResponse[StreamerCreateResponse], status_code=status.HTTP_202_ACCEPTED)
async def create_autonomous_broadcast(
    payload: StreamerCreateRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Crea y produce un video completo con IA desde cero a partir de un tema o premisa."""
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Debes indicar un tema para la producción del video.")

    task_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()

    with api_state.state_lock:
        api_state.tasks_progress[task_id] = {
            "step": "research", "progress": 10.0, "message": f"Investigando «{topic}» en la web...",
            "completed": False, "error": None, "result": None, "cancel_supported": True,
            "file_name": f"KAI Stream: {topic[:35]}",
            "created_at": now, "updated_at": now, "step_started_at": now,
            "events": [{"step": "research", "progress": 10.0, "message": f"Investigando «{topic}»...", "at": now}],
        }

    extra_opts = {
        "visual_mode": payload.visual_mode,
        "extra_notes": payload.extra_notes or "",
        "enable_avatar": payload.enable_avatar,
        "burn_subtitles": payload.burn_subtitles,
        "sub_style": payload.sub_style,
    }

    raw_dur = payload.duration_sec
    dur_sec = raw_dur * 60 if 0 < raw_dur <= 40 else raw_dur
    dur_sec = max(20, min(2400, dur_sec))

    options = StreamerOptions(
        topic=topic,
        style=payload.style,
        duration_sec=dur_sec,
        aspect_ratio=payload.aspect_ratio,
        card_theme=payload.card_theme,
        voice=payload.voice,
        rtmp_url=payload.rtmp_url,
        enable_avatar=payload.enable_avatar,
        burn_subtitles=payload.burn_subtitles,
        sub_style=payload.sub_style,
        visual_mode=payload.visual_mode,
        extra_notes=payload.extra_notes or "",
    )

    store = ProjectStore(task_id)
    store.create(
        source_file=settings.OUTPUTS_DIR / f"{task_id}_master.mp4",
        original_name=f"KAI Stream: {topic}",
        options={"topic": topic, "style": payload.style, "duration_sec": payload.duration_sec,
                 "mode": "streamer", "aspect_ratio": payload.aspect_ratio, "card_theme": payload.card_theme,
                 "voice": payload.voice, "origin": "api_v1", **extra_opts}
    )

    api_state.task_cancel_events[task_id] = threading.Event()
    if payload.webhook_url:
        api_state.register_webhook(task_id, payload.webhook_url)

    job = asyncio.create_task(_run_streamer_with_webhook(task_id, options, payload.webhook_url))
    api_state.task_jobs[task_id] = job

    return ApiResponse(
        success=True,
        message="Producción autónoma KAI iniciada en background.",
        data=StreamerCreateResponse(
            task_id=task_id,
            project_id=task_id,
            topic=topic,
            message="Investigación y redacción de guion en curso.",
        ),
    )
