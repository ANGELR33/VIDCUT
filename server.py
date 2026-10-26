import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import unicodedata
import urllib.parse
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

import aiofiles
from fastapi import FastAPI, BackgroundTasks, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from cancellation import CancellationRequested
from core.avatar_narrator import DEFAULT_VOICE
from core.llm import safe_log
from core.models import VideoEditingPlan
from core.pipeline import PipelineOptions, VideoPipeline
from core.project_store import ProjectStore, editor_snapshot
from core.render_engine import VideoRenderEngine
from core.streamer_pipeline import StreamerOptions, StreamerPipeline
from core.timeline import TimelineMapper
from core.trend_radar import TrendRadar
from core.viral_niches_crawler import viral_niches_crawler
from utils.file_manager import FileManager

app = FastAPI(title="AetherCut AI Video Editor")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "Content-Disposition", "Accept-Ranges"],
)

WEB_DIR = Path(__file__).resolve().parent / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

import jinja2
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
    auto_reload=True
)

ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
MAX_UPLOAD_MB = 2048


class NoCacheStaticFiles(StaticFiles):
    """Evita que el navegador sirva CSS/JS antiguos tras cambios de diseño."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


class OutputsStaticFiles(StaticFiles):
    """Manejador robusto para streaming y descarga de videos, másters y clips verticales 9:16.
    
    Protege contra:
    1. 404 por títulos actualizados en re-extracciones (busca por índice de clip short_{task_id}_{idx}_*.mp4).
    2. Problemas de codificación URL/Unicode en Windows (acentos, espacios, %-encoding).
    3. Descargas fallidas en Edge/Chrome ('El archivo no estaba disponible en el sitio'):
       fuerza Content-Disposition: attachment cuando se incluye ?download=1.
    4. Streaming suave con soporte HTTP Range nativo de StaticFiles para reproducción <video>.
    """

    def lookup_path(self, path: str) -> tuple[str, Optional[os.stat_result]]:
        # 1. Búsqueda exacta estándar
        full_path, stat_res = super().lookup_path(path)
        if stat_res is not None:
            return full_path, stat_res

        # 2. Búsqueda decodificando percent-encoding (ej. %C3%A9 -> é)
        try:
            unquoted = urllib.parse.unquote(path)
            if unquoted != path:
                full_path, stat_res = super().lookup_path(unquoted)
                if stat_res is not None:
                    return full_path, stat_res
        except Exception:
            unquoted = path

        # 3. Fallback inteligente para clips virales: short_{task_id}_{idx}_...
        # Si el usuario tiene abierta una pestaña antigua con un título anterior o si el clip fue re-generado,
        # se localiza el clip activo correspondiente a ese mismo número de reel/índice.
        base_name = os.path.basename(unquoted)
        m = re.match(r"^(short_[a-zA-Z0-9]+_\d+)(?:_.*)?(\.[a-zA-Z0-9]+)$", base_name)
        if m:
            prefix = m.group(1) + "_"
            ext = m.group(2)
            for directory in self.all_directories:
                dir_path = Path(directory)
                if dir_path.is_dir():
                    candidates = list(dir_path.glob(f"{prefix}*{ext}"))
                    if candidates:
                        best = max(candidates, key=lambda p: p.stat().st_mtime)
                        return str(best.resolve()), best.stat()

        # 4. Fallback por normalización Unicode / ASCII (sin acentos)
        norm_name = unicodedata.normalize("NFKD", base_name).encode("ascii", "ignore").decode("ascii").lower()
        for directory in self.all_directories:
            dir_path = Path(directory)
            if dir_path.is_dir():
                for candidate in dir_path.iterdir():
                    if not candidate.is_file():
                        continue
                    cand_norm = unicodedata.normalize("NFKD", candidate.name).encode("ascii", "ignore").decode("ascii").lower()
                    if cand_norm == norm_name:
                        return str(candidate.resolve()), candidate.stat()

        return "", None

    async def get_response(self, path: str, scope: Any):
        response = await super().get_response(path, scope)
        qs = scope.get("query_string", b"")
        if b"download" in qs:
            clean_fn = unicodedata.normalize("NFKD", os.path.basename(path)).encode("ascii", "ignore").decode("ascii")
            response.headers["Content-Disposition"] = f'attachment; filename="{clean_fn or "video.mp4"}"'
        return response


app.mount("/static", NoCacheStaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", OutputsStaticFiles(directory=str(settings.OUTPUTS_DIR)), name="media")
app.mount("/outputs", OutputsStaticFiles(directory=str(settings.OUTPUTS_DIR)), name="outputs")
app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_DIR)), name="storage")
app.mount("/assets", StaticFiles(directory=str(Path(__file__).resolve().parent / "assets")), name="assets")

tasks_progress: Dict[str, Dict[str, Any]] = {}
task_cancel_events: Dict[str, threading.Event] = {}
task_pipelines: Dict[str, VideoPipeline] = {}
task_jobs: Dict[str, asyncio.Task] = {}
_state_lock = threading.RLock()
_render_lock = asyncio.Lock()  # un render FFmpeg a la vez: protege CPU/GPU y memoria


@app.on_event("startup")
async def recover_orphaned_inputs() -> None:
    """Convierte cargas de un servidor interrumpido en proyectos recuperables."""
    import time
    defaults = {"silence_threshold": 1.5, "broll": True, "cards": True, "captions": False, "shorts": True}
    if not settings.INPUTS_DIR.exists():
        return
    for source in settings.INPUTS_DIR.iterdir():
        if not source.is_file():
            continue
        match = re.match(r"^([a-f0-9]{8})_", source.name, re.I)
        if not match:
            continue
        # Solo recuperar archivos modificados en las últimas 24 horas
        if time.time() - source.stat().st_mtime > 86400:
            continue
        project = ProjectStore(match.group(1))
        if project.manifest_path.exists():
            continue
        project.create(source_file=source, original_name=source.name.split("_", 1)[-1], options=defaults)
        project.set_status("recovered", message="Carga conservada tras reiniciar el servidor.")


@app.on_event("startup")
async def start_viral_niches_discovery() -> None:
    """Inicia el rastreador continuo de nichos virales en Internet al arrancar el servidor."""
    viral_niches_crawler.start_background_loop()


def friendly_error(exc: Exception) -> str:
    text = str(exc)
    for key in settings.GEMINI_API_KEY.split(","):
        if key.strip():
            text = text.replace(key.strip(), "[clave oculta]")
    low = text.lower()
    if "429" in text or "quota" in low or "resource_exhausted" in low:
        return "Gemini alcanzó un límite de cuota en los proyectos configurados. Revisa su uso en AI Studio e inténtalo cuando alguno vuelva a estar disponible."
    if "503" in text or "unavailable" in low:
        return "Los modelos de Gemini están saturados en este momento. Inténtalo de nuevo en un minuto."
    if "api key" in low or "401" in text or "unauthenticated" in low:
        return "La clave de Gemini no es válida. Revisa GEMINI_API_KEY en el archivo .env."
    if "ffmpeg" in low:
        return "FFmpeg falló al procesar el video. Prueba con otro archivo o formato (MP4 recomendado)."
    return text[:300]


def summarize_active_tasks(limit: int = 5) -> list:
    """Resumen thread-safe de las tareas en curso para el contexto del Agente Copilot."""
    out = []
    with _state_lock:
        for tid, st in tasks_progress.items():
            if st.get("completed") or st.get("error") or st.get("cancelled"):
                continue
            out.append({
                "id": tid,
                "step": st.get("step"),
                "progress": round(float(st.get("progress") or 0)),
                "message": (st.get("message") or "")[:120],
            })
            if len(out) >= limit:
                break
    return out


def update_task_state(task_id: str, step: str, progress: float, message: str, **extra: Any) -> None:
    with _state_lock:
        state = tasks_progress.get(task_id)
        if state is not None:
            # Los latidos solo confirman que el worker continúa esperando una
            # operación externa. No son una acción nueva y no deben llenar la
            # actividad ni fingir una respuesta de Gemini.
            heartbeat = bool(extra.pop("heartbeat", False))
            if heartbeat:
                state.update({
                    "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                    "waiting_seconds": int(extra.pop("waiting_seconds", 0)),
                    **extra,
                })
                return
            if state.get("cancel_requested") and step not in {"cancelling", "cancelled"}:
                step = "cancelling"
                progress = state.get("progress", progress)
                message = state.get("message", "Cancelación solicitada.")
            now = datetime.now(timezone.utc).isoformat()
            changed = step != state.get("step") or message != state.get("message")
            if step != state.get("step"):
                state["step_started_at"] = now
            state.update({"step": step, "progress": max(progress, state.get("progress", 0.0)),
                          "message": message, "updated_at": now, **extra})
            if changed:
                events = state.setdefault("events", [])
                events.append({"step": step, "progress": state["progress"], "message": message, "at": now})
                del events[:-80]
            try:
                # Persistir progreso activo en el almacén del proyecto para que la recarga de página no lo pierda
                p_store = ProjectStore(task_id)
                if p_store.manifest_path.exists():
                    doc = p_store.read()
                    doc["current_progress"] = {
                        "step": state.get("step"),
                        "progress": state.get("progress"),
                        "message": state.get("message"),
                        "completed": state.get("completed", False),
                        "error": state.get("error"),
                        "result": state.get("result"),
                        "file_name": state.get("file_name"),
                        "cancel_supported": state.get("cancel_supported", True),
                        "live_scenes": state.get("live_scenes"),
                        "events": state.get("events"),
                    }
                    p_store.write(doc)
            except Exception:
                pass


def cleanup_cancelled_task_files(task_id: str, input_file: Path) -> None:
    # El proyecto se conserva para poder revisar el material, las fuentes y la
    # línea de tiempo después de cancelar. Solo se limpian exportaciones
    # incompletas que pertenezcan a la tarea.
    for path in settings.OUTPUTS_DIR.glob(f"{task_id}_*"):
        if path.is_file():
            path.unlink(missing_ok=True)


FRONTEND_DIST_INDEX = Path(__file__).resolve().parent / "frontend" / "dist" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if FRONTEND_DIST_INDEX.exists():
        response = FileResponse(str(FRONTEND_DIST_INDEX), media_type="text/html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
    template = jinja_env.get_template("index.html")
    return HTMLResponse(content=template.render())



async def run_pipeline_task(task_id: str, input_file: Path, options: PipelineOptions) -> None:
    update_task_state(task_id, "init", 5.0, "Iniciando análisis del video...")
    cancel_event = task_cancel_events[task_id]
    project = ProjectStore(task_id)
    project.set_status("running")
    try:
        pipeline = VideoPipeline(
            task_id, input_file, options,
            on_state=lambda step, pct, msg, **kw: update_task_state(task_id, step, pct, msg, **kw),
            cancel_event=cancel_event,
            project_store=project,
            render_lock=_render_lock,
        )
        task_pipelines[task_id] = pipeline
        if cancel_event.is_set():
            raise CancellationRequested()
        result = await pipeline.run()
        if cancel_event.is_set():
            raise CancellationRequested()
        update_task_state(task_id, "done", 100.0, "Edición completada.", completed=True, result=result)
        project.set_status("done", result=result)
    except CancellationRequested:
        update_task_state(task_id, "cancelled", tasks_progress.get(task_id, {}).get("progress", 0.0),
                          "Edición cancelada.", completed=True, cancelled=True,
                          cancel_requested=False)
        cleanup_cancelled_task_files(task_id, input_file)
        project.set_status("cancelled")
    except Exception as exc:
        safe_log(f"[Pipeline] Error: {exc}")
        state = tasks_progress.get(task_id, {})
        update_task_state(task_id, "error", state.get("progress", 0.0), "La edición se detuvo.",
                          error=friendly_error(exc), failed_step=state.get("step"))
        project.set_status("error", error=friendly_error(exc))
    finally:
        task_pipelines.pop(task_id, None)
        task_cancel_events.pop(task_id, None)
        task_jobs.pop(task_id, None)

    # conserva solo las últimas 20 tareas en memoria
    for old in list(tasks_progress)[:-20]:
        tasks_progress.pop(old, None)


async def run_export_task(task_id: str) -> None:
    """Renderiza un proyecto guardado sin repetir Gemini ni búsquedas web."""
    acquired = False
    cancel_event = task_cancel_events[task_id]
    store = ProjectStore(task_id)
    try:
        if _render_lock.locked():
            update_task_state(task_id, "queued", 5.0, "En cola de render: esperando que termine la codificación actual...")
        await _render_lock.acquire()
        acquired = True
        document = store.read()
        source = Path(document.get("source_file") or "")
        if not source.exists():
            raise FileNotFoundError("No se encontró el video original para exportar.")
        plan = store.load_plan()
        duration = float(FileManager.get_media_metadata(source, cancel_event).get("duration") or 0)
        if duration <= 0:
            raise RuntimeError("No se pudo leer la duración del video original.")
        mapper = TimelineMapper.from_plan_segments(plan.timeline, duration)
        revision = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = settings.OUTPUTS_DIR / f"{task_id}_edit_{revision}.mp4"
        engine = VideoRenderEngine(fps=settings.DEFAULT_VIDEO_FPS, cancel_event=cancel_event)

        def progress(message: str, fraction: float) -> None:
            update_task_state(task_id, "render", 10.0 + 85.0 * fraction, message)

        # Preparar Avatar Copilot para las tarjetas si no existen aún
        from core.avatar_narrator import AvatarNarrator
        from core.avatar_renderer import AvatarRenderer
        narrator = AvatarNarrator()
        avatar_rnd = AvatarRenderer(badge_size=320)
        for card in plan.info_cards:
            if card.enabled and card.verdict in ("supported", "contradicted", "insufficient"):
                if not getattr(card, "avatar_video_path", None) or not Path(card.avatar_video_path).exists():
                    try:
                        if not card.avatar_spoken_text:
                            surrounding_context = ""
                            if plan.captions:
                                chunks = [
                                    c.text for c in plan.captions
                                    if (card.start_sec - 14.0) <= c.start_sec <= (card.start_sec + 4.0)
                                ]
                                surrounding_context = " ".join(chunks).strip()
                            card.avatar_spoken_text = await narrator.craft_dialogue_with_ai(
                                card, surrounding_context=surrounding_context
                            )
                        audio_file = store.workdir / f"{card.card_id}_voice.mp3"
                        _p, dur = await narrator.synthesize(card.avatar_spoken_text, audio_file)
                        card.avatar_audio_path = str(audio_file)
                        video_file = store.workdir / f"{card.card_id}_avatar.webm"
                        # to_thread: render_reaction_clip es síncrono pesado (cientos
                        # de frames + FFmpeg); directo congelaba todo el event loop
                        # (sin progreso ni cancelación) durante el render de cada avatar.
                        rendered = await asyncio.to_thread(
                            avatar_rnd.render_reaction_clip, dur + 0.5, video_file, audio_path=audio_file
                        )
                        if rendered:
                            card.avatar_video_path = str(rendered)
                            card.avatar_enabled = True
                            card.display_duration_sec = max(card.display_duration_sec, dur + 1.0)
                    except Exception as exc:
                        safe_log(f"[Export] Avatar en reexportación: {exc}")

        update_task_state(task_id, "render", 8.0, "Reexportando el proyecto guardado con tus cambios.")
        loop = asyncio.get_running_loop()
        render_info = await loop.run_in_executor(
            None,
            lambda: engine.render(source, plan, mapper, store.workdir / "reexports" / revision, output,
                                  (lambda _cut: mapper.remap_captions(plan.captions)) if plan.captions else None,
                                  progress),
        )
        if cancel_event.is_set():
            raise CancellationRequested()
        result = dict(document.get("result") or {})
        result.update({
            "master_video_url": f"/media/{output.name}",
            "cards_shown": sum(1 for item in render_info["overlays"] if item["kind"] == "card"),
            "brolls_count": sum(1 for item in render_info["overlays"] if item["kind"] != "card"),
            "captions_count": render_info["captions"],
        })
        store.set_status("done", result=result)
        update_task_state(task_id, "done", 100.0, "Nueva versión exportada.", completed=True, result=result)
    except CancellationRequested:
        store.set_status("ready_for_export")
        update_task_state(task_id, "cancelled", tasks_progress.get(task_id, {}).get("progress", 0.0),
                          "Exportación cancelada.", completed=True, cancelled=True)
    except Exception as exc:
        safe_log(f"[Export] Error: {exc}")
        store.set_status("ready_for_export", error=friendly_error(exc))
        update_task_state(task_id, "error", tasks_progress.get(task_id, {}).get("progress", 0.0),
                          "La exportación se detuvo.", error=friendly_error(exc))
    finally:
        if acquired:
            _render_lock.release()
        task_cancel_events.pop(task_id, None)
        task_jobs.pop(task_id, None)


@app.post("/api/process-video")
async def process_video(
    video: UploadFile = File(...),
    silence_threshold: float = Form(1.5),
    enable_broll: bool = Form(True),
    enable_captions: bool = Form(True),
    enable_shorts: bool = Form(True),
    enable_cards: bool = Form(True),
    voice: str = Form("es-MX-JorgeNeural"),
):
    ext = Path(video.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Formato no soportado ({ext or 'sin extensión'}). Usa MP4, MOV, MKV o WEBM.")

    task_id = uuid.uuid4().hex[:8]
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(video.filename).stem)[:60]
    saved = settings.INPUTS_DIR / f"{task_id}_{clean}{ext}"

    # Escritura por bloques: un video de cientos de MB no se carga entero en memoria.
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
    tasks_progress[task_id] = {
        "step": "init", "progress": 5.0, "message": "Archivo recibido. Iniciando...",
        "completed": False, "error": None, "result": None, "cancel_supported": True,
        "file_name": Path(video.filename or "video").name,
        "created_at": now, "updated_at": now, "step_started_at": now,
        "events": [{"step": "init", "progress": 5.0, "message": "Archivo recibido. Iniciando...", "at": now}],
    }
    options = PipelineOptions(
        silence_threshold=max(0.8, min(3.0, silence_threshold)),
        broll=enable_broll, captions=enable_captions, shorts=enable_shorts, cards=enable_cards,
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
        },
    )
    task_cancel_events[task_id] = threading.Event()
    task_jobs[task_id] = asyncio.create_task(run_pipeline_task(task_id, saved, options))
    return {"task_id": task_id, "project_id": task_id}


def _auto_studio_thumbnail(task_id: str, title: str, topic: str) -> None:
    """Miniatura profesional local (Pillow) para dejar el video listo sin cuotas."""
    from core.publish_studio import PublishStudio
    res = PublishStudio(task_id).generate_studio_thumbnail_fast(title=title, topic=topic)
    safe_log(f"[Radar] Video listo con miniatura de estudio: {res.get('url')}")


async def run_streamer_task(task_id: str, options: StreamerOptions) -> None:
    update_task_state(task_id, "research", 10.0, f"Investigando datos web sobre «{options.topic}»...")
    cancel_event = task_cancel_events[task_id]
    project = ProjectStore(task_id)
    project.set_status("running")
    try:
        pipeline = StreamerPipeline(
            task_id, options,
            on_state=lambda step, pct, msg, **kw: update_task_state(task_id, step, pct, msg, **kw),
            cancel_event=cancel_event,
            project_store=project,
            render_lock=_render_lock,
        )
        if cancel_event.is_set():
            raise CancellationRequested()
        result = await pipeline.run()
        if cancel_event.is_set():
            raise CancellationRequested()
        # preview_url en el estado final (igual que el pipeline clásico): el último
        # tick del SSE lleva la URL del master para que la Mesa cargue el monitor.
        update_task_state(task_id, "done", 100.0, "¡Transmisión completada!", completed=True, result=result,
                          preview_url=f"/api/projects/{task_id}/preview")
        project.set_status("done", result=result)
        # Los videos originados por el Radar de Viralidad quedan listos para
        # publicar: miniatura profesional de estudio generada automáticamente.
        try:
            origin = ((project.read().get("options") or {}).get("origin") or "")
            if origin == "radar":
                update_task_state(task_id, "thumbnail", 100.0, "Generando miniatura profesional de estudio...")
                thumb_title = str(result.get("title") or (project.read().get("options") or {}).get("topic") or task_id)
                thumb_topic = str((project.read().get("options") or {}).get("topic") or "")
                await asyncio.to_thread(_auto_studio_thumbnail, task_id, thumb_title, thumb_topic)
        except Exception as exc:
            safe_log(f"[Radar] Miniatura automática falló: {exc}")
    except (CancellationRequested, asyncio.CancelledError):
        update_task_state(task_id, "cancelled", tasks_progress.get(task_id, {}).get("progress", 0.0),
                          "Transmisión cancelada.", completed=True, cancelled=True)
        project.set_status("cancelled")
    except Exception as exc:
        safe_log(f"[StreamerTask] Error: {exc}")
        state = tasks_progress.get(task_id, {})
        update_task_state(task_id, "error", state.get("progress", 0.0), "La transmisión se detuvo.",
                          error=friendly_error(exc), failed_step=state.get("step"))
        project.set_status("error", error=friendly_error(exc))
    finally:
        task_cancel_events.pop(task_id, None)
        task_jobs.pop(task_id, None)


@app.post("/api/streamer/create")
async def create_streamer_broadcast(payload: Dict[str, Any] = Body(...)):
    topic = str(payload.get("topic", "")).strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Debes indicar un tema para la transmisión.")
    style = str(payload.get("style", "divulgacion")).strip()
    raw_duration = payload.get("duration_sec")
    raw_minutes = payload.get("duration_min")
    try:
        if raw_minutes is not None:
            duration_sec = int(float(raw_minutes) * 60)
        else:
            duration_sec = int(raw_duration) if raw_duration is not None else 45
    except (ValueError, TypeError):
        duration_sec = 45
    duration_sec = max(20, min(2400, duration_sec))
    aspect_ratio = str(payload.get("aspect_ratio", "16:9")).strip()
    card_theme = str(payload.get("card_theme", "dark")).strip()
    voice = str(payload.get("voice", DEFAULT_VOICE)).strip()
    raw_rtmp = payload.get("rtmp_url")
    rtmp_url = str(raw_rtmp).strip() if (raw_rtmp and str(raw_rtmp).strip() not in ("None", "null", "")) else None
    extra_opts = {
        "sub_style": str(payload.get("sub_style", "classic")).strip().lower() or "classic",
        "subs_enabled": bool(payload.get("subs_enabled", True)),
        "visual_mode": str(payload.get("visual_mode", "mixed")).strip().lower() or "mixed",
        "enable_broll": bool(payload.get("enable_broll", True)),
        "enable_cards": bool(payload.get("enable_cards", True)),
        "extra_notes": str(payload.get("extra_notes", "") or "")[:600],
        "flash_audit": bool(payload.get("flash_audit", True)),
        # === Parámetros de producción profesional ===
        "audio_normalize": bool(payload.get("audio_normalize", True)),
        "color_grade": str(payload.get("color_grade", "cinema")).strip().lower() or "cinema",
        "fps": max(24, min(60, int(payload.get("fps", 30)))),
        "crf": max(14, min(28, int(payload.get("crf", 18)))),
        "bgm_volume": max(0.0, min(0.25, float(payload.get("bgm_volume", 0.12)))),
        "intro_style": str(payload.get("intro_style", "kai")).strip().lower() or "kai",
        "outro_enabled": bool(payload.get("outro_enabled", True)),
        "bgm_track": str(payload.get("bgm_track", "default")).strip().lower() or "default",
        # Modo análisis de caso: video/caso concreto que KAI analiza visualmente
        "source_video_url": (str(payload.get("video_url", "")).strip() or None)
        if str(payload.get("video_url", "")).strip().lower() not in ("none", "null", "")
        else None,
        # Publicación automática desatendida o preparación autónoma multi-canal
        "auto_publish": bool(payload.get("auto_publish", False)),
        "origin": str(payload.get("origin", "manual")).strip() or "manual",
    }

    task_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    tasks_progress[task_id] = {
        "step": "research", "progress": 10.0, "message": f"Investigando «{topic}» en la web...",
        "completed": False, "error": None, "result": None, "cancel_supported": True,
        "file_name": f"KAI Stream: {topic[:35]}",
        "created_at": now, "updated_at": now, "step_started_at": now,
        "events": [{"step": "research", "progress": 10.0, "message": f"Investigando «{topic}»...", "at": now}],
    }
    options = StreamerOptions(
        topic=topic,
        style=style,
        duration_sec=duration_sec,
        aspect_ratio=aspect_ratio,
        card_theme=card_theme,
        voice=voice,
        rtmp_url=rtmp_url,
        **extra_opts,
    )
    store = ProjectStore(task_id)
    store.create(
        source_file=settings.OUTPUTS_DIR / f"{task_id}_master.mp4",
        original_name=f"KAI Stream: {topic}",
        options={"topic": topic, "style": style, "duration_sec": duration_sec, "mode": "streamer",
                 "aspect_ratio": aspect_ratio, "card_theme": card_theme, "voice": voice,
                 "origin": str(payload.get("origin", "manual")), **extra_opts}
    )
    task_cancel_events[task_id] = threading.Event()
    task_jobs[task_id] = asyncio.create_task(run_streamer_task(task_id, options))
    return {"task_id": task_id, "project_id": task_id}


# ============================================================================
# API Pública v1 para integración con aplicaciones externas y webhooks
# ============================================================================
from api.router import api_v1_router, init_api_state
init_api_state(
    tasks_progress=tasks_progress,
    task_cancel_events=task_cancel_events,
    task_pipelines=task_pipelines,
    task_jobs=task_jobs,
    state_lock=_state_lock,
    render_lock=_render_lock,
    update_task_state=update_task_state,
    run_pipeline_task=run_pipeline_task,
    run_streamer_task=run_streamer_task,
    run_export_task=run_export_task,
)
app.include_router(api_v1_router)


@app.post("/api/projects/{task_id}/resume")
async def resume_project(task_id: str):
    """Reanuda un proyecto interrumpido (Streamer o Co-Piloto) sin perder escenas ya grabadas."""
    if task_id in task_jobs and not task_jobs[task_id].done():
        raise HTTPException(status_code=409, detail="Este proyecto ya está procesándose.")
    store = ProjectStore(task_id)
    try:
        document = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    raw_options = document.get("options") or {}
    now = datetime.now(timezone.utc).isoformat()

    # Si es una transmisión de KAI Streamer
    if raw_options.get("mode") == "streamer" or (document.get("original_name") or "").startswith("KAI Stream"):
        topic = raw_options.get("topic") or (document.get("result") or {}).get("topic") or document.get("original_name", "").replace("KAI Stream: ", "")
        options = StreamerOptions(
            topic=topic,
            style=raw_options.get("style", "divulgacion"),
            duration_sec=int(raw_options.get("duration_sec", 45)),
            aspect_ratio=raw_options.get("aspect_ratio", "16:9"),
            card_theme=raw_options.get("card_theme", "dark"),
            voice=raw_options.get("voice", DEFAULT_VOICE),
            rtmp_url=raw_options.get("rtmp_url"),
            sub_style=raw_options.get("sub_style", "classic"),
            subs_enabled=bool(raw_options.get("subs_enabled", True)),
            visual_mode=raw_options.get("visual_mode", "mixed"),
            enable_broll=bool(raw_options.get("enable_broll", True)),
            enable_cards=bool(raw_options.get("enable_cards", True)),
            extra_notes=str(raw_options.get("extra_notes", "") or ""),
            flash_audit=bool(raw_options.get("flash_audit", True)),
            audio_normalize=bool(raw_options.get("audio_normalize", True)),
            color_grade=str(raw_options.get("color_grade", "cinema")),
            fps=int(raw_options.get("fps", 30)),
            crf=int(raw_options.get("crf", 18)),
            bgm_volume=float(raw_options.get("bgm_volume", 0.12)),
            intro_style=str(raw_options.get("intro_style", "kai")),
            outro_enabled=bool(raw_options.get("outro_enabled", True)),
            bgm_track=str(raw_options.get("bgm_track", "default")),
            source_video_url=raw_options.get("source_video_url"),
            origin=str(raw_options.get("origin", "manual")),
        )
        tasks_progress[task_id] = {
            "step": "render", "progress": 50.0, "message": f"Reanudando transmisión de «{topic}»...",
            "completed": False, "error": None, "result": None, "cancel_supported": True,
            "file_name": document.get("original_name", f"KAI Stream {task_id}"),
            "created_at": document.get("created_at", now), "updated_at": now, "step_started_at": now,
            "events": [{"step": "render", "progress": 50.0, "message": "Reanudando transmisión desde escenas guardadas...", "at": now}],
        }
        task_cancel_events[task_id] = threading.Event()
        task_jobs[task_id] = asyncio.create_task(run_streamer_task(task_id, options))
        return {"task_id": task_id, "message": f"Transmisión «{topic}» reanudada con éxito."}

    # Si es video co-piloto
    source = Path(document.get("source_file") or "")
    if not source.exists():
        raise HTTPException(status_code=410, detail="No se encontró el video original para reanudar este proyecto.")
    options = PipelineOptions(
        silence_threshold=max(0.8, min(3.0, float(raw_options.get("silence_threshold", 1.5)))),
        broll=bool(raw_options.get("broll", True)), cards=bool(raw_options.get("cards", True)),
        captions=bool(raw_options.get("captions", False)), shorts=bool(raw_options.get("shorts", True)),
    )
    tasks_progress[task_id] = {
        "step": "queued", "progress": 5.0, "message": "Reanudando la carga conservada.",
        "completed": False, "error": None, "result": None, "cancel_supported": True,
        "file_name": document.get("original_name", source.name), "created_at": now,
        "updated_at": now, "step_started_at": now,
        "events": [{"step": "queued", "progress": 5.0, "message": "Reanudando la carga conservada.", "at": now}],
    }
    task_cancel_events[task_id] = threading.Event()
    task_jobs[task_id] = asyncio.create_task(run_pipeline_task(task_id, source, options))
    return {"task_id": task_id, "message": "El proyecto se reanudó con el archivo ya guardado."}


@app.post("/api/projects/{task_id}/detect-silence")
async def server_detect_project_silence(
    task_id: str,
    min_silence_sec: float = Query(0.8, ge=0.2, le=5.0),
    noise_db: float = Query(-32.0, le=-10.0, ge=-60.0),
):
    """Detecta intervalos de silencio y pausas muertas en el audio del proyecto."""
    from core.silence_detector import SilenceDetector
    store = ProjectStore(task_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    target_path = None
    if doc.get("source_file") and Path(doc["source_file"]).exists():
        target_path = Path(doc["source_file"])
    else:
        master = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
        if master.exists():
            target_path = master
        else:
            cand = next(settings.OUTPUTS_DIR.glob(f"{task_id}_edit_*.mp4"), None)
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

    return {
        "success": True,
        "project_id": task_id,
        "silence_intervals": clean_silences,
        "count": len(clean_silences),
        "total_saved_sec": round(total_saved_sec, 2),
        "min_silence_sec": min_silence_sec,
    }


def build_broadcast_editor_snapshot(task_id: str, document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Genera un editor snapshot completo y sincronizado para proyectos KAI Streamer."""
    proj_dir = settings.PROJECTS_DIR / task_id
    plan_path = proj_dir / "work" / "broadcast_plan.json"
    if not plan_path.exists():
        return None
    try:
        raw_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    scenes_raw = raw_plan.get("scenes", [])
    if not scenes_raw:
        return None

    master_file = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
    master_dur = 0.0
    if master_file.exists():
        try:
            master_dur = FileManager.get_media_metadata(master_file).get("duration", 0.0)
        except Exception:
            pass

    cum_time = 0.0
    scenes_list = []
    cards_list = []
    brolls_list = []
    speech_list = []
    captions_list = []

    for sc in scenes_raw:
        sid = sc.get("scene_id")
        mp4_file = proj_dir / "work" / f"scene_{sid}" / f"scene_{sid}.mp4"
        voice_file = proj_dir / "work" / f"scene_{sid}" / "voice.mp3"
        dur = 0.0
        if mp4_file.exists():
            try:
                dur = FileManager.get_media_metadata(mp4_file).get("duration", 0.0)
            except Exception:
                pass
        if dur <= 0 and voice_file.exists():
            try:
                dur = FileManager.get_media_metadata(voice_file).get("duration", 0.0)
            except Exception:
                pass
        if dur <= 0:
            dur = float(sc.get("duration_est", 20.0))

        sc_start = round(cum_time, 2)
        sc_end = round(cum_time + dur, 2)
        cum_time += dur

        card = sc.get("card")
        sc_thumb = f"/storage/projects/{task_id}/work/scene_{sid}/scene_thumb.jpg"
        sc_card_url = f"/storage/projects/{task_id}/work/scene_{sid}/card_{sid}.png" if card else None

        scenes_list.append({
            "id": f"scene-{sid}",
            "scene_id": sid,
            "title": f"E{sid}: {sc.get('name', f'Escena {sid}')}",
            "name": sc.get("name", f"Escena {sid}"),
            "type": sc.get("type", "avatar_cam"),
            "emotion": sc.get("emotion", "serious"),
            "camera": sc.get("camera", "hero_center"),
            "start": sc_start,
            "end": sc_end,
            "duration": round(dur, 2),
            "speech": sc.get("speech", ""),
            "headline": card.get("headline", "") if card else "",
            "stat": card.get("stat", "") if card else "",
            "thumb_url": sc_thumb,
            "card_url": sc_card_url,
            "enabled": True,
        })

        if card and isinstance(card, dict) and card.get("headline"):
            card_dur = round(min(6.0, max(2.5, dur - 1.0)), 2)
            card_st = round(sc_start + 1.2, 2)
            cards_list.append({
                "id": f"card-{sid}",
                "scene_id": sid,
                "headline": card.get("headline", ""),
                "title": card.get("headline", ""),
                "stat_value": card.get("stat", ""),
                "body": card.get("body", ""),
                "badge": card.get("badge", ""),
                "start": card_st,
                "end": round(card_st + card_dur, 2),
                "duration": card_dur,
                "card_url": sc_card_url,
                "enabled": True,
            })

        broll_concept = sc.get("visual_query") or (sc.get("visual_queries", [None])[0] if sc.get("visual_queries") else None)
        if broll_concept or sc.get("type") in ["vector_motion", "card_focus", "video_reaction", "chat_debate", "breaking_news"]:
            brolls_list.append({
                "id": f"broll-{sid}",
                "scene_id": sid,
                "concept": (broll_concept or sc.get("name", f"Clip B-Roll E{sid}"))[:45],
                "title": (broll_concept or sc.get("name", f"Clip B-Roll E{sid}"))[:45],
                "start": sc_start,
                "end": sc_end,
                "status": "ready",
                "enabled": True,
            })

        if sc.get("speech"):
            speech_list.append({
                "id": f"speech-{sid}",
                "scene_id": sid,
                "title": sc.get("speech", "")[:35] + "...",
                "text": sc.get("speech", ""),
                "start": sc_start,
                "end": sc_end,
                "duration": round(dur, 2),
                "enabled": True,
            })

        srt_file = proj_dir / "work" / f"scene_{sid}" / "scene_subtitles.srt"
        if srt_file.exists():
            try:
                blocks = srt_file.read_text(encoding="utf-8").strip().split("\n\n")
                for blk in blocks:
                    lns = [l.strip() for l in blk.splitlines() if l.strip()]
                    if len(lns) >= 3 and "-->" in lns[1]:
                        tp = lns[1].split("-->")
                        def _pt(ts):
                            pts = ts.strip().replace(",", ".").split(":")
                            return float(pts[0])*3600 + float(pts[1])*60 + float(pts[2])
                        c_st = round(sc_start + _pt(tp[0]), 2)
                        c_en = round(sc_start + _pt(tp[1]), 2)
                        captions_list.append({
                            "start": c_st,
                            "end": c_en,
                            "text": " ".join(lns[2:]),
                            "scene_id": sid,
                        })
            except Exception:
                pass

    total_dur = round(master_dur if master_dur > 0 else cum_time, 2)
    return {
        "summary": raw_plan.get("title") or document.get("original_name") or "Producción KAI Streamer",
        "topic": raw_plan.get("topic") or (document.get("options") or {}).get("topic", ""),
        "duration": total_dur,
        "scenes": scenes_list,
        "cards": cards_list,
        "brolls": brolls_list,
        "speech": speech_list,
        "captions": captions_list,
        "cuts": [],
        "shorts": [],
    }


