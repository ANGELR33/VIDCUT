"""Endpoints para seguimiento en tiempo real y gestión de tareas en background."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.schemas import ApiResponse, TaskStatusResponse
from api.security import verify_api_key
from api.state import api_state
from core.project_store import ProjectStore

router = APIRouter(prefix="/tasks", tags=["Task Progress & Tracking"])


@router.get("", response_model=ApiResponse[List[TaskStatusResponse]])
async def list_recent_tasks(_auth: bool = Depends(verify_api_key)):
    """Lista todas las tareas activas y recientes registradas en memoria."""
    out: List[TaskStatusResponse] = []
    with api_state.state_lock:
        for tid, st in api_state.tasks_progress.items():
            out.append(TaskStatusResponse(
                task_id=tid,
                step=st.get("step", "unknown"),
                progress=float(st.get("progress") or 0.0),
                message=st.get("message") or "",
                completed=bool(st.get("completed")),
                cancelled=bool(st.get("cancelled")),
                error=st.get("error"),
                file_name=st.get("file_name"),
                created_at=st.get("created_at"),
                updated_at=st.get("updated_at"),
                result=st.get("result"),
                events=st.get("events") or [],
            ))
    out.sort(key=lambda t: t.updated_at or "", reverse=True)
    return ApiResponse(
        success=True,
        message=f"{len(out)} tareas encontradas",
        data=out,
    )


@router.get("/{task_id}", response_model=ApiResponse[TaskStatusResponse])
async def get_task_status(task_id: str, _auth: bool = Depends(verify_api_key)):
    """Obtiene el estado detallado, porcentaje de avance y resultado de una tarea."""
    with api_state.state_lock:
        state = api_state.tasks_progress.get(task_id)

    # Si no está en memoria, verificar si fue persistida en el almacén de proyectos
    if not state:
        try:
            store = ProjectStore(task_id)
            doc = store.read()
            curr = doc.get("current_progress") or {}
            res = doc.get("result")
            status_str = doc.get("status", "unknown")
            is_done = (status_str == "done")
            state = {
                "step": curr.get("step", status_str),
                "progress": float(curr.get("progress") or (100.0 if is_done else 0.0)),
                "message": curr.get("message", "Proyecto archivado"),
                "completed": is_done,
                "cancelled": (status_str == "cancelled"),
                "error": doc.get("error"),
                "file_name": doc.get("original_name"),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "result": res,
                "events": curr.get("events") or [],
            }
        except Exception:
            raise HTTPException(status_code=404, detail=f"No se encontró la tarea o proyecto '{task_id}'.")

    return ApiResponse(
        success=True,
        message="Estado de la tarea obtenido",
        data=TaskStatusResponse(
            task_id=task_id,
            step=state.get("step", "unknown"),
            progress=float(state.get("progress") or 0.0),
            message=state.get("message") or "",
            completed=bool(state.get("completed")),
            cancelled=bool(state.get("cancelled")),
            error=state.get("error"),
            file_name=state.get("file_name"),
            created_at=state.get("created_at"),
            updated_at=state.get("updated_at"),
            result=state.get("result"),
            events=state.get("events") or [],
        ),
    )


@router.get("/{task_id}/events")
async def stream_task_events(task_id: str):
    """Transmite eventos en tiempo real vía Server-Sent Events (SSE)."""
    async def event_generator():
        last_step = None
        last_prog = None
        while True:
            with api_state.state_lock:
                state = api_state.tasks_progress.get(task_id)
            if not state:
                # Si terminó o no está en memoria, revisar si ya existe el resultado en disco
                try:
                    doc = ProjectStore(task_id).read()
                    yield f"data: {json.dumps({'step': doc.get('status', 'done'), 'progress': 100.0, 'completed': True, 'result': doc.get('result')})}\n\n"
                except Exception:
                    yield f"data: {json.dumps({'error': 'Tarea no encontrada', 'completed': True})}\n\n"
                break

            step = state.get("step")
            prog = state.get("progress")
            if step != last_step or prog != last_prog:
                last_step = step
                last_prog = prog
                payload = {
                    "task_id": task_id,
                    "step": step,
                    "progress": prog,
                    "message": state.get("message"),
                    "completed": state.get("completed", False),
                    "error": state.get("error"),
                    "result": state.get("result"),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if state.get("completed") or state.get("error") or state.get("cancelled"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{task_id}/cancel", response_model=ApiResponse[Dict[str, Any]])
async def cancel_task(task_id: str, _auth: bool = Depends(verify_api_key)):
    """Cancela una tarea activa en ejecución."""
    event = api_state.task_cancel_events.get(task_id)
    if not event:
        raise HTTPException(status_code=404, detail="La tarea no está activa o ya ha finalizado.")
    event.set()
    api_state.update_task_state(task_id, "cancelling", 0.0, "Cancelación solicitada por API...", cancel_requested=True)
    return ApiResponse(
        success=True,
        message=f"Cancelación solicitada para la tarea '{task_id}'.",
        data={"task_id": task_id, "status": "cancelling"},
    )
