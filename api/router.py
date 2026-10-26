"""Router central de la API pública de AetherCut AI (v1).

Monta todos los sub-routers y proporciona el endpoint de descubrimiento
y el portal interactivo de documentación en /api/v1/docs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from api.docs_html import API_DOCS_HTML
from api.schemas import ApiResponse
from api.state import api_state
from api.v1.agent import router as agent_router
from api.v1.clips import router as clips_router
from api.v1.projects import router as projects_router
from api.v1.publish import router as publish_router
from api.v1.streamer import router as streamer_router
from api.v1.system import router as system_router
from api.v1.tasks import router as tasks_router
from api.v1.templates import router as templates_router
from api.v1.trends import router as trends_router
from api.v1.tts import router as tts_router
from api.v1.videos import router as videos_router

api_v1_router = APIRouter(prefix="/api/v1")

# Montaje de sub-routers organizados
api_v1_router.include_router(system_router)
api_v1_router.include_router(videos_router)
api_v1_router.include_router(streamer_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(clips_router)
api_v1_router.include_router(tts_router)
api_v1_router.include_router(trends_router)
api_v1_router.include_router(publish_router)
api_v1_router.include_router(agent_router)
api_v1_router.include_router(templates_router)


@api_v1_router.get("", response_model=ApiResponse[Dict[str, Any]])
async def api_v1_index():
    """Punto de entrada y descubrimiento de servicios de la API v1."""
    return ApiResponse(
        success=True,
        message="AetherCut AI Public API v1 activa y lista para comunicarse con aplicaciones externas.",
        data={
            "version": "1.0.0",
            "server_time": datetime.now(timezone.utc).isoformat(),
            "documentation": {
                "interactive_portal": "/api/v1/docs",
                "swagger_ui": "/docs",
                "redoc": "/redoc",
                "openapi_json": "/openapi.json",
            },
            "services": [
                {"name": "System & Health", "prefix": "/api/v1/system"},
                {"name": "Video Processing (File & URL)", "prefix": "/api/v1/videos"},
                {"name": "Autonomous AI Streamer", "prefix": "/api/v1/streamer"},
                {"name": "Task Progress & SSE Stream", "prefix": "/api/v1/tasks"},
                {"name": "Projects & Downloads", "prefix": "/api/v1/projects"},
                {"name": "Shorts & Viral Clips", "prefix": "/api/v1/clips"},
                {"name": "Voiceover & TTS Studio", "prefix": "/api/v1/tts"},
                {"name": "Trend Radar & Intelligence", "prefix": "/api/v1/trends"},
                {"name": "Publishing & YouTube Multi-Channel", "prefix": "/api/v1/publish"},
                {"name": "AI Director Copilot", "prefix": "/api/v1/agent"},
                {"name": "Visual Templates & Overlays", "prefix": "/api/v1/templates"},
            ],
        },
    )


@api_v1_router.get("/docs", response_class=HTMLResponse)
async def api_developer_portal():
    """Portal interactivo para desarrolladores con snippets en cURL, Python y JavaScript."""
    return HTMLResponse(content=API_DOCS_HTML)


def init_api_state(
    *,
    tasks_progress: Dict[str, Any],
    task_cancel_events: Dict[str, Any],
    task_pipelines: Dict[str, Any],
    task_jobs: Dict[str, Any],
    state_lock: Any,
    render_lock: Any,
    update_task_state: Callable[..., None],
    run_pipeline_task: Callable[..., Coroutine[Any, Any, None]],
    run_streamer_task: Callable[..., Coroutine[Any, Any, None]],
    run_export_task: Callable[..., Coroutine[Any, Any, None]],
) -> None:
    """Inicializa la referencia al estado del servidor para la API v1."""
    api_state.initialize(
        tasks_progress=tasks_progress,
        task_cancel_events=task_cancel_events,
        task_pipelines=task_pipelines,
        task_jobs=task_jobs,
        state_lock=state_lock,
        render_lock=render_lock,
        update_task_state=update_task_state,
        run_pipeline_task=run_pipeline_task,
        run_streamer_task=run_streamer_task,
        run_export_task=run_export_task,
    )
