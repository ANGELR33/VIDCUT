"""Endpoints de diagnóstico, capacidades y salud del sistema."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from config.settings import settings
from api.schemas import ApiResponse, SystemHealthResponse
from api.security import verify_api_key
from api.state import api_state

router = APIRouter(prefix="/system", tags=["System & Health"])


def _check_tool_installed(name: str) -> bool:
    try:
        subprocess.run([name, "-version"], capture_output=True, text=True, check=True)
        return True
    except Exception:
        return False


def _check_gpu() -> bool:
    try:
        res = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False


@router.get("/health", response_model=ApiResponse[SystemHealthResponse])
async def get_system_health():
    """Comprueba el estado operativo del motor, FFmpeg, GPU y almacenamiento."""
    ffmpeg_ok = _check_tool_installed("ffmpeg")
    ffprobe_ok = _check_tool_installed("ffprobe")
    gpu_ok = _check_gpu()

    total, used, free = shutil.disk_usage(str(settings.STORAGE_DIR))
    free_gb = round(free / (1024 ** 3), 2)

    with api_state.state_lock:
        active_count = sum(
            1 for st in api_state.tasks_progress.values()
            if not (st.get("completed") or st.get("error") or st.get("cancelled"))
        )

    data = SystemHealthResponse(
        status="ok" if (ffmpeg_ok and ffprobe_ok) else "degraded",
        version="2.0.0",
        server_time=datetime.now(timezone.utc).isoformat(),
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
        gpu_available=gpu_ok,
        storage_free_gb=free_gb,
        active_tasks_count=active_count,
    )
    return ApiResponse(
        success=True,
        message="Sistema operativo y listo para procesar solicitudes",
        data=data,
    )


@router.get("/status", response_model=ApiResponse[Dict[str, Any]])
async def get_system_status(_auth: bool = Depends(verify_api_key)):
    """Devuelve la carga actual del servidor, cola de renderizado y tareas activas."""
    with api_state.state_lock:
        tasks = []
        for tid, st in api_state.tasks_progress.items():
            if not (st.get("completed") or st.get("error") or st.get("cancelled")):
                tasks.append({
                    "task_id": tid,
                    "step": st.get("step"),
                    "progress": st.get("progress"),
                    "message": st.get("message"),
                    "file_name": st.get("file_name"),
                })

    return ApiResponse(
        success=True,
        message="Estado de carga del servidor obtenido",
        data={
            "active_tasks": tasks,
            "render_locked": api_state.render_lock.locked(),
            "max_concurrent_renders": 1,
            "inputs_dir": str(settings.INPUTS_DIR),
            "outputs_dir": str(settings.OUTPUTS_DIR),
        },
    )


@router.get("/models", response_model=ApiResponse[Dict[str, Any]])
async def get_available_models(_auth: bool = Depends(verify_api_key)):
    """Lista todos los modelos de IA configurados (Gemini, NVIDIA NIM, GLM, Kimi)."""
    from core.app_agent import AppAgentController
    controller = AppAgentController()
    models = controller.get_models_list()
    return ApiResponse(
        success=True,
        message="Catálogo de modelos LLM disponibles",
        data={"models": models, "active_default": settings.GEMINI_MODEL},
    )
