"""Motor procedural de escenas explicativas animadas para VIDCUT.

Genera overlays RGBA reproducibles usando Pillow + FFmpeg. No necesita APIs externas.
Las escenas son declarativas y seguras: solo se aceptan tipos y parámetros conocidos.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageFont


ALLOWED_SCENES = {"automation", "comparison", "cause_effect", "concept", "timeline", "flow", "network", "stat", "sequence", "route", "layers"}
FPS_DEFAULT = 24


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _fit_label(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> str:
    """Recorta etiquetas por búsqueda binaria; termina incluso con anchos mínimos."""
    text = str(text).strip()
    max_width = max(0, int(max_width))
    if not text or max_width == 0:
        return ""
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    if draw.textlength(ellipsis, font=font) > max_width:
        return ""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = text[:mid].rstrip() + ellipsis
        if draw.textlength(candidate, font=font) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ellipsis


class VisualSceneEngine:
    """Renderiza escenas explicativas transparentes para superponer sobre el video."""

    def __init__(self, fps: int = FPS_DEFAULT):
        try:
            requested_fps = int(fps)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Los FPS deben ser un número entero entre 12 y 30.") from exc
        if not 12 <= requested_fps <= 30:
            raise ValueError("Los FPS deben estar entre 12 y 30.")
        self.fps = requested_fps

    @staticmethod
    def validate(scene: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(scene, dict):
            raise ValueError("La escena debe ser un objeto.")
        kind = str(scene.get("kind", "concept")).strip().lower()
        if kind not in ALLOWED_SCENES:
            raise ValueError(f"Tipo de escena no permitido: {kind}")
        try:
            duration = float(scene.get("duration", 4.0))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("La duración debe ser un número entre 1 y 15 segundos.") from exc
        if not math.isfinite(duration) or not 1.0 <= duration <= 15.0:
            raise ValueError("La duración de una escena debe estar entre 1 y 15 segundos.")
        title = str(scene.get("title") or "")[:100]
        label_a = str(scene.get("label_a") or "PERSONA")[:48]
        label_b = str(scene.get("label_b") or "SISTEMA")[:48]
        return {"kind": kind, "duration": duration, "title": title,
                "label_a": label_a, "label_b": label_b}

    def render(self, scene: Dict[str, Any], output_path: Path,
               width: int = 1280, height: int = 720) -> Path:
        """Genera un MOV con canal alfa y animación determinista para usar como overlay."""
        spec = self.validate(scene)
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("No se encontró FFmpeg en PATH.")
        try:
            width, height = int(width), int(height)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("El ancho y el alto deben ser enteros válidos.") from exc
        if width < 320 or height < 240:
            raise ValueError("La resolución mínima de escena es 320x240.")
        if width > 3840 or height > 2160:
            raise ValueError("La resolución máxima de escena es 3840x2160 para limitar el uso de recursos.")
        output_path = Path(output_path)
        if output_path.suffix.lower() != ".mov":
            raise ValueError("Las escenas con transparencia deben exportarse a .mov.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames = max(1, round(spec["duration"] * self.fps))

        with tempfile.TemporaryDirectory(prefix="vidcut-scene-") as tmp:
            tmpdir = Path(tmp)
            for index in range(frames):
                t = index / max(1, frames - 1)
                img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img, "RGBA")
                # Editorial overlay: no giant card. Keep the illustration dominant and
                # use only a restrained title strip so the underlying footage remains visible.
                margin = int(width * 0.055)
                panel_w, panel_h = int(width * 0.89), int(height * 0.48)
                panel_x, panel_y = (width - panel_w) // 2, int(height * 0.27)
                fade = int(235 * _clamp(min(t * 8 + 0.05, (1 - t) * 8 + 0.05)))
                draw.rounded_rectangle(
                    (panel_x + int(width * .18), int(height * .10),
                     panel_x + int(panel_w * .82), int(height * .19)),
                    radius=max(8, width // 100), fill=(13, 16, 20, int(fade * .82)),
                    outline=(245, 245, 240, int(fade * .32)), width=max(1, width // 900))
                draw.rounded_rectangle(
                    (panel_x + int(width * .18), int(height * .10),
                     panel_x + int(width * .18) + max(4, width // 240), int(height * .19)),
                    radius=max(3, width // 300), fill=(235, 95, 63, fade))
                title = spec["title"] or {
                    "automation": "DE LA TAREA MANUAL A LA AUTOMATIZACIÓN",
                    "comparison": "COMPARACIÓN VISUAL",
                    "cause_effect": "CAUSA  →  CONSECUENCIA",
                    "concept": "IDEA CLAVE",
                    "timeline": "EVOLUCIÓN EN EL TIEMPO",
                    "flow": "CÓMO FUNCIONA",
                    "network": "RED DE RELACIONES",
                    "stat": "LA CIFRA CLAVE",
                    "sequence": "PASO A PASO",
                    "route": "RECORRIDO ESQUEMÁTICO",
                    "layers": "CÓMO SE COMPONE",
                }[spec["kind"]]
                title_font = _font(max(14, width // 52))
                title = _fit_label(draw, title[:48], title_font, int(width * .60))
                title_box = draw.textbbox((0, 0), title, font=title_font)
                title_width = title_box[2] - title_box[0]
                draw.text(((width - title_width) // 2, int(height * .12)), title,
                          font=title_font, fill=(250, 248, 242, fade))
                center_y = panel_y + int(panel_h * .52)
                left_x = panel_x + int(panel_w * .25)
                right_x = panel_x + int(panel_w * .75)
                travel = int(width * 0.018 * math.sin(t * math.pi * 2))
                label_font = _font(max(12, width // 90))
                label_a = _fit_label(draw, spec["label_a"], label_font, int(width * .28))
                label_b = _fit_label(draw, spec["label_b"], label_font, int(width * .28))
                if spec["kind"] == "automation":
                    self._stick_figure(draw, left_x + travel, center_y, height, fade)
                    self._robot(draw, right_x - travel, center_y, height, fade)
                    self._arrow(draw, left_x + int(width * .09), center_y, right_x - int(width * .09), center_y, fade)
                    left_label_x, right_label_x = left_x - int(width * .07), right_x - int(width * .07)
                elif spec["kind"] == "comparison":
                    baseline = center_y + int(height * .10)
                    draw.line((left_x-int(width*.07), baseline, right_x+int(width*.07), baseline),
                              fill=(235, 235, 230, int(fade*.65)), width=max(2, width//500))
                    height_left = int(height * (0.08 + 0.13 * (0.5 + 0.5 * math.sin(t * math.pi * 2))) )
                    height_right = int(height * (0.08 + 0.20 * (0.5 + 0.5 * math.sin(t * math.pi * 2 + 1.5))) )
                    self._bar(draw, left_x, baseline, height_left, fade, (105, 185, 230))
                    self._bar(draw, right_x, baseline, height_right, fade, (235, 125, 90))
                    left_label_x, right_label_x = left_x - int(width * .07), right_x - int(width * .07)
                elif spec["kind"] == "cause_effect":
                    r1 = int(height * .055)
                    r2 = int(height * (0.055 + 0.012 * (0.5 + 0.5 * math.sin(t * math.pi * 2))))
                    draw.ellipse((left_x-r1,center_y-r1,left_x+r1,center_y+r1),
                                 fill=(105,185,230,int(fade*.85)),outline=(245,248,242,fade),width=3)
                    self._arrow(draw, left_x + int(width * .08), center_y, right_x - int(width * .08), center_y, fade)
                    draw.ellipse((right_x-r2,center_y-r2,right_x+r2,center_y+r2),
                                 fill=(235,125,90,fade),outline=(245,248,242,fade),width=3)
                    left_label_x, right_label_x = left_x - int(width * .07), right_x - int(width * .07)
                elif spec["kind"] == "timeline":
                    # Two-point timeline with a moving progress marker.
                    y = center_y
                    x1, x2 = panel_x + int(panel_w * .18), panel_x + int(panel_w * .82)
                    draw.line((x1, y, x2, y), fill=(235, 235, 230, int(fade * .55)), width=max(3, width // 420))
                    for px, color in ((x1, (105, 185, 230)), (x2, (235, 125, 90))):
                        rr = int(height * .035)
                        draw.ellipse((px-rr, y-rr, px+rr, y+rr), fill=(*color, fade),
                                     outline=(245, 248, 242, fade), width=max(2, width // 600))
                    marker_x = int(x1 + (x2-x1) * _clamp(t))
                    mr = int(height * .018)
                    draw.ellipse((marker_x-mr, y-mr, marker_x+mr, y+mr),
                                 fill=(250, 248, 242, fade), outline=(235, 95, 63, fade), width=3)
                    left_label_x, right_label_x = x1 - int(width * .04), x2 - int(width * .04)
                elif spec["kind"] == "flow":
                    # A clear two-step process: input, connector, output.
                    box_w, box_h = int(width * .20), int(height * .12)
                    y1 = center_y - box_h // 2
                    for cx, color in ((left_x, (105, 185, 230)), (right_x, (235, 125, 90))):
                        draw.rounded_rectangle((cx-box_w//2, y1, cx+box_w//2, y1+box_h),
                            radius=max(8, width//120), fill=(13, 16, 20, int(fade*.82)),
                            outline=(*color, fade), width=max(3, width//360))
                    self._arrow(draw, left_x + box_w//2 + int(width*.015), center_y,
                                right_x - box_w//2 - int(width*.015), center_y, fade)
                    left_label_x, right_label_x = left_x - int(width * .07), right_x - int(width * .07)
                elif spec["kind"] == "network":
                    # A small relationship network, with links drawn before nodes.
                    cx, cy = width // 2, center_y
                    points = [
                        (cx, cy),
                        (cx-int(width*.15), cy-int(height*.09)),
                        (cx+int(width*.15), cy-int(height*.09)),
                        (cx-int(width*.15), cy+int(height*.09)),
                        (cx+int(width*.15), cy+int(height*.09)),
                    ]
                    for px, py in points[1:]:
                        draw.line((cx, cy, px, py), fill=(235, 95, 63, int(fade*.8)), width=max(2, width//420))
                    for idx, (px, py) in enumerate(points):
                        rr = int(height * (.032 if idx == 0 else .024))
                        col = (235, 125, 90) if idx == 0 else (105, 185, 230)
                        draw.ellipse((px-rr, py-rr, px+rr, py+rr), fill=(*col, fade),
                                     outline=(245, 248, 242, fade), width=max(2, width//600))
                    left_label_x, right_label_x = left_x - int(width * .07), right_x - int(width * .07)
                elif spec["kind"] == "sequence":
                    # Three sequential stages; animate the active stage across the timeline.
                    xs = [panel_x + int(panel_w * f) for f in (.20, .50, .80)]
                    y = center_y
                    for idx in range(2):
                        self._arrow(draw, xs[idx] + int(width*.045), y, xs[idx+1] - int(width*.045), y,
                                    int(fade * (.75 if t < (idx+1)/2 else 1)))
                    active = min(2, int(t * 3))
                    for idx, px in enumerate(xs):
                        rr = int(height * (.034 if idx == active else .026))
                        col = (235, 125, 90) if idx == active else (105, 185, 230)
                        draw.ellipse((px-rr, y-rr, px+rr, y+rr), fill=(*col, fade),
                                     outline=(245, 248, 242, fade), width=max(2, width//600))
                    left_label_x, right_label_x = xs[0] - int(width*.04), xs[2] - int(width*.04)
                elif spec["kind"] == "route":
                    # Schematic route, deliberately not a geographic map.
                    pts = [
                        (panel_x + int(panel_w*.18), center_y + int(height*.04)),
                        (panel_x + int(panel_w*.37), center_y - int(height*.07)),
                        (panel_x + int(panel_w*.55), center_y + int(height*.035)),
                        (panel_x + int(panel_w*.80), center_y - int(height*.06)),
                    ]
                    draw.line(pts, fill=(105, 185, 230, int(fade*.8)), width=max(4, width//300))
                    progress = _clamp(t) * (len(pts)-1)
                    segment = min(len(pts)-2, int(progress))
                    local_t = progress-segment
                    mx = int(pts[segment][0] + (pts[segment+1][0]-pts[segment][0])*local_t)
                    my = int(pts[segment][1] + (pts[segment+1][1]-pts[segment][1])*local_t)
                    for idx, (px, py) in enumerate((pts[0], pts[-1])):
                        rr = int(height*.025)
                        col = (105, 185, 230) if idx == 0 else (235, 125, 90)
                        draw.ellipse((px-rr, py-rr, px+rr, py+rr), fill=(*col, fade),
                                     outline=(245, 248, 242, fade), width=max(2, width//600))
                    rr = int(height*.014)
                    draw.ellipse((mx-rr, my-rr, mx+rr, my+rr), fill=(250, 248, 242, fade),
                                 outline=(235, 95, 63, fade), width=3)
                    left_label_x, right_label_x = pts[0][0]-int(width*.04), pts[-1][0]-int(width*.04)
                elif spec["kind"] == "layers":
                    # Three stacked layers make system architecture easier to explain.
                    layer_w, layer_h = int(width*.30), int(height*.055)
                    cx = width // 2
                    for idx, color in enumerate(((105, 185, 230), (180, 190, 200), (235, 125, 90))):
                        y1 = center_y - layer_h//2 + (idx-1)*int(height*.075)
                        offset = int(width*.012*math.sin(t*math.pi*2 + idx))
                        draw.rounded_rectangle((cx-layer_w//2+offset, y1, cx+layer_w//2+offset, y1+layer_h),
                            radius=max(5, width//180), fill=(13, 16, 20, int(fade*.82)),
                            outline=(*color, fade), width=max(2, width//500))
                    left_label_x, right_label_x = left_x-int(width*.07), right_x-int(width*.07)
                elif spec["kind"] == "stat":
                    # Editorial metric treatment. The scene label is the value/quantity,
                    # not an invented number: Gemini must supply a literal value from narration.
                    metric = spec["label_a"][:18]
                    metric_font = _font(max(28, width // 15))
                    bbox = draw.textbbox((0, 0), metric, font=metric_font)
                    draw.text(((width-(bbox[2]-bbox[0]))//2, center_y-int(height*.09)),
                              metric, font=metric_font, fill=(250, 248, 242, fade),
                              stroke_width=max(1, width//900), stroke_fill=(13, 16, 20, int(fade*.8)))
                    accent_y = center_y + int(height*.06)
                    draw.line((width//2-int(width*.12), accent_y, width//2+int(width*.12), accent_y),
                              fill=(235, 95, 63, fade), width=max(3, width//360))
                    left_label_x, right_label_x = -10000, -10000
                else:
                    # Concept map: central idea with three connected supporting nodes.
                    r = int(height * (.055 + .008 * math.sin(t * math.pi * 2)))
                    node_x, node_y = width // 2, center_y
                    for angle in (-math.pi/2, math.pi/6, 5*math.pi/6):
                        nx = int(node_x + width*.13*math.cos(angle))
                        ny = int(node_y + height*.12*math.sin(angle))
                        draw.line((node_x,node_y,nx,ny),fill=(235,95,63,int(fade*.85)),width=max(2,width//420))
                        nr = int(height*.025)
                        draw.ellipse((nx-nr,ny-nr,nx+nr,ny+nr),fill=(105,185,230,fade),
                                     outline=(245,248,242,fade),width=2)
                    draw.ellipse((node_x-r,node_y-r,node_x+r,node_y+r),
                                 fill=(13,16,20,int(fade*.92)),outline=(235,95,63,fade),width=max(3,width//300))
                    left_label_x, right_label_x = left_x - int(width * .07), right_x - int(width * .07)
                if spec["kind"] == "stat":
                    context_font = _font(max(12, width // 80))
                    context = _fit_label(draw, label_b, context_font, int(width * .50))
                    context_width = draw.textlength(context, font=context_font)
                    draw.text(((width-context_width)//2, center_y + int(height*.09)), context,
                              font=context_font, fill=(235, 235, 230, fade))
                else:
                    draw.text((left_label_x, center_y + int(height * .14)), label_a,
                              font=label_font, fill=(235, 235, 230, fade))
                    draw.text((right_label_x, center_y + int(height * .14)), label_b,
                              font=label_font, fill=(235, 235, 230, fade))
                img.save(tmpdir / f"frame_{index:06d}.png")
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-framerate", str(self.fps), "-i", str(tmpdir / "frame_%06d.png"),
                   "-frames:v", str(frames), "-an", "-c:v", "qtrle", "-pix_fmt", "argb",
                   str(output_path)]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            except subprocess.TimeoutExpired as exc:
                output_path.unlink(missing_ok=True)
                raise RuntimeError("El render de la escena superó el límite de 180 segundos.") from exc
            if proc.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
                output_path.unlink(missing_ok=True)
                detail = (proc.stderr or "FFmpeg no generó un archivo válido.")[-1000:]
                raise RuntimeError("No se pudo renderizar la escena animada: " + detail)
        return output_path

    @staticmethod
    def _stick_figure(draw, x, y, height, alpha):
        scale = height / 720
        r = int(17 * scale)
        ink = (245, 245, 240, alpha)
        draw.ellipse((x-r, y-int(105*scale)-r, x+r, y-int(105*scale)+r), outline=ink, width=max(2, int(4*scale)))
        draw.line((x, y-int(85*scale), x, y+int(5*scale)), fill=ink, width=max(3, int(5*scale)))
        draw.line((x, y-int(60*scale), x-int(34*scale), y-int(28*scale)), fill=ink, width=max(3, int(5*scale)))
        draw.line((x, y-int(60*scale), x+int(35*scale), y-int(40*scale)), fill=ink, width=max(3, int(5*scale)))
        draw.line((x, y+int(5*scale), x-int(27*scale), y+int(55*scale)), fill=ink, width=max(3, int(5*scale)))
        draw.line((x, y+int(5*scale), x+int(30*scale), y+int(55*scale)), fill=ink, width=max(3, int(5*scale)))

    @staticmethod
    def _robot(draw, x, y, height, alpha):
        s = height / 720
        w, h = int(70*s), int(70*s)
        draw.rounded_rectangle((x-w//2, y-int(100*s), x+w//2, y-int(100*s)+h),
                               radius=max(4, int(8*s)), fill=(75, 115, 135, alpha),
                               outline=(245, 245, 240, alpha), width=max(2, int(3*s)))
        for eye_x in (x-int(17*s), x+int(17*s)):
            draw.ellipse((eye_x-int(5*s), y-int(78*s), eye_x+int(5*s), y-int(68*s)),
                         fill=(250, 250, 245, alpha))
        draw.line((x, y-int(100*s), x, y-int(125*s)), fill=(245,245,240,alpha), width=max(2,int(3*s)))
        draw.ellipse((x-int(5*s), y-int(132*s), x+int(5*s), y-int(122*s)), fill=(235,95,63,alpha))
        draw.line((x-w//2, y-int(70*s), x-int(50*s), y-int(38*s)), fill=(245,245,240,alpha), width=max(2,int(4*s)))
        draw.line((x+w//2, y-int(70*s), x+int(50*s), y-int(38*s)), fill=(245,245,240,alpha), width=max(2,int(4*s)))

    @staticmethod
    def _arrow(draw, x1, y, x2, y2, alpha):
        color = (235, 95, 63, alpha)
        draw.line((x1, y, x2, y2), fill=color, width=5)
        head = 14
        draw.polygon(((x2, y2), (x2-head, y2-head//2), (x2-head, y2+head//2)), fill=color)

    @staticmethod
    def _bar(draw, x, baseline, height, alpha, color):
        width = 42
        draw.rounded_rectangle((x-width//2, baseline-height, x+width//2, baseline),
                               radius=5, fill=(*color, alpha))
