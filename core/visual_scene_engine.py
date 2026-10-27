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


ALLOWED_SCENES = {"automation", "comparison", "cause_effect", "concept"}
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


class VisualSceneEngine:
    """Renderiza escenas explicativas transparentes para superponer sobre el video."""

    def __init__(self, fps: int = FPS_DEFAULT):
        self.fps = max(12, min(int(fps), 30))

    @staticmethod
    def validate(scene: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(scene, dict):
            raise ValueError("La escena debe ser un objeto.")
        kind = str(scene.get("kind", "concept")).lower()
        if kind not in ALLOWED_SCENES:
            raise ValueError(f"Tipo de escena no permitido: {kind}")
        duration = float(scene.get("duration", 4.0))
        if not 1.0 <= duration <= 15.0:
            raise ValueError("La duración de una escena debe estar entre 1 y 15 segundos.")
        title = str(scene.get("title", ""))[:100]
        label_a = str(scene.get("label_a", "PERSONA"))[:48]
        label_b = str(scene.get("label_b", "SISTEMA"))[:48]
        return {"kind": kind, "duration": duration, "title": title,
                "label_a": label_a, "label_b": label_b}

    def render(self, scene: Dict[str, Any], output_path: Path,
               width: int = 1280, height: int = 720) -> Path:
        """Genera un MOV con canal alfa y animación determinista para usar como overlay."""
        spec = self.validate(scene)
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("No se encontró FFmpeg en PATH.")
        width, height = max(320, int(width)), max(240, int(height))
        output_path = Path(output_path)
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
                }[spec["kind"]]
                draw.text((panel_x + margin, panel_y + int(height * .035)), title,
                          font=_font(max(14, width // 52)), fill=(250, 248, 242, fade))
                center_y = panel_y + int(panel_h * .52)
                left_x = panel_x + int(panel_w * .25)
                right_x = panel_x + int(panel_w * .75)
                travel = int(width * 0.018 * math.sin(t * math.pi * 2))
                label_font = _font(max(12, width // 90))
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
                draw.text((left_label_x, center_y + int(height * .14)), spec["label_a"],
                          font=label_font, fill=(235, 235, 230, fade))
                draw.text((right_label_x, center_y + int(height * .14)), spec["label_b"],
                          font=label_font, fill=(235, 235, 230, fade))
                img.save(tmpdir / f"frame_{index:06d}.png")
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-framerate", str(self.fps), "-i", str(tmpdir / "frame_%06d.png"),
                   "-frames:v", str(frames), "-an", "-c:v", "qtrle", "-pix_fmt", "argb",
                   str(output_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if proc.returncode != 0 or not output_path.exists():
                raise RuntimeError("No se pudo renderizar la escena animada: " + proc.stderr[-1000:])
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
