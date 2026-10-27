"""Mezcla de efectos de sonido y música de fondo con ducking sobre un video ya compuesto.

Toma el plan del director de edición (``edit_director``): efectos con su segundo y ventanas de voz.
No toca el video (``-c:v copy``); solo rehace la pista de audio. Si faltan archivos de sonido o
FFmpeg falla, devuelve False y el video original queda intacto (fail-open).
Usa solo sonidos que tengas con licencia que permita monetizar (p. ej. CC0).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

AUDIO_EXT = (".wav", ".mp3", ".ogg", ".m4a")


def enabled() -> bool:
    return os.getenv("AUDIO_MIX", "1").strip().lower() not in ("0", "false", "no", "off")


def find_sfx(sfx_dir: Path, name: str) -> Optional[Path]:
    for ext in AUDIO_EXT:
        p = Path(sfx_dir) / f"{name}{ext}"
        if p.is_file():
            return p
    return None


def build_filter(n_sfx: int, delays_ms: Sequence[int], gains: Sequence[float], has_music: bool,
                 duck: Sequence[Dict[str, float]], music_gain: float = 0.18, duck_gain: float = 0.06) -> str:
    """Grafo de filtros. Entrada 0 = video con voz; 1..n = efectos; última = música (si hay)."""
    parts: List[str] = ["[0:a]anull[voice]"]
    labels = ["[voice]"]
    for i in range(n_sfx):
        d = max(0, int(delays_ms[i]))
        parts.append(f"[{i + 1}:a]adelay={d}|{d},volume={gains[i]:.2f}[s{i}]")
        labels.append(f"[s{i}]")
    if has_music:
        mi = n_sfx + 1
        # Ducking: se baja la música dentro de cada ventana de voz.
        base = music_gain
        expr = "+".join(f"between(t,{w['start']:.2f},{w['end']:.2f})" for w in duck[:60]) or "0"
        chain = (f"[{mi}:a]aloop=loop=-1:size=2e9,"
                 f"volume='if(gt({expr},0),{duck_gain:.3f},{base:.3f})':eval=frame[mus]")
        parts.append(chain)
        labels.append("[mus]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[aout]")
    return ";".join(parts)


def mix_audio(video: Path, out: Path, sfx_plan: Sequence[Dict[str, Any]], sfx_dir: Path,
              music: Optional[Path] = None, duck: Sequence[Dict[str, float]] = (),
              sfx_gain: float = 0.35, timeout: int = 600) -> bool:
    events = []
    for ev in sfx_plan:
        path = find_sfx(sfx_dir, ev["name"])
        if path:
            events.append((ev["t"], path))
    has_music = bool(music and Path(music).is_file())
    if not events and not has_music:
        return False
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    for _, p in events:
        cmd += ["-i", str(p)]
    if has_music:
        cmd += ["-i", str(music)]
    graph = build_filter(len(events), [int(t * 1000) for t, _ in events], [sfx_gain] * len(events), has_music, duck)
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return res.returncode == 0 and Path(out).is_file()
