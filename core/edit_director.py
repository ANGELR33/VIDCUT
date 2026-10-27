"""Director de edición: decide CUÁNDO, DÓNDE y CÓMO aplicar énfasis visual y sonoro.

Antes, cada subtítulo con palabras resaltadas disparaba un zoom: el resultado era un video que se
movía sin criterio. El director puntúa cada momento y aplica reglas de oficio:

  - El énfasis se gana: cifras, preguntas, exclamaciones, palabras clave y frases cortas puntúan más.
  - Un zoom no se pone encima de una tarjeta o B-Roll (la imagen ya cambia; sumar movimiento cansa).
  - Separación mínima entre zooms y tope por minuto: el ritmo se nota por contraste, no por saturación.
  - Alterna "punch" (golpe rápido, énfasis) y "slow" (empuje lento, tensión) para no repetir el gesto.
  - Si pasan demasiados segundos sin ningún cambio visual, propone un "pattern interrupt" suave.
  - Los efectos de sonido siguen a lo visual (whoosh al entrar B-Roll, pop en tarjetas, impact en
    el énfasis más fuerte) con un tope de densidad.

El principio de fondo (creadores como Mario Joos o los editores de Hormozi) es que retiene la
información nueva y el contraste, no la velocidad de cortes en sí. Por eso aquí manda el tope.
Todo es función pura y se desactiva con ``EDIT_DIRECTOR=0`` (vuelve al comportamiento anterior).
Los umbrales son valores iniciales razonables, no verdades medidas: calibra con tus videos.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

_NUM = re.compile(r"\d")


@dataclass
class DirectorConfig:
    min_emphasis: float = 2.0       # puntaje mínimo para ganarse un zoom
    min_gap_sec: float = 4.0        # separación mínima entre inicios de zoom
    max_per_minute: float = 5.0     # tope de zooms por minuto de video
    min_caption_sec: float = 0.4    # subtítulos más breves no sostienen un zoom
    max_zoom_sec: float = 2.5
    static_gap_sec: float = 12.0    # sin cambio visual durante tanto tiempo -> pattern interrupt
    sfx_min_gap_sec: float = 2.5
    max_sfx_per_minute: float = 8.0
    overlay_margin_sec: float = 0.3


def enabled() -> bool:
    return os.getenv("EDIT_DIRECTOR", "1").strip().lower() not in ("0", "false", "no", "off")


def emphasis_score(cap: Any, is_first: bool = False) -> float:
    """Cuánto merece un momento ser enfatizado. 0 = nada."""
    text = (getattr(cap, "text", "") or "").strip()
    if not text:
        return 0.0
    score = 0.0
    score += min(2.0, 1.0 * len(getattr(cap, "highlight_words", []) or []))
    if _NUM.search(text):
        score += 1.0
    if "!" in text or "¡" in text:
        score += 1.0
    if "?" in text or "¿" in text:
        score += 0.5
    words = text.split()
    if 0 < len(words) <= 6:
        score += 0.5           # frase corta y contundente
    if is_first:
        score += 1.0           # el gancho pide energía
    return score


def _overlaps(start: float, end: float, windows: Sequence[Dict[str, float]], margin: float) -> bool:
    return any(start < w["end"] + margin and end > w["start"] - margin for w in windows)


def _windows(overlays: Sequence[Dict[str, Any]]) -> List[Dict[str, float]]:
    return [{"start": float(o["start"]), "end": float(o["start"]) + float(o.get("dur", 0)), "kind": o.get("kind", "")}
            for o in overlays if "start" in o]


def direct_edit(captions: Sequence[Any], overlays: Sequence[Dict[str, Any]], duration: float,
                cfg: DirectorConfig | None = None) -> Dict[str, Any]:
    """Devuelve {zooms, sfx, interrupts, report}. Los zooms tienen el formato que usa ``compose``."""
    cfg = cfg or DirectorConfig()
    wins = _windows(overlays)
    caps = sorted(captions, key=lambda c: c.start_sec)
    scored = []
    skipped = {"poco_enfasis": 0, "sobre_overlay": 0, "muy_breve": 0, "muy_cerca": 0, "tope_por_minuto": 0}

    for i, cap in enumerate(caps):
        dur = cap.end_sec - cap.start_sec
        if dur < cfg.min_caption_sec:
            skipped["muy_breve"] += 1
            continue
        score = emphasis_score(cap, is_first=(i == 0))
        if score < cfg.min_emphasis:
            skipped["poco_enfasis"] += 1
            continue
        scored.append((score, cap))

    # Se asignan primero los momentos más fuertes; luego se ordena en el tiempo.
    cap_total = max(1, int(round(max(duration, 1.0) / 60.0 * cfg.max_per_minute)))
    chosen: List[Dict[str, Any]] = []
    for score, cap in sorted(scored, key=lambda t: t[0], reverse=True):
        start = float(cap.start_sec)
        length = min(cap.end_sec - cap.start_sec, cfg.max_zoom_sec)
        if _overlaps(start, start + length, wins, cfg.overlay_margin_sec):
            skipped["sobre_overlay"] += 1
            continue
        if any(abs(start - z["start"]) < cfg.min_gap_sec for z in chosen):
            skipped["muy_cerca"] += 1
            continue
        if len(chosen) >= cap_total:
            skipped["tope_por_minuto"] += 1
            continue
        chosen.append({"start": round(start, 3), "dur": round(length, 3), "score": round(score, 2)})

    chosen.sort(key=lambda z: z["start"])
    for i, z in enumerate(chosen):
        z["style"] = "punch" if i % 2 == 0 else "slow"

    # Pattern interrupts: tramos largos sin zoom ni overlay.
    events = sorted([(z["start"], z["start"] + z["dur"]) for z in chosen] + [(w["start"], w["end"]) for w in wins])
    interrupts: List[Dict[str, Any]] = []
    cursor = 0.0
    for s, e in events + [(duration, duration)]:
        if s - cursor >= cfg.static_gap_sec:
            interrupts.append({"start": round(cursor, 2), "end": round(s, 2),
                               "suggestion": "zoom suave o B-Roll: tramo largo sin cambio visual"})
        cursor = max(cursor, e)

    sfx = plan_sfx(chosen, wins, duration, cfg)
    report = {
        "zooms": len(chosen), "per_minute": round(len(chosen) / max(duration / 60.0, 0.01), 2),
        "sfx": len(sfx), "static_stretches": len(interrupts), "skipped": skipped,
    }
    return {"zooms": chosen, "sfx": sfx, "interrupts": interrupts, "report": report}


def plan_sfx(zooms: Sequence[Dict[str, Any]], wins: Sequence[Dict[str, float]], duration: float,
             cfg: DirectorConfig) -> List[Dict[str, Any]]:
    """Efectos de sonido que acompañan a lo visual, con separación y tope de densidad."""
    candidates: List[Dict[str, Any]] = []
    for w in wins:
        candidates.append({"t": w["start"], "name": "pop" if w["kind"] == "card" else "whoosh", "priority": 2})
    if zooms:
        top = max(zooms, key=lambda z: z.get("score", 0))
        candidates.append({"t": top["start"], "name": "impact", "priority": 3})
    cap_total = max(1, int(round(max(duration, 1.0) / 60.0 * cfg.max_sfx_per_minute)))
    chosen: List[Dict[str, Any]] = []
    for c in sorted(candidates, key=lambda c: (-c["priority"], c["t"])):
        if len(chosen) >= cap_total:
            break
        if any(abs(c["t"] - x["t"]) < cfg.sfx_min_gap_sec for x in chosen):
            continue
        chosen.append(c)
    chosen.sort(key=lambda c: c["t"])
    return [{"t": round(c["t"], 3), "name": c["name"]} for c in chosen]


def duck_windows(speech: Sequence[Any], pad: float = 0.15) -> List[Dict[str, float]]:
    """Tramos donde la música debe bajar (cuando hay voz), fusionando los muy cercanos."""
    spans = sorted((max(0.0, c.start_sec - pad), c.end_sec + pad) for c in speech)
    merged: List[List[float]] = []
    for s, e in spans:
        if merged and s - merged[-1][1] <= 0.4:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [{"start": round(s, 2), "end": round(e, 2)} for s, e in merged]
