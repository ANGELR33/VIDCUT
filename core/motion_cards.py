"""Tarjetas animadas de concepto: ayuda visual generada cuando no hay imagen real relevante.

Si ningún proveedor entrega una foto o clip que ilustre lo que se dice, en vez de dejar el
fondo vacío se genera un clip corto con el concepto: fondo con degradado en movimiento, barra
de acento que crece y el texto entrando con desvanecido y desplazamiento. Solo usa FFmpeg
(drawtext + gradients), sin red ni modelos, así que siempre está disponible.

Es una ayuda para orientar a quien mira, no sustituye a una imagen real: el reporte de decisiones
la marca como ``generada``. Se desactiva con ``MOTION_FALLBACK=0``.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import List, Optional, Tuple

PALETTES: List[Tuple[str, str, str]] = [  # (fondo 1, fondo 2, acento)
    ("0x141a3a", "0x2b3a8f", "0xffc857"),
    ("0x1b1b1b", "0x3a3a3a", "0xff6b35"),
    ("0x0b3d3a", "0x1b7f79", "0xf4e285"),
    ("0x2a1233", "0x6a2c70", "0xf9a826"),
    ("0x10253a", "0x1f6f8b", "0xe84a5f"),
]
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def enabled() -> bool:
    return os.getenv("MOTION_FALLBACK", "1").strip().lower() not in ("0", "false", "no", "off")


def find_font() -> Optional[str]:
    env = os.getenv("MOTION_FONT", "").strip()
    for p in ([env] if env else []) + FONT_CANDIDATES:
        if p and Path(p).is_file():
            return p
    return None


def palette_for(text: str) -> Tuple[str, str, str]:
    """Paleta estable: el mismo concepto siempre recibe los mismos colores."""
    digest = int(hashlib.sha1((text or "").lower().encode("utf-8")).hexdigest(), 16)
    return PALETTES[digest % len(PALETTES)]


def wrap_text(text: str, width: int = 20, max_lines: int = 3) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    lines = textwrap.wrap(clean, width=width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;:") + "…"
    return "\n".join(lines)


def build_filter(textfile: str, fontfile: str, accent: str, size: Tuple[int, int], dur: float) -> str:
    w, h = size
    fs = max(36, h // 10)
    esc_font = fontfile.replace("\\", "/").replace(":", "\\:")
    esc_text = textfile.replace("\\", "/").replace(":", "\\:")
    fade_in, fade_out = 0.45, 0.4
    alpha = f"if(lt(t,{fade_in}),t/{fade_in},if(gt(t,{dur - fade_out}),({dur}-t)/{fade_out},1))"
    y_expr = f"(h-text_h)/2+if(lt(t,{fade_in}),(1-t/{fade_in})*40,0)"
    bar = (f"drawbox=x=(iw-min(t*{w}*0.6\\,{int(w * 0.28)}))/2:y=ih*0.72:"
           f"w=min(t*{w}*0.6\\,{int(w * 0.28)}):h=10:color={accent}@0.95:t=fill")
    text = (f"drawtext=fontfile='{esc_font}':textfile='{esc_text}':fontsize={fs}:fontcolor=white:"
            f"line_spacing=12:x=(w-text_w)/2:y='{y_expr}':alpha='{alpha}':"
            f"shadowcolor=black@0.5:shadowx=3:shadowy=3")
    return f"{bar},{text},format=yuv420p"


def make_concept_card(text: str, out: Path, duration: float = 4.0, size: Tuple[int, int] = (1280, 720),
                      fps: int = 24, timeout: int = 120) -> Optional[Path]:
    """Genera un .mp4 con el concepto animado. Devuelve la ruta o None si no se pudo."""
    text = (text or "").strip()
    font = find_font()
    if not text or not font:
        return None
    c1, c2, accent = palette_for(text)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write(wrap_text(text.upper(), width=18))
            tmp = fh.name
        w, h = size
        vf = build_filter(tmp, font, accent, size, duration)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
               f"gradients=s={w}x{h}:c0={c1}:c1={c2}:speed=0.03:d={duration}:r={fps}",
               "-vf", vf, "-t", f"{duration:.2f}", "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", str(out)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out if res.returncode == 0 and out.is_file() and out.stat().st_size > 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
