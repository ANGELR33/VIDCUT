"""Miniaturas editoriales generadas desde el fact sheet (sin look "IA").

Composición:
- Fotograma real del video como fondo (o imagen de respaldo).
- Degradado lateral para legibilidad.
- Kicker, gancho corto en tipografía grande, fuente y cifra protagonista.
- 1280x720 para YouTube y 1080x1920 para Shorts.

Renderiza HTML con Chromium headless (misma familia tipográfica que las cards)
y convierte a JPG. Si Chromium falla, genera un fallback sobrio con Pillow.
"""

from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path
from typing import Optional

PANEL = "#0a0b0d"
TEXT = "#f7f5f0"
MUTED = "#a8a29e"
ACCENT = "#f2542d"

_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")


def _clean(text: str, limit: int = 0) -> str:
    text = _EMOJI_RE.sub("", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = (cut or text[:limit]).rstrip(".,;:") + "…"
    return text


def _short_hook(text: str, max_words: int = 10) -> str:
    clean = _clean(text)
    words = clean.split()
    if len(words) <= max_words or len(clean) <= 110:
        return clean

    # Centrar la frase en el primer dato numérico: es lo que vende la miniatura.
    num_idx = next((i for i, w in enumerate(words) if re.search(r"\d", w)), None)
    if num_idx is not None and num_idx >= 4:
        start = max(0, num_idx - 4)
        phrase = " ".join(words[start:start + max_words + 1])
        if "," in phrase:
            head = phrase.rsplit(",", 1)[0]
            if len(head.split()) >= 5:
                phrase = head
        phrase = phrase.strip(" ,;:–—-")
        dangling = {"de", "del", "desde", "en", "con", "y", "o", "que", "por", "para", "a", "al", "la", "el", "los", "las"}
        parts = phrase.split()
        while parts and parts[-1].lower() in dangling:
            parts.pop()
        phrase = " ".join(parts)
        if len(phrase.split()) >= 5:
            return phrase[0].upper() + phrase[1:] if phrase else phrase

    cut = " ".join(words[:max_words])
    if "," in cut:
        head = cut.rsplit(",", 1)[0]
        if len(head.split()) >= 5:
            return head.strip()
    return cut.rstrip(".,;:")


def _font_size(text: str, base: int, floor: int) -> int:
    n = len(text or "")
    size = base - max(0, n - 34) * 1.35
    return max(floor, int(size))


def _html(hook: str, source: str, stat: str, bg_uri: str, vertical: bool) -> str:
    width, height = (1080, 1920) if vertical else (1280, 720)
    hook_size = _font_size(hook, 118 if vertical else 96, 56 if vertical else 54)
    stat_size = 250 if vertical else 220
    pad = 84 if vertical else 70
    hook_width = int(width * 0.92) if vertical else int(width * 0.60)
    stat_pos = f"top: {pad}px; right: {pad}px;" if vertical else f"right: {pad}px; bottom: {pad}px;"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {width}px; height: {height}px; overflow: hidden; background: {PANEL}; }}
  .bg {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
  .shade {{ position: absolute; inset: 0;
    background: linear-gradient(90deg, rgba(7,8,10,.97) 0%, rgba(7,8,10,.90) 46%, rgba(7,8,10,.30) 100%),
                linear-gradient(0deg, rgba(7,8,10,.92) 0%, rgba(7,8,10,0) 46%); }}
  .bar {{ position: absolute; left: 0; top: 0; bottom: 0; width: 12px; background: {ACCENT}; }}
  .wrap {{ position: absolute; left: {pad}px; right: {pad}px; top: {pad}px; bottom: {pad}px;
    display: flex; flex-direction: column; justify-content: flex-end; color: {TEXT};
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; }}
  .kicker {{ color: {ACCENT}; font-size: 22px; font-weight: 800; letter-spacing: .24em; text-transform: uppercase; margin-bottom: 26px; }}
  .hook {{ font-size: {hook_size}px; line-height: 1.04; font-weight: 800; letter-spacing: -.025em; max-width: {hook_width}px; }}
  .foot {{ margin-top: 30px; font-size: 22px; font-weight: 700; letter-spacing: .06em; color: {MUTED}; text-transform: uppercase; }}
  .stat {{ position: absolute; {stat_pos} font-size: {stat_size}px; font-weight: 800;
    color: {ACCENT}; letter-spacing: -.055em; line-height: .9; font-variant-numeric: tabular-nums; text-align: right; }}
</style></head>
<body>
  <img class="bg" src="{bg_uri}">
  <div class="shade"></div>
  <div class="bar"></div>
  <div class="wrap">
    <div class="kicker">DATO</div>
    <div class="hook">{hook}</div>
    <div class="foot">Fuente: {source}</div>
  </div>
  {f'<div class="stat">{stat}</div>' if stat else ''}
</body></html>"""


def _browser_bin() -> Optional[str]:
    try:
        from core.web_card_renderer import _get_browser_bin
        return _get_browser_bin()
    except Exception:
        return None


def extract_frame(video_path: Path, out_jpg: Path, at_seconds: float = 2.0) -> Optional[Path]:
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{at_seconds:.2f}", "-i", str(video_path),
             "-frames:v", "1", "-update", "1", "-q:v", "2", str(out_jpg)],
            capture_output=True, timeout=25, check=True,
        )
    except Exception:
        return None
    return out_jpg if out_jpg.exists() and out_jpg.stat().st_size > 5000 else None


def _fallback(hook: str, source: str, stat: str, out_jpg: Path, vertical: bool) -> Optional[Path]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    width, height = (1080, 1920) if vertical else (1280, 720)
    image = Image.new("RGB", (width, height), (10, 11, 13))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 12, height], fill=(242, 84, 45))
    font_path = Path("C:/Windows/Fonts/segoeuib.ttf")
    if not font_path.exists():
        font_path = Path("C:/Windows/Fonts/arialbd.ttf")
    try:
        title_font = ImageFont.truetype(str(font_path), 76 if not vertical else 96)
        small_font = ImageFont.truetype(str(font_path), 24)
        stat_font = ImageFont.truetype(str(font_path), 150)
    except Exception:
        return None
    words = _short_hook(hook, 12).split()
    lines, current = [], ""
    for word in words:
        cand = f"{current} {word}".strip()
        if draw.textlength(cand, font=title_font) <= width - 180 or not current:
            current = cand
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    y = height - 120 - len(lines) * 86
    for line in lines[:4]:
        draw.text((80, y), line, font=title_font, fill=(247, 245, 240))
        y += 86
    draw.text((80, height - 86), f"FUENTE: {_clean(source, 60).upper()}", font=small_font, fill=(168, 162, 158))
    if stat:
        draw.text((width - 80, height - 210), stat, font=stat_font, fill=(242, 84, 45), anchor="ra")
    image.save(out_jpg, "JPEG", quality=92)
    return out_jpg


def build_thumbnail(
    frame_path: Optional[Path],
    hook: str,
    source: str,
    stat: str,
    out_jpg: Path,
    vertical: bool = False,
    fallback_image: Optional[Path] = None,
) -> Optional[Path]:
    out_jpg = Path(out_jpg)
    out_jpg.parent.mkdir(parents=True, exist_ok=True)

    bg = frame_path if (frame_path and Path(frame_path).exists()) else fallback_image
    if not bg or not Path(bg).exists():
        default = Path("assets/streamer_studio_room.jpg")
        bg = default if default.exists() else None

    clean_hook = _short_hook(hook, 9 if not vertical else 11)
    clean_source = _clean(source, 60) or "AetherCut"
    clean_stat = _clean(stat, 12)

    bin_path = _browser_bin()
    if bg and bin_path:
        try:
            bg_uri = Path(bg).resolve().as_uri()
            html = _html(clean_hook, clean_source, clean_stat, bg_uri, vertical)
            html_path = out_jpg.with_suffix(".html")
            html_path.write_text(html, encoding="utf-8")
            width, height = (1080, 1920) if vertical else (1280, 720)
            png_tmp = out_jpg.with_suffix(".png")
            subprocess.run(
                [bin_path, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                 f"--screenshot={png_tmp.resolve()}", f"--window-size={width},{height}",
                 html_path.resolve().as_uri()],
                capture_output=True, timeout=25, check=True,
            )
            if png_tmp.exists() and png_tmp.stat().st_size > 5000:
                try:
                    from PIL import Image
                    with Image.open(png_tmp) as im:
                        im.convert("RGB").save(out_jpg, "JPEG", quality=93)
                    png_tmp.unlink(missing_ok=True)
                    html_path.unlink(missing_ok=True)
                    return out_jpg
                except Exception:
                    pass
        except Exception:
            pass

    return _fallback(clean_hook, clean_source, clean_stat, out_jpg, vertical)
