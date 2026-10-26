"""Tarjeta de dato animada (count-up) con el mismo lenguaje editorial.

Genera un video corto con canal alfa (QuickTime qtrle) que se superpone en la
escena como si fuera la tarjeta estática, pero con la cifra subiendo de 0 al
valor real. Se usa solo para valores numéricos inequívocos; si el texto no se
puede interpretar ("1 de cada 3", rangos, etc.) se conserva la tarjeta estática.

Diseño: panel casi opaco, barra de acento, kicker, cifra gigante, titular,
cuerpo y fuente. Sin glow, sin blur, sin emojis.
"""

from __future__ import annotations

import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

PANEL = (10, 11, 13, 248)
TEXT = (247, 245, 240, 255)
MUTED = (168, 162, 158, 255)
ACCENT = (242, 84, 45, 255)
RULE = (255, 255, 255, 36)

WIDTH = 880
BORDER = 7
PAD_X = 48
PAD_TOP = 40
PAD_BOTTOM = 34
GAP = 14

BOLD_CANDIDATES = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
REGULAR_CANDIDATES = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")

_NUM_RE = re.compile(r"^(?P<prefix>[^\d]*?)(?P<num>[-+]?\d[\d.,]*)(?P<suffix>.*)$")


@dataclass
class ParsedStat:
    prefix: str
    target: float
    decimals: int
    suffix: str
    thousands: bool

    def format(self, value: float) -> str:
        if self.decimals > 0:
            number = f"{value:.{self.decimals}f}".replace(".", ",")
        else:
            number = f"{int(round(value))}"
            if self.thousands:
                number = f"{int(number):,}".replace(",", ".")
        return f"{self.prefix}{number}{self.suffix}"


def parse_stat(value: str) -> Optional[ParsedStat]:
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    if not raw:
        return None
    match = _NUM_RE.match(raw)
    if not match:
        return None
    prefix = match.group("prefix").strip()
    number = match.group("num").strip().replace(" ", "")
    suffix = match.group("suffix")
    if re.search(r"\d", suffix):
        return None  # "1 de cada 3", rangos, años múltiples: no animar
    if not re.fullmatch(r"[-+]?\d[\d.,]*", number):
        return None

    # Decidir separador decimal y de miles.
    body = number.lstrip("+-")
    sign = "-" if number.startswith("-") else ("+" if number.startswith("+") else "")
    decimals = 0
    thousands = False
    if "," in body and "." in body:
        if body.rfind(",") > body.rfind("."):
            decimals = len(body) - body.rfind(",") - 1
            body = body.replace(".", "").replace(",", ".")
        else:
            decimals = len(body) - body.rfind(".") - 1
            body = body.replace(",", "")
    elif "," in body:
        parts = body.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            decimals = len(parts[1])
            body = body.replace(",", ".")
        elif len(parts) == 2 and len(parts[0]) <= 3:
            thousands = True
            body = body.replace(",", "")
        else:
            thousands = True
            body = body.replace(",", "")
    elif "." in body:
        parts = body.split(".")
        if len(parts) == 2 and len(parts[1]) != 3:
            decimals = len(parts[1])
        elif len(parts) == 2 and len(parts[0]) <= 3:
            thousands = True
            body = body.replace(".", "")
        else:
            thousands = True
            body = body.replace(".", "")

    try:
        target = float(body)
    except ValueError:
        return None
    if target <= 0 or target > 1_000_000_000:
        return None

    return ParsedStat(
        prefix=sign + prefix,
        target=target,
        decimals=max(0, min(2, decimals)),
        suffix=suffix,
        thousands=thousands,
    )


