"""Piloto automático: investiga, pule con datos, crea, programa y publica solo.

Ciclo continuo por canal conectado:
  1. Planifica huecos en horas estratégicas (Shorts de sobra, 1-2 videos largos al día).
  2. Elige un tema de valor que la propia app investiga (nichos virales + radar de
     tendencias) que encaje con la etiqueta/palabras clave del canal y no se haya usado.
  3. SIEMPRE lo pule con datos reales (AI Producer: gancho, datos duros, brief).
  4. Crea el video (Short 9:16 o largo 16:9) con el mismo pipeline de la app.
  5. Genera metadatos y lo sube al canal correspondiente, programado para su hora.

Reutiliza los endpoints existentes de la app por HTTP local para no duplicar lógica.
"""

from __future__ import annotations

import json
import random
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config.settings import settings
from core.llm import safe_log

BASE_URL = "http://127.0.0.1:8000"
CONFIG_FILE = settings.STORAGE_DIR / "autopilot.json"
QUEUE_FILE = settings.STORAGE_DIR / "autopilot_queue.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "shorts_per_day": 3,          # por canal
    "longs_per_day": 1,           # por canal
    "publish_mode": "public",     # public = público directo | schedule = programado | private = privado para revisar
    "lookahead_hours": 30,
    "min_retention_score": 70,
    "short_duration_sec": 50,
    "long_duration_min": 10,
    "short_hours": [],            # vacío = horas estratégicas automáticas
    "long_hours": [],
    # La cuota diaria por defecto de la API de YouTube permite ~6 subidas al día en total.
    "max_uploads_per_day": 6,
    # Minutos de margen antes de publicar (ventana para revisar/cancelar en YouTube).
    "review_lead_minutes": 10,
    # Generar miniatura mejorada también para Shorts (usa fotogramas del video).
    "thumbnail_for_shorts": True,
    "require_manual_approval": True,
}

# Horas locales estratégicas (mañana, mediodía, tarde y noche) según cuántas toquen al día.
STRATEGIC_SHORT_HOURS = {
    1: [19], 2: [12, 19], 3: [8, 13, 20], 4: [8, 12, 18, 21],
    5: [7, 10, 13, 18, 21], 6: [7, 9, 12, 15, 18, 21],
}
STRATEGIC_LONG_HOURS = {1: [19], 2: [13, 19]}

MIN_LEAD_MINUTES = 40          # margen mínimo entre planificar y publicar
ACTIVE_STATES = ("researching", "polishing", "creating", "uploading")
STUCK_MINUTES = 150

_lock = threading.RLock()
_wake = threading.Event()
_thread: Optional[threading.Thread] = None
_started = False


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        safe_log(f"[Autopilot] No se pudo leer {path.name}: {exc}")
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_config() -> Dict[str, Any]:
    with _lock:
        cfg = dict(DEFAULT_CONFIG)
        stored = _read_json(CONFIG_FILE, {})
        if isinstance(stored, dict):
            cfg.update({k: v for k, v in stored.items() if k in DEFAULT_CONFIG})
        return cfg


def update_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        cfg = get_config()
        for key, value in (patch or {}).items():
            if key not in DEFAULT_CONFIG:
                continue
            default = DEFAULT_CONFIG[key]
            try:
                if isinstance(default, bool):
                    cfg[key] = bool(value)
                elif isinstance(default, int):
                    cfg[key] = int(value)
                elif isinstance(default, list):
                    cfg[key] = sorted({int(h) for h in value if 0 <= int(h) <= 23}) if isinstance(value, list) else []
                else:
                    cfg[key] = str(value)
            except (TypeError, ValueError):
                continue
        cfg["shorts_per_day"] = max(0, min(8, cfg["shorts_per_day"]))
        cfg["longs_per_day"] = max(0, min(3, cfg["longs_per_day"]))
        cfg["max_uploads_per_day"] = max(1, min(200, cfg["max_uploads_per_day"]))
        cfg["min_retention_score"] = max(0, min(100, cfg["min_retention_score"]))
        cfg["review_lead_minutes"] = max(5, min(180, cfg["review_lead_minutes"]))
        if cfg["publish_mode"] not in ("schedule", "private"):
            cfg["publish_mode"] = "schedule"
        _write_json(CONFIG_FILE, cfg)
    if cfg.get("enabled"):
        try:
            from core.universal_autopilot_tour import start_universal_tour_worker
            start_universal_tour_worker()
        except Exception:
            pass
    _wake.set()
    return cfg


