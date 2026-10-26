"""Alineación a nivel de palabra de la locución sintetizada.

El TTS de estudio (Speechify/Gemini) no entrega marcas de tiempo. Para que las
tarjetas, keywords, subtítulos y cortes caigan en el instante exacto, se
transcribe el audio ya generado con Whisper y se alinea su salida con el guion
original: cada palabra del guion recibe un inicio y un fin reales.

La alineación usa difflib para emparejar las palabras transcritas con las del
guion; las palabras que Whisper no reconoce (nombres propios, cifras) se
interpolan entre las vecinas ya conocidas. Si el modelo no está disponible o la
transcripción falla, se devuelve ``(None, None)`` y el motor sigue usando sus
estimaciones por carácter, sin romper el render.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_CLEAN_RE = re.compile(r"[^\wáéíóúüñÁÉÍÓÚÜÑ]+", re.UNICODE)
_DISABLED = False
_TRANSCRIBE_LOCK = threading.Lock()


def _norm(token: str) -> str:
    return _CLEAN_RE.sub("", token).lower()


def _tokenize(text: str) -> List[str]:
    return [tok for tok in (text or "").split() if _norm(tok)]


def _extract_wav(audio_path: Path) -> Path:
    wav_path = audio_path.with_name(f"{audio_path.stem}.align16k.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path), "-vn", "-ac", "1", "-ar", "16000", str(wav_path)],
        capture_output=True,
        check=True,
        timeout=120,
    )
    return wav_path


def _transcribe_words(audio_path: Path, language: str, cancel_event: Optional[Any]) -> List[Dict[str, Any]]:
    from core.transcriber import get_whisper_model

    model = get_whisper_model("base")
    wav_path = _extract_wav(audio_path)
    try:
        with _TRANSCRIBE_LOCK:
            segments, _info = model.transcribe(
                str(wav_path),
                language=language,
                word_timestamps=True,
                vad_filter=False,
                beam_size=1,
                condition_on_previous_text=False,
            )
            words: List[Dict[str, Any]] = []
            for seg in segments:
                if cancel_event is not None and cancel_event.is_set():
                    return []
                for w in (seg.words or []):
                    token = (w.word or "").strip()
                    if token:
                        words.append({"word": token, "start": float(w.start), "end": float(w.end)})
        return words
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass


def _interpolate_times(tokens: List[str], hyp_words: List[Dict[str, Any]], duration: float) -> Optional[List[Tuple[float, float]]]:
    """Empareja tokens del guion con la transcripción y rellena los huecos."""
    a = [_norm(t) for t in tokens]
    b = [_norm(w["word"]) for w in hyp_words]
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)

    starts: List[Optional[float]] = [None] * len(a)
    ends: List[Optional[float]] = [None] * len(a)
    matched = 0
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            starts[block.a + k] = hyp_words[block.b + k]["start"]
            ends[block.a + k] = hyp_words[block.b + k]["end"]
            matched += 1

    if matched == 0:
        return None
    # Si apenas coincide, es mejor no inventar tiempos: el motor usará su fallback.
    if len(a) >= 6 and matched / len(a) < 0.4:
        return None

    known = [i for i, s in enumerate(starts) if s is not None]
    first, last = known[0], known[-1]
    first_start = starts[first] or 0.0
    last_end = ends[last] or first_start
    total_chars = max(1, sum(len(t) + 1 for t in a))

    # Velocidad media (caracteres por segundo) para extrapolar los extremos.
    chars_known = sum(len(a[i]) + 1 for i in known)
    span_known = max(0.1, last_end - first_start)
    cps = (chars_known / span_known) if chars_known > 1 else (total_chars / max(0.1, duration))

    # Extrapolación hacia atrás desde la primera palabra reconocida.
    cursor = first_start
    for i in range(first - 1, -1, -1):
        word_dur = (len(a[i]) + 1) / cps
        cursor = max(0.0, cursor - word_dur)
        starts[i] = cursor
        ends[i] = min(first_start, cursor + word_dur * 0.92)

    # Interpolación lineal entre anclas conocidas.
    for left, right in zip(known, known[1:]):
        if right - left <= 1:
            continue
        t0, t1 = starts[left] or 0.0, starts[right] or t0
        share = (t1 - t0) / (right - left)
        for offset, i in enumerate(range(left + 1, right), start=1):
            starts[i] = t0 + share * offset
            ends[i] = starts[i] + max(0.08, share * 0.9)

    # Extrapolación hacia adelante desde la última palabra reconocida.
    cursor = last_end
    for i in range(last + 1, len(a)):
        word_dur = (len(a[i]) + 1) / cps
        starts[i] = cursor
        ends[i] = cursor + word_dur * 0.92
        cursor = ends[i]

    result: List[Tuple[float, float]] = []
    previous_end = 0.0
    for i in range(len(a)):
        start = max(previous_end, float(starts[i] or 0.0))
        end = max(start + 0.06, float(ends[i] or start + 0.12))
        if duration and duration > 0:
            start = min(start, max(0.0, duration - 0.05))
            end = min(end, duration)
            if end <= start:
                end = min(duration, start + 0.06)
        result.append((round(start, 3), round(end, 3)))
        previous_end = end
    return result


def _sentences_from_words(text: str, words: List[Dict[str, Any]]) -> List[Tuple[float, float, str]]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", (text or "").strip()) if p.strip()]
    sentences: List[Tuple[float, float, str]] = []
    idx = 0
    for part in parts:
        count = len(_tokenize(part))
        if count <= 0:
            continue
        chunk = words[idx:idx + count]
        idx += count
        if not chunk:
            break
        sentences.append((chunk[0]["start"], chunk[-1]["end"], part))
    return sentences


def align_audio_to_script(
    audio_path: Path,
    speech_text: str,
    duration: float,
    cache_path: Optional[Path] = None,
    language: str = "es",
    cancel_event: Optional[Any] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Tuple[float, float, str]]]]:
    """Devuelve (palabras, oraciones) con tiempos reales, o (None, None) si falla."""
    global _DISABLED
    if _DISABLED or not speech_text or not audio_path.exists():
        return None, None
    if os.getenv("AETHERCUT_WORD_ALIGN", "1").strip().lower() in ("0", "false", "off", "no"):
        return None, None

    text_hash = hashlib.sha1(
        f"{speech_text}|{audio_path.name}|{audio_path.stat().st_size}".encode("utf-8")
    ).hexdigest()
    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("text_hash") == text_hash and cached.get("words"):
                return cached["words"], [tuple(s) for s in cached.get("sentences", [])]
        except Exception:
            pass

    tokens = _tokenize(speech_text)
    if not tokens:
        return None, None

    try:
        hyp_words = _transcribe_words(audio_path, language, cancel_event)
    except Exception as exc:
        try:
            from core.llm import safe_log
            safe_log(f"[WordAligner] Whisper no disponible ({exc}); se usan estimaciones por carácter.")
        except Exception:
            pass
        _DISABLED = True
        return None, None

    if not hyp_words:
        return None, None

    times = _interpolate_times(tokens, hyp_words, duration)
    if not times:
        return None, None

    words = [
        {"word": tokens[i], "start": times[i][0], "end": times[i][1]}
        for i in range(len(tokens))
    ]
    sentences = _sentences_from_words(speech_text, words)

    if cache_path:
        try:
            cache_path.write_text(
                json.dumps({"text_hash": text_hash, "words": words, "sentences": sentences}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except OSError:
            pass

    return words, sentences