def _font(candidates: Tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for name in candidates:
        for base in (Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")):
            path = base / name
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size)
                except Exception:
                    continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list:
    words = str(text or "").split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        return []
    # Si quedó texto fuera, recortar la última línea con puntos suspensivos.
    consumed = len(" ".join(lines).split())
    if consumed < len(words):
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last.rsplit(" ", 1)[0] if " " in last else ""
        lines[-1] = (last.rstrip(".,;:") + "…") if last else "…"
    return lines


def _fit_size(draw, text: str, candidates: Tuple[str, ...], start: int, floor: int, max_width: int) -> int:
    size = start
    while size > floor:
        font = _font(candidates, size)
        if draw.textlength(text, font=font) <= max_width:
            return size
        size -= 4
    return floor


def _letter_spaced(draw, xy, text: str, font, fill, spacing: float = 2.0):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += draw.textlength(char, font=font) + spacing


def _clean(value: str, limit: int = 0) -> str:
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = (cut or text[:limit]).rstrip(".,;:") + "…"
    return text


def _render_static(parsed: ParsedStat, headline: str, body: str, source: str) -> Tuple[Image.Image, int, int, int]:
    """Devuelve (imagen base, x cifra, y cifra, tamaño de fuente de la cifra)."""
    probe = ImageDraw.Draw(Image.new("RGBA", (WIDTH, 10)))
    inner_w = WIDTH - BORDER - PAD_X * 2

    headline = _clean(headline, 92)
    body = _clean(body, 190)
    source = _clean(source, 70).upper()

    stat_font_size = _fit_size(probe, parsed.format(parsed.target), BOLD_CANDIDATES, 118, 64, inner_w)
    head_size = _fit_size(probe, headline, BOLD_CANDIDATES, 44, 28, inner_w) if headline else 0

    stat_font = _font(BOLD_CANDIDATES, stat_font_size)
    head_font = _font(BOLD_CANDIDATES, head_size) if headline else None
    body_font = _font(REGULAR_CANDIDATES, 21)
    kicker_font = _font(BOLD_CANDIDATES, 13)
    source_font = _font(BOLD_CANDIDATES, 13)

    # Calcular alto del panel.
    y = PAD_TOP
    y += 18 + GAP
    stat_h = int(stat_font_size * 1.08)
    y += stat_h + GAP
    head_lines = _wrap(probe, headline, head_font, inner_w, 3) if headline else []
    y += int(len(head_lines) * head_size * 1.12) + (GAP if head_lines else 0)
    body_lines = _wrap(probe, body, body_font, inner_w, 3) if body else []
    y += int(len(body_lines) * 21 * 1.45) + (GAP if body_lines else 0)
    if source:
        y += 10 + 14 + 14
    height = y + PAD_BOTTOM
    height = max(220, height)

    image = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, WIDTH - 1, height - 1], fill=PANEL)
    draw.rectangle([0, 0, BORDER - 1, height - 1], fill=ACCENT)
    draw.rectangle([BORDER, 0, WIDTH - 1, height - 1], outline=RULE, width=1)

    _letter_spaced(draw, (BORDER + PAD_X, PAD_TOP), "DATO", kicker_font, ACCENT, 2.6)

    stat_y = PAD_TOP + 18 + GAP
    y = stat_y + stat_h + GAP
    for line in head_lines:
        draw.text((BORDER + PAD_X, y), line, font=head_font, fill=TEXT)
        y += int(head_size * 1.12)
    if head_lines:
        y += GAP
    for line in body_lines:
        draw.text((BORDER + PAD_X, y), line, font=body_font, fill=MUTED)
        y += int(21 * 1.45)
    if body_lines:
        y += GAP
    if source:
        y += 8
        draw.line([(BORDER + PAD_X, y), (WIDTH - PAD_X, y)], fill=RULE, width=1)
        y += 12
        draw.text((BORDER + PAD_X, y), source, font=source_font, fill=MUTED)

    return image, BORDER + PAD_X, stat_y, stat_font_size


def create_animated_stat_card(
    stat_value: str,
    out_path: Path,
    headline: str = "",
    body: str = "",
    source: str = "",
    fps: int = 30,
    duration: float = 0.9,
) -> Optional[Tuple[Path, int, int, float]]:
    """Genera el .mov con alfa. Devuelve (ruta, ancho, alto, duración) o None."""
    parsed = parse_stat(stat_value)
    if parsed is None:
        return None

    base, stat_x, stat_y, stat_size = _render_static(parsed, headline, body, source)
    width, height = base.size
    stat_font = _font(BOLD_CANDIDATES, stat_size)

    frames = max(2, int(round(duration * fps)))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-c:v", "qtrle", "-pix_fmt", "argb",
        str(out_path),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert proc.stdin is not None
        for i in range(frames):
            progress = i / (frames - 1)
            eased = 1.0 - (1.0 - progress) ** 3
            frame = base.copy()
            draw = ImageDraw.Draw(frame)
            draw.text((stat_x, stat_y), parsed.format(parsed.target * eased), font=stat_font, fill=TEXT)
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        if proc.wait(timeout=30) != 0:
            return None
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        return None

    if not out_path.exists() or out_path.stat().st_size < 2000:
        return None
    return out_path, width, height, frames / float(fps)
