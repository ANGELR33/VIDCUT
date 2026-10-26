"""Línea de tiempo visual legible por la IA y por la interfaz.

El render trabaja por escenas, pero para auditar/editar hace falta un mapa
explícito de qué ocurre en cada segundo: escena, cortes internos, tarjeta,
subtítulos y fuente. Este módulo construye ese mapa desde el plan del director.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_visual_timeline(plan: Any, durations: Optional[List[float]] = None) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    cursor = 0.0

    for index, scene in enumerate(getattr(plan, "scenes", []) or []):
        duration = 0.0
        if durations and index < len(durations):
            duration = float(durations[index] or 0.0)
        if duration <= 0:
            duration = float(getattr(scene, "duration_est", 0.0) or 6.0)
        start = round(cursor, 2)
        end = round(cursor + duration, 2)
        scene_id = getattr(scene, "scene_id", index + 1)

        events.append({
            "type": "scene",
            "scene_id": scene_id,
            "start": start,
            "end": end,
            "name": str(getattr(scene, "name", "") or ""),
            "type_scene": str(getattr(scene, "type", "") or ""),
            "camera": str(getattr(scene, "camera", "") or ""),
            "emotion": str(getattr(scene, "emotion", "") or ""),
            "visual_query": str(getattr(scene, "visual_query", "") or ""),
            "speech": str(getattr(scene, "speech", "") or "")[:260],
        })

        beats = list(getattr(scene, "visual_beats", []) or [])
        for beat_index, beat in enumerate(beats, start=1):
            if not isinstance(beat, dict):
                continue
            at = start + round(duration * beat_index / (len(beats) + 1), 2)
            events.append({
                "type": "cut",
                "scene_id": scene_id,
                "at": at,
                "trigger": str(beat.get("trigger", "") or ""),
                "visual_query": str(beat.get("query", "") or ""),
            })

        card = getattr(scene, "card", None)
        if card:
            events.append({
                "type": "card",
                "scene_id": scene_id,
                "start": round(start + 0.5, 2),
                "end": round(max(start + 1.0, end - 0.6), 2),
                "template": str(getattr(card, "template", "") or "auto"),
                "headline": str(getattr(card, "headline", "") or ""),
                "stat": str(getattr(card, "stat", "") or ""),
                "source": str((getattr(card, "params", {}) or {}).get("source", "") or ""),
            })

        cursor = end

    return {
        "version": 1,
        "total_duration": round(cursor, 2),
        "events": events,
    }
