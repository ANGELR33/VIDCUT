"""Motor del Agente Programador de AetherCut basado en OpenCode.

Lanza `opencode serve` como subproceso con nuestras APIs por defecto
(Gemini y NVIDIA NIM: GLM-5.3, GLM-5.3 Flash, Kimi-k3) y expone el bucle de agente
completo de OpenCode (read, edit, write, glob, grep, bash, todo, subagentes...) más las
herramientas propias de la app (ver .opencode/tools/aether.ts).

Si OpenCode no está disponible, el servidor cae al motor clásico (AppAgentController).
"""

from __future__ import annotations

import json
import os
import queue as _queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

from config.settings import settings

ROOT = Path(__file__).resolve().parent.parent
OC_PORT = int(os.getenv("OPENCODE_PORT", "4096"))
OC_URL = f"http://127.0.0.1:{OC_PORT}"

# Mapeo de selectores de la UI -> (providerID, modelID) en OpenCode
MODEL_MAP: Dict[str, tuple] = {
    "gemini": ("google", "gemini-flash-latest"),
    "glm-5.3": ("nvidia", "z-ai/glm-5.3"),
    "glm-5.3-flash": ("nvidia", "z-ai/glm-5.3-flash"),
    "kimi-k3": ("nvidia", "moonshotai/kimi-k3"),
}

# Acciones de UI encoladas por las herramientas de la app, por sesión de OpenCode.
_action_queues: Dict[str, List[Dict[str, Any]]] = {}
_action_lock = threading.Lock()
# Suscriptores en vivo (frontends conectados al SSE /api/oc/events).
_live_subscribers: List["_queue.Queue[Dict[str, Any]]"] = []
_live_lock = threading.Lock()
# Permisos pendientes: request_id -> {"event": Event, "reply": str}
_pending_permissions: Dict[str, Dict[str, Any]] = {}


def _broadcast_action(action: Dict[str, Any]) -> None:
    """Envía una acción a todos los frontends conectados por SSE (tiempo real)."""
    with _live_lock:
        subs = list(_live_subscribers)
    for q in subs:
        try:
            q.put_nowait(action)
        except Exception:
            pass


def subscribe_live_actions() -> "_queue.Queue[Dict[str, Any]]":
    """Registra una cola que recibirá cada acción de UI en el instante en que se publique."""
    q: "_queue.Queue[Dict[str, Any]]" = _queue.Queue()
    with _live_lock:
        _live_subscribers.append(q)
    return q


def unsubscribe_live_actions(q: "_queue.Queue[Dict[str, Any]]") -> None:
    with _live_lock:
        try:
            _live_subscribers.remove(q)
        except ValueError:
            pass


def push_action(session_id: str, action: Dict[str, Any]) -> None:
    action = dict(action)
    # Identificador único para que el frontend no ejecute dos veces la misma acción
    # (llega por SSE en vivo y también drenada al final del turno del chat).
    action.setdefault("uid", f"act-{time.time_ns()}-{id(action)}")
    with _action_lock:
        _action_queues.setdefault(session_id or "_", []).append(action)
    _broadcast_action(action)


def drain_actions(session_id: str) -> List[Dict[str, Any]]:
    with _action_lock:
        return _action_queues.pop(session_id or "_", [])


def resolve_permission(request_id: str, reply: str) -> bool:
    """reply: 'once' | 'always' | 'reject'."""
    item = _pending_permissions.get(request_id)
    if not item:
        return False
    item["reply"] = reply if reply in ("once", "always", "reject") else "reject"
    item["event"].set()
    return True


def _resolve_model(model_id: str) -> Dict[str, str]:
    if model_id in MODEL_MAP:
        p, m = MODEL_MAP[model_id]
        return {"providerID": p, "modelID": m}
    return {"providerID": "google", "modelID": "gemini-flash-latest"}


