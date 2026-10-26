from __future__ import annotations
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from config.settings import settings
from core.llm import safe_log


def _get_font(names, size):
    for fn in names:
        p = Path("C:/Windows/Fonts") / fn
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def _open_as_rgb(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        base = Image.new("RGB", rgba.size, (9, 10, 13))
        base.paste(rgba, (0, 0), rgba)
        return base
    return im.convert("RGB")


STYLE_PALETTES = {
    "cinematic": {
        "gradient_left": (8, 8, 20), "gradient_mid": (15, 20, 45),
        "accent": (56, 189, 248), "text_main": (255, 255, 255),
        "text_accent": (254, 240, 138), "badge_bg": (239, 68, 68),
        "badge_text": "EXCLUSIVO", "vignette_alpha": 200,
        "blur_bg": 5, "enhance_contrast": 1.2,
    },
    "viral": {
        "gradient_left": (20, 4, 40), "gradient_mid": (40, 8, 60),
        "accent": (217, 70, 239), "text_main": (255, 255, 255),
        "text_accent": (250, 204, 21), "badge_bg": (217, 70, 239),
        "badge_text": "VIRAL", "vignette_alpha": 210,
        "blur_bg": 4, "enhance_contrast": 1.3,
    },
    "neon": {
        "gradient_left": (2, 14, 30), "gradient_mid": (4, 28, 55),
        "accent": (0, 255, 200), "text_main": (255, 255, 255),
        "text_accent": (0, 255, 200), "badge_bg": (0, 188, 150),
        "badge_text": "TECH", "vignette_alpha": 220,
        "blur_bg": 3, "enhance_contrast": 1.25,
    },
    "alerta": {
        "gradient_left": (30, 4, 4), "gradient_mid": (60, 10, 10),
        "accent": (239, 68, 68), "text_main": (255, 255, 255),
        "text_accent": (255, 200, 40), "badge_bg": (239, 68, 68),
        "badge_text": "URGENTE", "vignette_alpha": 230,
        "blur_bg": 4, "enhance_contrast": 1.4,
    },
    "educativo": {
        "gradient_left": (10, 20, 40), "gradient_mid": (20, 35, 70),
        "accent": (99, 102, 241), "text_main": (255, 255, 255),
        "text_accent": (165, 243, 252), "badge_bg": (99, 102, 241),
        "badge_text": "APRENDE", "vignette_alpha": 180,
        "blur_bg": 3, "enhance_contrast": 1.1,
    },
}


class YouTubeThumbnailMaker:
    W, H = 1280, 720

    def __init__(self, output_dir=None):
        self.output_dir = output_dir or settings.OUTPUTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, title, badge_text="", subtitle=None, project_id=None, style="cinematic", frame_path=None):
        W, H = self.W, self.H
        palette = STYLE_PALETTES.get(style, STYLE_PALETTES["cinematic"])
        safe_id = project_id or str(uuid.uuid4()).replace("-", "")[:8]
        thumb_id = "thumb_" + safe_id
        out_file = self.output_dir / (thumb_id + ".jpg")
        canvas = self._build_background(palette, project_id, frame_path, W, H)
        canvas = self._apply_gradient_overlay(canvas, palette, W, H)
        draw = ImageDraw.Draw(canvas)
        accent = palette["accent"]
        draw.rectangle([0, 0, 6, H], fill=accent)
        badge = badge_text.strip() or palette.get("badge_text", "KAI")
        self._draw_badge(draw, badge, palette, W, H)
        ty = self._draw_headline(draw, title, palette, W, H)
        if subtitle:
            self._draw_subtitle(draw, subtitle, ty, W, H)
        self._draw_footer(draw, palette, W, H)
        canvas = self._apply_vignette(canvas, W, H)
        canvas.save(str(out_file), "JPEG", quality=95)
        safe_log("[ThumbnailMaker] Generada: " + out_file.name)
        return {
            "thumbnail_id": thumb_id,
            "filename": out_file.name,
            "url": "/media/" + out_file.name,
            "path": str(out_file),
            "title": title,
            "badge": badge,
            "style": style,
        }

    def _build_background(self, palette, project_id, frame_path, W, H):
        bg_img = None
        if frame_path and Path(frame_path).exists():
            try:
                bg_img = _open_as_rgb(Path(frame_path))
            except Exception:
                bg_img = None
        if not bg_img and project_id:
            bg_img = self._find_project_frame(project_id)
        if bg_img:
            bg_w, bg_h = bg_img.size
            ratio = max(W / bg_w, H / bg_h)
            new_w, new_h = int(bg_w * ratio), int(bg_h * ratio)
            bg_resized = bg_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            x0 = (new_w - W) // 2
            y0 = (new_h - H) // 2
            canvas = bg_resized.crop((x0, y0, x0 + W, y0 + H))
            blur_r = palette.get("blur_bg", 4)
            canvas = canvas.filter(ImageFilter.GaussianBlur(blur_r))
            contrast = palette.get("enhance_contrast", 1.2)
            canvas = ImageEnhance.Contrast(canvas).enhance(contrast)
            canvas = ImageEnhance.Color(canvas).enhance(1.15)
        else:
            canvas = self._generate_gradient(palette, W, H)
        return canvas

    def _find_project_frame(self, project_id):
        proj_dir = settings.PROJECTS_DIR / project_id
        candidates = [
            proj_dir / "work" / "streamer_card_0.png",
            proj_dir / "work" / "scene_1" / "scene_thumb.jpg",
            proj_dir / "work" / "scene_0" / "scene_thumb.jpg",
        ]
        work_dir = proj_dir / "work"
        if work_dir.exists():
            for pattern in ["pub_frame_*.jpg", "frame_*.jpg", "*thumb*.jpg", "*thumb*.png"]:
                candidates.extend(sorted(work_dir.glob(pattern), reverse=True)[:3])
        candidates.extend(list(settings.OUTPUTS_DIR.glob("*" + project_id + "*card*.png"))[:2])
        candidates.extend(list(settings.OUTPUTS_DIR.glob("*" + project_id + "*.jpg"))[:2])
        for c in candidates:
            cp = Path(c)
            if cp.exists() and cp.stat().st_size > 0:
                try:
                    return _open_as_rgb(cp)
                except Exception:
                    pass
        return None

    def _generate_gradient(self, palette, W, H):
        canvas = Image.new("RGB", (W, H))
        pix = canvas.load()
        gl = palette["gradient_left"]
        gm = palette["gradient_mid"]
        for y in range(H):
            for x in range(W):
                hf = x / W
                vf = y / H
                r = int(gl[0] + (gm[0] - gl[0]) * hf + vf * 8)
                g = int(gl[1] + (gm[1] - gl[1]) * hf + vf * 6)
                b = int(gl[2] + (gm[2] - gl[2]) * hf + vf * 12)
                pix[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        return canvas

    def _apply_gradient_overlay(self, canvas, palette, W, H):
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        alpha_max = palette.get("vignette_alpha", 200)
        cover = int(W * 0.78)
        for x in range(cover):
            t = x / cover
            alpha = int(alpha_max * (1 - t ** 1.6))
            o_draw.line([(x, 0), (x, H)], fill=(5, 6, 12, alpha))
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.paste(overlay, (0, 0), overlay)
        return canvas_rgba.convert("RGB")

    def _apply_vignette(self, canvas, W, H):
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        for i in range(30):
            t = i / 30
            alpha = int(100 * (1 - t) ** 2)
            margin = i * 4
            d.rectangle([margin, margin, W - margin, H - margin],
                         outline=(0, 0, 0, alpha), width=3)
        result = canvas.convert("RGBA")
        result.paste(overlay, (0, 0), overlay)
        return result.convert("RGB")

    def _draw_badge(self, draw, text, palette, W, H):
        f = _get_font(["impact.ttf", "segoeuib.ttf", "arialbd.ttf"], 20)
        clean = text.upper().strip()
        tw = int(draw.textlength(clean, font=f))
        bw = tw + 44
        bh = 44
        bx, by = 20, 20
        bg = palette.get("badge_bg", (239, 68, 68))
        draw.rounded_rectangle([bx + 3, by + 3, bx + bw + 3, by + bh + 3], radius=6, fill=(0, 0, 0))
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=6, fill=bg)
        accent = palette["accent"]
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=6, outline=accent, width=2)
        draw.text((bx + 22, by + 11), clean, font=f, fill=(255, 255, 255))

    def _draw_headline(self, draw, title, palette, W, H):
        f_main = _get_font(["impact.ttf", "segoeuib.ttf", "arialbd.ttf"], 72)
        f_large = _get_font(["impact.ttf", "segoeuib.ttf", "arialbd.ttf"], 84)
        words = title.replace("\n", " ").split()
        lines = []
        curr = ""
        for w in words:
            cand = (curr + " " + w).strip()
            if len(cand) <= 17:
                curr = cand
            else:
                if curr:
                    lines.append(curr)
                curr = w
        if curr:
            lines.append(curr)
        lines = lines[:4]
        colors = [palette["text_main"], palette["text_accent"],
                  palette["text_main"], palette["text_accent"]]
        accent = palette["accent"]
        ty = 88
        for idx, line in enumerate(lines):
            line_txt = line.upper()
            font = f_large if idx == 0 and len(line_txt) <= 12 else f_main
            col = colors[idx % len(colors)]
            for offset in range(8, 1, -1):
                alpha_val = max(0, 255 - offset * 28)
                for dx, dy in [(-offset, -offset), (offset, offset), (-offset, offset), (offset, -offset)]:
                    try:
                        draw.text((20 + dx, ty + dy), line_txt, font=font, fill=(*accent[:3], alpha_val))
                    except TypeError:
                        draw.text((20 + dx, ty + dy), line_txt, font=font, fill=accent)
            for sx, sy in [(-3, -3), (3, 3), (-3, 3), (3, -3), (0, 4), (4, 0)]:
                draw.text((20 + sx, ty + sy), line_txt, font=font, fill=(0, 0, 0))
            draw.text((20, ty), line_txt, font=font, fill=col)
            ty += 84
        return ty

    def _draw_subtitle(self, draw, subtitle, ty, W, H):
        f = _get_font(["segoeuib.ttf", "arialbd.ttf", "segoeui.ttf"], 28)
        text = str(subtitle).strip()[:80]
        sub_y = min(H - 80, max(ty + 10, H - 120))
        draw.text((22, sub_y + 2), text, font=f, fill=(0, 0, 0))
        draw.text((20, sub_y), text, font=f, fill=(203, 213, 225))

    def _draw_footer(self, draw, palette, W, H):
        accent = palette["accent"]
        draw.line([(20, H - 30), (520, H - 30)], fill=accent, width=4)
        draw.ellipse([516, H - 36, 528, H - 24], fill=accent)
        f_sm = _get_font(["segoeui.ttf", "arial.ttf"], 16)
        draw.text((540, H - 38), "HD - KAI STUDIO", font=f_sm, fill=(100, 116, 139))