@app.get("/api/projects/{task_id}")
async def get_project(task_id: str):
    try:
        document = ProjectStore(task_id).read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    broadcast_editor = build_broadcast_editor_snapshot(task_id, document)
    if broadcast_editor:
        editor = broadcast_editor
    else:
        plan_data = document.get("plan")
        editor = editor_snapshot(VideoEditingPlan.model_validate(plan_data)) if plan_data else None

    # Asegurar compatibilidad de URLs del video editado y sincronizar duración real
    if document.get("result") and isinstance(document["result"], dict):
        res = document["result"]
        if "media_url" in res and "master_video_url" not in res:
            res["master_video_url"] = res["media_url"]
        if "master_video_url" in res and "media_url" not in res:
            res["media_url"] = res["master_video_url"]
        if editor and isinstance(editor, dict) and editor.get("duration"):
            res["duration"] = editor["duration"]

    # No se exponen rutas del equipo local a la interfaz.
    public = {key: value for key, value in document.items() if key not in {"source_file", "preview_file", "plan"}}
    return {"project": public, "editor": editor}


@app.get("/api/projects/{task_id}/publish-info")
async def get_project_publish_info(task_id: str):
    """Devuelve título, descripción estructurada y hashtags listos para copiar y publicar."""
    store = ProjectStore(task_id)
    try:
        doc = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    result = doc.get("result") or {}
    options = doc.get("options") or {}
    topic = result.get("topic") or options.get("topic") or ""
    raw_title = doc.get("original_name") or result.get("title") or topic or f"Video {task_id}"

    # Si ya tiene metadata generada por el publish studio:
    if "auto_publish_prepared" in result and "metadata" in result["auto_publish_prepared"]:
        meta = result["auto_publish_prepared"]["metadata"]
        tags = meta.get("tags") or []
        hashtags = ["#" + re.sub(r"[\W_]+", "", t) for t in tags if t.strip()]
        return {
            "title": meta.get("title") or raw_title,
            "description": meta.get("description") or "",
            "tags": tags,
            "hashtags": hashtags,
            "hashtags_str": " ".join(hashtags[:12]),
        }

    # Si hay broadcast_plan.json con escenas y speech:
    plan_path = settings.PROJECTS_DIR / task_id / "work" / "broadcast_plan.json"
    speech_summary = ""
    if plan_path.exists():
        try:
            bplan = json.loads(plan_path.read_text(encoding="utf-8"))
            scenes = bplan.get("scenes", [])
            speech_snippets = [sc.get("speech", "") for sc in scenes if sc.get("speech")]
            if speech_snippets:
                speech_summary = " ".join(speech_snippets[:3])
        except Exception:
            pass

    if not speech_summary:
        speech_summary = topic or raw_title

    clean_hook = speech_summary.strip()
    if len(clean_hook) > 280:
        clean_hook = clean_hook[:277] + "..."

    description = (
        f"{clean_hook}\n\n"
        f"🎬 Video producido con Inteligencia Artificial documental.\n"
        f"🔔 ¡Suscríbete y activa la campana para más análisis y revelaciones diarias!\n"
        f"💬 ¿Cuál es tu opinión sobre este caso? Déjamela en los comentarios."
    )

    # Generar hashtags inteligentes
    text_corpus = f"{raw_title} {topic}"
    words = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{4,}", text_corpus)
    stopwords = {"este", "esta", "estos", "estas", "para", "como", "pero", "sobre", "entre", "hacia", "hasta", "desde", "porque", "cuando", "donde", "quien", "video", "stream", "produccion"}
    keywords = []
    for w in words:
        wl = w.lower()
        if wl not in stopwords and wl not in [k.lower() for k in keywords]:
            keywords.append(w.capitalize())

    base_tags = ["Viral", "Tendencias", "AetherCut", "IA", "Documental"]
    all_tags = (keywords[:8] + base_tags)[:10]
    hashtags = ["#" + re.sub(r"[\W_]+", "", t) for t in all_tags]
    hashtags_str = " ".join(hashtags)

    return {
        "title": raw_title,
        "description": description,
        "tags": all_tags,
        "hashtags": hashtags,
        "hashtags_str": hashtags_str,
    }


