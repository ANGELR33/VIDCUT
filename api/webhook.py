"""Despachador asíncrono de Webhooks para notificar a sistemas externos.

Permite enviar eventos automáticos (video.completed, video.failed, streamer.completed)
a plataformas como Zapier, Make, n8n, Discord, Slack o servidores propios.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
from config.settings import settings
from core.llm import safe_log
from core.project_store import ProjectStore


async def dispatch_task_webhook(
    task_id: str,
    webhook_url: str,
    event_type: str,
    extra_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """Envía un webhook HTTP POST con el payload del proyecto y artefactos generados."""
    if not webhook_url or not str(webhook_url).startswith("http"):
        return False

    payload: Dict[str, Any] = {
        "event": event_type,
        "task_id": task_id,
        "project_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        store = ProjectStore(task_id)
        if store.manifest_path.exists():
            document = store.read()
            res = document.get("result") or {}
            title = res.get("title") or document.get("original_name") or f"AetherCut Video {task_id}"
            topic = res.get("topic") or (document.get("options") or {}).get("topic", "")
            duration = res.get("duration") or 0.0

            thumb_path = settings.OUTPUTS_DIR / f"{task_id}_thumbnail.jpg"
            master_path = settings.OUTPUTS_DIR / f"{task_id}_master.mp4"
            if not master_path.exists():
                cand = next(settings.OUTPUTS_DIR.glob(f"{task_id}_edit_*.mp4"), None)
                if cand:
                    master_path = cand

            # Clips verticales generados
            shorts = []
            for p in sorted(settings.OUTPUTS_DIR.glob(f"short_{task_id}_*.mp4")):
                try:
                    shorts.append({
                        "filename": p.name,
                        "url": f"/outputs/{p.name}",
                        "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                    })
                except OSError:
                    pass

            payload.update({
                "status": document.get("status", "unknown"),
                "title": title,
                "topic": topic,
                "duration_sec": round(duration, 2),
                "download_urls": {
                    "master_video": f"/media/{master_path.name}" if master_path.exists() else res.get("master_video_url"),
                    "thumbnail": f"/media/{thumb_path.name}" if thumb_path.exists() else None,
                    "subtitles_srt": f"/api/v1/projects/{task_id}/download/subtitles",
                    "transcript": f"/api/v1/projects/{task_id}/download/transcript",
                    "materials_zip": f"/api/v1/projects/{task_id}/materials/download",
                },
                "shorts": shorts,
                "error": document.get("error"),
            })
    except Exception as exc:
        safe_log(f"[Webhook] Error recopilando datos del proyecto {task_id}: {exc}")

    if extra_data:
        payload.update(extra_data)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "AetherCut-AI-API/1.0",
            }
            async with session.post(webhook_url, json=payload, headers=headers) as resp:
                success = (200 <= resp.status < 300)
                safe_log(f"[Webhook] Notificación enviada a {webhook_url} (HTTP {resp.status})")
                return success
    except Exception as exc:
        safe_log(f"[Webhook] Fallo al enviar webhook a {webhook_url}: {exc}")
        return False
