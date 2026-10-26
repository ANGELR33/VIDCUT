"""Cadena de audio profesional para la voz y normalización de loudness en dos pasadas.

Orden de la cadena de voz (el orden importa):
  1. highpass      -> quita rumble y golpes de micrófono por debajo de 80 Hz.
  2. afftdn        -> reduce ruido de fondo constante (opcional; no hace falta en TTS).
  3. equalizer     -> recorta "barro" (250 Hz) y realza presencia/inteligibilidad (4 kHz).
  4. deesser       -> controla sibilancias antes de comprimir (el compresor las acentuaría).
  5. acompressor   -> nivela la dinámica para que la voz se mantenga estable.
  6. loudnorm      -> normaliza a -16 LUFS (YouTube) o -14 LUFS (Shorts); en dos pasadas
                      queda exacto en lugar de aproximado.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

TARGET_LUFS_YOUTUBE = -16.0
TARGET_LUFS_SHORTS = -14.0
TARGET_TP = -1.5
TARGET_LRA = 11.0

# Con sidechain, la música baja ~9 dB bajo la voz. Se parte de un nivel 2x (+6 dB) para
# que en las pausas "respire" y bajo la voz quede cerca (-3 dB) del nivel fijo anterior.
BGM_DUCK_BOOST = 2.0


def voice_chain(denoise: bool = True) -> str:
    """Filtros de limpieza y tono de la voz, sin la normalización final."""
    parts: List[str] = ["highpass=f=80"]
    if denoise:
        parts.append("afftdn=nr=10:nf=-35:tn=0")
    parts += [
        "equalizer=f=250:t=q:w=1:g=-2",
        "equalizer=f=4000:t=q:w=1:g=2.5",
        "deesser=i=0.3:m=0.5:f=0.5",
        "acompressor=threshold=-20dB:ratio=3:attack=15:release=200:makeup=2",
    ]
    return ",".join(parts)


def measure_loudness(
    path: Path,
    pre_filter: str = "",
    target_i: float = TARGET_LUFS_YOUTUBE,
    start: Optional[float] = None,
    duration: Optional[float] = None,
    timeout: int = 600,
) -> Optional[Dict[str, float]]:
    """Primera pasada de loudnorm: mide el audio (ya con `pre_filter` aplicado).

    Devuelve None si FFmpeg falla o el audio no tiene señal medible; el llamador
    debe caer entonces a la normalización de una sola pasada.
    """
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]
    chain = f"{pre_filter}," if pre_filter else ""
    cmd += [
        "-vn", "-af",
        f"{chain}loudnorm=I={target_i}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    blocks = re.findall(r"\{[^{}]*\}", proc.stderr, flags=re.S)
    if not blocks:
        return None
    try:
        raw = json.loads(blocks[-1])
        measured = {
            "input_i": float(raw["input_i"]),
            "input_tp": float(raw["input_tp"]),
            "input_lra": float(raw["input_lra"]),
            "input_thresh": float(raw["input_thresh"]),
            "target_offset": float(raw["target_offset"]),
        }
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
    # "-inf" (silencio total) llega como número muy negativo o inf: no es medible.
    if any(abs(v) == float("inf") or v != v for v in measured.values()) or measured["input_i"] < -70:
        return None
    return measured


def loudnorm_filter(measured: Optional[Dict[str, float]], target_i: float = TARGET_LUFS_YOUTUBE) -> str:
    """Filtro loudnorm: segunda pasada (lineal y exacta) si hay medición; si no, una pasada."""
    base = f"loudnorm=I={target_i}:TP={TARGET_TP}:LRA={TARGET_LRA}"
    # loudnorm remuestrea internamente a 192 kHz; se vuelve a 48 kHz para no inflar el audio final.
    tail = ",aresample=48000"
    if not measured:
        return base + tail
    return (
        f"{base}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true{tail}"
    )


def full_voice_filter(
    source: Optional[Path] = None,
    target_i: float = TARGET_LUFS_YOUTUBE,
    denoise: bool = True,
    start: Optional[float] = None,
    duration: Optional[float] = None,
    two_pass: bool = True,
    prefix: str = "",
) -> str:
    """Cadena de voz completa + loudnorm. Con `source` mide y usa dos pasadas.

    `prefix` son filtros que van antes de la cadena (p. ej. un `aformat` a estéreo).
    Se aplican igual al medir y al normalizar: si el formato de canales difiere entre
    ambas pasadas, la medición queda desfasada (un mono duplicado a estéreo suma 3 dB).
    """
    chain = voice_chain(denoise=denoise)
    pre = f"{prefix},{chain}" if prefix else chain
    measured = None
    if two_pass and source is not None:
        measured = measure_loudness(source, pre_filter=pre, target_i=target_i,
                                    start=start, duration=duration)
    return f"{pre},{loudnorm_filter(measured, target_i)}"


def music_ducking_filter(
    music_label: str,
    voice_sidechain_label: str,
    out_label: str,
    threshold: float = 0.04,
    ratio: float = 4.0,
    attack_ms: int = 25,
    release_ms: int = 450,
) -> str:
    """Compresión por sidechain: la pista principal baja cuando suena la de control y
    vuelve a subir en las pausas. Con los valores por defecto la música baja ~9 dB bajo la voz."""
    return (
        f"[{music_label}][{voice_sidechain_label}]"
        f"sidechaincompress=threshold={threshold}:ratio={ratio}:attack={attack_ms}:release={release_ms}:makeup=1"
        f"[{out_label}]"
    )