class OpenCodeEngine:
    """Gestiona el servidor OpenCode y ejecuta prompts con streaming."""

    _proc: Optional[subprocess.Popen] = None
    _lock = threading.Lock()

    # ── ciclo de vida ────────────────────────────────────────────────────
    @staticmethod
    def installed() -> bool:
        return bool(shutil.which("opencode"))

    @staticmethod
    def healthy() -> bool:
        try:
            r = httpx.get(f"{OC_URL}/global/health", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    @classmethod
    def ensure_running(cls, timeout: float = 30.0) -> bool:
        if cls.healthy():
            return True
        exe = shutil.which("opencode")
        if not exe:
            return False
        with cls._lock:
            if cls.healthy():
                return True
            env = dict(os.environ)
            # Proveer variables para que OpenCode detecte Gemini y NVIDIA
            if settings.GEMINI_API_KEY:
                env["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
                env["GOOGLE_GENERATIVE_AI_API_KEY"] = settings.GEMINI_API_KEY
                env["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY
            if getattr(settings, "NVIDIA_API_KEY", ""):
                env["NVIDIA_API_KEY"] = settings.NVIDIA_API_KEY
            env["AETHERCUT_URL"] = f"http://127.0.0.1:{os.getenv('PORT', '8000')}"

            flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
            cls._proc = subprocess.Popen(
                [exe, "serve", "--port", str(OC_PORT), "--hostname", "127.0.0.1"],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            end = time.time() + timeout
            while time.time() < end:
                if cls.healthy():
                    return True
                time.sleep(0.4)
            return False

    @classmethod
    def shutdown(cls) -> None:
        if cls._proc and cls._proc.poll() is None:
            cls._proc.terminate()

    # ── sesiones ─────────────────────────────────────────────────────────
    @staticmethod
    def create_session(title: str = "AetherCopilot") -> str:
        r = httpx.post(f"{OC_URL}/session", json={"title": title[:60]}, timeout=15)
        r.raise_for_status()
        return r.json()["id"]

    @staticmethod
    def abort(session_id: str) -> None:
        try:
            httpx.post(f"{OC_URL}/session/{session_id}/abort", timeout=10)
        except Exception:
            pass

    # ── ejecución con streaming ──────────────────────────────────────────
    @classmethod
    def run_prompt(
        cls,
        message: str,
        model_id: str,
        session_id: Optional[str],
        emit: Callable[[Dict[str, Any]], None],
        context_note: str = "",
        max_seconds: float = 900.0,
    ) -> Dict[str, Any]:
        if not cls.ensure_running():
            raise RuntimeError("OpenCode no pudo iniciarse.")

        sid = session_id or cls.create_session(message[:50])
        model = _resolve_model(model_id)
        text = (context_note + "\n\n" + message).strip() if context_note else message

        text_parts: Dict[str, str] = {}
        part_order: List[str] = []
        reasoning_parts: Dict[str, str] = {}
        tool_seen: Dict[str, str] = {}
        tool_calls_executed: List[Dict[str, Any]] = []
        message_roles: Dict[str, str] = {}
        error_msg: Optional[str] = None

        def handle(evt: Dict[str, Any]) -> bool:
            """Devuelve True cuando la sesión terminó."""
            nonlocal error_msg
            etype = evt.get("type", "")
            props = evt.get("properties", {}) or {}

            # Rastrear qué mensajes son 'user' vs 'assistant'
            if etype == "message.updated":
                info = props.get("info", {}) or {}
                mid = info.get("id")
                role = info.get("role")
                if mid and role:
                    message_roles[mid] = role
                return False

            if etype == "message.part.updated":
                part = props.get("part", {}) or {}
                if part.get("sessionID") != sid:
                    return False

                mid = part.get("messageID", "")
                role = message_roles.get(mid, "assistant")
                # Solo procesar partes de respuesta del asistente (ignorar el prompt del usuario)
                if role == "user":
                    return False

                ptype, pid = part.get("type"), part.get("id", "")
                if ptype == "text" and not part.get("synthetic"):
                    if pid not in text_parts:
                        part_order.append(pid)
                    text_parts[pid] = part.get("text", "")
                    full_reply = "\n\n".join(text_parts[p] for p in part_order if text_parts[p].strip())
                    emit({"type": "text", "text": full_reply})

                elif ptype == "reasoning":
                    reasoning_parts[pid] = part.get("text", "")
                    full_reas = "\n".join(reasoning_parts.values())
                    emit({"type": "reasoning", "text": full_reas})

                elif ptype == "tool":
                    st = part.get("state", {}) or {}
                    status = st.get("status", "")
                    key = pid + ":" + status
                    tool_name = part.get("tool", "")
                    if tool_seen.get(pid) != key:
                        tool_seen[pid] = key
                        tool_item = {
                            "type": "tool",
                            "id": pid,
                            "tool": tool_name,
                            "status": status,
                            "title": st.get("title") or tool_name,
                            "input": st.get("input") or {},
                        }
                        if status in ("completed", "done", "success"):
                            tool_calls_executed.append(tool_item)
                        emit(tool_item)
                return False

            if etype in ("permission.asked", "permission.updated"):
                if props.get("sessionID") != sid:
                    return False
                rid = props.get("id", "")
                if rid in _pending_permissions:
                    return False
                ev = threading.Event()
                _pending_permissions[rid] = {"event": ev, "reply": "reject"}
                emit({
                    "type": "permission",
                    "id": rid,
                    "permission": props.get("permission") or props.get("type") or "",
                    "patterns": props.get("patterns") or props.get("pattern") or [],
                    "title": props.get("title") or "",
                })

                def waiter(rid=rid, ev=ev):
                    ev.wait(timeout=300)
                    reply = _pending_permissions.pop(rid, {}).get("reply", "reject")
                    try:
                        httpx.post(f"{OC_URL}/permission/{rid}/reply",
                                   json={"reply": reply}, timeout=15)
                    except Exception:
                        pass
                threading.Thread(target=waiter, daemon=True).start()
                return False

            if etype == "session.error":
                if props.get("sessionID") in (None, sid):
                    err = props.get("error", {}) or {}
                    error_msg = (err.get("data", {}) or {}).get("message") or err.get("name") or "Error de sesión"
                    return True
                return False

            if etype == "session.idle" and props.get("sessionID") == sid:
                return True

            if etype == "session.status" and props.get("sessionID") == sid:
                if (props.get("status", {}) or {}).get("type") == "idle":
                    return True

            return False

        emit({"type": "status", "message": "Iniciando motor OpenCode…"})
        started = time.time()
        with httpx.Client(timeout=httpx.Timeout(10.0, read=None)) as client:
            with client.stream("GET", f"{OC_URL}/event") as stream:
                # El stream ya está abierto: ahora sí se envía el prompt.
                body = {"parts": [{"type": "text", "text": text}], "model": model}
                r = client.post(f"{OC_URL}/session/{sid}/prompt_async", json=body, timeout=30)
                r.raise_for_status()
                emit({"type": "status", "message": "El agente está trabajando…"})

                data_lines: List[str] = []
                for line in stream.iter_lines():
                    if time.time() - started > max_seconds:
                        cls.abort(sid)
                        error_msg = "Tiempo máximo excedido."
                        break
                    if line.startswith("data:"):
                        data_lines.append(line[5:].strip())
                    elif line == "" and data_lines:
                        raw = "\n".join(data_lines)
                        data_lines = []
                        try:
                            evt = json.loads(raw)
                        except Exception:
                            continue
                        if handle(evt):
                            break

        reply = "\n\n".join(text_parts[p] for p in part_order if text_parts[p].strip()).strip()
        if error_msg and not reply:
            reply = f"⚠️ {error_msg}"
        elif not reply:
            reply = "Listo. Las operaciones fueron ejecutadas."

        return {
            "model_used": model_id,
            "reply": reply,
            "reasoning": "\n".join(reasoning_parts.values()),
            "actions": drain_actions(sid),
            "extra": {
                "oc_session_id": sid,
                "engine": "opencode",
                "tools_used": [t.get("tool") for t in tool_calls_executed],
            },
        }
