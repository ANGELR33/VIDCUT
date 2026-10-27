"""Corte de muletillas y tartamudeos usando los tiempos por palabra de Whisper.

Quita solo lo que casi nunca aporta:
  - Vacilaciones vocales puras: "eh", "em", "mmm", "uh", "um", "ah"...
  - Tartamudeos: una palabra funcional repetida de inmediato ("el el", "que que", "de de").
No toca muletillas con significado ("o sea", "este", "pues") ni repeticiones enfáticas ("no no", "muy muy").

Salvaguardas (el montaje nunca debe quedar peor que sin esta función):
  - Cada corte se acorta ``pad`` por lado, para no morder las palabras vecinas.
  - Se omite un corte si deja un fragmento hablado de menos de ``min_fragment`` segundos.
  - El total cortado no pasa de ``max_ratio`` de la duración (se conservan los más largos).
  - Todo es función pura y deja un informe; se desactiva con ``FILLER_CUT=0``.

Whisper a veces omite las muletillas al transcribir; en ese caso simplemente hay menos cortes.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Sequence, Tuple

from core.models import ActionType, TimelineSegment

HESITATIONS = {
    "eh", "ehh", "eeh", "eee", "eeee", "em", "emm", "emmm", "mm", "mmm", "mmmm", "hmm", "hm", "hmmm",
    "uh", "uhh", "um", "umm", "ah", "ahh", "aah", "ahm", "ehm", "mhm",
}
STUTTER_WORDS = {
    "el", "la", "los", "las", "un", "una", "que", "de", "en", "y", "a", "se", "lo", "yo", "es", "por",
    "con", "para", "me", "mi", "tu", "su", "al", "del", "the", "i", "to", "of", "and",
}
_LETTERS = re.compile(r"[^\wáéíóúüñ]+", re.UNICODE)


def enabled() -> bool:
    return os.getenv("FILLER_CUT", "1").strip().lower() not in ("0", "false", "no", "off")


def norm(token: str) -> str:
    return _LETTERS.sub("", (token or "").lower())


def find_fillers(words: Sequence[Dict[str, Any]], min_dur: float = 0.2, max_gap: float = 0.35) -> List[Dict[str, Any]]:
    """Devuelve [{start, end, kind, text}] a partir de [{word, start, end}] en orden temporal."""
    found: List[Dict[str, Any]] = []
    for i, w in enumerate(words):
        token = norm(w.get("word", ""))
        start, end = float(w["start"]), float(w["end"])
        if not token or end <= start:
            continue
        if token in HESITATIONS and end - start >= min_dur:
            found.append({"start": start, "end": end, "kind": "vacilacion", "text": w["word"].strip()})
            continue
        if i + 1 < len(words):
            nxt = words[i + 1]
            if (token in STUTTER_WORDS and norm(nxt.get("word", "")) == token
                    and float(nxt["start"]) - end <= max_gap and end - start <= 0.6):
                # Se corta la primera aparición: desde su inicio hasta el inicio de la repetición.
                found.append({"start": start, "end": float(nxt["start"]), "kind": "tartamudeo",
                              "text": f"{w['word'].strip()} {nxt['word'].strip()}"})
    return found


def _plan_cuts(fillers: Sequence[Dict[str, Any]], pad: float, min_cut: float,
               total_duration: float, max_ratio: float) -> Tuple[List[Dict[str, Any]], int]:
    cuts = []
    for f in fillers:
        start, end = f["start"] + pad, f["end"] - pad
        if end - start >= min_cut:
            cuts.append({**f, "cut_start": start, "cut_end": end})
    cap = max(0.0, total_duration * max_ratio)
    skipped_cap = 0
    if sum(c["cut_end"] - c["cut_start"] for c in cuts) > cap:
        chosen, acc = [], 0.0
        for c in sorted(cuts, key=lambda c: c["cut_end"] - c["cut_start"], reverse=True):
            length = c["cut_end"] - c["cut_start"]
            if acc + length <= cap:
                chosen.append(c)
                acc += length
            else:
                skipped_cap += 1
        cuts = chosen
    return sorted(cuts, key=lambda c: c["cut_start"]), skipped_cap


def apply_filler_cuts(segments: Sequence[TimelineSegment], fillers: Sequence[Dict[str, Any]],
                      total_duration: float, pad: float = 0.05, min_cut: float = 0.1,
                      min_fragment: float = 0.25, max_ratio: float = 0.06
                      ) -> Tuple[List[TimelineSegment], Dict[str, Any]]:
    """Parte los tramos KEEP e inserta tramos CUT_FILLER. Devuelve (segmentos, informe)."""
    out: List[TimelineSegment] = [s.model_copy() for s in segments]
    cuts, skipped_cap = _plan_cuts(fillers, pad, min_cut, total_duration, max_ratio)
    applied: List[Dict[str, Any]] = []
    skipped = {"limite_6_por_ciento": skipped_cap, "fragmento_muy_corto": 0, "fuera_de_tramo": 0}

    for cut in cuts:
        cs, ce = cut["cut_start"], cut["cut_end"]
        idx = next((i for i, s in enumerate(out)
                    if s.action == ActionType.KEEP and s.start_sec <= cs and ce <= s.end_sec), None)
        if idx is None:
            skipped["fuera_de_tramo"] += 1
            continue
        seg = out[idx]
        left, right = cs - seg.start_sec, seg.end_sec - ce
        if (0.001 < left < min_fragment) or (0.001 < right < min_fragment):
            skipped["fragmento_muy_corto"] += 1
            continue
        pieces: List[TimelineSegment] = []
        if left > 0.001:
            pieces.append(TimelineSegment(start_sec=seg.start_sec, end_sec=cs, action=ActionType.KEEP,
                                          reasoning=seg.reasoning))
        pieces.append(TimelineSegment(start_sec=cs, end_sec=ce, action=ActionType.CUT_FILLER,
                                      reasoning=f"{cut['kind']}: «{cut['text']}»"))
        if right > 0.001:
            pieces.append(TimelineSegment(start_sec=ce, end_sec=seg.end_sec, action=ActionType.KEEP,
                                          reasoning=seg.reasoning))
        out[idx:idx + 1] = pieces
        applied.append({"start": round(cs, 2), "end": round(ce, 2), "kind": cut["kind"], "text": cut["text"]})

    report = {
        "detected": len(fillers), "applied": len(applied),
        "seconds_cut": round(sum(a["end"] - a["start"] for a in applied), 2),
        "skipped": skipped, "cuts": applied,
    }
    return out, report


def clean_caption_text(text: str) -> str:
    """Quita vacilaciones y colapsa tartamudeos para que el subtítulo coincida con lo que se oye."""
    tokens = [t for t in (text or "").split() if norm(t) not in HESITATIONS]
    cleaned: List[str] = []
    for t in tokens:
        if cleaned and norm(t) == norm(cleaned[-1]) and norm(t) in STUTTER_WORDS:
            continue
        cleaned.append(t)
    return " ".join(cleaned).strip()


def clean_captions(captions: List[Any]) -> int:
    """Limpia en su sitio el texto de los subtítulos; quita los que quedan vacíos. Devuelve cuántos cambió."""
    changed = 0
    for cap in list(captions):
        new = clean_caption_text(cap.text)
        if new != cap.text:
            changed += 1
            if not new:
                captions.remove(cap)
            else:
                cap.text = new
                cap.highlight_words = [w for w in cap.highlight_words if norm(w) in {norm(t) for t in new.split()}]
    return changed
