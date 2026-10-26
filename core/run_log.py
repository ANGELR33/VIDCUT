"""Registro estructurado de ejecuciones (observabilidad) para cualquier tipo de contenido.

Cada ejecución (edición de video, Short, anime, podcast, geopolítica, etc.) crea un
``RunLog`` que guarda, dentro de la carpeta del proyecto:

- ``run_events.jsonl``: un evento por línea (etapa, nivel, mensaje, datos).
- ``run_report.json`` y ``run_report.md``: resumen con duración por etapa, llamadas,
  tokens y latencia por modelo, costo estimado, contadores, advertencias y salidas.

Los módulos de bajo nivel (``llm.py``, proveedores, etc.) registran sin necesidad de
recibir el objeto: usan ``current()``, que apunta a la ejecución activa (ContextVar).
Si no hay ejecución activa, todas las funciones ``log_*`` son no-ops.

Los costos se calculan con ``config/pricing.json`` (editable). Si un modelo no tiene
tarifa, el reporte lo indica como "sin tarifa" en lugar de inventar un precio.
Ninguna clave o token se escribe en el log: todo texto pasa por ``redact``.
"""

from __future__ import annotations

import contextvars
import json
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_PRICING_PATH = Path(__file__).resolve().parent.parent / "config" / "pricing.json"