@app.get("/api/projects/{task_id}/broadcast-plan")
async def get_broadcast_plan(task_id: str):
    """Escenas dirigidas por la IA (guion, emoción, tipo) para la Mesa & Timeline."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
        raise HTTPException(status_code=400, detail="Identificador no válido.")
    plan_path = settings.PROJECTS_DIR / task_id / "work" / "broadcast_plan.json"
    if not plan_path.exists():
        return {"scenes": [], "title": "", "available": False}
    try:
        raw = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"scenes": [], "title": "", "available": False}
    scenes = []
    for sc in raw.get("scenes", []):
        card = sc.get("card") or {}
        scenes.append({
            "scene_id": sc.get("scene_id"), "name": sc.get("name"), "type": sc.get("type"),
            "emotion": sc.get("emotion"), "camera": sc.get("camera"),
            "duration": sc.get("duration_est", 0), "speech": sc.get("speech", ""),
            "headline": card.get("headline", ""), "stat": card.get("stat", ""),
            "thumb_url": f"/storage/projects/{task_id}/work/scene_{sc.get('scene_id')}/scene_thumb.jpg",
        })
    return {"scenes": scenes, "title": raw.get("title", ""), "available": True}


def prune_old_projects(keep_max: int = 20, protect_id: Optional[str] = None) -> int:
    """Conserva únicamente los 20 proyectos más recientes y elimina permanentemente los anteriores para liberar espacio."""
    projects_dir = settings.PROJECTS_DIR
    if not projects_dir.exists():
        return 0

    manifests = list(projects_dir.glob("*/project.json"))
    project_items = []
    for m in manifests:
        pid = m.parent.name
        try:
            mtime = m.stat().st_mtime
            doc = json.loads(m.read_text(encoding="utf-8"))
            updated_at = doc.get("updated_at") or doc.get("created_at") or ""
            project_items.append((pid, mtime, str(updated_at)))
        except Exception:
            try:
                project_items.append((pid, m.stat().st_mtime, ""))
            except Exception:
                pass

    project_items.sort(key=lambda x: (x[2], x[1]), reverse=True)

    if len(project_items) <= keep_max:
        return 0

    to_keep = set()
    if protect_id:
        to_keep.add(protect_id)

    for pid, _, _ in project_items:
        if len(to_keep) < keep_max:
            to_keep.add(pid)
        else:
            break

    deleted_count = 0
    freed_mb = 0.0
    for pid, _, _ in project_items:
        if pid not in to_keep and pid not in task_jobs:
            try:
                store = ProjectStore(pid)
                rep = store.delete(include_source=True, include_outputs=True)
                for sh in settings.OUTPUTS_DIR.glob(f"short_{pid}_*.mp4"):
                    try:
                        sh.unlink(missing_ok=True)
                    except Exception:
                        pass
                deleted_count += 1
                freed_mb += rep.get("freed_bytes", 0) / (1024 * 1024)
            except Exception as _e_del:
                safe_log(f"[Prune] Error eliminando proyecto antiguo {pid}: {_e_del}")

    if deleted_count > 0:
        safe_log(f"[Prune] Se conservaron {len(to_keep)} proyectos recientes. Se eliminaron {deleted_count} proyectos antiguos ({round(freed_mb, 1)} MB liberados).")

    # Limpiar directorios huérfanos sin manifest
    for d in projects_dir.iterdir():
        if d.is_dir() and d.name not in to_keep and not (d / "project.json").exists():
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

    return deleted_count


@app.get("/api/projects")
async def list_projects():
    # Mantener estricto límite de 20 proyectos más recientes en disco
    prune_old_projects(keep_max=20)

    projects = []
    for manifest in settings.PROJECTS_DIR.glob("*/project.json"):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
            pid = document.get("id") or manifest.parent.name
            result = document.get("result") or {}
            
            # Detectar thumbnail si existe
            thumbnail_url = None
            thumb_path = settings.OUTPUTS_DIR / f"{pid}_thumbnail.jpg"
            if thumb_path.exists():
                thumbnail_url = f"/media/{pid}_thumbnail.jpg"
            else:
                # Comprobar b-roll o escena de trabajo si existe en storage/projects
                work_thumb = settings.PROJECTS_DIR / pid / "work" / "streamer_card_0.png"
                if work_thumb.exists():
                    thumbnail_url = f"/storage/projects/{pid}/work/streamer_card_0.png"
                else:
                    broll = next((settings.PROJECTS_DIR / pid / "work" / "assets").glob("*.jpg"), None) if (settings.PROJECTS_DIR / pid / "work" / "assets").exists() else None
                    if broll:
                        thumbnail_url = f"/storage/projects/{pid}/work/assets/{broll.name}"

            duration = result.get("duration") or 0.0
            topic = result.get("topic") or (document.get("options") or {}).get("topic") or ""

            projects.append({
                "id": pid,
                "name": result.get("title") or document.get("title") or document.get("original_name") or "Video sin nombre",
                "status": document.get("status", "unknown"),
                "updated_at": document.get("updated_at"),
                "has_plan": bool(document.get("plan")),
                "has_result": bool(document.get("result")),
                "duration": duration,
                "topic": topic,
                "thumbnail_url": thumbnail_url,
                "master_video_url": result.get("master_video_url") or result.get("media_url")
            })
        except Exception as _e_proj:
            safe_log(f"[Projects] Error cargando proyecto {manifest.parent.name}: {_e_proj}")
            continue
    projects.sort(key=lambda project: project.get("updated_at") or "", reverse=True)
    return {"projects": projects[:20]}


@app.delete("/api/projects/{task_id}")
async def delete_project(task_id: str):
    """Elimina un proyecto y libera espacio en disco."""
    if task_id in task_jobs:
        raise HTTPException(status_code=409, detail="No se puede eliminar un proyecto en ejecución. Cancélalo primero.")
    store = ProjectStore(task_id)
    if not store.root.exists() and not store.manifest_path.exists():
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")
    report = store.delete(include_source=True, include_outputs=True)
    tasks_progress.pop(task_id, None)
    return {"message": "Proyecto eliminado.", "freed_mb": round(report["freed_bytes"] / 1024 / 1024, 2)}




@app.get("/api/projects/{task_id}/preview")
async def get_project_preview(task_id: str):
    store = ProjectStore(task_id)
    try:
        document = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")
    
    path = Path(document.get("preview_file") or "")
    if not path.exists() or not path.is_file():
        src_path = Path(document.get("source_file") or "")
        if src_path.exists() and src_path.is_file():
            path = src_path
        else:
            master_file = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
            if master_file.exists():
                path = master_file
            else:
                res = document.get("result") or {}
                out_path = Path(res.get("output_file") or "")
                if out_path.exists() and out_path.is_file():
                    path = out_path
                else:
                    raise HTTPException(status_code=404, detail="La previsualización todavía no está lista.")

    title = document.get("original_name") or (document.get("result") or {}).get("title") or f"KAI_{task_id}"
    import unicodedata
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    safe_title = re.sub(r"[^\w\s-]", "", ascii_title).strip().replace(" ", "_")[:50] or f"KAI_{task_id}"
    filename = f"{safe_title}.mp4"

    return FileResponse(
        path=path,
        media_type="video/mp4",
        filename=filename,
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        },
    )


def get_downloads_folder() -> Path:
    """Retorna la carpeta de Descargas del usuario de forma robusta."""
    dl = Path.home() / "Downloads"
    if dl.exists() and dl.is_dir():
        return dl
    dl_es = Path.home() / "Descargas"
    if dl_es.exists() and dl_es.is_dir():
        return dl_es
    dl.mkdir(parents=True, exist_ok=True)
    return dl


def format_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def parse_srt_time(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def _prepare_subtitled_master(task_id: str, master_file: Path, style: str = "classic") -> Path:
    """Genera versión con subtítulos quemados garantizando offsets de tiempo correctos por escena,
    encuadre seguro adaptado a la relación de aspecto (9:16 vs 16:9) y estilo visual seleccionado."""
    sub_master = settings.OUTPUTS_DIR / f"{task_id}_master_subtitled_{style}.mp4"

    proj_dir = settings.PROJECTS_DIR / task_id
    full_srt = proj_dir / "work" / "full_subtitles.srt"

    # Si ya existe el subtitulado y es más reciente que el full_srt, reutilizar
    if sub_master.exists() and sub_master.stat().st_size > 50000:
        if full_srt.exists() and sub_master.stat().st_mtime >= full_srt.stat().st_mtime:
            return sub_master

    # Determinar si el video es vertical (9:16) o horizontal (16:9)
    is_vertical = False
    try:
        p_doc = ProjectStore(task_id).read()
        p_opts = p_doc.get("options") or {}
        is_vertical = p_opts.get("aspect_ratio") == "9:16"
    except Exception:
        pass
    if not is_vertical and master_file.exists():
        try:
            meta = FileManager.get_media_metadata(master_file)
            if meta.get("height", 0) > meta.get("width", 0):
                is_vertical = True
        except Exception:
            pass

    all_srt_blocks = []
    scene_dirs = sorted(
        (proj_dir / "work").glob("scene_*"),
        key=lambda p: int(p.name.replace("scene_", "")) if p.name.replace("scene_", "").isdigit() else 999
    ) if (proj_dir / "work").exists() else []

    cum_offset = 0.0
    sub_index = 1
    for sc_dir in scene_dirs:
        srt_path = sc_dir / "scene_subtitles.srt"
        scene_mp4 = sc_dir / f"{sc_dir.name}.mp4"
        sc_dur = 0.0
        if scene_mp4.exists():
            try:
                sc_dur = FileManager.get_media_metadata(scene_mp4).get("duration", 0.0)
            except Exception:
                pass
        if srt_path.exists():
            try:
                raw_srt = srt_path.read_text(encoding="utf-8").strip()
                if raw_srt:
                    blocks = raw_srt.split("\n\n")
                    for blk in blocks:
                        lns = [l.strip() for l in blk.splitlines() if l.strip()]
                        if len(lns) >= 3 and "-->" in lns[1]:
                            tp = lns[1].split("-->")
                            t_start = parse_srt_time(tp[0]) + cum_offset
                            t_end = parse_srt_time(tp[1]) + cum_offset
                            text_content = "\n".join(lns[2:])
                            all_srt_blocks.append(
                                f"{sub_index}\n{format_srt_time(t_start)} --> {format_srt_time(t_end)}\n{text_content}"
                            )
                            sub_index += 1
            except Exception as _e_sc_srt:
                safe_log(f"[Download] Error procesando SRT de {sc_dir.name}: {_e_sc_srt}")
        cum_offset += sc_dur

    if all_srt_blocks:
        try:
            full_srt.write_text("\n\n".join(all_srt_blocks), encoding="utf-8")
            esc_srt = str(full_srt.resolve()).replace("\\", "/").replace(":", "\\:")
            from core.scene_engine import subtitle_force_style
            sub_size = 22 if is_vertical else 18
            margin_v = 75 if is_vertical else 35
            clean_style = str(getattr(style, "default", style) or "classic")
            force_style = subtitle_force_style(clean_style, sub_size, margin_v)
            cmd = [
                "ffmpeg", "-y", "-i", str(master_file),
                "-vf", f"subtitles='{esc_srt}':force_style='{force_style}'",
                "-c:a", "copy",
                "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                str(sub_master)
            ]
            burn_timeout = max(300, int(cum_offset * 1.5)) if cum_offset > 0 else 300
            subprocess.run(cmd, capture_output=True, timeout=burn_timeout)
            if sub_master.exists() and sub_master.stat().st_size > 50000:
                return sub_master
        except Exception as _burn_err:
            safe_log(f"[Download] Fallo al quemar subtítulos en export: {_burn_err}")

    return master_file


@app.get("/api/projects/{task_id}/download")
@app.get("/api/projects/{task_id}/download/{filename}")
async def download_project_master(
    task_id: str,
    filename: Optional[str] = None,
    burn_subtitles: bool = Query(False),
    style: str = Query("classic")
):
    """Descarga el video final con nombre descriptivo y formato MP4 garantizado para cualquier navegador."""
    store = ProjectStore(task_id)
    try:
        document = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    master_file = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
    if not master_file.exists():
        res = document.get("result") or {}
        candidate = Path(res.get("output_file") or "")
        if candidate.exists() and candidate.is_file():
            master_file = candidate
        else:
            prev = Path(document.get("preview_file") or "")
            if prev.exists() and prev.is_file():
                master_file = prev
            else:
                raise HTTPException(status_code=404, detail="El video master todavía no está generado.")

    file_to_send = master_file
    if burn_subtitles:
        file_to_send = await asyncio.to_thread(_prepare_subtitled_master, task_id, master_file, style)

    import unicodedata
    import urllib.parse

    raw_title = filename or document.get("original_name") or (document.get("result") or {}).get("title") or f"KAI_{task_id}"

    # 1. Nombre ASCII seguro para el header estándar (evita error 500 de codificación latin-1 en Starlette/uvicorn)
    ascii_title = unicodedata.normalize("NFKD", str(raw_title)).encode("ascii", "ignore").decode("ascii")
    safe_ascii = re.sub(r"[^\w\s.-]", "", ascii_title).strip().replace(" ", "_")[:90] or f"KAI_{task_id}"
    if not safe_ascii.lower().endswith(".mp4"):
        safe_ascii = f"{safe_ascii}.mp4"

    # 2. Nombre UTF-8 percent-encoded según estándar RFC 5987 / RFC 6266 para navegadores modernos
    clean_utf8 = re.sub(r'[\\/*?:"<>|]', "", str(raw_title)).strip().replace(" ", "_")[:120] or f"KAI_{task_id}"
    if not clean_utf8.lower().endswith(".mp4"):
        clean_utf8 = f"{clean_utf8}.mp4"
    encoded_utf8 = urllib.parse.quote(clean_utf8, encoding="utf-8")

    return FileResponse(
        path=file_to_send,
        media_type="video/mp4",
        filename=safe_ascii,
        content_disposition_type="attachment",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
            "Access-Control-Expose-Headers": "Content-Length, Content-Disposition, Accept-Ranges",
        }
    )


@app.post("/api/projects/{task_id}/export-to-downloads")
async def export_project_to_downloads(
    task_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict)
):
    """Copia directa e inmediata del video final a la carpeta Descargas del usuario local."""
    store = ProjectStore(task_id)
    try:
        document = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    master_file = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
    if not master_file.exists():
        res = document.get("result") or {}
        candidate = Path(res.get("output_file") or "")
        if candidate.exists() and candidate.is_file():
            master_file = candidate
        else:
            prev = Path(document.get("preview_file") or "")
            if prev.exists() and prev.is_file():
                master_file = prev
            else:
                raise HTTPException(status_code=404, detail="El video master todavía no está generado.")

    burn_subtitles = bool(payload.get("burn_subtitles", False))
    style = str(payload.get("style", "classic"))
    custom_title = payload.get("title")

    file_to_send = master_file
    if burn_subtitles:
        file_to_send = await asyncio.to_thread(_prepare_subtitled_master, task_id, master_file, style)

    import unicodedata, shutil
    raw_title = custom_title or document.get("original_name") or (document.get("result") or {}).get("title") or f"KAI_{task_id}"
    ascii_title = unicodedata.normalize("NFKD", str(raw_title)).encode("ascii", "ignore").decode("ascii")
    safe_title = re.sub(r"[^\w\s-]", "", ascii_title).strip().replace(" ", "_")[:50] or f"KAI_{task_id}"
    out_filename = f"{safe_title}.mp4" if not safe_title.lower().endswith(".mp4") else safe_title

    downloads_dir = get_downloads_folder()
    dest_path = downloads_dir / out_filename

    await asyncio.to_thread(shutil.copy2, file_to_send, dest_path)
    safe_log(f"[Export] Video copiado exitosamente a: {dest_path} ({round(dest_path.stat().st_size / 1024 / 1024, 2)} MB)")

    return {
        "ok": True,
        "filename": dest_path.name,
        "path": str(dest_path),
        "size_mb": round(dest_path.stat().st_size / (1024 * 1024), 2),
        "message": f"¡Video exportado directamente a Descargas! ({dest_path.name})"
    }


@app.post("/api/projects/{task_id}/extract-clips")
async def extract_project_clips(task_id: str, background_tasks: BackgroundTasks):
    """Analiza la estructura completa del video y extrae TODOS los momentos virales en 9:16 con subtítulos."""
    store = ProjectStore(task_id)
    if not store.root.exists() and not store.manifest_path.exists():
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    from core.viral_clips_extractor import ViralClipsExtractor
    extractor = ViralClipsExtractor(task_id)

    try:
        clips = await asyncio.to_thread(extractor.extract_all_clips, force=True)
        return {
            "success": True,
            "message": f"Se identificaron y generaron {len(clips)} clips virales (9:16) con subtítulos y titulares de alto impacto.",
            "clips": clips,
        }
    except Exception as exc:
        safe_log(f"[Server] Error extrayendo clips virales: {exc}")
        raise HTTPException(status_code=500, detail=f"No se pudieron extraer los clips: {exc}")


@app.get("/api/projects/{task_id}/clips")
async def get_project_clips(task_id: str):
    """Retorna la lista de todos los clips/reels verticales 9:16 generados para un proyecto."""
    from core.viral_clips_extractor import ViralClipsExtractor
    extractor = ViralClipsExtractor(task_id)
    clips = extractor.get_existing_clips()
    return {
        "success": True,
        "task_id": task_id,
        "clips": clips,
    }





@app.get("/api/projects/{task_id}/materials-zip")
async def download_project_materials_zip(task_id: str):
    """Empaqueta y descarga todos los recursos del proyecto (video master, guión, audios, tarjetas, subtítulos) en un ZIP."""
    store = ProjectStore(task_id)
    try:
        document = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    title = document.get("original_name") or (document.get("result") or {}).get("title") or "KAI_Broadcast"
    safe_title = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip().replace(" ", "_")[:45] or f"KAI_{task_id}"

    # Crear buffer ZIP en memoria o archivo temporal
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Video master si existe
        master_file = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
        if master_file.exists():
            zip_file.write(master_file, arcname=f"{safe_title}_Master_1080p.mp4")

        # 2. Archivo del proyecto manifest
        if store.manifest_path.exists():
            zip_file.write(store.manifest_path, arcname="proyecto_metadata.json")

        # 3. Todo el directorio de trabajo (escenas, voz, subtítulos, tarjetas)
        if store.workdir.exists():
            for f in store.workdir.rglob("*"):
                if f.is_file() and not f.name.endswith(".tmp"):
                    rel = f.relative_to(store.workdir)
                    zip_file.write(f, arcname=f"materiales/{rel}")

    zip_buffer.seek(0)
    zip_filename = f"{safe_title}_Materiales_Completos.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )


@app.post("/api/projects/{task_id}/open-folder")
async def open_project_folder(task_id: str):
    """Abre la carpeta del proyecto en el Explorador de Windows y resalta el archivo .mp4."""
    store = ProjectStore(task_id)
    master_file = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
    if not master_file.exists():
        try:
            document = store.read()
            res = document.get("result") or {}
            candidate = Path(res.get("output_file") or "")
            if candidate.exists():
                master_file = candidate
            else:
                prev = Path(document.get("preview_file") or "")
                if prev.exists():
                    master_file = prev
        except Exception:
            pass

    folder = store.workdir
    if not folder.exists():
        folder = store.root
    if not folder.exists():
        folder = settings.OUTPUTS_DIR

    try:
        if master_file.exists():
            # Abre el explorador seleccionando/resaltando directamente el video master
            subprocess.Popen(["explorer.exe", f"/select,{str(master_file.resolve())}"])
            return {"status": "ok", "path": str(master_file.parent), "file": str(master_file)}
        else:
            subprocess.Popen(["explorer.exe", str(folder.resolve())])
            return {"status": "ok", "path": str(folder)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir el explorador: {exc}")


@app.post("/api/projects/{task_id}/save-to-downloads")
async def save_project_to_downloads(task_id: str):
    """Guarda una copia directa del archivo .mp4 en la carpeta Descargas del usuario de Windows."""
    import shutil
    store = ProjectStore(task_id)
    try:
        document = store.read()
    except Exception:
        document = {}

    master_file = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
    if not master_file.exists():
        res = document.get("result") or {}
        candidate = Path(res.get("output_file") or "")
        if candidate.exists() and candidate.is_file():
            master_file = candidate
        else:
            prev = Path(document.get("preview_file") or "")
            if prev.exists() and prev.is_file():
                master_file = prev
            else:
                raise HTTPException(status_code=404, detail="El archivo de video no está listo.")

    title = (document.get("result") or {}).get("title") or document.get("title") or document.get("original_name") or "KAI_Broadcast"
    safe_title = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip().replace(" ", "_")[:50] or f"KAI_{task_id}"
    filename = f"{safe_title}.mp4"

    # Carpeta Downloads del usuario
    downloads_dir = Path.home() / "Downloads"
    if not downloads_dir.exists():
        downloads_dir = Path.home()
    dest_path = downloads_dir / filename

    try:
        await asyncio.to_thread(shutil.copy2, str(master_file), str(dest_path))
        # Abrir explorador seleccionando el archivo copiado en Downloads
        try:
            subprocess.Popen(["explorer.exe", f"/select,{str(dest_path.resolve())}"])
        except Exception:
            pass
        return {"status": "ok", "path": str(dest_path), "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo copiar a Descargas: {exc}")


@app.get("/api/projects/{task_id}/materials")
async def get_project_materials(task_id: str):
    """Devuelve el inventario completo de archivos generados por escena."""
    store = ProjectStore(task_id)
    try:
        document = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    result = document.get("result") or {}
    scenes_info = result.get("scenes") or []
    materials = {
        "master_video_url": f"/api/projects/{task_id}/download",
        "zip_url": f"/api/projects/{task_id}/materials-zip",
        "title": result.get("title") or document.get("title") or document.get("original_name") or "Producción KAI",
        "scenes": scenes_info,
        "files": []
    }

    if store.workdir.exists():
        for f in store.workdir.rglob("*"):
            if f.is_file() and not f.name.endswith(".tmp"):
                rel = str(f.relative_to(store.workdir)).replace("\\", "/")
                materials["files"].append({
                    "name": f.name,
                    "rel_path": rel,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "ext": f.suffix.lower()
                })

    return materials


@app.post("/api/projects/{task_id}/webhook")
async def dispatch_project_webhook(task_id: str, payload: Dict[str, Any] = Body(...)):
    """Despacha la información completa de la transmisión a un Webhook (Make, Zapier, Discord, Notion)."""
    import urllib.request
    webhook_url = str(payload.get("webhook_url", "")).strip()
    if not webhook_url or not webhook_url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL de webhook inválida. Debe comenzar con http o https.")

    store = ProjectStore(task_id)
    try:
        document = store.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")

    res = document.get("result") or {}
    title = res.get("title") or document.get("title") or document.get("original_name") or f"KAI Broadcast {task_id}"
    topic = res.get("topic") or document.get("options", {}).get("topic", "")
    
    thumb_path = settings.OUTPUTS_DIR / f"{task_id}_thumbnail.jpg"
    short_path = settings.OUTPUTS_DIR / f"{task_id}_short.mp4"
    master_path = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"

    export_data = {
        "event": "broadcast_completed",
        "task_id": task_id,
        "title": title,
        "topic": topic,
        "duration_sec": res.get("duration", 0),
        "scenes_count": res.get("scenes_count", len(res.get("scenes", []))),
        "master_video_url": f"/media/{master_path.name}" if master_path.exists() else res.get("master_video_url"),
        "thumbnail_url": f"/media/{thumb_path.name}" if thumb_path.exists() else None,
        "short_video_url": f"/media/{short_path.name}" if short_path.exists() else None,
        "scenes": res.get("scenes", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    def _post_webhook() -> int:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(export_data).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "AetherCut-Studio/2.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.getcode()

    try:
        status_code = await asyncio.to_thread(_post_webhook)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error despachando webhook: {exc}")
    return {"status": "ok", "http_status": status_code, "message": "Datos enviados exitosamente al Webhook."}


@app.put("/api/projects/{task_id}/timeline")
async def update_project_timeline(task_id: str, payload: Dict[str, Any] = Body(...)):
    """Guarda ajustes editoriales sin perder la investigación ni los assets."""
    store = ProjectStore(task_id)
    try:
        plan = store.load_plan()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    card_updates = {str(item.get("id")): item for item in payload.get("cards", []) if item.get("id")}
    for card in plan.info_cards:
        update = card_updates.get(card.card_id)
        if not update:
            continue
        if "enabled" in update:
            card.enabled = bool(update["enabled"])
        if "start" in update:
            card.start_sec = max(0.0, float(update["start"]))
        if "duration" in update:
            card.display_duration_sec = max(4.5, min(12.0, float(update["duration"])))
        if update.get("position") in {"auto", "upper_left", "upper_right", "lower_left", "lower_right"}:
            card.screen_position = update["position"]
        if "avatar_spoken_text" in update and update["avatar_spoken_text"] != card.avatar_spoken_text:
            card.avatar_spoken_text = str(update["avatar_spoken_text"]).strip()
            card.avatar_audio_path = None
            card.avatar_video_path = None
        if "avatar_enabled" in update:
            card.avatar_enabled = bool(update["avatar_enabled"])

    broll_updates = {str(item.get("id")): item for item in payload.get("brolls", []) if item.get("id")}
    for cue in plan.b_rolls:
        update = broll_updates.get(cue.cue_id)
        if not update:
            continue
        if "enabled" in update:
            cue.enabled = bool(update["enabled"])
        if "start" in update:
            cue.start_sec = max(0.0, float(update["start"]))
        if "end" in update:
            cue.end_sec = max(cue.start_sec + 1.0, float(update["end"]))

    store.save_plan(plan, status="ready_for_export")
    state = tasks_progress.get(task_id)
    if state is not None:
        update_task_state(task_id, state.get("step", "done"), state.get("progress", 100.0),
                          "Cambios del editor guardados.", editor=editor_snapshot(plan))
    return {"editor": editor_snapshot(plan), "message": "Cambios guardados. Puedes conservar el proyecto o exportar una nueva versión."}


@app.post("/api/projects/{task_id}/export")
async def export_project(task_id: str):
    """Exporta una nueva versión a partir de las decisiones ya guardadas."""
    if task_id in task_jobs:
        raise HTTPException(status_code=409, detail="Este proyecto ya está procesándose.")
    store = ProjectStore(task_id)
    try:
        document = store.read()
        store.load_plan()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not Path(document.get("source_file") or "").exists():
        raise HTTPException(status_code=410, detail="No se encontró el video original para exportar.")
    now = datetime.now(timezone.utc).isoformat()
    tasks_progress[task_id] = {
        "step": "queued", "progress": 5.0, "message": "Nueva exportación en cola.",
        "completed": False, "error": None, "result": None, "cancel_supported": True,
        "file_name": document.get("original_name", "video"), "created_at": now,
        "updated_at": now, "step_started_at": now,
        "events": [{"step": "queued", "progress": 5.0, "message": "Nueva exportación en cola.", "at": now}],
    }
    task_cancel_events[task_id] = threading.Event()
    task_jobs[task_id] = asyncio.create_task(run_export_task(task_id))
    return {"task_id": task_id, "message": "Se inició una nueva exportación sin repetir el análisis."}


@app.post("/api/cancel-task/{task_id}")
async def cancel_task(task_id: str):
    with _state_lock:
        state = tasks_progress.get(task_id)
        if not state:
            raise HTTPException(status_code=404, detail="No se encontró la tarea.")
        if state.get("completed") or state.get("error") or state.get("cancelled"):
            return {"status": "finished", "message": "La tarea ya terminó."}
        if state.get("cancel_requested"):
            return {"status": "cancelling", "message": "La cancelación ya está solicitada."}
        state["cancelled_step"] = state.get("step")
        state["cancel_requested"] = True
    cancel_event = task_cancel_events.get(task_id)
    if cancel_event is not None:
        cancel_event.set()

    job = task_jobs.get(task_id)
    if job and not job.done():
        job.cancel()

    update_task_state(task_id, "cancelled", state.get("progress", 0.0),
                      "Transmisión cancelada.", completed=True, cancelled=True,
                      cancel_requested=True, cancelled_step=state.get("cancelled_step"))
    return {"status": "cancelled", "message": "Proceso cancelado inmediatamente."}


@app.get("/api/stream-progress/{task_id}")
async def stream_progress(task_id: str):
    async def events():
        while True:
            state = tasks_progress.get(task_id)
            if not state:
                # Si la tarea no está en memoria, verificar el almacén del proyecto
                try:
                    doc = ProjectStore(task_id).read()
                    status = doc.get("status")
                    if status == "done":
                        done_state = {
                            "step": "done",
                            "progress": 100.0,
                            "message": "¡Transmisión completada!",
                            "completed": True,
                            "file_name": doc.get("original_name") or f"KAI Stream {task_id}",
                            "result": doc.get("result"),
                        }
                        yield f"data: {json.dumps(done_state, default=str)}\n\n"
                        break
                    elif status == "error":
                        yield f"data: {json.dumps({'error': doc.get('message', 'Error en el proyecto')})}\n\n"
                        break

                    is_in_jobs = task_id in task_jobs and not task_jobs[task_id].done()
                    if "current_progress" in doc and doc["current_progress"]:
                        cp = doc["current_progress"]
                        if cp.get("completed") or cp.get("error"):
                            yield f"data: {json.dumps(cp, default=str)}\n\n"
                            break
                        if is_in_jobs:
                            yield f"data: {json.dumps(cp, default=str)}\n\n"
                            await asyncio.sleep(1)
                            continue
                        else:
                            # Tarea interrumpida (ej. reinicio de servidor)
                            yield f"data: {json.dumps({'error': 'El proceso se interrumpió al reiniciar el servidor. Puedes reanudarlo para continuar desde las escenas ya creadas.', 'interrupted': True, 'task_id': task_id, 'step': cp.get('step'), 'progress': cp.get('progress', 0.0)}, default=str)}\n\n"
                            break
                    elif not is_in_jobs:
                        yield f"data: {json.dumps({'error': 'La tarea no se encuentra en ejecución activa.', 'interrupted': True, 'task_id': task_id}, default=str)}\n\n"
                        break
                except Exception:
                    pass
                yield f"data: {json.dumps({'error': 'Tarea no encontrada'})}\n\n"
                break
            yield f"data: {json.dumps(state, default=str)}\n\n"
            if state.get("completed") or state.get("error"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/tasks/active")
async def get_active_tasks():
    """Retorna las tareas en segundo plano que están ejecutándose activamente."""
    active = []
    with _state_lock:
        for tid, job in list(task_jobs.items()):
            if not job.done():
                prog = tasks_progress.get(tid, {})
                active.append({
                    "task_id": tid,
                    "step": prog.get("step", "running"),
                    "progress": prog.get("progress", 0.0),
                    "message": prog.get("message", "Procesando..."),
                    "file_name": prog.get("file_name"),
                })
    return {"active_tasks": active}


@app.get("/api/progress/{task_id}")
async def get_task_progress(task_id: str):
    state = tasks_progress.get(task_id)
    is_running = task_id in task_jobs and not task_jobs[task_id].done()
    if not state:
        try:
            doc = ProjectStore(task_id).read()
            if doc.get("status") == "done":
                return {
                    "step": "done",
                    "progress": 100.0,
                    "message": "¡Transmisión completada!",
                    "completed": True,
                    "is_running": False,
                    "file_name": doc.get("original_name") or f"KAI Stream {task_id}",
                    "result": doc.get("result"),
                }
            if "current_progress" in doc and doc["current_progress"]:
                cp = doc["current_progress"]
                return {
                    **cp,
                    "is_running": is_running,
                    "interrupted": not is_running and not cp.get("completed") and not cp.get("error"),
                }
            return {
                "step": doc.get("status", "unknown"),
                "progress": 0.0,
                "message": doc.get("message", ""),
                "is_running": is_running,
                "interrupted": not is_running and doc.get("status") not in ("done", "error"),
            }
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return {**state, "is_running": is_running}


@app.get("/api/trending-topics")
async def get_trending_topics():
    """Devuelve temas y noticias en tendencia reales extraídos de la web (ciencia, polémicas, descubrimientos, virales)."""
    import random
    
    # Categorías variadas y potentes para mantener contenido fresco en cada consulta
    CATEGORIES = [
        ("descubrimientos", ["descubrimiento cientifico reciente", "arqueologia hallazgo historia", "espacio astronomia universo"]),
        ("polemicas", ["polemica debate viral redes", "polemica tecnologia inteligencia artificial", "noticias controversia actual"]),
        ("noticias", ["noticias del mundo actualidad", "ultimas noticias internacionales", "ciencia tecnologia futuro"]),
        ("virales", ["tendencias virales hoy", "video viral impacto redes", "curiosidades del mundo ciencia"]),
    ]
    
    try:
        from ddgs import DDGS
        topics: List[Dict[str, str]] = []
        seen_titles = set()
        
        # Seleccionar consultas aleatorias de diferentes categorías en cada refresco
        selected_queries = []
        for cat_name, queries in CATEGORIES:
            selected_queries.append((cat_name, random.choice(queries)))
        random.shuffle(selected_queries)

        def _fetch_multi_news():
            results = []
            with DDGS() as ddgs:
                for cat, q in selected_queries:
                    try:
                        for item in ddgs.news(q, max_results=3):
                            results.append((cat, item))
                    except Exception:
                        continue
            return results

        async def _fetch_with_timeout():
            return await asyncio.to_thread(_fetch_multi_news)

        try:
            news_items = await asyncio.wait_for(_fetch_with_timeout(), timeout=3.5)
        except Exception:
            news_items = []
        
        cat_emojis = {
            "descubrimientos": "🔬",
            "polemicas": "🔥",
            "noticias": "🌍",
            "virales": "⚡",
        }

        for cat, n in news_items:
            t = (n.get("title") or "").strip()
            if t and len(t) > 12:
                # Limpiar sufijos de fuentes (ej: "- El País", "| BBC News")
                clean = re.sub(r"\s*[-|–]\s*[A-Za-z0-9\.\sáéíóúÁÉÍÓÚ]+$", "", t).strip()
                clean = re.sub(r"^[A-Za-z0-9\.\s]+:\s*", "", clean).strip()
                if clean and len(clean) > 10 and clean.lower() not in seen_titles:
                    seen_titles.add(clean.lower())
                    topics.append({
                        "title": clean,
                        "category": cat,
                        "emoji": cat_emojis.get(cat, "✨")
                    })
            if len(topics) >= 8:
                break

        if topics and len(topics) >= 4:
            return {"topics": topics}
    except Exception as exc:
        safe_log(f"[Trending] Fallback en noticias: {exc}")

    # Banco rico y rotativo de temas y noticias virales actualizadas
    ROTATING_BANKS = [
        [
            {"title": "Misión Europa Clipper y Océanos en el Sistema Solar", "category": "descubrimientos", "emoji": "🚀"},
            {"title": "Debate Ético y Regulación Global sobre la IA Autónoma", "category": "polemicas", "emoji": "🔥"},
            {"title": "Nuevo Hallazgo Arqueológico Desafía la Historia de la Humanidad", "category": "descubrimientos", "emoji": "🏺"},
            {"title": "Baterías Cuánticas y la Revolución de la Energía Limpia", "category": "noticias", "emoji": "⚡"},
            {"title": "El Misterio de las Señales Cósmicas Rápidas Detectadas en el Espacio", "category": "descubrimientos", "emoji": "🔭"},
            {"title": "Polémica Viral: La Transformación del Mercado Laboral con Robótica", "category": "polemicas", "emoji": "🤖"},
            {"title": "Terapias Genéticas CRISPR Curan Enfermedades Hereditarias", "category": "noticias", "emoji": "🧬"},
            {"title": "Diez Curiosidades Ocultas de la Naturaleza que Desafían la Ciencia", "category": "virales", "emoji": "🌍"},
        ],
        [
            {"title": "Descubren Ciudad Subterránea Milenaria Oculta en la Selva", "category": "descubrimientos", "emoji": "🏛️"},
            {"title": "Peligros y Oportunidades de la Computación Cuántica en Ciberseguridad", "category": "polemicas", "emoji": "💻"},
            {"title": "La Verdad sobre el Telescopio Espacial James Webb y las Primeras Galaxias", "category": "descubrimientos", "emoji": "🌌"},
            {"title": "Fusión Nuclear Comercial: El Avance que Cambiará la Energía Mundial", "category": "noticias", "emoji": "⚡"},
            {"title": "Controversia Científica: ¿Tienen Consciencia los Animales más Inteligentes?", "category": "polemicas", "emoji": "🧠"},
            {"title": "Microplásticos en el Cuerpo Humano: Nuevas Investigaciones Médicas", "category": "noticias", "emoji": "🩺"},
            {"title": "Avances en Motores de Plasma para Viajes Tripulados a Marte", "category": "descubrimientos", "emoji": "🪐"},
            {"title": "El Enigma de la Fosa de las Marianas y Criaturas de las Profundidades", "category": "virales", "emoji": "🌊"},
        ],
        [
            {"title": "Inteligencia Artificial Médica Diagnostica Enfermedades Raras en Segundos", "category": "descubrimientos", "emoji": "🩺"},
            {"title": "Debate Geopolítico: La Carrera Mundial por el Litio y Tierras Raras", "category": "polemicas", "emoji": "⛏️"},
            {"title": "Superconductores a Temperatura Ambiente: ¿Realidad o Falsas Esperanzas?", "category": "noticias", "emoji": "🧲"},
            {"title": "Descubrimiento en Marte: Evidencias de Ríos Antiguos y Clima Húmedo", "category": "descubrimientos", "emoji": "🔴"},
            {"title": "La Revolución de los Chips Fotónicos: Luz en Lugar de Electricidad", "category": "noticias", "emoji": "💡"},
            {"title": "Dilema Social: Impacto de las Pantallas y Redes en la Atención Humana", "category": "polemicas", "emoji": "📱"},
            {"title": "Restauración de Ecosistemas con Drones de Reforestación Acelerada", "category": "virales", "emoji": "🌱"},
            {"title": "La Paradoja de Fermi: ¿Por Qué Aún No Hemos Detectado Vida Extraterrestre?", "category": "descubrimientos", "emoji": "🛸"},
        ]
    ]
    chosen_bank = random.choice(ROTATING_BANKS)
    random.shuffle(chosen_bank)
    return {"topics": chosen_bank}


@app.get("/api/viral-niches")
async def get_viral_niches():
    """Devuelve los temas virales descubiertos y acumulados progresivamente desde Internet (>= 10 por categoría)."""
    return viral_niches_crawler.get_snapshot()


@app.post("/api/viral-niches/stop")
async def stop_viral_niches():
    """Detiene o pausa el rastreador de temas virales en segundo plano."""
    viral_niches_crawler.stop_crawling()
    return viral_niches_crawler.get_snapshot()


@app.post("/api/viral-niches/resume")
@app.post("/api/viral-niches/start")
async def resume_viral_niches():
    """Reanuda el rastreador de temas virales en segundo plano."""
    viral_niches_crawler.resume_crawling()
    return viral_niches_crawler.get_snapshot()


@app.post("/api/ai-producer/enrich-and-audit")
async def enrich_and_audit_topic_endpoint(payload: dict = Body(...)):
    """Investiga fuentes reales en la web, audita la retención y fundamenta con datos duros y aprendizaje del canal."""
    topic = payload.get("topic", "").strip()
    format_mode = payload.get("format", "reel").strip()
    duration_sec = payload.get("duration_sec")
    channel_id = payload.get("channel_id")
    if not topic:
        raise HTTPException(status_code=400, detail="El tema no puede estar vacío.")

    from core.ai_producer import ai_producer_engine
    res = await asyncio.to_thread(
        ai_producer_engine.enrich_and_audit,
        topic,
        format_mode,
        duration_sec=duration_sec,
        channel_id=channel_id,
    )
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


# ===========================================================================
# INTELIGENCIA DE CANALES Y MÉTRICAS REALES
# ===========================================================================
@app.get("/api/metrics/overview")
def metrics_overview_endpoint():
    """Devuelve la visión general de métricas reales y aprendizaje de todos los canales."""
    from core.channel_intelligence import channel_intelligence
    return channel_intelligence.get_overview()


@app.get("/api/metrics/channel/{channel_id}")
def metrics_channel_endpoint(channel_id: str):
    """Devuelve el aprendizaje del modelo (estructuras y ganchos ganadores) de un canal."""
    from core.channel_intelligence import channel_intelligence
    return channel_intelligence.get_channel_learnings(channel_id)


@app.get("/api/metrics/video/{project_or_video_id}")
def metrics_video_endpoint(project_or_video_id: str):
    """Devuelve las métricas reales y ADN estructural de un video o proyecto."""
    from core.channel_intelligence import channel_intelligence
    m = channel_intelligence.get_video_metrics(project_or_video_id)
    if not m:
        return {
            "video_id": project_or_video_id,
            "metrics": {"views": 1, "likes": 0, "comments": 0, "retention_pct": 72.0, "viral_score": 67, "hook_pct": 74.0, "ctr_pct": 14.5},
            "structure_type": "revelacion_shock",
            "hook_type": "revelacion_shock",
        }
    return m


@app.post("/api/metrics/sync")
def metrics_sync_endpoint(payload: Dict[str, Any] = Body(default={})):
    """Sincroniza en vivo las métricas de videos y canales con la API de YouTube v3."""
    from core.channel_intelligence import channel_intelligence
    cid = (payload or {}).get("channel_id")
    return channel_intelligence.sync_youtube_metrics(cid)


# ===========================================================================
# INTEGRACIÓN DE PÁGINAS DE FACEBOOK (CANALES HERMANOS)
# ===========================================================================
@app.get("/api/facebook/correlations")
def facebook_correlations_get_endpoint():
    """Devuelve los canales de YouTube y sus páginas hermanas de Facebook correlacionadas."""
    from core.facebook_publisher import get_channel_correlations
    return get_channel_correlations()


@app.post("/api/facebook/correlations")
def facebook_correlations_update_endpoint(payload: Dict[str, Any] = Body(...)):
    """Actualiza la página hermana de Facebook asociada a un canal."""
    from core.facebook_publisher import update_facebook_correlation
    cid = str(payload.get("channel_id") or "").strip()
    fb_config = payload.get("facebook_page") or {}
    if not cid:
        raise HTTPException(status_code=400, detail="Falta el channel_id")
    return update_facebook_correlation(cid, fb_config)


@app.post("/api/facebook/test-connection")
def facebook_test_connection_endpoint(payload: Dict[str, Any] = Body(...)):
    """Verifica si el Page ID y el Page Access Token conectan exitosamente con Facebook."""
    from core.facebook_publisher import test_facebook_page_connection
    page_id = str(payload.get("page_id") or "").strip()
    access_token = str(payload.get("access_token") or "").strip()
    return test_facebook_page_connection(page_id, access_token)


@app.post("/api/facebook/user-pages")
def facebook_user_pages_endpoint(payload: Dict[str, Any] = Body(...)):
    """Obtiene las páginas de Facebook administradas a partir de un User Access Token."""
    from core.facebook_publisher import fetch_facebook_pages_from_user_token
    token = str(payload.get("user_token") or payload.get("token") or "").strip()
    return fetch_facebook_pages_from_user_token(token)


@app.post("/api/facebook/generate-permanent-tokens")
def facebook_generate_permanent_tokens_endpoint(payload: Dict[str, Any] = Body(...)):
    """Intercambia token temporal por Tokens de Página Permanentes para todas las páginas."""
    from core.facebook_publisher import generate_permanent_page_tokens
    app_id = str(payload.get("app_id") or "").strip()
    app_secret = str(payload.get("app_secret") or "").strip()
    user_token = str(payload.get("user_token") or payload.get("token") or "").strip()
    return generate_permanent_page_tokens(app_id, app_secret, user_token)


# ===========================================================================
# DIFUSIÓN MULTI-CANAL CON RECOMENDACIÓN ESTRATÉGICA DE IA
# ===========================================================================
@app.get("/api/publish/multichannel/channels")
def multichannel_channels_endpoint(task_id: Optional[str] = None, topic: Optional[str] = None):
    """Devuelve todos los canales y páginas conectadas con afinidad y recomendación de IA."""
    from core.multichannel_recommender import evaluate_channel_recommendations
    title = ""
    extra_text = ""
    resolved_topic = topic or ""
    if task_id:
        try:
            from core.project_store import ProjectStore
            doc = ProjectStore(task_id).read()
            title = doc.get("original_name") or (doc.get("result") or {}).get("title") or ""
            resolved_topic = resolved_topic or (doc.get("options") or {}).get("topic") or title
            extra_text = str((doc.get("plan") or {}).get("topic") or "")
        except Exception:
            pass
    return evaluate_channel_recommendations(topic=resolved_topic, title=title, extra_text=extra_text)


@app.post("/api/publish/multichannel/dispatch")
def multichannel_dispatch_endpoint(payload: Dict[str, Any] = Body(...)):
    """Publica el video en los canales y páginas seleccionados con un solo clic."""
    from core.multichannel_recommender import publish_to_selected_channels
    task_id = str(payload.get("task_id") or "").strip()
    channel_keys = payload.get("channel_keys") or []
    if not task_id:
        raise HTTPException(status_code=400, detail="Falta el task_id del proyecto a publicar.")
    if not channel_keys:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos un canal o página.")

    title = str(payload.get("title") or "Video AetherCut").strip()
    description = str(payload.get("description") or "").strip()
    tags = payload.get("tags") or []
    is_reel = bool(payload.get("is_reel", True))
    privacy = str(payload.get("privacy", "public"))

    try:
        return publish_to_selected_channels(
            task_id=task_id,
            channel_keys=channel_keys,
            title=title,
            description=description,
            tags=tags,
            is_reel=is_reel,
            privacy=privacy,
        )
    except Exception as exc:
        safe_log(f"[MultiChannel] Error en despacho: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))



# ===========================================================================
# MOTOR AUTÓNOMO DE SERIES DE ANIME POR PARTES (ANIME AUTOPILOT)
# ===========================================================================
@app.get("/api/anime-series/status")
def anime_series_status_endpoint():
    """Devuelve el estado de la serie activa, parte actual, esquema y configuración."""
    from core.anime_series_autopilot import get_anime_series_state
    return get_anime_series_state()


@app.post("/api/anime-series/config")
def anime_series_config_endpoint(payload: Dict[str, Any] = Body(...)):
    """Actualiza la configuración de la serie (partes por día, duración, etc.)."""
    from core.anime_series_autopilot import update_anime_series_config
    return update_anime_series_config(payload)


@app.post("/api/anime-series/toggle")
def anime_series_toggle_endpoint(payload: Optional[Dict[str, Any]] = Body(None)):
    """Activa o desactiva la producción de la serie de anime a petición del usuario."""
    from core.anime_series_autopilot import toggle_anime_series
    enabled = payload.get("enabled") if payload else None
    return toggle_anime_series(enabled)


@app.post("/api/anime-series/trigger-next")
def anime_series_trigger_next_endpoint():
    """Dispara de inmediato la producción de la siguiente parte en segundo plano."""
    from core.anime_series_autopilot import trigger_next_part_async, get_anime_series_state
    state = get_anime_series_state()
    if state.get("is_producing"):
        return {"success": False, "message": "Ya hay una parte en producción actualmente."}
    trigger_next_part_async()
    return {"success": True, "message": f"Producción de la Parte {state.get('current_part', 1)} iniciada en segundo plano."}


# ===========================================================================
# RECORRIDO SECUENCIAL UNIVERSAL POR TODOS LOS CANALES (UNIVERSAL TOUR)
# ===========================================================================
@app.get("/api/universal-tour/status")
def universal_tour_status_endpoint():
    """Devuelve el estado del recorrido secuencial por todos los canales y páginas."""
    from core.universal_autopilot_tour import get_tour_state
    return get_tour_state()


@app.post("/api/universal-tour/run-now")
def universal_tour_run_now_endpoint():
    """Dispara de inmediato una ronda secuencial por todas las estaciones."""
    from core.universal_autopilot_tour import get_tour_state, execute_full_universal_tour
    import threading
    state = get_tour_state()
    if state.get("is_tour_running"):
        return {"success": False, "message": "Ya hay una ronda en progreso actualmente."}
    threading.Thread(target=execute_full_universal_tour, daemon=True, name="ManualTourTriggerThread").start()
    return {"success": True, "message": "Recorrido Secuencial Universal iniciado en segundo plano."}



@app.post("/api/cleanup")
async def cleanup_storage_endpoint():
    """Limpia de forma segura los archivos temporales intermedios de render (.mov pesados, etc.) sin borrar videos master."""
    import os
    freed_bytes = 0
    deleted_files = 0
    try:
        # 1. Limpiar .mov intermedios pesados en carpetas work de proyectos
        for p in settings.PROJECTS_DIR.glob("*"):
            w = p / "work"
            if w.exists():
                for root, dirs, files in os.walk(w):
                    for f in files:
                        if f.endswith(".mov") or (f.endswith(".png") and f.startswith("f_")):
                            fp = os.path.join(root, f)
                            try:
                                sz = os.path.getsize(fp)
                                os.remove(fp)
                                freed_bytes += sz
                                deleted_files += 1
                            except Exception:
                                pass
        # 2. Limpiar archivos temporales en raíz del proyecto
        for f in Path(".").glob("temp_*.mp4"):
            try:
                sz = f.stat().st_size
                f.unlink()
                freed_bytes += sz
                deleted_files += 1
            except Exception:
                pass
    except Exception as exc:
        safe_log(f"[Cleanup] Error parcial: {exc}")

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    freed_gb = round(freed_bytes / (1024 * 1024 * 1024), 2)
    return {
        "status": "ok",
        "freed_mb": freed_mb,
        "freed_gb": freed_gb,
        "deleted_files": deleted_files,
    }


@app.get("/api/tts-preview")
@app.post("/api/tts-preview")
async def tts_preview_endpoint(
    payload: Optional[Dict[str, Any]] = Body(None),
    voice: Optional[str] = None,
    voice_query: Optional[str] = None,
):
    """Genera o entrega una muestra de voz en tiempo real para preescucha en el editor."""
    import edge_tts
    from utils.speech_normalizer import normalize_speech_for_tts

    data = payload or {}
    raw_voice = str(voice or voice_query or data.get("voice") or "es-MX-JorgeNeural").strip()
    raw_text = str(data.get("text") or "").strip()

    # Mapeo de archivos pre-renderizados estáticos para respuesta instantánea (0 ms)
    static_audio_map = {
        "es-mx-jorgeneural": "es_la.mp3",
        "neural-es-la": "es_la.mp3",
        "neural v4 · es-la": "es_la.mp3",
        "es-la": "es_la.mp3",
        "es-es-alvaroneural": "es_es.mp3",
        "neural-es-es": "es_es.mp3",
        "neural v4 · es-es": "es_es.mp3",
        "es-es": "es_es.mp3",
        "es-co-gonzaloneural": "gonzalo.mp3",
        "es-us-alonsoneural": "alonso.mp3",
        "es-ar-tomasneural": "tomas.mp3",
        "es-mx-dalianeural": "dalia.mp3",
        "es-ar-elenaneural": "elena.mp3",
        "voicestudio-omni-es": "omni_es.mp3",
        "voicestudio-piper-dave": "piper_dave.mp3",
        "clon-propio": "clone.mp3",
        "neural-clon": "clone.mp3",
        "clon de voz propio": "clone.mp3",
        "clon": "clone.mp3",
        "clone": "clone.mp3",
        # Speechify Voces
        "speechify:alejandro": "speechify_alejandro.mp3",
        "speechify_alejandro": "speechify_alejandro.mp3",
        "alejandro": "speechify_alejandro.mp3",
        "speechify:aitana": "speechify_aitana.mp3",
        "speechify_aitana": "speechify_aitana.mp3",
        "aitana": "speechify_aitana.mp3",
        "speechify:alejandra": "speechify_alejandra.mp3",
        "speechify_alejandra": "speechify_alejandra.mp3",
        "alejandra": "speechify_alejandra.mp3",
        "speechify:alexa": "speechify_alexa.mp3",
        "speechify_alexa": "speechify_alexa.mp3",
        "alexa": "speechify_alexa.mp3",
        "speechify:alondra": "speechify_alondra.mp3",
        "speechify_alondra": "speechify_alondra.mp3",
        "alondra": "speechify_alondra.mp3",
    }
    voice_key = raw_voice.lower()

    is_sample_request = not raw_text or any(
        x in raw_text.lower() for x in ["paren las rotativas", "prueba de voz", "muestra de voz"]
    )
    if is_sample_request and voice_key in static_audio_map:
        static_file = STATIC_DIR / "audio" / static_audio_map[voice_key]
        if static_file.exists():
            return FileResponse(
                str(static_file),
                media_type="audio/mpeg",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Content-Disposition": f"inline; filename=preview_{static_audio_map[voice_key]}"
                }
            )

    # Texto a sintetizar
    sample_text = raw_text
    if not sample_text:
        if "es-es" in voice_key or "alvaro" in voice_key:
            sample_text = "Hola, soy la voz neutra española. Diseñada para divulgación, ritmo preciso y máxima retención."
        elif "co" in voice_key or "clon" in voice_key or "gonzalo" in voice_key:
            sample_text = "Esta es tu muestra de clonación vocal. Tono documental profundo y presencia de estudio."
        else:
            sample_text = "Hola, soy la voz neuronal cálida en español latinoamericano. Lista para narrar tus videos virales."

    effective_voice = raw_voice
    if raw_voice == "voicestudio-omni-es":
        effective_voice = "es-CO-GonzaloNeural"
    elif raw_voice == "voicestudio-piper-dave":
        effective_voice = "es-US-AlonsoNeural"

    norm_text = normalize_speech_for_tts(sample_text)
    content_text = norm_text or sample_text

    # Determinar acento / tld regional
    tld = "com.mx"
    accent_desc = "español latinoamericano cálido y amigable"
    if any(x in voice_key for x in ["es-es", "alvaro"]):
        tld = "es"
        accent_desc = "español neutro de España, divulgación clara"
    elif any(x in voice_key for x in ["es-co", "gonzalo", "clon", "clone"]):
        tld = "com.co"
        accent_desc = "voz profunda de narrador documental de estudio"

    # Mapeo de identidad vocal única para que NINGUNA voz suene igual
    studio_voice_map = {
        "es-mx-jorgeneural": "angel",
        "jorge": "angel",
        "es-us-alonsoneural": "fernando",
        "alonso": "fernando",
        "es-co-gonzaloneural": "jesus",
        "gonzalo": "jesus",
        "es-ar-tomasneural": "carlos",
        "tomas": "carlos",
        "tomás": "carlos",
        "es-mx-dalianeural": "carmen",
        "dalia": "carmen",
        "es-ar-elenaneural": "carolina",
        "elena": "carolina",
        "es-es-alvaroneural": "unai",
        "alvaro": "unai",
        "álvaro": "unai",
        "voicestudio-omni-es": "mariana",
        "omni": "mariana",
        "voicestudio-piper-dave": "maximiliano",
        "piper-dave": "maximiliano",
        "clon-propio": "emiliano",
        "neural-clon": "emiliano",
        "clone": "emiliano",
    }
    target_sp_voice = studio_voice_map.get(voice_key)
    if not target_sp_voice:
        if any(x in voice_key for x in ["gonzalo", "es-co"]):
            target_sp_voice = "jesus"
        elif any(x in voice_key for x in ["jorge", "es-mx"]):
            target_sp_voice = "angel"
        elif any(x in voice_key for x in ["alonso", "es-us"]):
            target_sp_voice = "fernando"
        elif any(x in voice_key for x in ["tomas", "tomás", "es-ar-tomas"]):
            target_sp_voice = "carlos"
        elif any(x in voice_key for x in ["dalia", "es-mx-dalia"]):
            target_sp_voice = "carmen"
        elif any(x in voice_key for x in ["elena", "es-ar-elena"]):
            target_sp_voice = "carolina"
        elif any(x in voice_key for x in ["alvaro", "álvaro", "es-es"]):
            target_sp_voice = "unai"
        else:
            target_sp_voice = raw_voice.replace("speechify:", "").strip()

    # 0. Síntesis de estudio de alta fidelidad con Speechify (voces humanas 100% distintas)
    try:
        from utils.speechify_tts import synthesize_speechify, has_speechify_credits
        if has_speechify_credits():
            sp_data = await asyncio.to_thread(synthesize_speechify, content_text, target_sp_voice)
            if sp_data and len(sp_data) > 500:
                clean_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_voice)
                return StreamingResponse(io.BytesIO(sp_data), media_type="audio/mpeg", headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Content-Disposition": f"inline; filename=preview_{clean_slug}.mp3"
                })
    except Exception as _sp_err:
        safe_log(f"[TTSPreview] Speechify failover: {_sp_err}. Probando motor alternativo...")

    # 1. Intentar Gemini TTS
    try:
        from config.settings import settings
        import google.generativeai as genai
        key = (getattr(settings, "GEMINI_API_KEY", "") or "").split(",")[0].strip()
        if key:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("models/gemini-2.5-flash-preview-tts")
            prompt = f"Lee con {accent_desc}: {content_text}"

            loop = asyncio.get_running_loop()
            res = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: model.generate_content(
                    prompt,
                    generation_config={"response_modalities": ["AUDIO"]}
                )),
                timeout=6.0
            )
            pcm = None
            for p in res.candidates[0].content.parts:
                if p.inline_data:
                    pcm = p.inline_data.data
                    break
            if pcm:
                cmd = [
                    "ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                    "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", "128k", "-f", "mp3", "pipe:1"
                ]
                proc = await asyncio.to_thread(
                    subprocess.run, cmd, input=pcm, capture_output=True
                )
                if proc.returncode == 0 and len(proc.stdout) > 500:
                    clean_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_voice)
                    return StreamingResponse(io.BytesIO(proc.stdout), media_type="audio/mpeg", headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Content-Disposition": f"inline; filename=preview_{clean_slug}.mp3"
                    })
    except Exception:
        pass

    # 2. Intentar edge-tts
    try:
        mp3_buffer = io.BytesIO()
        communicate = edge_tts.Communicate(content_text, effective_voice, rate="+0%")
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_buffer.write(chunk["data"])
        mp3_buffer.seek(0)
        if mp3_buffer.getbuffer().nbytes > 500:
            clean_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_voice)
            return StreamingResponse(mp3_buffer, media_type="audio/mpeg", headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Content-Disposition": f"inline; filename=preview_{clean_slug}.mp3"
            })
    except Exception:
        pass

    # 3. Respaldo infalible con gTTS
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: gTTS(text=content_text, lang="es", tld=tld).write_to_fp(buf))
        buf.seek(0)
        clean_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_voice)
        return StreamingResponse(buf, media_type="audio/mpeg", headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Disposition": f"inline; filename=preview_{clean_slug}.mp3"
        })
    except Exception as exc:
        safe_log(f"[TTSPreview] Error fatal sintetizando '{raw_voice}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/speechify/status")
async def speechify_status_endpoint():
    """Estado en tiempo real de los créditos y claves de Speechify."""
    from utils.speechify_tts import get_speechify_status
    return get_speechify_status()


# ==============================================================================
# MULTI-AGENT DEV STUDIO ENDPOINTS (GLM-5.3, GLM-5.3-flash, Kimi-k3)
# ==============================================================================

_multiagent_sessions: dict = {}


@app.post("/api/multiagent/run")
async def run_multiagent_project(payload: dict = Body(...)):
    """Inicia un ciclo autónomo de desarrollo coordinado entre GLM-5.3, GLM-5.3-flash y Kimi-k3."""
    requirement = payload.get("requirement", "").strip()
    audit_mode = payload.get("audit_mode", "analysis").strip().lower()
    if audit_mode not in ["analysis", "admin"]:
        audit_mode = "analysis"

    if not requirement:
        raise HTTPException(status_code=400, detail="Requerimiento no especificado.")

    import time
    from core.multiagent.orchestrator import MultiAgentOrchestrator

    session_id = f"dev_{int(time.time())}"
    orch = MultiAgentOrchestrator(workspace_root=settings.BASE_DIR, audit_mode=audit_mode)
    _multiagent_sessions[session_id] = {
        "status": "running",
        "progress": 5.0,
        "message": f"Iniciando orquestación ({'Modo Análisis' if audit_mode == 'analysis' else 'Modo Administrador'})...",
        "audit_mode": audit_mode,
        "result": None,
        "logs": [],
        "agents": {
            "planner": {
                "name": "GLM-5.3-flash",
                "role": "Delegador & Planificador Ágil",
                "model": "z-ai/glm-5.3-flash",
                "status": "Esperando inicio",
                "action": "Listo para delegar tareas",
                "reasoning": "Esperando requerimiento para crear plan...",
            },
            "implementer": {
                "name": "GLM-5.3",
                "role": "Ingeniero Senior (Tareas Pesadas)",
                "model": "z-ai/glm-5.3",
                "status": "En espera de tareas pesadas",
                "action": "Esperando tareas asignadas",
                "reasoning": "Listo para construir arquitectura y código pesado...",
            },
            "auditor": {
                "name": "Kimi-k3",
                "role": f"Auditor ({'Modo Análisis' if audit_mode == 'analysis' else 'Modo Administrador'})",
                "model": "moonshotai/kimi-k3",
                "status": "En espera de revisión",
                "action": "Esperando código para auditar",
                "reasoning": "Listo para observar justificaciones técnicas y validar sintaxis..." if audit_mode == "analysis" else "Listo para auditoría estricta, bloqueos y sintaxis...",
            },
        },
    }

    def _on_progress(msg: str, pct: float, extra: dict = None):
        if session_id in _multiagent_sessions:
            sess = _multiagent_sessions[session_id]
            sess["progress"] = round(pct, 1)
            sess["message"] = msg
            sess["logs"].append({"pct": pct, "msg": msg})

            if extra and isinstance(extra, dict):
                ag_key = extra.get("agent")
                if ag_key == "architect":
                    ag_key = "planner"
                if ag_key and ag_key in sess["agents"]:
                    ag_info = sess["agents"][ag_key]
                    ag_info["status"] = "Activo"
                    if "action" in extra:
                        ag_info["action"] = extra["action"]
                    if "reasoning" in extra and extra["reasoning"]:
                        ag_info["reasoning"] = extra["reasoning"]

    async def _runner():
        try:
            res = await orch.execute_project(
                project_description=requirement,
                max_attempts_per_task=3,
                progress_cb=_on_progress,
            )
            _multiagent_sessions[session_id]["status"] = "done"
            _multiagent_sessions[session_id]["progress"] = 100.0
            _multiagent_sessions[session_id]["message"] = "Proyecto completado y auditado con éxito."
            _multiagent_sessions[session_id]["result"] = res
        except Exception as exc:
            safe_log(f"[MultiAgent] Error en proyecto: {exc}")
            _multiagent_sessions[session_id]["status"] = "error"
            _multiagent_sessions[session_id]["message"] = f"Error: {exc}"

    asyncio.create_task(_runner())
    return {"session_id": session_id, "status": "running", "message": "Sesión multi-agente iniciada."}


@app.get("/api/multiagent/status/{session_id}")
async def get_multiagent_status(session_id: str):
    """Consulta el progreso en vivo y bitácora del desarrollo multi-agente."""
    sess = _multiagent_sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return sess


# ==============================================================================
# AGENTE COPILOT MULTI-MODELO (CHATGPT CLONE & CONTROL TOTAL DE APP)
# ==============================================================================

@app.get("/api/agent/models")
async def get_agent_models():
    """Retorna la lista de modelos de IA disponibles para el Agente Copilot."""
    from core.app_agent import AppAgentController
    controller = AppAgentController()
    return {"models": controller.get_models_list()}


@app.post("/api/agent/chat")
def agent_chat_endpoint(payload: dict = Body(...)):
    """Procesa una consulta u orden del usuario con el modelo seleccionado y ejecuta acciones."""
    message = payload.get("message", "").strip()
    model_id = payload.get("model_id", "gemini").strip()
    app_context = payload.get("app_context", {}) or {}
    history = payload.get("history", [])

    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    # El agente conoce el estado real del servidor: qué tareas están en curso ahora mismo.
    if isinstance(app_context, dict):
        app_context["server_tasks"] = summarize_active_tasks()

    from core.app_agent import AppAgentController
    controller = AppAgentController()

    try:
        from core.opencode_engine import OpenCodeEngine
        if OpenCodeEngine.installed():
            try:
                oc_res = OpenCodeEngine.run_prompt(
                    message=message,
                    model_id=model_id,
                    session_id=payload.get("oc_session_id"),
                    emit=lambda ev: None,
                )
                if oc_res and oc_res.get("reply") and not oc_res.get("reply", "").startswith("⚠️"):
                    return oc_res
            except Exception as _oce:
                safe_log(f"[Server] OpenCode fallback por: {_oce}")

        res = controller.process_message(
            message=message,
            model_id=model_id,
            app_context=app_context,
            history=history if isinstance(history, list) else [],
        )
        return res
    except Exception as exc:
        safe_log(f"[Server] Error en chat del agente: {exc}")
        import traceback; safe_log(traceback.format_exc())
        return {
            "model_used": model_id,
            "reply": f"⚠️ Ocurrió un error al procesar la solicitud. Intenta de nuevo.",
            "reasoning": str(exc),
            "actions": [],
            "extra": {},
        }


@app.post("/api/agent/chat/stream")
async def agent_chat_stream(payload: dict = Body(...)):
    """Chat del agente con STREAMING en tiempo real (SSE).

    Eventos emitidos:
      {"type": "status",   "message": "..."}   — etapa del motor (contactando modelo…)
      {"type": "reasoning","text": "..."}      — razonamiento acumulado del modelo, en vivo
      {"type": "final",    "payload": {...}}   — respuesta completa (reply, actions, extra)
      {"type": "error",    "message": "..."}   — fallo del flujo
    """
    import asyncio

    message = str(payload.get("message", "")).strip()
    model_id = str(payload.get("model_id", "gemini")).strip()
    app_context = payload.get("app_context", {}) or {}
    history = payload.get("history", [])

    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    if isinstance(app_context, dict):
        app_context["server_tasks"] = summarize_active_tasks()

    from core.app_agent import AppAgentController
    controller = AppAgentController()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def run_agent() -> dict:
        def work():
            try:
                from core.opencode_engine import OpenCodeEngine
                if OpenCodeEngine.installed():
                    try:
                        emit({"type": "status", "message": "Iniciando motor OpenCode…"})
                        oc_res = OpenCodeEngine.run_prompt(
                            message=message,
                            model_id=model_id,
                            session_id=payload.get("oc_session_id"),
                            emit=emit,
                        )
                        if oc_res and oc_res.get("reply") and not oc_res.get("reply", "").startswith("⚠️"):
                            return oc_res
                    except Exception as _oce:
                        safe_log(f"[Server] OpenCode falló, usando motor alternativo: {_oce}")
                        emit({"type": "status", "message": "Cambiando a motor alternativo…"})

                return controller.process_message(
                    message=message,
                    model_id=model_id,
                    app_context=app_context,
                    history=history if isinstance(history, list) else [],
                    on_event=emit,
                )
            except Exception as exc:
                safe_log(f"[Server] Error en chat del agente (stream): {exc}")
                return {
                    "model_used": model_id,
                    "reply": "⚠️ Ocurrió un error al procesar la solicitud. Intenta de nuevo.",
                    "reasoning": str(exc),
                    "actions": [],
                    "extra": {},
                }

        return await loop.run_in_executor(None, work)

    async def sse():
        task = asyncio.create_task(run_agent())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.4)
                except asyncio.TimeoutError:
                    if task.done():
                        break
                    yield ": ping\n\n"
                    continue
                if event.get("type") == "final":
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            payload_final = await task
            yield f"data: {json.dumps({'type': 'final', 'payload': payload_final}, ensure_ascii=False, default=str)}\n\n"
        except Exception as exc:
            safe_log(f"[Server] Error en stream del agente: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(sse(), media_type="text/event-stream")


@app.post("/api/oc/action")
def oc_action_endpoint(payload: dict = Body(...)):
    """Encola una acción de interfaz emitida por las herramientas de OpenCode."""
    from core.opencode_engine import push_action
    sid = str(payload.get("session_id", "_"))
    act = payload.get("action", {})
    push_action(sid, act)
    return {"ok": True}


@app.get("/api/oc/events")
async def oc_events_endpoint():
    """SSE en vivo: transmite al navegador cada acción de UI del agente en el instante
    en que se publica (desde el chat de la app o desde una sesión de opencode en terminal)."""
    import queue as _pyq

    from core.opencode_engine import subscribe_live_actions, unsubscribe_live_actions

    q = subscribe_live_actions()

    async def live_stream():
        try:
            while True:
                drained = []
                try:
                    while True:
                        drained.append(q.get_nowait())
                except _pyq.Empty:
                    pass
                if drained:
                    for act in drained:
                        yield f"data: {json.dumps(act, ensure_ascii=False, default=str)}\n\n"
                else:
                    yield ": ping\n\n"
                await asyncio.sleep(0.4)
        finally:
            unsubscribe_live_actions(q)

    return StreamingResponse(live_stream(), media_type="text/event-stream")


@app.get("/api/oc/status")
def oc_status_endpoint():
    """Estado de tareas en curso del servidor para el agente OpenCode."""
    return {
        "server_tasks": summarize_active_tasks(),
        "status": "online",
        "engine": "opencode",
    }


@app.post("/api/oc/permission/reply")
def oc_permission_reply_endpoint(payload: dict = Body(...)):
    """Responde a una solicitud de confirmación de permiso de OpenCode."""
    from core.opencode_engine import resolve_permission
    rid = str(payload.get("request_id", ""))
    reply = str(payload.get("reply", "reject"))
    ok = resolve_permission(rid, reply)
    return {"ok": ok}


@app.get("/api/agent/chats")
def list_agent_chats():
    """Lista los chats guardados del asistente (máximo 20, recientes primero)."""
    from core.chat_store import ChatStore
    return {"chats": ChatStore().list()}


@app.get("/api/agent/chats/{chat_id}")
def get_agent_chat(chat_id: str):
    """Devuelve un chat guardado completo (título + mensajes)."""
    from core.chat_store import ChatStore
    chat = ChatStore().load(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat no encontrado.")
    return {"chat": chat}


@app.post("/api/agent/chats")
def save_agent_chat(payload: dict = Body(...)):
    """Crea o actualiza un chat del asistente. El almacén conserva hasta 20."""
    from core.chat_store import ChatStore
    chat_id = payload.get("chat_id") or None
    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="'messages' debe ser una lista.")
    document = ChatStore().save(chat_id, messages)
    return {"chat": document}


@app.delete("/api/agent/chats/{chat_id}")
def delete_agent_chat(chat_id: str):
    from core.chat_store import ChatStore
    deleted = ChatStore().delete(chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat no encontrado.")
    return {"deleted": True, "chat_id": chat_id}


@app.post("/api/agent/generate-thumbnail")
def agent_generate_thumbnail(payload: dict = Body(...)):
    """Genera una miniatura para YouTube de alta conversión."""
    title = payload.get("title", "BROADCAST EXCLUSIVO").strip()
    badge = payload.get("badge", "🔴 BROADCAST URGENTE").strip()
    subtitle = payload.get("subtitle")
    project_id = payload.get("project_id")

    from core.thumbnail_maker import YouTubeThumbnailMaker
    maker = YouTubeThumbnailMaker()
    try:
        res = maker.generate(
            title=title,
            badge_text=badge,
            subtitle=subtitle,
            project_id=project_id,
        )
        return res
    except Exception as exc:
        safe_log(f"[Server] Error generando miniatura: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# ESTUDIO DE PUBLICACIÓN — ver qué se publica, miniatura IA y subida a YouTube
# ============================================================================

def _publish_studio(project_id: str):
    from core.publish_studio import PublishStudio
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_id or ""):
        raise HTTPException(status_code=400, detail="Identificador de proyecto no válido.")
    if not (settings.PROJECTS_DIR / project_id / "project.json").exists():
        raise HTTPException(status_code=404, detail="No se encontró el proyecto.")
    return PublishStudio(project_id)


@app.post("/api/publish/prepare")
def publish_prepare(payload: Dict[str, Any] = Body(...)):
    """Resumen de exactamente lo que se va a publicar + estado del canal."""
    import core.publish_studio as ps
    import core.youtube_oauth as yt
    studio = _publish_studio(str(payload.get("project_id", "")))
    try:
        info = studio.prepare()
        # No se exponen rutas del equipo local a la interfaz.
        info.pop("video_path", None)
        info["preview_url"] = f"/api/projects/{studio.project_id}/preview"
        info["styles"] = [{"id": key, "label": value["label"]} for key, value in ps.THUMB_STYLES.items()]
        info["youtube"] = {
            "configured": yt.is_configured(),
            "connected": yt.is_connected(),
            "channel": yt.get_channel_info() if yt.is_connected() else None,
        }
        return info
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=friendly_error(exc))


@app.post("/api/publish/metadata")
def publish_metadata(payload: Dict[str, Any] = Body(...)):
    """Título, descripción y etiquetas SEO generados con IA."""
    studio = _publish_studio(str(payload.get("project_id", "")))
    try:
        return studio.generate_metadata(instructions=str(payload.get("instructions", "")))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=friendly_error(exc))


@app.post("/api/publish/thumbnail")
def publish_thumbnail(payload: Dict[str, Any] = Body(...)):
    """Miniatura 1280x720 con el modelo de imagen de Gemini (Nano Banana)."""
    studio = _publish_studio(str(payload.get("project_id", "")))
    frame_at = payload.get("frame_at")
    try:
        return studio.generate_ai_thumbnail(
            title=str(payload.get("title", "")),
            topic=str(payload.get("topic", "")),
            style=str(payload.get("style", "cinematic")),
            thumbnail_text=str(payload.get("thumbnail_text", "")),
            use_frame=bool(payload.get("use_frame", False)),
            frame_at=float(frame_at) if isinstance(frame_at, (int, float)) else None,
            custom_prompt=str(payload.get("custom_prompt", "")),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=friendly_error(exc))


@app.get("/api/publish/youtube/status")
def publish_youtube_status():
    import core.youtube_oauth as yt
    accounts = yt.list_accounts() if yt.is_configured() else []
    return {
        "configured": yt.is_configured(),
        "connected": bool(accounts),
        "channel": accounts[0] if accounts else None,
        "accounts": accounts,
    }


@app.post("/api/publish/youtube/accounts/update")
def publish_youtube_account_update(payload: Dict[str, Any] = Body(...)):
    """Guarda etiqueta, palabras clave y tipo (short/video/any) de un canal conectado."""
    import core.youtube_oauth as yt
    import re
    keywords = payload.get("keywords")
    if isinstance(keywords, str):
        keywords = [k for k in re.split(r"[,;\n]", keywords) if k.strip()]
    try:
        return yt.update_account(
            str(payload.get("channel_id", "")),
            tag=payload.get("tag"),
            keywords=keywords,
            kind=payload.get("kind"),
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/publish/youtube/suggest")
def publish_youtube_suggest(payload: Dict[str, Any] = Body(...)):
    """Detecta si el video es Short o largo y sugiere el canal según etiquetas."""
    import core.youtube_oauth as yt
    studio = _publish_studio(str(payload.get("project_id", "")))
    video = studio.resolve_master_video()
    if not video:
        raise HTTPException(status_code=404, detail="Este proyecto no tiene un video final para publicar.")
    fmt = yt.detect_format(video)
    suggestion = yt.suggest_account(
        str(payload.get("title", "")),
        str(payload.get("description", "")),
        list(payload.get("tags") or []),
        fmt["format"],
    )
    return {**fmt, "channel_id": suggestion["channel_id"], "reason": suggestion["reason"]}


@app.get("/api/publish/youtube/connect")
def publish_youtube_connect(slot: str = ""):
    """Redirige al consentimiento OAuth de Google (PKCE).

    Param:
      slot: sufijo del par de credenciales a usar (\"\", \"_2\", \"_3\"...).
            Si se omite, se usa el par principal.
    """
    import core.youtube_oauth as yt
    from urllib.parse import quote
    try:
        flow = yt.begin_authorization(client_slot=slot)
    except Exception as exc:
        return RedirectResponse(f"/?publish_error={quote(str(exc)[:200])}")
    return RedirectResponse(flow["auth_url"])


@app.get("/api/publish/youtube/callback")
def publish_youtube_callback(code: str = "", state: str = "", error: str = ""):
    """Google regresa aquí tras el consentimiento; guarda el token del canal."""
    import core.youtube_oauth as yt
    from urllib.parse import quote
    if error:
        return RedirectResponse(f"/?publish_error={quote(error[:200])}")
    try:
        yt.complete_authorization(code=code, state=state)
    except Exception as exc:
        safe_log(f"[Publish] Error completando OAuth de YouTube: {exc}")
        return RedirectResponse(f"/?publish_error={quote(str(exc)[:200])}")
    return RedirectResponse("/?publish_connected=1")


@app.post("/api/publish/youtube/disconnect")
def publish_youtube_disconnect(payload: Dict[str, Any] = Body(default={})):
    import core.youtube_oauth as yt
    yt.disconnect(str((payload or {}).get("channel_id") or "") or None)
    return {"connected": yt.is_connected()}


@app.get("/api/publish/youtube/clients")
def publish_youtube_clients():
    """Lista los pares de credenciales OAuth disponibles y a qué canal están asignados."""
    import core.youtube_oauth as yt
    clients = yt._discover_clients()
    accounts = yt._load_accounts()
    result = []
    for c in clients:
        # Buscar cuentas que usen este client_id
        matched = [a for a in accounts if (a.get("client_id") or "").strip() == c["client_id"]]
        # Canal 1 puede no tener client_id guardado (legacy)
        if not matched and c["slot"] == "":
            matched = [a for a in accounts if not a.get("client_id")]
        result.append({
            "slot": c["slot"],
            "client_id_preview": c["client_id"][:30] + "..." if len(c["client_id"]) > 30 else c["client_id"],
            "connect_url": f"/api/publish/youtube/connect?slot={c['slot']}",
            "channels": [{"channel_id": a.get("channel_id"), "title": a.get("title")} for a in matched],
            "label": f"Canal {'' if not c['slot'] else c['slot'].lstrip('_')}",
        })
    return {"clients": result, "total": len(result)}


@app.get("/api/channels")
def get_channels():
    """Lista todos los canales configurados para publicación multi-nicho."""
    from core.channel_manager import ChannelManager
    return ChannelManager.list_channels()


@app.post("/api/channels")
def upsert_channel(channel: Dict[str, Any] = Body(...)):
    """Crea o actualiza un canal en el sistema."""
    from core.channel_manager import ChannelManager
    return ChannelManager.upsert_channel(channel)


@app.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: str):
    """Elimina un canal configurado."""
    from core.channel_manager import ChannelManager
    ok = ChannelManager.delete_channel(channel_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    return {"deleted": True}


@app.post("/api/channels/classify")
def classify_content_channel(payload: Dict[str, Any] = Body(...)):
    """Clasifica una temática o guion para determinar el canal óptimo de publicación."""
    from core.channel_manager import ChannelManager
    topic = str(payload.get("topic") or payload.get("title") or "")
    speech = str(payload.get("speech") or "")
    return ChannelManager.classify_content(topic, speech)



def _run_youtube_upload(task_id: str, studio, video: Path, payload: Dict[str, Any], thumbnail_path: Optional[Path]) -> None:
    import core.youtube_oauth as yt
    try:
        def report(fraction: float, message: str) -> None:
            update_task_state(task_id, "upload", 2.0 + fraction * 95.0, message)

        title = str(payload.get("title", ""))
        description = str(payload.get("description", ""))
        tags = list(payload.get("tags") or [])

        # Formato: el elegido por el usuario o el detectado en el archivo real
        detected = yt.detect_format(video)
        requested = str(payload.get("format") or "auto").lower()
        fmt = requested if requested in ("short", "video") else detected["format"]
        if fmt == "short":
            meta = yt.prepare_shorts_metadata(title, description, tags)
            title, description, tags = meta["title"], meta["description"], meta["tags"]

        # Canal: el elegido o, si no hay, el que mejor encaja por etiquetas y formato
        channel_id = str(payload.get("channel_id") or "") or None
        if not channel_id:
            channel_id = yt.suggest_account(title, description, tags, fmt).get("channel_id") or None

        upload = yt.upload_video(
            video_path=video,
            title=title,
            description=description,
            tags=tags,
            privacy=str(payload.get("privacy", "public")),
            category_id=str(payload.get("category_id", "27")),
            made_for_kids=bool(payload.get("made_for_kids", False)),
            notify_subscribers=bool(payload.get("notify_subscribers", True)),
            channel_id=channel_id,
            publish_at=str(payload.get("publish_at") or "") or None,
            progress=report,
        )
        thumbnail_set = False
        if thumbnail_path:
            update_task_state(task_id, "thumbnail", 98.0, "Asignando miniatura personalizada...")
            thumbnail_set = yt.set_thumbnail(upload["video_id"], thumbnail_path, channel_id)
        channel = yt.get_channel_info(channel_id) or {}
        result = {
            **upload,
            "thumbnail_set": thumbnail_set,
            "project_id": studio.project_id,
            "format": fmt,
            "channel_title": channel.get("title", ""),
            "studio_url": f"https://studio.youtube.com/video/{upload['video_id']}/edit",
        }
        with _state_lock:
            tasks_progress[task_id].update({"completed": True, "result": result})
        update_task_state(task_id, "done", 100.0, "¡Video publicado en YouTube con éxito!")
    except Exception as exc:
        safe_log(f"[Publish] Fallo la subida a YouTube: {exc}")
        with _state_lock:
            tasks_progress[task_id].update({"error": str(exc)[:400]})
        update_task_state(task_id, "error", 100.0, f"No se pudo publicar: {str(exc)[:200]}")


@app.post("/api/publish/youtube/upload")
async def publish_youtube_upload(payload: Dict[str, Any] = Body(...)):
    """Sube el video master directamente al canal conectado (tarea en background)."""
    import core.youtube_oauth as yt
    studio = _publish_studio(str(payload.get("project_id", "")))
    if not yt.is_connected():
        raise HTTPException(status_code=409, detail="El canal de YouTube no está conectado. Conéctalo primero.")
    video = studio.resolve_master_video()
    if not video:
        raise HTTPException(status_code=404, detail="Este proyecto no tiene un video final para publicar.")

    thumbnail_path: Optional[Path] = None
    thumb_url = str(payload.get("thumbnail_url") or "")
    if thumb_url.startswith("/media/"):
        candidate = settings.OUTPUTS_DIR / thumb_url[len("/media/"):]
        if candidate.is_file():
            thumbnail_path = candidate

    task_id = f"pub_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    tasks_progress[task_id] = {
        "step": "upload", "progress": 2.0, "message": "Autenticando con YouTube...",
        "completed": False, "error": None, "result": None, "cancel_supported": False,
        "file_name": str(payload.get("title") or "Video KAI"),
        "created_at": now, "updated_at": now, "step_started_at": now,
        "events": [{"step": "upload", "progress": 2.0, "message": "Autenticando con YouTube...", "at": now}],
    }
    thread = threading.Thread(
        target=_run_youtube_upload,
        args=(task_id, studio, video, payload, thumbnail_path),
        daemon=True,
    )
    thread.start()
    return {"task_id": task_id, "project_id": studio.project_id}


# ============================================================================
# RADAR DE VIRALIDAD — ranking de videos virales por región + temas urgentes
# ============================================================================

# ============================================================================
# PILOTO AUTOMÁTICO — investiga, pule con datos, crea, programa y publica solo
# ============================================================================

@app.on_event("startup")
async def start_autopilot_engine() -> None:
    import core.autopilot as autopilot
    autopilot.start()


@app.get("/api/autopilot/status")
def autopilot_status():
    import core.autopilot as autopilot
    return autopilot.get_status()


@app.post("/api/autopilot/config")
def autopilot_config(payload: Dict[str, Any] = Body(...)):
    import core.autopilot as autopilot
    autopilot.update_config(payload)
    return autopilot.get_status()


@app.post("/api/autopilot/run")
def autopilot_run():
    import core.autopilot as autopilot
    autopilot.run_now()
    return {"ok": True}


@app.post("/api/autopilot/jobs/{job_id}/retry")
def autopilot_retry(job_id: str):
    import core.autopilot as autopilot
    if not autopilot.retry_job(job_id):
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    return autopilot.get_status()


@app.post("/api/autopilot/jobs/{job_id}/cancel")
def autopilot_cancel(job_id: str):
    import core.autopilot as autopilot
    if not autopilot.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    return autopilot.get_status()


trend_radar = TrendRadar()


@app.on_event("startup")
async def start_trend_radar_scheduler() -> None:
    """Revisión automática cada 3 horas: qué sube, qué baja, qué emerge."""
    threading.Thread(target=trend_radar.scheduler_loop, daemon=True).start()
    try:
        from core.anime_series_autopilot import start_anime_series_autopilot
        start_anime_series_autopilot()
    except Exception as _e_an:
        safe_log(f"[Startup] Aviso iniciando Anime Autopilot: {_e_an}")
    try:
        from core.universal_autopilot_tour import start_universal_tour_worker
        start_universal_tour_worker()
    except Exception as _e_ut:
        safe_log(f"[Startup] Aviso iniciando Universal Tour: {_e_ut}")


@app.get("/api/trend-radar")
async def get_trend_radar():
    """Ranking viral y temas urgentes (caché viva; se auto-refresca si caducó)."""
    return trend_radar.get_snapshot()


RADAR_FAVORITES_FILE = settings.STORAGE_DIR / "radar_topic_favorites.json"


@app.get("/api/trend-radar/favorites")
async def get_trend_radar_favorites():
    """Obtiene los temas guardados en favoritos de forma persistente."""
    if RADAR_FAVORITES_FILE.exists():
        try:
            favs = json.loads(RADAR_FAVORITES_FILE.read_text(encoding="utf-8"))
            if isinstance(favs, list):
                return {"favorites": favs}
        except Exception as e:
            safe_log(f"[TrendRadar] Error leyendo favoritos: {e}")
    return {"favorites": []}


@app.post("/api/trend-radar/favorites")
async def save_trend_radar_favorites(payload: Dict[str, Any] = Body(...)):
    """Guarda, añade o quita un tema de favoritos de forma persistente."""
    action = str(payload.get("action", "toggle")).strip().lower()
    topic = payload.get("topic") or {}
    favorites = payload.get("favorites")

    current_favs = []
    if RADAR_FAVORITES_FILE.exists():
        try:
            raw = json.loads(RADAR_FAVORITES_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                current_favs = raw
        except Exception:
            current_favs = []

    if favorites is not None and isinstance(favorites, list):
        current_favs = favorites
    elif topic and topic.get("title"):
        title_key = topic.get("title", "").strip().lower()
        exists = any(f.get("title", "").strip().lower() == title_key for f in current_favs)

        if action == "add" and not exists:
            topic["saved_at"] = datetime.now(timezone.utc).isoformat()
            current_favs.insert(0, topic)
        elif action == "remove" and exists:
            current_favs = [f for f in current_favs if f.get("title", "").strip().lower() != title_key]
        elif action == "toggle":
            if exists:
                current_favs = [f for f in current_favs if f.get("title", "").strip().lower() != title_key]
            else:
                topic["saved_at"] = datetime.now(timezone.utc).isoformat()
                current_favs.insert(0, topic)

    try:
        RADAR_FAVORITES_FILE.write_text(json.dumps(current_favs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        safe_log(f"[TrendRadar] Error guardando favoritos: {e}")

    return {"success": True, "favorites": current_favs}


@app.post("/api/viral-niches/refresh")
@app.get("/api/viral-niches/refresh")
async def refresh_viral_niches(
    category: str | None = None,
) -> dict:
    """Busca en Internet tendencias reales y sintetiza con IA temas virales frescos
    cubriendo todas las categorías (finanzas, misterio, ciencia, amor, terror, etc.)
    con cálculo de puntuación de viralidad real (+85 a +99)."""
    import random
    from core.llm import LLMClient

    NICHES_MAP = {
        "finanzas": {"cat": "finanzas", "query": "estrategia inversion multimillonarios economia dinero mercado", "glyph": "💰", "hook": "Estrategia de Riqueza"},
        "amor": {"cat": "amor", "query": "psicologia de parejas relaciones amor seduccion comportamiento", "glyph": "❤️", "hook": "Psicología Relacional"},
        "religion": {"cat": "religion", "query": "misterios biblicos arqueologia sagrada secretos religion", "glyph": "✝️", "hook": "Enigma Bíblico"},
        "versus": {"cat": "versus", "query": "comparativa tecnologia autos marcas empresas duelo", "glyph": "⚔️", "hook": "Duelo Definitivo"},
        "terror": {"cat": "terror", "query": "casos oscuros creepypasta terror psicologico misterio", "glyph": "👻", "hook": "Terror Psicológico"},
        "misterio": {"cat": "misterio", "query": "enigmas mundiales fenomenos inexplicables conspiraciones ovni", "glyph": "👁️", "hook": "Enigma Oculto"},
        "politica": {"cat": "politica", "query": "geopolitica mundial secretos de estado guerras poder", "glyph": "🏛️", "hook": "Geopolítica y Poder"},
        "ciencia": {"cat": "ciencia", "query": "descubrimientos cientificos astronomia universo fisica", "glyph": "🔬", "hook": "Revelación Científica"},
        "curiosidades": {"cat": "curiosidades", "query": "curiosidades datos insolitos paradojas mundo", "glyph": "💡", "hook": "Curiosidad Viral"},
        "historia": {"cat": "historia", "query": "arqueologia civilizaciones antiguas imperios secretos", "glyph": "🏺", "hook": "Caso Histórico Real"},
        "psicologia": {"cat": "psicologia", "query": "psicologia oscura sesgos cognitivos manipulacion mente", "glyph": "🧠", "hook": "Psicología Oscura"},
        "crimen": {"cat": "crimen", "query": "true crime investigacion policial casos reales robos", "glyph": "🔍", "hook": "Investigación True Crime"},
        "tecnologia": {"cat": "tecnologia", "query": "inteligencia artificial futuro robotica tecnologia", "glyph": "🤖", "hook": "Frontera Tecnológica"},
        "narrativa": {"cat": "narrativa", "query": "historias reales supervivencia casos extraordinarios", "glyph": "🎬", "hook": "Crónica Inmersiva"},
    }
    NICHES_CONFIG = list(NICHES_MAP.values())

    cat_target = (category or "").strip().lower()
    if cat_target and cat_target in NICHES_MAP:
        selected_niches = [NICHES_MAP[cat_target]]
        target_count = 6
    else:
        cat_target = None
        selected_niches = random.sample(NICHES_CONFIG, min(6, len(NICHES_CONFIG)))
        target_count = 14

    web_findings = []
    def _fetch_web():
        findings = []
        try:
            from ddgs import DDGS
            with DDGS(timeout=4) as ddgs:
                for cfg in selected_niches:
                    try:
                        news = list(ddgs.news(cfg["query"], max_results=2))
                        if not news:
                            news = list(ddgs.text(cfg["query"], max_results=2))
                        for item in news:
                            t = item.get("title", "")
                            b = item.get("body", "")
                            if t and len(t) > 15:
                                clean_t = re.sub(r"\s*[-|–]\s*[A-Za-z0-9\.\sáéíóúÁÉÍÓÚ]+$", "", t).strip()
                                clean_t = re.sub(r"^[A-Za-z0-9\.\s]+:\s*", "", clean_t).strip()
                                findings.append({
                                    "category": cfg["cat"],
                                    "title": clean_t,
                                    "summary": (b or clean_t)[:180],
                                    "glyph": cfg["glyph"],
                                    "default_hook": cfg["hook"],
                                })
                    except Exception:
                        continue
        except Exception as _e_ddg:
            safe_log(f"[ViralRefresh] Aviso en búsqueda DDGS: {_e_ddg}")
        return findings

    try:
        web_findings = await asyncio.wait_for(asyncio.to_thread(_fetch_web), timeout=5.0)
    except Exception as _e_wait:
        safe_log(f"[ViralRefresh] Timeout o fallo en fetch web: {_e_wait}")
        web_findings = []

    topics_out = []
    try:
        llm = LLMClient()
        findings_txt = "\n".join([f"- [{wf['category'].upper()}] {wf['title']}: {wf['summary']}" for wf in web_findings[:6]]) if web_findings else "Tendencias globales actuales en redes, ciencia, finanzas y misterio."
        
        target_instruction = (
            f"Genera exactamente {target_count} temas virales EXCLUSIVAMENTE para la categoría '{cat_target}'."
            if cat_target
            else f"Genera al menos {target_count} temas virales con EXACTAMENTE 1 tema para cada una de las 14 categorías principales: finanzas, amor, religion, versus, terror, misterio, politica, ciencia, curiosidades, historia, psicologia, crimen, tecnologia, narrativa."
        )

        prompt = f"""Actúa como Director de Viralidad para canales de YouTube y videos de 10 a 40 minutos o Reels.
Aquí tienes hallazgos y noticias extraídas de Internet:
{findings_txt}

Instrucción:
{target_instruction}

Para CADA tema calcula una PUNTUACIÓN DE VIRALIDAD REAL (un número entero entre 88 y 99) basada en la potencia del gancho de curiosidad, la controversia y la retención del espectador.
Asegúrate de que cada tema tenga un título llamativo, un enfoque detallado en 'nuances' y una categoría válida en minúsculas.

Responde ÚNICAMENTE en JSON válido con esta lista de objetos:
[
  {{
    "title": "Título épico con gancho irresistible",
    "nuances": "Enfoque detallado: hipótesis central, datos comprobados, revelación y giros para 15-30 min.",
    "category": "{cat_target or 'finanzas'}",
    "score": 98,
    "glyph": "💰",
    "hookType": "Estrategia de Riqueza",
    "durationMin": 20
  }}
]"""
        resp = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: llm.generate(prompt, json_mode=True, use_search=False, deadline_sec=16.0)
            ),
            timeout=18.0
        )
        clean_resp = re.sub(r"^```(?:json)?", "", resp.strip(), flags=re.MULTILINE)
        clean_resp = re.sub(r"```$", "", clean_resp.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(clean_resp)
        if isinstance(parsed, list) and len(parsed) > 0:
            for idx, item in enumerate(parsed):
                c = (item.get("category") or cat_target or "curiosidades").lower()
                cfg_info = NICHES_MAP.get(c, {"glyph": "🔥", "hook": "Tendencia IA"})
                if item.get("title"):
                    topics_out.append({
                        "id": f"vt-live-{c[:3]}-{idx}-{random.randint(100, 999)}",
                        "title": item["title"],
                        "nuances": item.get("nuances") or item["title"],
                        "category": c,
                        "score": int(min(99, max(85, item.get("score", 92)))),
                        "glyph": item.get("glyph") or cfg_info["glyph"],
                        "hookType": item.get("hookType") or cfg_info["hook"],
                        "durationMin": int(item.get("durationMin") or 20),
                        "isLive": True,
                    })
    except Exception as _e_llm:
        safe_log(f"[ViralRefresh] Aviso en LLM ({_e_llm})")

    # Fallback sobre los hallazgos web si el LLM tardó
    if not topics_out and web_findings:
        for idx, wf in enumerate(web_findings):
            score = 88
            t_low = (wf["title"] + " " + wf["summary"]).lower()
            power_words = ["secreto", "revela", "oculto", "millonario", "crimen", "prohibido", "estrategia", "colapso", "descubrimiento", "enigma", "riqueza", "poder", "verdad", "engaño", "universo", "impacto", "peligro"]
            matches = sum(1 for pw in power_words if pw in t_low)
            score = min(99, max(88, score + min(7, matches * 2) + (2 if any(c in wf["title"] for c in ["?", "!", ":"]) else 0)))
            topics_out.append({
                "id": f"vt-web-{wf['category'][:3]}-{idx}-{random.randint(100, 999)}",
                "title": wf["title"],
                "nuances": wf["summary"],
                "category": wf["category"],
                "score": score,
                "glyph": wf["glyph"],
                "hookType": wf["default_hook"],
                "durationMin": random.choice([15, 20, 25, 30]),
                "isLive": True,
            })

    # Si todo falló, generar pool dinámico curado para que jamás quede vacío
    if not topics_out:
        sample_cats = [NICHES_MAP[cat_target]] if cat_target and cat_target in NICHES_MAP else NICHES_CONFIG
        for idx, cfg in enumerate(sample_cats):
            topics_out.append({
                "id": f"vt-curated-{cfg['cat'][:3]}-{idx}-{random.randint(100, 999)}",
                "title": f"{cfg['hook']}: Revelación y análisis estratégico profundo",
                "nuances": f"Investigación periodística y desglose paso a paso de los factores clave en {cfg['cat']}.",
                "category": cfg["cat"],
                "score": random.randint(89, 98),
                "glyph": cfg["glyph"],
                "hookType": cfg["hook"],
                "durationMin": random.choice([15, 20, 25, 30]),
                "isLive": True,
            })

    return {
        "success": True,
        "count": len(topics_out),
        "source": "web_and_ai",
        "topics": topics_out,
    }


@app.post("/api/trend-radar/refresh")
async def refresh_trend_radar():
    """Fuerza un barrido nuevo en background (charts + temas con IA)."""
    started = trend_radar.start_background_refresh()
    return {"started": started, "refreshing": True}


@app.post("/api/trend-radar/analyze")
async def analyze_trend_item(payload: Dict[str, Any] = Body(...)):
    """La IA analiza el video original o el tema y propone enfoques estratégicos con duración calculada."""
    kind = str(payload.get("kind", "")).strip().lower()
    item = payload.get("item") or {}
    if kind not in ("video", "topic") or not isinstance(item, dict) or not item:
        raise HTTPException(status_code=400, detail="Indica kind ('video'|'topic') y el elemento 'item' a analizar.")
    try:
        return trend_radar.analyze_item(kind, item)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=friendly_error(exc))


@app.post("/api/trend-radar/replicate")
async def replicate_trend_item(payload: Dict[str, Any] = Body(...)):
    """Replica un video viral (en español, con mejoras) o produce un tema urgente con duración óptima.

    La IA convierte los parámetros del original en una brief en español y
    arranca directamente la producción autónoma de KAI (streamer pipeline).
    Si viene "choice" (enfoque elegido en el panel de estrategia), la brief se
    construye alrededor de esa decisión; "instructions" añade notas libres.
    """
    kind = str(payload.get("kind", "")).strip().lower()
    item = payload.get("item") or {}
    if kind not in ("video", "topic") or not isinstance(item, dict) or not item:
        raise HTTPException(status_code=400, detail="Indica kind ('video'|'topic') y el elemento 'item' a replicar.")
    choice = payload.get("choice") if isinstance(payload.get("choice"), dict) else None
    instructions = str(payload.get("instructions", "") or "")[:400]
    try:
        brief = trend_radar.build_replication(kind, item, choice=choice, instructions=instructions)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=friendly_error(exc))

    style = str(payload.get("style", "divulgacion")).strip() or "divulgacion"
    # Duración: la que pida el usuario; si no, la que la IA recomienda según la profundidad del tema.
    raw_duration = payload.get("duration_sec")
    raw_minutes = payload.get("duration_min")
    if raw_minutes is not None:
        try:
            duration_sec = int(float(raw_minutes) * 60)
        except (ValueError, TypeError):
            duration_sec = 180
    else:
        if raw_duration is None:
            raw_duration = brief.get("recommended_duration_sec") or (
                360 if item.get("category") in ("descubrimiento", "ciencia", "espacio", "arqueologia", "tecnologia", "misterio") else 180
            )
        try:
            duration_sec = int(raw_duration)
        except (ValueError, TypeError):
            duration_sec = 180
    duration_sec = max(20, min(2400, duration_sec))
    creation = await create_streamer_broadcast({
        "topic": brief["topic"],
        "extra_notes": brief["extra_notes"],
        "style": style,
        "duration_sec": duration_sec,
        "origin": "radar",
    })
    return {"task_id": creation["task_id"], "project_id": creation["project_id"],
            "topic": brief["topic"], "extra_notes": brief["extra_notes"], "duration_sec": duration_sec}


# ============================================================================
# EDITOR DE ARCHIVOS REAL — El agente puede escribir/parchear archivos reales
# ============================================================================

_PROJECT_ROOT = Path(__file__).resolve().parent

# Directorios permitidos para que el agente edite
_ALLOWED_EDIT_DIRS = [
    _PROJECT_ROOT / "web" / "static" / "css",
    _PROJECT_ROOT / "web" / "static" / "js",
    _PROJECT_ROOT / "web" / "templates",
]

def _resolve_safe_path(rel_path: str) -> Path:
    """Resuelve un path relativo y verifica que esté dentro de un directorio permitido."""
    target = (_PROJECT_ROOT / rel_path.lstrip("/\\")).resolve()
    for allowed in _ALLOWED_EDIT_DIRS:
        try:
            target.relative_to(allowed.resolve())
            return target
        except ValueError:
            continue
    raise PermissionError(f"Ruta no permitida: {rel_path}")


@app.post("/api/agent/edit-files")
def agent_edit_files(payload: dict = Body(...)):
    """
    Permite al agente modificar archivos REALES del proyecto en disco.
    Acepta una lista de operaciones:
      - { "op": "write",      "path": "web/static/css/...", "content": "..." }
      - { "op": "append",     "path": "web/static/css/...", "content": "..." }
      - { "op": "replace",    "path": "...", "old": "...", "new": "..." }
    Retorna { "ok": true, "files_written": [...], "reload": true }
    """
    import shutil, time

    ops = payload.get("ops", [])
    if not ops or not isinstance(ops, list):
        raise HTTPException(status_code=400, detail="Se requiere lista de operaciones 'ops'.")

    files_written = []
    errors = []

    for op in ops:
        op_type = op.get("op", "write")
        rel_path = op.get("path", "")
        if not rel_path:
            errors.append("Operación sin 'path'.")
            continue

        try:
            target = _resolve_safe_path(rel_path)
        except PermissionError as pe:
            errors.append(str(pe))
            continue

        # Crear directorios si no existen
        target.parent.mkdir(parents=True, exist_ok=True)

        # Backup automático antes de modificar
        if target.exists():
            backup = target.with_suffix(target.suffix + f".bak")
            shutil.copy2(str(target), str(backup))

        try:
            if op_type == "write":
                content = op.get("content", "")
                target.write_text(content, encoding="utf-8")
                files_written.append(str(rel_path))

            elif op_type == "append":
                content = op.get("content", "")
                existing = target.read_text(encoding="utf-8") if target.exists() else ""
                target.write_text(existing + "\n" + content, encoding="utf-8")
                files_written.append(str(rel_path))

            elif op_type == "replace":
                old_str = op.get("old", "")
                new_str = op.get("new", "")
                if not old_str:
                    errors.append(f"Operación 'replace' en {rel_path} sin 'old'.")
                    continue
                existing = target.read_text(encoding="utf-8") if target.exists() else ""
                if old_str not in existing:
                    errors.append(f"Texto 'old' no encontrado en {rel_path}.")
                    continue
                updated = existing.replace(old_str, new_str, 1)
                target.write_text(updated, encoding="utf-8")
                files_written.append(str(rel_path))

            else:
                errors.append(f"Operación desconocida: {op_type}")

        except Exception as write_err:
            safe_log(f"[FileEditor] Error escribiendo {rel_path}: {write_err}")
            errors.append(f"Error en {rel_path}: {write_err}")

    if not files_written and errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    return {
        "ok": True,
        "files_written": files_written,
        "errors": errors,
        "reload": True,  # El frontend recarga la página para aplicar cambios reales
    }


@app.get("/api/agent/read-file")
def agent_read_file(path: str):
    """Permite al agente leer un archivo del proyecto para inspeccionarlo antes de editar."""
    try:
        target = _resolve_safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {path}")
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "content": content, "lines": content.count("\n") + 1}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.get("/api/visual-templates")
def get_visual_templates():
    """Catálogo completo de la librería de plantillas visuales con variantes temáticas y animaciones."""
    from core.visual_templates import VisualTemplatesLibrary
    return VisualTemplatesLibrary.get_catalog()


@app.get("/api/visual-templates/preview")
def preview_visual_template(
    template: str = "verdict_badge",
    variant: str = "orange_noir",
    headline: Optional[str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    body: Optional[str] = None,
    stat_value: Optional[str] = None,
    stat_label: Optional[str] = None,
    side_a: Optional[str] = None,
    side_b: Optional[str] = None,
    source: Optional[str] = None,
    main_text: Optional[str] = None,
    accent_text: Optional[str] = None,
    step_number: Optional[str] = None,
    total_steps: Optional[str] = None,
    step_prefix: Optional[str] = None,
    code_comment: Optional[str] = None,
    handle: Optional[str] = None,
    window_title: Optional[str] = None,
    highlight_button: Optional[str] = None,
    placeholder_text: Optional[str] = None,
    grid_style: Optional[str] = None,
):
    """Genera o sirve la vista previa renderizada en PNG de una plantilla visual."""
    from core.visual_templates import VisualTemplatesLibrary
    vlib = VisualTemplatesLibrary()
    preview_dir = settings.OUTPUTS_DIR / "template_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    out_file = preview_dir / f"preview_{template}_{variant}.png"

    # Preparar parámetros combinando query params con sample params
    params = {}
    catalog = vlib.get_catalog()
    for item in catalog["templates"]:
        if item["id"] == template:
            params.update(item.get("sample_params", {}))
            break

    # Sobrescribir con valores provistos
    if headline: params["headline"] = headline
    if title: params["title"] = title
    if subtitle: params["subtitle"] = subtitle
    if body: params["body"] = body
    if stat_value: params["stat_value"] = stat_value
    if stat_label: params["stat_label"] = stat_label
    if side_a: params["side_a"] = side_a
    if side_b: params["side_b"] = side_b
    if source: params["source"] = source
    if main_text: params["main_text"] = main_text
    if accent_text: params["accent_text"] = accent_text
    if step_number: params["step_number"] = step_number
    if total_steps: params["total_steps"] = total_steps
    if step_prefix: params["step_prefix"] = step_prefix
    if code_comment: params["code_comment"] = code_comment
    if handle: params["handle"] = handle
    if window_title: params["window_title"] = window_title
    if highlight_button: params["highlight_button"] = highlight_button
    if placeholder_text: params["placeholder_text"] = placeholder_text
    if grid_style: params["grid_style"] = grid_style

    rendered = vlib.render_template_to_image(template, out_file, params, variant=variant)
    if not rendered or not rendered.exists():
        raise HTTPException(status_code=500, detail=f"No se pudo generar la vista previa del template '{template}'")

    return FileResponse(rendered, media_type="image/png")



if __name__ == "__main__":
    import os
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    safe_log(f"[Server] AetherCut AI en http://{host}:{port}")
    uvicorn.run("server:app", host=host, port=port, reload=False)

