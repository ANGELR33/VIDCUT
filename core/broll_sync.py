"""Sincroniza los apoyos visuales (B-Roll) con la voz real transcrita por Whisper.

Gemini estima los tiempos viendo el video y suele errar por uno o dos segundos. Aquí cada
B-Roll se alinea con la frase de Whisper que más se parece a lo que el plan dice que debe
ilustrar (``spoken_phrase`` y, si falta, ``concept``/``search_query_en``). La duración se conserva.

Es una función pura (sin red ni modelos) para poder probarla.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

_WORD = re.compile(r"[a-záéíóúüñ0-9]{3,}", re.IGNORECASE)
_STOP = {
    "que", "los", "las", "una", "uno", "con", "por", "para", "del", "como", "pero", "esto", "esta",
    "este", "muy", "más", "mas", "sus", "the", "and", "for", "with", "that", "this",
}


def _tokens(text: str) -> set:
    return {w.lower() for w in _WORD.findall(text or "") if w.lower() not in _STOP}


def resync_broll_to_captions(cues: Sequence[Any], captions: Sequence[Any], window_sec: float = 12.0,
                             min_shift_sec: float = 0.4) -> List[Dict[str, Any]]:
    """Mueve el inicio de cada cue a la frase hablada que mejor lo respalda.

    Devuelve la lista de ajustes aplicados (para registrar en el log). No modifica un cue
    si ninguna frase cercana comparte suficientes palabras, o si el desfase es menor a
    ``min_shift_sec``.
    """
    adjustments: List[Dict[str, Any]] = []
    if not cues or not captions:
        return adjustments

    for cue in cues:
        reference = _tokens(getattr(cue, "spoken_phrase", "") or "")
        source = "spoken_phrase"
        if len(reference) < 2:
            reference = _tokens(f"{getattr(cue, 'concept', '')} {getattr(cue, 'search_query_en', '')}")
            source = "concept"
        if not reference:
            continue

        best, best_score = None, 0.0
        for cap in captions:
            if abs(cap.start_sec - cue.start_sec) > window_sec:
                continue
            shared = len(reference & _tokens(cap.text))
            if shared == 0:
                continue
            score = shared / len(reference)
            # Con una referencia corta basta 1 palabra solo si cubre toda la referencia.
            if shared < 2 and score < 1.0:
                continue
            # Desempate: la frase más cercana al tiempo original.
            if score > best_score or (score == best_score and best is not None
                                      and abs(cap.start_sec - cue.start_sec) < abs(best.start_sec - cue.start_sec)):
                best, best_score = cap, score

        if best is None or best_score < (0.5 if source == "spoken_phrase" else 0.34):
            continue
        shift = best.start_sec - cue.start_sec
        if abs(shift) < min_shift_sec:
            continue
        duration = max(1.0, cue.end_sec - cue.start_sec)
        old_start = cue.start_sec
        cue.start_sec = max(0.0, best.start_sec)
        cue.end_sec = cue.start_sec + duration
        adjustments.append({
            "cue_id": cue.cue_id, "from_sec": round(old_start, 2), "to_sec": round(cue.start_sec, 2),
            "shift_sec": round(shift, 2), "match": round(best_score, 2), "source": source,
        })
    return adjustments