def _load_jobs() -> List[Dict[str, Any]]:
    data = _read_json(QUEUE_FILE, [])
    return data if isinstance(data, list) else []


def _save_jobs(jobs: List[Dict[str, Any]]) -> None:
    _write_json(QUEUE_FILE, jobs[-400:])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _parse(value: str) -> datetime:
    return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _update_job(job_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    with _lock:
        jobs = _load_jobs()
        for job in jobs:
            if job.get("id") == job_id:
                msg = fields.pop("log", None)
                job.update(fields)
                job["updated_at"] = _iso(_now())
                if msg:
                    job.setdefault("log", []).append({"at": job["updated_at"], "msg": str(msg)[:240]})
                    job["log"] = job["log"][-25:]
                _save_jobs(jobs)
                return job
    return None


def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        for job in _load_jobs():
            if job.get("id") == job_id:
                return job
    return None


# ---------------------------------------------------------------------------
# Planificación de huecos por canal
# ---------------------------------------------------------------------------

def _hours_for(kind: str, cfg: Dict[str, Any]) -> List[int]:
    custom = cfg.get("short_hours" if kind == "short" else "long_hours") or []
    if custom:
        return list(custom)
    per_day = cfg["shorts_per_day"] if kind == "short" else cfg["longs_per_day"]
    table = STRATEGIC_SHORT_HOURS if kind == "short" else STRATEGIC_LONG_HOURS
    if per_day <= 0:
        return []
    return list(table[min(per_day, max(table))])


def _allowed_kinds(account: Dict[str, Any]) -> List[str]:
    kind = account.get("kind", "any")
    return ["short", "video"] if kind == "any" else [kind]


def _plan_slots() -> int:
    """Crea trabajos 'planned' para los huecos estratégicos que aún no tienen uno."""
    import core.youtube_oauth as yt
    cfg = get_config()
    accounts = yt.list_accounts() if yt.is_configured() else []
    if not accounts:
        return 0
    local_tz = datetime.now().astimezone().tzinfo
    now = _now()
    horizon = now + timedelta(hours=cfg["lookahead_hours"])
    created = 0
    with _lock:
        jobs = _load_jobs()
        existing = {(j.get("channel_id"), j.get("kind"), j.get("slot_at")) for j in jobs if j.get("status") != "cancelled"}
        today_local = datetime.now(local_tz).date()
        for account in accounts:
            for kind in _allowed_kinds(account):
                job_kind = "short" if kind == "short" else "long"
                for day in range(0, 4):
                    date = today_local + timedelta(days=day)
                    for hour in _hours_for(job_kind, cfg):
                        slot_local = datetime(date.year, date.month, date.day, hour, 0, tzinfo=local_tz)
                        slot_utc = slot_local.astimezone(timezone.utc)
                        if slot_utc < now + timedelta(minutes=MIN_LEAD_MINUTES) or slot_utc > horizon:
                            continue
                        slot_iso = _iso(slot_utc)
                        key = (account["channel_id"], job_kind, slot_iso)
                        if key in existing:
                            continue
                        jobs.append({
                            "id": uuid.uuid4().hex[:8],
                            "channel_id": account["channel_id"],
                            "channel_title": account.get("title", ""),
                            "channel_tag": account.get("tag", ""),
                            "kind": job_kind,
                            "slot_at": slot_iso,
                            "status": "planned",
                            "attempts": 0,
                            "progress": 0,
                            "created_at": _iso(now),
                            "updated_at": _iso(now),
                            "log": [],
                        })
                        existing.add(key)
                        created += 1
        if created:
            _save_jobs(jobs)
    return created


# ---------------------------------------------------------------------------
# Elección de tema
# ---------------------------------------------------------------------------

def _http_get(path: str, timeout: int = 30) -> Any:
    response = requests.get(f"{BASE_URL}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def _http_post(path: str, body: Dict[str, Any], timeout: int = 60) -> Any:
    response = requests.post(f"{BASE_URL}{path}", json=body, timeout=timeout)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text[:200])
        except Exception:
            detail = response.text[:200]
        raise RuntimeError(f"{path}: {detail}")
    return response.json()


def _candidate_topics() -> List[Dict[str, Any]]:
    """Temas que la app investiga sola: nichos virales en vivo + temas urgentes del radar."""
    topics: List[Dict[str, Any]] = []
    try:
        snap = _http_get("/api/viral-niches")
        for t in snap.get("topics", []):
            if t.get("title"):
                topics.append({
                    "title": t["title"],
                    "nuances": t.get("nuances", ""),
                    "category": t.get("category", ""),
                    "score": float(t.get("score", 60) or 60),
                    "durationMin": t.get("durationMin"),
                    "source": "nichos",
                })
    except Exception as exc:
        safe_log(f"[Autopilot] No se pudieron leer los nichos virales: {exc}")
    try:
        radar = _http_get("/api/trend-radar")
        for t in radar.get("topics", []) or []:
            title = t.get("title") or t.get("topic") or ""
            if title:
                topics.append({
                    "title": title,
                    "nuances": t.get("why") or t.get("reason") or t.get("description") or "",
                    "category": t.get("category", ""),
                    "score": float(t.get("score", 70) or 70) + 20,  # temas urgentes: bonus
                    "durationMin": None,
                    "source": "radar",
                })
    except Exception as exc:
        safe_log(f"[Autopilot] No se pudo leer el radar de tendencias: {exc}")
    return topics


def _used_titles(channel_id: str) -> set:
    cutoff = _now() - timedelta(days=21)
    used = set()
    for job in _load_jobs():
        title = job.get("topic")
        if not title or job.get("status") in ("cancelled",):
            continue
        try:
            when = _parse(job.get("created_at", _iso(_now())))
        except Exception:
            when = _now()
        if when >= cutoff:
            used.add(_norm(title))
    return used


def _pick_topic(account: Dict[str, Any], kind: str, skip: set) -> Optional[Dict[str, Any]]:
    candidates = _candidate_topics()
    if not candidates:
        return None
    used = _used_titles(account["channel_id"]) | skip
    terms = [account.get("tag", "")] + list(account.get("keywords") or [])
    terms = [_norm(t) for t in terms if t and t.strip()]

    scored = []
    for topic in candidates:
        if _norm(topic["title"]) in used:
            continue
        haystack = _norm(f"{topic['title']} {topic.get('category', '')} {topic.get('nuances', '')}")
        match = sum(1 for t in terms if t and t in haystack)
        score = topic["score"] + min(match, 3) * 40
        dur = topic.get("durationMin")
        if kind == "short":
            if isinstance(dur, (int, float)) and dur <= 12:
                score += 8
        else:
            if isinstance(dur, (int, float)) and dur >= 12:
                score += 10
        scored.append((score, match, topic))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    pool = scored[:3]
    # Si el canal tiene etiqueta/palabras clave, se prefiere lo que coincida.
    if terms and any(m > 0 for _, m, _ in pool):
        pool = [p for p in pool if p[1] > 0] or pool
    return random.choice(pool)[2]


# ---------------------------------------------------------------------------
# Producción de un trabajo
# ---------------------------------------------------------------------------

class _Cancelled(Exception):
    pass


def _check_cancel(job_id: str) -> None:
    job = _get_job(job_id)
    if not job or job.get("status") == "cancelled" or job.get("cancel"):
        raise _Cancelled()


def _poll_task(job_id: str, task_id: str, label: str, start_pct: float, end_pct: float, timeout_min: int) -> Dict[str, Any]:
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        _check_cancel(job_id)
        time.sleep(8)
        try:
            p = _http_get(f"/api/progress/{task_id}", timeout=20)
        except Exception:
            continue
        pct = float(p.get("progress", 0) or 0)
        _update_job(job_id, progress=round(start_pct + (end_pct - start_pct) * min(pct, 100) / 100, 1),
                    message=f"{label}: {p.get('message', '')}"[:160])
        if p.get("error"):
            raise RuntimeError(str(p["error"])[:300])
        if p.get("completed"):
            return p
    raise RuntimeError(f"{label}: tiempo de espera agotado")


def _capacity_ok(cfg: Dict[str, Any]) -> bool:
    """Respeta la cuota diaria de subidas de la API de YouTube."""
    cutoff = _now() - timedelta(hours=24)
    count = 0
    for job in _load_jobs():
        if job.get("status") in ACTIVE_STATES:
            count += 1
        elif job.get("uploaded_at"):
            try:
                if _parse(job["uploaded_at"]) >= cutoff:
                    count += 1
            except Exception:
                pass
    return count < cfg["max_uploads_per_day"]


def _polish_with_data(job_id: str, topic: Dict[str, Any], kind: str, min_score: int, channel_id: Optional[str] = None) -> Dict[str, Any]:
    from core.ai_producer import ai_producer_engine
    fmt = "reel" if kind == "short" else "long"
    brief = topic["title"]
    if topic.get("nuances"):
        brief = f"{topic['title']}. {topic['nuances'][:300]}"
    res = ai_producer_engine.enrich_and_audit(brief, fmt, channel_id=channel_id)
    if "error" in res:
        raise RuntimeError(res["error"])
    facts = res.get("supporting_facts") or []
    if not res.get("polished_prompt") or not facts:
        raise RuntimeError("El pulido con datos no devolvió datos verificables")
    if int(res.get("retention_score", 0) or 0) < min_score:
        raise RuntimeError(f"Puntuación de retención baja ({res.get('retention_score')})")
    return res


def _build_notes(polish: Dict[str, Any]) -> str:
    facts = "; ".join(
        f"{f.get('fact', '')} ({f.get('source_tag', '')})" for f in (polish.get("supporting_facts") or [])[:3]
    )
    notes = f"GANCHO: {polish.get('master_hook', '')} | DATOS: {facts} | ARTE: {polish.get('visual_atmosphere', '')}"
    return notes[:590]


def _produce(job: Dict[str, Any], cfg: Dict[str, Any], account: Dict[str, Any]) -> None:
    job_id = job["id"]
    kind = job["kind"]

    # 1-2. Tema de valor + pulido con datos (se reintenta con otro tema si no cumple)
    polish: Optional[Dict[str, Any]] = None
    topic: Optional[Dict[str, Any]] = None
    if not job.get("project_id"):
        skip: set = set()
        last_error = ""
        for attempt in range(3):
            _check_cancel(job_id)
            _update_job(job_id, status="researching", progress=3, message="Eligiendo un tema de valor...",
                        log="Buscando tema")
            topic = _pick_topic(account, kind, skip)
            if not topic:
                raise RuntimeError("No hay temas disponibles todavía; esperando a que la app investigue más.")
            skip.add(_norm(topic["title"]))
            _update_job(job_id, topic=topic["title"], topic_source=topic.get("source"), status="polishing",
                        progress=8, message="Puliendo con datos reales...", log=f"Tema: {topic['title'][:90]}")
            try:
                polish = _polish_with_data(job_id, topic, kind, cfg["min_retention_score"], channel_id=account.get("channel_id"))
                break
            except Exception as exc:
                last_error = str(exc)
                _update_job(job_id, log=f"Tema descartado: {last_error[:120]}")
        if not polish or not topic:
            raise RuntimeError(f"No se pudo pulir ningún tema con datos ({last_error})")
        _update_job(job_id, retention_score=polish.get("retention_score"), log="Pulido con datos completado")

        # 3. Crear el video con el pipeline de la app
        _check_cancel(job_id)
        polished_prompt = str(polish.get("polished_prompt", "")).strip()
        payload = {
            "topic": polished_prompt if 0 < len(polished_prompt) <= 300 else topic["title"],
            "style": "divulgacion",
            "duration_sec": cfg["short_duration_sec"] if kind == "short" else cfg["long_duration_min"],
            "aspect_ratio": "9:16" if kind == "short" else "16:9",
            "extra_notes": _build_notes(polish),
            "voice": "speechify:alejandro",
            "flash_audit": True,
            "origin": "autopilot",
            "auto_publish": False,
        }
        created = _http_post("/api/streamer/create", payload)
        project_id = created["project_id"]
        _update_job(job_id, status="creating", project_id=project_id, progress=12,
                    message="Creando video...", log=f"Proyecto {project_id} en producción")
        _poll_task(job_id, project_id, "Producción", 12, 80, timeout_min=120 if kind == "long" else 50)
    else:
        project_id = job["project_id"]
        master = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"
        if not (master.exists() and master.stat().st_size > 0):
            _update_job(job_id, status="creating", message="Reanudando producción...", log="Reanudando proyecto")
            try:
                _http_post(f"/api/projects/{project_id}/resume", {})
                _poll_task(job_id, project_id, "Producción", 12, 80, timeout_min=120)
            except Exception as exc:
                _update_job(job_id, project_id=None, log=f"No se pudo reanudar: {str(exc)[:100]}")
                raise

    # 4. Metadatos + miniatura mejorada (Shorts y largos) + subida programada
    _check_cancel(job_id)
    _update_job(job_id, status="uploading", progress=82, message="Preparando metadatos...", log="Preparando publicación")
    info = _http_get(f"/api/projects/{project_id}/publish-info", timeout=60)
    title = info.get("title") or (job.get("topic") or "Video")
    description = "\n\n".join(p for p in [info.get("description"), info.get("hashtags_str")] if p)
    tags = info.get("tags") or []

    # Puerta de calidad visual antes de publicar: el autopilot no debe subir
    # planos incoherentes, collages, texto cortado o anime.
    try:
        from core.vision_qa import vision_qa
        video_path = Path(info.get("video_path") or info.get("output_file") or (settings.OUTPUTS_DIR / f"{project_id}_master.mp4"))
        qa = vision_qa.audit_video(
            video_path=video_path,
            expected_niche=job.get("channel_tag") or job.get("channel_title") or "divulgación profesional",
            forbidden_elements=[
                "anime", "caricaturas", "collage", "texto cortado",
                "elementos incoherentes", "marcas de agua",
            ],
            channel_name=job.get("channel_title") or "Autopilot",
        )
        if not qa.get("approved", True):
            critique = qa.get("critique") or "Composición no aprobada"
            _update_job(
                job_id,
                status="failed",
                message=f"Rechazado por QA visual: {critique}",
                error=critique,
                log="QA visual rechazó el video; no se publica.",
            )
            return
    except Exception as qa_err:
        _update_job(job_id, log=f"QA visual no disponible: {str(qa_err)[:100]}")

    # Miniaturas: se generan para todos los tipos (shorts y largos)
    # Para Shorts se usa estilo viral/neón con fotograma del video
    # Para largos se usa estilo cinemático con fotograma del video
    thumbnail_url = None
    existing_thumb = settings.OUTPUTS_DIR / f"{project_id}_thumbnail.jpg"
    if existing_thumb.exists():
        thumbnail_url = f"/media/{existing_thumb.name}"
        _update_job(job_id, log=f"Miniatura editorial del proyecto: {thumbnail_url}")
    wants_thumb = kind == "long" or cfg.get("thumbnail_for_shorts", True)
    if wants_thumb and not thumbnail_url:
        thumb_style = "viral" if kind == "short" else "cinematic"
        try:
            prep = _http_post("/api/publish/prepare", {"project_id": project_id}, timeout=120)
            thumbnail_url = prep.get("thumbnail_url")
            if not thumbnail_url:
                # Generar miniatura: primero con fotograma del video (use_frame=True)
                thumb = _http_post("/api/publish/thumbnail", {
                    "project_id": project_id,
                    "title": title,
                    "topic": prep.get("topic") or title,
                    "style": thumb_style,
                    "use_frame": True,
                    "thumbnail_text": (title.split()[:4] and " ".join(title.split()[:4])) or title,
                }, timeout=240)
                thumbnail_url = thumb.get("url")
            _update_job(job_id, log=f"Miniatura lista ({thumb_style}): {thumbnail_url}")
        except Exception as exc:
            _update_job(job_id, log=f"Miniatura omitida: {str(exc)[:100]}")

    # Calcular ventana de revisión: review_lead_minutes para que el usuario
    # pueda entrar a YouTube Studio y cancelar/editar antes de que se publique.
    review_lead = int(cfg.get("review_lead_minutes", 10))
    publish_at = None
    privacy = "private"
    if cfg.get("require_manual_approval", True):
        # Modo seguro: subir privado, sin programar. Se publica solo tras aprobación.
        privacy = "private"
        publish_at = None
    elif cfg.get("publish_mode") == "public":
        privacy = "public"
        publish_at = None
    elif cfg.get("publish_mode") == "schedule":
        slot = _parse(job["slot_at"])
        # El publish_at es el MAX del slot planificado y ahora+review_lead,
        # de forma que siempre haya al menos review_lead minutos de ventana.
        publish_at = _iso(max(slot, _now() + timedelta(minutes=review_lead)))

    upload = _http_post("/api/publish/youtube/upload", {
        "project_id": project_id,
        "title": title,
        "description": description,
        "tags": tags,
        "privacy": privacy,
        "thumbnail_url": thumbnail_url,
        "channel_id": job["channel_id"],
        # Forzar el formato segun el tipo de job para garantizar que los Shorts
        # reciban prepare_shorts_metadata (titulo + descripcion con #Shorts)
        # sin depender de detect_format que puede fallar si el archivo no existe aun.
        "format": "short" if kind == "short" else "video",
        "publish_at": publish_at,
    })
    result = _poll_task(job_id, upload["task_id"], "Subida a YouTube", 84, 99, timeout_min=90)
    res = result.get("result") or {}
    _update_job(
        job_id,
        status="scheduled" if publish_at else ("public" if privacy == "public" else "uploaded_private"),
        progress=100,
        message="Programado en YouTube" if publish_at else ("Publicado en YouTube" if privacy == "public" else "Subido en privado para revisar"),
        video_url=res.get("video_url", ""),
        video_id=res.get("video_id", ""),
        title=title,
        publish_at=publish_at,
        uploaded_at=_iso(_now()),
        log=f"Listo: {res.get('video_url', '')}",
    )
    try:
        from core.channel_intelligence import channel_intelligence
        channel_intelligence.register_video(
            project_id=project_id,
            channel_id=job["channel_id"],
            title=title,
            topic=job.get("topic") or title,
            format_mode="short" if kind == "short" else "video",
            video_id=res.get("video_id", ""),
            video_url=res.get("video_url", ""),
            structure_type=polish.get("chosen_structure", "") if polish else "",
            hook_type=polish.get("chosen_hook_type", "") if polish else "",
            retention_score=int(polish.get("retention_score", 85) or 85) if polish else 85,
        )
    except Exception as _reg_err:
        safe_log(f"[Autopilot] Aviso registrando en inteligencia de canal: {_reg_err}")

    # Cross-posting a Página Hermana de Facebook (si está configurada para este canal)
    try:
        from core.facebook_publisher import auto_cross_post_for_channel
        master_file = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"
        if master_file.exists():
            fb_res = auto_cross_post_for_channel(
                channel_id=job["channel_id"],
                video_path=master_file,
                title=title,
                description=description,
                is_reel=(kind == "short"),
            )
            if fb_res:
                _update_job(job_id, log=f"Cross-posting en Facebook: {fb_res.get('post_url')}")
    except Exception as _fb_err:
        safe_log(f"[Autopilot] Aviso cross-posting Facebook: {_fb_err}")


def _process_job(job: Dict[str, Any]) -> None:
    import core.youtube_oauth as yt
    cfg = get_config()
    job_id = job["id"]
    account = next((a for a in yt.list_accounts() if a["channel_id"] == job["channel_id"]), None)
    if not account:
        _update_job(job_id, status="failed", message="El canal ya no está conectado", log="Canal desconectado")
        return
    _update_job(job_id, attempts=job.get("attempts", 0) + 1, cancel=False)
    try:
        _produce(_get_job(job_id) or job, cfg, account)
    except _Cancelled:
        _update_job(job_id, status="cancelled", message="Cancelado", log="Cancelado por el usuario")
    except Exception as exc:
        safe_log(f"[Autopilot] Fallo en {job_id}: {exc}")
        _update_job(job_id, status="failed", message=str(exc)[:200], error=str(exc)[:300],
                    log=f"Error: {str(exc)[:160]}")


# ---------------------------------------------------------------------------
# Bucle principal
# ---------------------------------------------------------------------------

def _recover_and_retry() -> None:
    """Reanuda trabajos interrumpidos y reintenta los fallidos tras un tiempo de espera."""
    now = _now()
    with _lock:
        jobs = _load_jobs()
        changed = False
        for job in jobs:
            status = job.get("status")
            try:
                age = now - _parse(job.get("updated_at", _iso(now)))
            except Exception:
                age = timedelta(0)
            if status in ACTIVE_STATES and age > timedelta(minutes=STUCK_MINUTES):
                job["status"] = "planned"
                job.setdefault("log", []).append({"at": _iso(now), "msg": "Trabajo atascado: se reintenta"})
                changed = True
            elif status == "failed" and job.get("attempts", 0) < 3 and age > timedelta(minutes=15):
                job["status"] = "planned"
                job.setdefault("log", []).append({"at": _iso(now), "msg": "Reintento automático"})
                changed = True
        if changed:
            _save_jobs(jobs)


def _next_job() -> Optional[Dict[str, Any]]:
    with _lock:
        planned = [j for j in _load_jobs() if j.get("status") == "planned"]
    if not planned:
        return None
    planned.sort(key=lambda j: (j.get("slot_at", ""), 0 if j.get("kind") == "short" else 1))
    return planned[0]


def _server_ready() -> bool:
    try:
        requests.get(f"{BASE_URL}/api/viral-niches", timeout=5)
        return True
    except Exception:
        return False


def _worker_loop() -> None:
    safe_log("[Autopilot] Motor iniciado.")
    # Tras un reinicio, lo que estaba en curso vuelve a la cola, salvo ranuras vencidas.
    with _lock:
        jobs = _load_jobs()
        cutoff = _now() - timedelta(hours=2)
        for job in jobs:
            if job.get("status") in ACTIVE_STATES:
                try:
                    slot = _parse(job.get("slot_at", ""))
                except Exception:
                    slot = None
                if slot is not None and slot < cutoff:
                    job["status"] = "cancelled"
                    job["message"] = "Cancelado: ranura vencida; no se publica tarde."
                    job.setdefault("log", []).append(
                        {"at": _iso(_now()), "msg": "Cancelado por ranura vencida."}
                    )
                else:
                    job["status"] = "planned"
        _save_jobs(jobs)
    while True:
        try:
            cfg = get_config()
            if cfg["enabled"] and _server_ready():
                _recover_and_retry()
                _plan_slots()
                job = _next_job()
                if job:
                    if _capacity_ok(cfg):
                        _process_job(job)
                        continue  # siguiente trabajo sin esperar
                    _update_job(job["id"], message="Esperando cuota diaria de subidas de YouTube")
        except Exception as exc:
            safe_log(f"[Autopilot] Error en el bucle: {exc}")
        _wake.wait(timeout=45)
        _wake.clear()


def start() -> None:
    global _thread, _started
    if _started:
        return
    _started = True
    _thread = threading.Thread(target=_worker_loop, name="autopilot", daemon=True)
    _thread.start()


# ---------------------------------------------------------------------------
# Interfaz para la API
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    import core.youtube_oauth as yt
    cfg = get_config()
    jobs = _load_jobs()
    now = _now()
    local_tz = datetime.now().astimezone().tzinfo
    today = datetime.now(local_tz).date()

    channels = []
    for account in (yt.list_accounts() if yt.is_configured() else []):
        mine = [j for j in jobs if j.get("channel_id") == account["channel_id"]]

        def count(kind: str) -> int:
            n = 0
            for j in mine:
                if j.get("kind") != kind or j.get("status") in ("cancelled", "failed"):
                    continue
                try:
                    if _parse(j["slot_at"]).astimezone(local_tz).date() == today:
                        n += 1
                except Exception:
                    pass
            return n

        channels.append({
            **account,
            "today_shorts": count("short"),
            "today_longs": count("long"),
            "scheduled_total": sum(1 for j in mine if j.get("status") == "scheduled"),
        })

    visible = sorted(
        [j for j in jobs if j.get("status") != "cancelled"],
        key=lambda j: j.get("slot_at", ""),
    )
    upcoming = [j for j in visible if j.get("status") in ("planned",) + ACTIVE_STATES or j.get("status") in ("scheduled", "uploaded_private", "failed")]
    cutoff = now - timedelta(hours=12)
    upcoming = [j for j in upcoming if j.get("status") != "scheduled" or _parse(j.get("slot_at", _iso(now))) >= cutoff]
    running = next((j for j in jobs if j.get("status") in ACTIVE_STATES), None)

    uploads_24h = 0
    for j in jobs:
        if j.get("uploaded_at"):
            try:
                if _parse(j["uploaded_at"]) >= now - timedelta(hours=24):
                    uploads_24h += 1
            except Exception:
                pass

    return {
        "config": cfg,
        "channels": channels,
        "jobs": upcoming[-80:],
        "running": running,
        "uploads_24h": uploads_24h,
        "hours": {
            "short": _hours_for("short", cfg),
            "long": _hours_for("long", cfg),
        },
        "timezone": str(datetime.now().astimezone().tzinfo),
        "server_time": _iso(now),
    }


def retry_job(job_id: str) -> bool:
    job = _update_job(job_id, status="planned", attempts=0, error=None, message="En cola", log="Reintento manual")
    _wake.set()
    return bool(job)


def cancel_job(job_id: str) -> bool:
    job = _get_job(job_id)
    if not job:
        return False
    if job.get("project_id") and job.get("status") in ACTIVE_STATES:
        try:
            requests.post(f"{BASE_URL}/api/cancel-task/{job['project_id']}", timeout=10)
        except Exception:
            pass
    _update_job(job_id, status="cancelled", cancel=True, message="Cancelado", log="Cancelado")
    return True


def run_now() -> None:
    _wake.set()
