"""Dibuja las animaciones de representación (cifra que cuenta, comparación con barras, pasos).

Cada fotograma se dibuja con Pillow (suavizado, easing real, barras redondeadas) y se envía a
FFmpeg por una tubería, así que no hace falta red ni modelos. Recibe la especificación que produce
``core.animations.choose_animation``. Si algo falla devuelve None y el llamador usa la tarjeta simple.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.motion_cards import find_font, palette_for

W, H, FPS = 1280, 720, 24


def _rgb(hex_color: str) -> Tuple[int, int, int]:
    v = int(hex_color, 16)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def ease_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_out_back(x: float) -> float:
    x = max(0.0, min(1.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def format_number(value: float, decimals: int = 0) -> str:
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


class _Canvas:
    def __init__(self, text: str, size: Tuple[int, int] = (W, H)):
        from PIL import Image
        self.w, self.h = size
        c1, c2, accent = palette_for(text)
        self.accent = _rgb(accent)
        grad = Image.linear_gradient("L").resize(size)
        self.bg = Image.composite(Image.new("RGB", size, _rgb(c2)), Image.new("RGB", size, _rgb(c1)), grad)
        self.font_path = find_font()

    def font(self, size: int):
        from PIL import ImageFont
        return ImageFont.truetype(self.font_path, size) if self.font_path else ImageFont.load_default()

    def fit(self, draw, text: str, max_w: int, start: int, minimum: int = 28):
        size = start
        while size > minimum:
            f = self.font(size)
            if draw.textlength(text, font=f) <= max_w:
                return f
            size -= 4
        return self.font(minimum)

    def new_frame(self, t: float):
        from PIL import Image, ImageDraw
        img = self.bg.copy()
        # Destello suave que se desplaza: da vida al fondo sin distraer.
        glow = Image.new("RGB", img.size, self.accent)
        mask = Image.new("L", img.size, 0)
        d = ImageDraw.Draw(mask)
        cx = int(self.w * (0.15 + 0.7 * ((t * 0.08) % 1.0)))
        d.ellipse((cx - 260, -200, cx + 260, 260), fill=34)
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.GaussianBlur(90))
        img.paste(glow, (0, 0), mask)
        return img, ImageDraw.Draw(img)


def _title(cv: _Canvas, draw, title: str, t: float) -> None:
    if not title:
        return
    a = ease_out_cubic(t / 0.5)
    f = cv.fit(draw, title.upper(), int(cv.w * 0.8), 44, 24)
    y = 70 - int((1 - a) * 24)
    color = tuple(int(255 * a * 0.9 + c * (1 - a * 0.9)) for c in (0, 0, 0))
    draw.text((cv.w // 2, y), title.upper(), font=f, fill=color, anchor="mt")


def _counter(cv: _Canvas, spec: Dict[str, Any], t: float):
    img, draw = cv.new_frame(t)
    _title(cv, draw, spec.get("title", ""), t)
    count_dur = 1.8
    p = ease_out_cubic((t - 0.3) / count_dur)
    value = spec["value"] * p
    text = f"{spec.get('prefix', '')}{format_number(value, spec.get('decimals', 0))}{spec.get('suffix', '')}"
    pop = 1.0 + 0.06 * math.sin(min(1.0, max(0.0, (t - 0.3 - count_dur) / 0.35)) * math.pi)
    base = int(cv.h * 0.30 * pop)
    f = cv.fit(draw, text, int(cv.w * 0.86), base, 60)
    draw.text((cv.w // 2 + 4, cv.h // 2 + 4), text, font=f, fill=(0, 0, 0), anchor="mm")
    draw.text((cv.w // 2, cv.h // 2), text, font=f, fill=(255, 255, 255), anchor="mm")
    bar_w = int(cv.w * 0.3 * ease_out_cubic((t - 0.2) / 0.8))
    draw.rounded_rectangle((cv.w // 2 - bar_w // 2, int(cv.h * 0.72), cv.w // 2 + bar_w // 2, int(cv.h * 0.72) + 10),
                           radius=5, fill=cv.accent)
    return img


def _compare(cv: _Canvas, spec: Dict[str, Any], t: float):
    img, draw = cv.new_frame(t)
    _title(cv, draw, spec.get("title", ""), t)
    items = spec["items"][:3]
    top = max(float(i["value"]) for i in items) or 1.0
    left, right = int(cv.w * 0.12), int(cv.w * 0.88)
    row_h = 130
    y0 = int((cv.h - len(items) * row_h) / 2 + 80)
    colors = [cv.accent, (255, 255, 255), (150, 200, 255)]
    for idx, item in enumerate(items):
        start = 0.4 + idx * 0.35
        p = ease_out_cubic((t - start) / 1.2)
        y = y0 + idx * row_h
        lab_font = cv.fit(draw, item["label"], int((right - left) * 0.8), 40, 24)
        draw.text((left, y), item["label"], font=lab_font, fill=(255, 255, 255), anchor="ls")
        full = (right - left) * float(item["value"]) / top
        w = max(0, int(full * p))
        draw.rounded_rectangle((left, y + 14, left + (right - left), y + 54), radius=20, fill=(0, 0, 0))
        if w > 0:
            draw.rounded_rectangle((left, y + 14, left + max(w, 40), y + 54), radius=20, fill=colors[idx % 3])
        if p > 0.6:
            vf = cv.font(36)
            draw.text((left + max(w, 40) + 14, y + 34), item["display"], font=vf, fill=(255, 255, 255), anchor="lm")
    return img


def _steps(cv: _Canvas, spec: Dict[str, Any], t: float):
    img, draw = cv.new_frame(t)
    _title(cv, draw, spec.get("title", ""), t)
    items = spec["items"][:5]
    row_h = min(110, int((cv.h * 0.7) / max(1, len(items))))
    y0 = int((cv.h - len(items) * row_h) / 2 + 50)
    for idx, text in enumerate(items):
        p = ease_out_back((t - (0.4 + idx * 0.6)) / 0.5)
        if p <= 0:
            continue
        y = y0 + idx * row_h
        x = int(cv.w * 0.14 - (1 - min(p, 1.0)) * 80)
        r = 30
        draw.ellipse((x, y, x + 2 * r, y + 2 * r), fill=cv.accent)
        draw.text((x + r, y + r), str(idx + 1), font=cv.font(36), fill=(0, 0, 0), anchor="mm")
        f = cv.fit(draw, text, int(cv.w * 0.66), 44, 26)
        draw.text((x + 2 * r + 26, y + r), text, font=f, fill=(255, 255, 255), anchor="lm")
    return img


RENDERERS = {"counter": _counter, "compare": _compare, "steps": _steps}


def supports(spec: Dict[str, Any]) -> bool:
    return spec.get("kind") in RENDERERS and find_font() is not None


def frame_at(spec: Dict[str, Any], t: float, size: Tuple[int, int] = (W, H)):
    cv = _Canvas(spec.get("title", "") or spec.get("kind", ""), size)
    return RENDERERS[spec["kind"]](cv, spec, t)


def render_animation(spec: Dict[str, Any], out: Path, duration: float = 4.0, fps: int = FPS,
                     size: Tuple[int, int] = (W, H), timeout: int = 180) -> Optional[Path]:
    """Genera el .mp4 de la animación. None si el tipo no es soportado o algo falla."""
    if not supports(spec):
        return None
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", str(out)]
    try:
        cv = _Canvas(spec.get("title", "") or spec.get("kind", ""), size)
        draw_fn = RENDERERS[spec["kind"]]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        for i in range(int(duration * fps)):
            proc.stdin.write(draw_fn(cv, spec, i / fps).convert("RGB").tobytes())
        proc.stdin.close()
        proc.wait(timeout=timeout)
        return out if proc.returncode == 0 and out.is_file() and out.stat().st_size > 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
        return None
