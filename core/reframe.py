"""Reencuadre vertical dinámico: la cámara sigue a la persona sin marear.

Antes el Short usaba un solo recorte fijo (mediana de rostros). Si la persona se mueve, sale del
cuadro. Aquí se muestrea el rostro en el tiempo y se genera una trayectoria estable:

  - Zona muerta: la cámara solo se mueve cuando el rostro se sale de una franja central.
  - Límite de velocidad: nunca desliza más de ``max_speed`` (fracción del ancho por segundo).
  - Huecos (sin rostro) se rellenan manteniendo la última posición, o el centro si nunca hubo.
  - En un corte de escena la cámara salta en lugar de deslizarse (un paneo entre planos distintos marea).
  - Se reduce a pocos fotogramas clave y se emite como expresión lineal por tramos de FFmpeg.

Todo es función pura (la detección se inyecta), así que se prueba sin OpenCV ni video.
Si hay muy pocas detecciones se devuelve None y el llamador usa el recorte fijo anterior.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

Sample = Tuple[float, Optional[float]]  # (segundo relativo al clip, centro x normalizado 0-1 o None)


def enabled() -> bool:
    return os.getenv("DYNAMIC_REFRAME", "1").strip().lower() not in ("0", "false", "no", "off")


def smooth_track(samples: Sequence[Sample], cuts: Sequence[float] = (), deadzone: float = 0.06,
                 max_speed: float = 0.25, min_detect_ratio: float = 0.3) -> Optional[List[Tuple[float, float]]]:
    """[(t, cx)] suavizado, o None si hubo pocas detecciones para fiarse."""
    pts = sorted(samples, key=lambda s: s[0])
    if not pts:
        return None
    found = sum(1 for _, c in pts if c is not None)
    if found / len(pts) < min_detect_ratio:
        return None
    cuts_sorted = sorted(cuts)
    first = next(c for _, c in pts if c is not None)
    cam = first
    out: List[Tuple[float, float]] = []
    prev_t = pts[0][0]
    target = first
    for t, c in pts:
        if c is not None:
            target = c
        dt = max(0.0, t - prev_t)
        crossed_cut = any(prev_t < ct <= t for ct in cuts_sorted)
        if crossed_cut and c is not None:
            cam = c
        elif abs(target - cam) > deadzone:
            goal = target - deadzone if target > cam else target + deadzone
            step = max_speed * dt
            cam += max(-step, min(step, goal - cam))
        out.append((t, max(0.0, min(1.0, cam))))
        prev_t = t
    return out


def decimate(track: Sequence[Tuple[float, float]], max_points: int = 14,
             min_delta: float = 0.01) -> List[Tuple[float, float]]:
    """Quita fotogramas clave que no cambian la trayectoria y limita su número."""
    keep: List[Tuple[float, float]] = []
    for i, p in enumerate(track):
        if i in (0, len(track) - 1) or not keep or abs(p[1] - keep[-1][1]) >= min_delta:
            keep.append(p)
    while len(keep) > max_points:
        # Quita el punto interior que menos aporta (el más cercano a la recta entre sus vecinos).
        best, best_err = 1, 1e9
        for i in range(1, len(keep) - 1):
            (t0, x0), (t1, x1), (t2, x2) = keep[i - 1], keep[i], keep[i + 1]
            lerp = x0 + (x2 - x0) * ((t1 - t0) / max(t2 - t0, 1e-6))
            err = abs(x1 - lerp)
            if err < best_err:
                best, best_err = i, err
        keep.pop(best)
    return keep


def crop_x_expression(track: Sequence[Tuple[float, float]], scaled_w: int, crop_w: int = 1080) -> str:
    """Expresión de FFmpeg para ``crop`` x (píxeles, con ``t``). Debe ir entre comillas simples en el filtro."""
    max_x = max(0, scaled_w - crop_w)

    def px(cx: float) -> float:
        return max(0.0, min(float(max_x), cx * scaled_w - crop_w / 2))

    pts = decimate(track)
    xs = [px(c) for _, c in pts]
    if len(pts) == 1 or max(xs) - min(xs) < 0.5:
        return f"{xs[0]:.1f}"
    expr = f"{px(pts[-1][1]):.1f}"
    for (t0, c0), (t1, c1) in reversed(list(zip(pts, pts[1:]))):
        x0, x1 = px(c0), px(c1)
        span = max(t1 - t0, 1e-3)
        seg = f"{x0:.1f}+({x1 - x0:.1f})*(t-{t0:.3f})/{span:.3f}"
        expr = f"if(lt(t,{t1:.3f}),{seg},{expr})"
    return expr
