"""Gestión centralizada de estado compartido para los endpoints de la API v1.

Permite conectar los controladores REST con los workers en background,
eventos de cancelación y colas de renderizado sin dependencias circulares.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Coroutine, Dict, Optional

class ApiServerState:
    def __init__(self) -> None:
        self.tasks_progress: Dict[str, Dict[str, Any]] = {}
        self.task_cancel_events: Dict[str, threading.Event] = {}
        self.task_pipelines: Dict[str, Any] = {}
        self.task_jobs: Dict[str, asyncio.Task] = {}
        self.task_webhooks: Dict[str, str] = {}
        self.state_lock: threading.RLock = threading.RLock()
        self.render_lock: asyncio.Lock = asyncio.Lock()
        
        # Callables provistos por server.py al iniciar
        self.update_task_state_fn: Optional[Callable[..., None]] = None
        self.run_pipeline_task_fn: Optional[Callable[..., Coroutine[Any, Any, None]]] = None
        self.run_streamer_task_fn: Optional[Callable[..., Coroutine[Any, Any, None]]] = None
        self.run_export_task_fn: Optional[Callable[..., Coroutine[Any, Any, None]]] = None

    def initialize(
        self,
        *,
        tasks_progress: Dict[str, Dict[str, Any]],
        task_cancel_events: Dict[str, threading.Event],
        task_pipelines: Dict[str, Any],
        task_jobs: Dict[str, asyncio.Task],
        state_lock: threading.RLock,
        render_lock: asyncio.Lock,
        update_task_state: Callable[..., None],
        run_pipeline_task: Callable[..., Coroutine[Any, Any, None]],
        run_streamer_task: Callable[..., Coroutine[Any, Any, None]],
        run_export_task: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        self.tasks_progress = tasks_progress
        self.task_cancel_events = task_cancel_events
        self.task_pipelines = task_pipelines
        self.task_jobs = task_jobs
        self.state_lock = state_lock
        self.render_lock = render_lock
        self.update_task_state_fn = update_task_state
        self.run_pipeline_task_fn = run_pipeline_task
        self.run_streamer_task_fn = run_streamer_task
        self.run_export_task_fn = run_export_task

    def register_webhook(self, task_id: str, webhook_url: Optional[str]) -> None:
        if webhook_url and str(webhook_url).strip().startswith("http"):
            self.task_webhooks[task_id] = str(webhook_url).strip()

    def get_webhook(self, task_id: str) -> Optional[str]:
        return self.task_webhooks.get(task_id)

    def pop_webhook(self, task_id: str) -> Optional[str]:
        return self.task_webhooks.pop(task_id, None)

    def update_task_state(self, task_id: str, step: str, progress: float, message: str, **extra: Any) -> None:
        if self.update_task_state_fn:
            self.update_task_state_fn(task_id, step, progress, message, **extra)

# Instancia singleton accesible para todos los sub-routers de la API v1
api_state = ApiServerState()
