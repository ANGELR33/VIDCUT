"""Ajusta los Shorts a límites de frase para que no empiecen ni terminen a media oración.

Los tiempos de Gemini suelen caer en medio de una palabra. Con las frases de Whisper se
mueve el inicio al comienzo de la frase que lo contiene y el final al cierre de la frase
más cercana, respetando la duración permitida (15-70 s). También se descartan Shorts que
se solapan casi por completo con otro (se conserva el de mayor puntaje de viralidad).
Función pura: no usa red ni modelos.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

MIN_SHORT_SEC = 15.0
MAX_SHORT_SEC = 70.0


def _snap_start(start: float, captions: Sequence[Any], lookback: float) -> float:
    """Inicio de la frase que contiene `start`, o el de la primera frase si cae en un hueco (<= lookback)."""
    for cap in captions:
        if cap.start_sec <= start < cap.end_sec:
            return cap.start_sec if start - cap.start_sec <= lookback else start
    before = [c for c in captions if c.end_sec <= start and start - c.end_sec <= 0.5]
    after = [c for c in captions if c.start_sec >= start and c.start_sec - start <= 1.5]
    if after:
        return min(after, key=lambda c: c.start_sec).start_sec
    return before[-1].end_sec if before else start


def _snap_end(end: float, captions: Sequence[Any], lookahead: float) -> float:
    for cap in captions:
        if cap.start_sec < end <= cap.end_sec:
            return cap.end_sec if cap.end_sec - end <= lookahead else cap.start_sec
    return end


def snap_highlights(highlights: Sequence[Any], captions: Sequence[Any], duration: float,
                    lookback: float = 3.0, lookahead: float = 4.0, overlap_ratio: float = 0.6) -> List[Dict[str, Any]]:
    """Modifica los Shorts en su sitio y devuelve el registro de cambios.

    Cada cambio: {clip_id, action: 'snapped'|'dropped', ...}. Los descartados se eliminan de
    la lista original (si es una lista mutable).
    """
    changes: List[Dict[str, Any]] = []
    caps = sorted(captions or [], key=lambda c: c.start_sec)

    for clip in list(highlights):
        old = (clip.start_sec, clip.end_sec)
        if caps:
            new_start = _snap_start(clip.start_sec, caps, lookback)
            new_end = _snap_end(clip.end_sec, caps, lookahead)
            if new_end - new_start > MAX_SHORT_SEC:  # no pasarse: recortar al final de frase anterior
                prior = [c.end_sec for c in caps if new_start + MIN_SHORT_SEC <= c.end_sec <= new_start + MAX_SHORT_SEC]
                new_end = prior[-1] if prior else new_start + MAX_SHORT_SEC
            if new_end - new_start < MIN_SHORT_SEC:  # muy corto: extender hasta la siguiente frase válida
                later = [c.end_sec for c in caps if c.end_sec >= new_start + MIN_SHORT_SEC][:1]
                if later and later[0] - new_start <= MAX_SHORT_SEC:
                    new_end = later[0]
            clip.start_sec = max(0.0, new_start)
            clip.end_sec = min(float(duration), max(clip.start_sec + 1.0, new_end))
        if (clip.start_sec, clip.end_sec) != old:
            changes.append({"clip_id": clip.clip_id, "action": "snapped",
                            "from": [round(old[0], 2), round(old[1], 2)],
                            "to": [round(clip.start_sec, 2), round(clip.end_sec, 2)]})

    # Quitar duplicados casi idénticos: gana el de mayor puntaje.
    ranked = sorted(list(highlights), key=lambda c: c.virality_score, reverse=True)
    kept: List[Any] = []
    for clip in ranked:
        span = max(0.1, clip.end_sec - clip.start_sec)
        dup = next((k for k in kept
                    if max(0.0, min(k.end_sec, clip.end_sec) - max(k.start_sec, clip.start_sec)) / span >= overlap_ratio), None)
        if dup is not None:
            changes.append({"clip_id": clip.clip_id, "action": "dropped", "reason": f"se solapa con {dup.clip_id}"})
            try:
                highlights.remove(clip)
            except (AttributeError, ValueError):
                pass
        else:
            kept.append(clip)
    return changes
