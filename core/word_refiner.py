"""Afinado opcional de los tiempos por palabra con alineación forzada (WhisperX / wav2vec2).

faster-whisper da tiempos por palabra con un margen de error de décimas de segundo, y el corte de
muletillas depende de esa precisión. Con ``ALIGNER=whisperx`` los tiempos se recalculan alineando el
audio con el texto ya transcrito.

Diseño a prueba de fallos:
  - Está APAGADO por defecto y no es una dependencia obligatoria (``pip install whisperx``).
  - Si falta la librería, el modelo o algo falla, se devuelven las palabras originales.
  - El resultado solo se adopta si pasa ``sanity_check``: no se acepta una alineación que mueva las
    palabras de forma absurda, rompa el orden temporal o pierda palabras.
"""

from __future__ import annotations

import difflib
import os
import re
from typing import Any, Dict, List, Sequence, Tuple

_NORM = re.compile(r"[^\wáéíóúüñ]+", re.UNICODE)


def enabled() -> bool:
    return os.getenv("ALIGNER", "off").strip().lower() == "whisperx"


def _n(word: str) -> str:
    return _NORM.sub("", (word or "").lower())


def merge_refined(original: Sequence[Dict[str, Any]], refined: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Aplica a ``original`` los tiempos de las palabras de ``refined`` que coinciden (por texto y orden).

    Devuelve (palabras, cuántas se ajustaron). Las que no coinciden conservan su tiempo original.
    """
    a = [_n(w["word"]) for w in original]
    b = [_n(w["word"]) for w in refined]
    out = [dict(w) for w in original]
    changed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            continue
        for k in range(i2 - i1):
            r = refined[j1 + k]
            start, end = r.get("start"), r.get("end")
            if start is None or end is None or end <= start:
                continue
            out[i1 + k]["start"], out[i1 + k]["end"] = float(start), float(end)
            changed += 1
    return out, changed


def sanity_check(original: Sequence[Dict[str, Any]], refined: Sequence[Dict[str, Any]], changed: int,
                 max_median_shift: float = 0.35, max_shift: float = 2.0, min_matched: float = 0.8) -> Tuple[bool, str]:
    if not original:
        return False, "sin palabras"
    if changed / len(original) < min_matched:
        return False, f"solo coincidió {changed}/{len(original)} palabras"
    shifts = sorted(abs(float(r["start"]) - float(o["start"])) for o, r in zip(original, refined))
    if shifts[len(shifts) // 2] > max_median_shift:
        return False, f"desplazamiento mediano {shifts[len(shifts) // 2]:.2f} s: la alineación no es fiable"
    if shifts[-1] > max_shift:
        return False, f"una palabra se movió {shifts[-1]:.2f} s"
    for prev, cur in zip(refined, refined[1:]):
        if float(cur["start"]) < float(prev["start"]) - 1e-6:
            return False, "el orden temporal quedó roto"
    return True, "ok"


def _segments(words: Sequence[Dict[str, Any]], gap: float = 0.8) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    chunk: List[Dict[str, Any]] = []
    for w in words:
        if chunk and (w["start"] - chunk[-1]["end"] > gap or len(chunk) >= 40):
            segments.append({"text": " ".join(x["word"] for x in chunk), "start": chunk[0]["start"], "end": chunk[-1]["end"]})
            chunk = []
        chunk.append(w)
    if chunk:
        segments.append({"text": " ".join(x["word"] for x in chunk), "start": chunk[0]["start"], "end": chunk[-1]["end"]})
    return segments


def _align_with_whisperx(audio_path: str, words: Sequence[Dict[str, Any]], language: str) -> List[Dict[str, Any]]:
    import whisperx  # noqa: WPS433 (dependencia opcional)
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"
    audio = whisperx.load_audio(str(audio_path))
    model, metadata = whisperx.load_align_model(language_code=language, device=device)
    result = whisperx.align(_segments(words), model, metadata, audio, device, return_char_alignments=False)
    return [{"word": w["word"], "start": w.get("start"), "end": w.get("end")} for w in result.get("word_segments", [])]


def refine_words(audio_path: Any, words: Sequence[Dict[str, Any]], language: str = "es",
                 aligner: Any = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """(palabras, informe). ``aligner`` permite inyectar una función de alineación en pruebas."""
    original = [dict(w) for w in words]
    report: Dict[str, Any] = {"engine": "whisperx", "adopted": False, "adjusted": 0, "reason": ""}
    if not original:
        report["reason"] = "sin palabras"
        return original, report
    try:
        refined_raw = (aligner or _align_with_whisperx)(str(audio_path), original, language)
        merged, changed = merge_refined(original, refined_raw)
        ok, reason = sanity_check(original, merged, changed)
        report.update(adjusted=changed, reason=reason)
        if ok:
            report["adopted"] = True
            return merged, report
    except Exception as exc:  # librería ausente, modelo sin descargar, memoria, etc.
        report["reason"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return original, report