_SECRET_PATTERNS = [
    re.compile(r"nvapi-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"sk_[A-Za-z0-9]{16,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AQ\.[A-Za-z0-9_\-]{20,}"),
    re.compile(r"GOCSPX-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"aethercut_live_[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"),
    re.compile(r"(?i)((?:api[_-]?key|secret|token|password)\s*[=:]\s*)[^\s,;&\"']{6,}"),
]


def redact(value: Any) -> Any:
    """Oculta claves y tokens en cualquier texto (recursivo en dict/list)."""
    if isinstance(value, str):
        out = value
        for pattern in _SECRET_PATTERNS:
            if pattern.groups:
                out = pattern.sub(lambda m: m.group(1) + "***", out)
            else:
                out = pattern.sub("***", out)
        return out
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def load_pricing(path: Optional[Path] = None) -> Dict[str, Any]:
    try:
        return json.loads((path or _PRICING_PATH).read_text(encoding="utf-8"))
    except Exception:
        return {}


def estimate_llm_cost(pricing: Dict[str, Any], model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """USD estimados, o None si el modelo no tiene tarifa configurada.

    Las tarifas son USD por 1 millón de tokens y se buscan por prefijo del nombre del modelo.
    """
    models = pricing.get("llm_per_million_tokens", {}) or {}
    name = (model or "").lower()
    best = None
    for prefix, rates in models.items():
        if prefix.startswith("_"):
            continue
        if name.startswith(prefix.lower()) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, rates)
    if not best:
        return None
    rates = best[1] or {}
    inp, out = rates.get("input"), rates.get("output")
    if inp is None or out is None:
        return None
    return (input_tokens * float(inp) + output_tokens * float(out)) / 1_000_000


_current: contextvars.ContextVar[Optional["RunLog"]] = contextvars.ContextVar("aethercut_run", default=None)


def current() -> Optional["RunLog"]:
    return _current.get()


class RunLog:
    def __init__(self, workdir: Path, content_type: str, mechanism: str,
                 run_id: Optional[str] = None, meta: Optional[Dict[str, Any]] = None,
                 pricing: Optional[Dict[str, Any]] = None):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.content_type = content_type
        self.mechanism = mechanism
        self.meta = redact(meta or {})
        self.pricing = pricing if pricing is not None else load_pricing()
        self.started_at = datetime.now(timezone.utc)
        self._t0 = time.monotonic()
        self._lock = threading.RLock()
        self._events_path = self.workdir / "run_events.jsonl"
        self._stages: List[Dict[str, Any]] = []
        self._open_stage: Optional[Dict[str, Any]] = None
        self._llm: Dict[str, Dict[str, Any]] = {}
        self._services: Dict[str, Dict[str, Any]] = {}
        self._counters: Dict[str, float] = {}
        self._issues: List[Dict[str, Any]] = []
        self._token = None
        self.status = "running"

    # ---- ciclo de vida ----
    @classmethod
    def start(cls, workdir: Path, content_type: str, mechanism: str, **kwargs: Any) -> "RunLog":
        run = cls(workdir, content_type, mechanism, **kwargs)
        run._token = _current.set(run)
        run.event("run", f"Inicio de ejecución ({content_type} / {mechanism})", **run.meta)
        return run

    def _elapsed(self) -> float:
        return round(time.monotonic() - self._t0, 3)

    # ---- eventos y etapas ----
    def event(self, stage: str, message: str, level: str = "info", **data: Any) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "t": self._elapsed(), "run": self.run_id, "stage": stage,
            "level": level, "message": redact(message), "data": redact(data),
        }
        with self._lock:
            try:
                with self._events_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            except OSError:
                pass
            if level in ("warning", "error"):
                self._issues.append({"t": record["t"], "stage": stage, "level": level,
                                     "message": record["message"][:300]})

    def warn(self, stage: str, message: str, **data: Any) -> None:
        self.event(stage, message, level="warning", **data)

    def error(self, stage: str, message: str, **data: Any) -> None:
        self.event(stage, message, level="error", **data)

    def begin_stage(self, name: str) -> None:
        """Abre una etapa; si había otra abierta, la cierra primero."""
        with self._lock:
            if self._open_stage and self._open_stage["name"] == name:
                return
            self.end_stage()
            self._open_stage = {"name": name, "start": self._elapsed(), "_t": time.monotonic()}

    def end_stage(self, ok: bool = True) -> None:
        with self._lock:
            stage = self._open_stage
            if not stage:
                return
            self._stages.append({
                "name": stage["name"], "start_sec": stage["start"],
                "duration_sec": round(time.monotonic() - stage["_t"], 2), "ok": ok,
            })
            self._open_stage = None

    @contextmanager
    def stage(self, name: str):
        self.begin_stage(name)
        try:
            yield
        except BaseException:
            self.end_stage(ok=False)
            raise
        else:
            self.end_stage()

    def on_state(self, step: str, message: str) -> None:
        """Enlace con el callback de progreso del pipeline."""
        self.begin_stage(step)
        self.event(step, message)

    # ---- métricas ----
    def count(self, name: str, n: float = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + n

    def record_llm(self, provider: str, model: str, purpose: str = "", input_tokens: int = 0,
                   output_tokens: int = 0, latency_sec: float = 0.0, ok: bool = True,
                   error: str = "", fallback: bool = False) -> None:
        key = f"{provider}:{model}"
        with self._lock:
            row = self._llm.setdefault(key, {
                "provider": provider, "model": model, "calls": 0, "failures": 0, "fallback_calls": 0,
                "input_tokens": 0, "output_tokens": 0, "latency_total_sec": 0.0, "purposes": {},
            })
            row["calls"] += 1
            row["failures"] += 0 if ok else 1
            row["fallback_calls"] += 1 if fallback else 0
            row["input_tokens"] += int(input_tokens or 0)
            row["output_tokens"] += int(output_tokens or 0)
            row["latency_total_sec"] += float(latency_sec or 0.0)
            if purpose:
                row["purposes"][purpose] = row["purposes"].get(purpose, 0) + 1
        self.event("llm", f"{key} {'OK' if ok else 'FALLÓ'} ({purpose or 'sin propósito'})",
                   level="info" if ok else "warning", input_tokens=input_tokens,
                   output_tokens=output_tokens, latency_sec=round(latency_sec, 2),
                   fallback=fallback, error=error[:200] if error else "")

    def record_service(self, service: str, units: float = 1, unit_name: str = "llamadas",
                       cost_usd: Optional[float] = None, ok: bool = True) -> None:
        """Servicios que no son LLM (TTS, búsqueda, descargas, cuota de YouTube, etc.)."""
        with self._lock:
            row = self._services.setdefault(service, {
                "service": service, "unit_name": unit_name, "units": 0.0, "calls": 0,
                "failures": 0, "cost_usd": 0.0, "cost_known": True,
            })
            row["units"] += units
            row["calls"] += 1
            row["failures"] += 0 if ok else 1
            unit_price = (self.pricing.get("services_per_unit", {}) or {}).get(service)
            if cost_usd is not None:
                row["cost_usd"] += cost_usd
            elif isinstance(unit_price, (int, float)):
                row["cost_usd"] += units * unit_price
            else:
                row["cost_known"] = False

    # ---- cierre y reporte ----
    def summary(self, outputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            llm_rows, total_cost, unknown = [], 0.0, []
            for row in self._llm.values():
                cost = estimate_llm_cost(self.pricing, row["model"], row["input_tokens"], row["output_tokens"])
                if cost is None:
                    unknown.append(f"{row['provider']}:{row['model']}")
                else:
                    total_cost += cost
                avg = row["latency_total_sec"] / row["calls"] if row["calls"] else 0.0
                llm_rows.append({**row, "avg_latency_sec": round(avg, 2),
                                 "latency_total_sec": round(row["latency_total_sec"], 2),
                                 "cost_usd": None if cost is None else round(cost, 6)})
            service_rows = []
            for row in self._services.values():
                if row["cost_known"]:
                    total_cost += row["cost_usd"]
                else:
                    unknown.append(f"servicio:{row['service']}")
                service_rows.append({**row, "cost_usd": round(row["cost_usd"], 6) if row["cost_known"] else None})
            return {
                "run_id": self.run_id,
                "content_type": self.content_type,
                "mechanism": self.mechanism,
                "status": self.status,
                "started_at": self.started_at.isoformat(timespec="seconds"),
                "duration_sec": self._elapsed(),
                "meta": self.meta,
                "stages": list(self._stages),
                "llm": llm_rows,
                "services": service_rows,
                "counters": dict(self._counters),
                "cost": {
                    "currency": "USD", "estimated_total": round(total_cost, 6),
                    "partial": bool(unknown), "without_rate": sorted(set(unknown)),
                    "note": "Estimación según config/pricing.json; no es una factura.",
                },
                "issues": self._issues[-25:],
                "issue_counts": {
                    "warnings": sum(1 for i in self._issues if i["level"] == "warning"),
                    "errors": sum(1 for i in self._issues if i["level"] == "error"),
                },
                "outputs": redact(outputs or {}),
            }

    def finalize(self, status: str = "completed", outputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.end_stage(ok=status == "completed")
        self.status = status
        self.event("run", f"Fin de ejecución: {status}", level="info" if status == "completed" else "warning")
        report = self.summary(outputs)
        try:
            (self.workdir / "run_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            (self.workdir / "run_report.md").write_text(render_markdown(report), encoding="utf-8")
        except OSError:
            pass
        if self._token is not None:
            try:
                _current.reset(self._token)
            except ValueError:
                _current.set(None)
            self._token = None
        return report


def _fmt_cost(value: Optional[float]) -> str:
    return "sin tarifa" if value is None else f"${value:.4f}"


def render_markdown(report: Dict[str, Any]) -> str:
    cost = report["cost"]
    lines = [
        f"# Reporte de ejecución `{report['run_id']}`",
        "",
        f"- **Contenido:** {report['content_type']}  ·  **Mecanismo:** {report['mechanism']}",
        f"- **Estado:** {report['status']}  ·  **Inicio:** {report['started_at']}  ·  "
        f"**Duración:** {report['duration_sec']:.1f} s",
        f"- **Costo estimado:** ${cost['estimated_total']:.4f} USD"
        + (" (parcial: faltan tarifas)" if cost["partial"] else ""),
        f"- **Avisos:** {report['issue_counts']['warnings']}  ·  **Errores:** {report['issue_counts']['errors']}",
        "",
    ]
    if report["stages"]:
        lines += ["## Etapas", "", "| Etapa | Inicio (s) | Duración (s) | OK |", "|---|---:|---:|:--:|"]
        lines += [f"| {s['name']} | {s['start_sec']:.1f} | {s['duration_sec']:.1f} | {'sí' if s['ok'] else 'no'} |"
                  for s in report["stages"]]
        lines.append("")
    if report["llm"]:
        lines += ["## Modelos de IA", "",
                  "| Proveedor / modelo | Llamadas | Fallos | Respaldo | Tokens in | Tokens out | Latencia media (s) | Costo |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        lines += [f"| {r['provider']} / {r['model']} | {r['calls']} | {r['failures']} | {r['fallback_calls']} | "
                  f"{r['input_tokens']} | {r['output_tokens']} | {r['avg_latency_sec']} | {_fmt_cost(r['cost_usd'])} |"
                  for r in report["llm"]]
        lines.append("")
    if report["services"]:
        lines += ["## Otros servicios", "", "| Servicio | Llamadas | Unidades | Fallos | Costo |", "|---|---:|---:|---:|---:|"]
        lines += [f"| {r['service']} | {r['calls']} | {r['units']:g} {r['unit_name']} | {r['failures']} | "
                  f"{_fmt_cost(r['cost_usd'])} |" for r in report["services"]]
        lines.append("")
    if report["counters"]:
        lines += ["## Contadores", ""] + [f"- {k}: {v:g}" for k, v in sorted(report["counters"].items())] + [""]
    if report["issues"]:
        lines += ["## Avisos y errores recientes", ""]
        lines += [f"- `{i['t']:.1f}s` [{i['level']}] **{i['stage']}**: {i['message']}" for i in report["issues"]]
        lines.append("")
    if report["outputs"]:
        lines += ["## Salidas", "", "```json", json.dumps(report["outputs"], ensure_ascii=False, indent=2, default=str), "```", ""]
    if cost["without_rate"]:
        lines += ["> Sin tarifa configurada: " + ", ".join(cost["without_rate"]) +
                  ". Edita `config/pricing.json` para completar el costo.", ""]
    return "\n".join(lines)


# ---- helpers de bajo nivel (no-op sin ejecución activa) ----
def log_llm(provider: str, model: str, purpose: str = "", input_tokens: int = 0, output_tokens: int = 0,
            latency_sec: float = 0.0, ok: bool = True, error: str = "", fallback: bool = False) -> None:
    run = current()
    if run:
        run.record_llm(provider, model, purpose, input_tokens, output_tokens, latency_sec, ok, error, fallback)


def log_service(service: str, units: float = 1, unit_name: str = "llamadas",
                cost_usd: Optional[float] = None, ok: bool = True) -> None:
    run = current()
    if run:
        run.record_service(service, units, unit_name, cost_usd, ok)


def log_count(name: str, n: float = 1) -> None:
    run = current()
    if run:
        run.count(name, n)


def log_event(stage: str, message: str, level: str = "info", **data: Any) -> None:
    run = current()
    if run:
        run.event(stage, message, level, **data)


def logged_run(content_type: str, mechanism: str, workdir_arg: str = "workdir") -> Callable:
    """Decorador para cualquier flujo de contenido (anime, podcast, geopolítica...).

    Envuelve una función (sync o async) que reciba ``workdir`` como argumento con nombre.
    Crea el RunLog, lo cierra con estado ``completed``/``failed`` y escribe el reporte.
    """
    import asyncio
    import inspect

    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)

        def _workdir(args, kwargs) -> Path:
            bound = sig.bind_partial(*args, **kwargs)
            value = bound.arguments.get(workdir_arg)
            return Path(value) if value else Path("storage") / "projects" / uuid.uuid4().hex[:8]

        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                run = RunLog.start(_workdir(args, kwargs), content_type, mechanism)
                try:
                    result = await fn(*args, **kwargs)
                    run.finalize("completed")
                    return result
                except BaseException as exc:
                    run.error("run", f"{type(exc).__name__}: {exc}")
                    run.finalize("cancelled" if type(exc).__name__ == "CancellationRequested" else "failed")
                    raise
            return async_wrapper

        @wraps(fn)
        def wrapper(*args, **kwargs):
            run = RunLog.start(_workdir(args, kwargs), content_type, mechanism)
            try:
                result = fn(*args, **kwargs)
                run.finalize("completed")
                return result
            except BaseException as exc:
                run.error("run", f"{type(exc).__name__}: {exc}")
                run.finalize("cancelled" if type(exc).__name__ == "CancellationRequested" else "failed")
                raise
        return wrapper

    return decorator
