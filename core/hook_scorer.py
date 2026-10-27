"""Puntuación del gancho de un Short y recorte de arranques vacíos.

Los primeros 3 segundos deciden si el espectador se queda. Con el texto de esos segundos
se calcula un puntaje 0-100 con señales conocidas de retención (pregunta, cifra, contraste,
promesa, apelación directa) y se penalizan los arranques vacíos ("hola", "bueno", "en este video").
También se avanza el inicio del Short para saltar saludos y muletillas de apertura.
Heurístico, en español e inglés básico; función pura, sin red ni modelos.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

HOOK_SECONDS = 4.0
_PUNCT = re.compile(r"[^\wáéíóúüñ\s]", re.UNICODE)

QUESTION_OPENERS = ("por qué", "porque", "cómo", "como", "qué pasa", "que pasa", "sabías", "sabias", "te has preguntado",
                    "alguna vez", "cuántas", "cuantas", "cuánto", "cuanto", "why", "how", "what if", "did you know")
CURIOSITY = ("nadie", "nunca", "jamás", "jamas", "el error", "secreto", "la verdad", "lo que no te dicen", "cuidado",
             "no es lo que", "increíble", "increible", "peor", "mejor", "gratis", "sorprend", "nobody", "never", "secret")
DIRECT = ("tú", "tu ", "te ", "si tú", "imagina", "piensa", "mira", "escucha", "you", "imagine")
EMPTY_OPENERS = ("hola", "buenas", "bienvenid", "bueno", "eh", "em", "ok", "okay", "pues", "entonces", "listo",
                 "en este video", "en el video de hoy", "hoy vamos a", "hey", "hello", "welcome")
_NUMBER = re.compile(r"\d")


def _clean(text: str) -> str:
    return _PUNCT.sub(" ", (text or "").lower()).strip()


def hook_text(clip: Any, captions: Sequence[Any], seconds: float = HOOK_SECONDS) -> str:
    parts = [c.text for c in captions if clip.start_sec - 0.2 <= c.start_sec <= clip.start_sec + seconds]
    return " ".join(parts).strip()


def score_hook(text: str) -> Dict[str, Any]:
    """{score: 0-100, signals: [...]} para el texto de apertura."""
    raw = (text or "").strip()
    low = _clean(raw)
    if not low:
        return {"score": 0, "signals": ["sin texto"]}
    signals, score = [], 30
    words = low.split()
    if "?" in raw or "¿" in raw or low.startswith(QUESTION_OPENERS):
        score += 25
        signals.append("pregunta")
    if _NUMBER.search(raw):
        score += 15
        signals.append("cifra")
    if any(k in low for k in CURIOSITY):
        score += 20
        signals.append("curiosidad/contraste")
    if any((k in low) if k.endswith(" ") else re.search(rf"\b{re.escape(k)}\b", low) for k in DIRECT):
        score += 10
        signals.append("apelación directa")
    first_sentence = re.split(r"[.!?]", raw)[0].split()
    if 0 < len(first_sentence) <= 12:
        score += 10
        signals.append("frase corta")
    if low.startswith(EMPTY_OPENERS) or low.split()[0] in EMPTY_OPENERS:
        score -= 25
        signals.append("arranque vacío")
    if len(words) < 3:
        score -= 10
        signals.append("muy poco texto")
    return {"score": max(0, min(100, score)), "signals": signals}


def _is_empty_opening(text: str) -> bool:
    low = _clean(text)
    if not low:
        return True
    words = low.split()
    return len(words) <= 4 and (low.startswith(EMPTY_OPENERS) or words[0] in EMPTY_OPENERS)


def trim_leading_filler(clip: Any, captions: Sequence[Any], max_trim: float = 6.0, min_len: float = 15.0) -> float:
    """Avanza el inicio del Short saltando frases de apertura vacías. Devuelve los segundos recortados."""
    caps = sorted((c for c in captions if c.start_sec >= clip.start_sec - 0.2), key=lambda c: c.start_sec)
    trimmed_to = clip.start_sec
    for cap in caps:
        if cap.start_sec - clip.start_sec > max_trim:
            break
        if _is_empty_opening(cap.text) and clip.end_sec - cap.end_sec >= min_len:
            trimmed_to = cap.end_sec
        else:
            break
    if trimmed_to > clip.start_sec:
        shift = trimmed_to - clip.start_sec
        clip.start_sec = trimmed_to
        return shift
    return 0.0


def rank_highlights(highlights: List[Any], captions: Sequence[Any], hook_weight: float = 0.4) -> List[Dict[str, Any]]:
    """Reordena los Shorts por puntaje combinado (viralidad + gancho). Devuelve el detalle por clip."""
    details = []
    for clip in highlights:
        result = score_hook(hook_text(clip, captions))
        combined = round((1 - hook_weight) * clip.virality_score + hook_weight * result["score"], 1)
        details.append({"clip_id": clip.clip_id, "virality": clip.virality_score, "hook": result["score"],
                        "combined": combined, "signals": result["signals"]})
    order = {d["clip_id"]: d["combined"] for d in details}
    highlights.sort(key=lambda c: order[c.clip_id], reverse=True)
    return sorted(details, key=lambda d: d["combined"], reverse=True)
