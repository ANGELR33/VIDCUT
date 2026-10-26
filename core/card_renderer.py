"""Módulo de renderizado de tarjetas gráficas (Info Cards) de alto impacto visual.

Estilo Pinterest / Modern Bento Glassmorphism:
- Diseño compacto, elegante y sin espacios vacíos.
- Soporte para tema Oscuro (Obsidian Glass) y Claro (Porcelain Snow Glass).
- Formato Bento horizontal para tarjetas con foto: miniatura redondeada a la izquierda,
  tipografía grande, nítida y de alto contraste a la derecha.
- Formato Floating Widget para datos de solo texto: altura auto-ajustada al contenido,
  micro-badge con indicador luminoso y pie de fuente verificado.
- Sombra difusa multicapa (ambient drop shadow) y sutil reflejo de cristal superior (rim highlight).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from core.models import InfoCard

FONT_DIR = Path("C:/Windows/Fonts")

# Paletas calibradas para micro-badges en estilo Negro Mate con Blanco puro (Zero azul, Zero morado)
BADGE_THEMES = {
    "white": {
        "dark": {"bg": (22, 22, 22, 255), "border": (255, 255, 255, 75), "text": (255, 255, 255, 255), "pip": (255, 255, 255, 255)},
        "light": {"bg": (245, 245, 245, 255), "border": (210, 210, 210, 255), "text": (15, 15, 15, 255), "pip": (15, 15, 15, 255)},
    },
    "green": {
        "dark": {"bg": (22, 22, 22, 255), "border": (255, 255, 255, 60), "text": (255, 255, 255, 255), "pip": (52, 211, 153, 255)},
        "light": {"bg": (241, 245, 249, 255), "border": (226, 232, 240, 255), "text": (15, 23, 42, 255), "pip": (16, 185, 129, 255)},
    },
    "amber": {
        "dark": {"bg": (22, 22, 22, 255), "border": (255, 255, 255, 60), "text": (255, 255, 255, 255), "pip": (251, 191, 36, 255)},
        "light": {"bg": (241, 245, 249, 255), "border": (226, 232, 240, 255), "text": (15, 23, 42, 255), "pip": (245, 158, 11, 255)},
    },
    "red": {
        "dark": {"bg": (22, 22, 22, 255), "border": (255, 255, 255, 60), "text": (255, 255, 255, 255), "pip": (248, 113, 113, 255)},
        "light": {"bg": (241, 245, 249, 255), "border": (226, 232, 240, 255), "text": (15, 23, 42, 255), "pip": (239, 68, 68, 255)},
    },
    "cyan": {
        "dark": {"bg": (22, 22, 22, 255), "border": (255, 255, 255, 75), "text": (255, 255, 255, 255), "pip": (255, 255, 255, 255)},
        "light": {"bg": (241, 245, 249, 255), "border": (226, 232, 240, 255), "text": (15, 23, 42, 255), "pip": (6, 182, 212, 255)},
    },
    "purple": {
        "dark": {"bg": (22, 22, 22, 255), "border": (255, 255, 255, 75), "text": (255, 255, 255, 255), "pip": (255, 255, 255, 255)},
        "light": {"bg": (241, 245, 249, 255), "border": (226, 232, 240, 255), "text": (15, 23, 42, 255), "pip": (168, 85, 247, 255)},
    },
}

KIND_LABELS = {
    "ley": ("NORMATIVA LEGAL", "white"),
    "normativa": ("NORMATIVA OFICIAL", "white"),
    "articulo": ("ARTÍCULO LEGAL", "white"),
    "cifra": ("ESTADÍSTICA", "white"),
    "estadistica": ("ESTADÍSTICA", "white"),
    "fecha": ("CRONOLOGÍA", "white"),
    "persona": ("PERFIL", "white"),
    "lugar": ("UBICACIÓN", "white"),
    "organizacion": ("INSTITUCIÓN", "white"),
    "organización": ("INSTITUCIÓN", "white"),
    "hardware": ("ESPECIFICACIÓN", "white"),
    "concepto": ("CONCEPTO CLAVE", "white"),
    "complemento": ("REFUERZO CLAVE", "white"),
    "refuerzo": ("REFUERZO CLAVE", "white"),
    "dato_extra": ("DATO EXTRA", "white"),
    "impacto": ("ESTUDIO DE IMPACTO", "white"),
    "contexto": ("CONTEXTO GLOBAL", "white"),
    "dato": ("DATO VERIFICADO", "white"),
    "confirmacion": ("CONFIRMADO", "white"),
    "confirmación": ("CONFIRMADO", "white"),
}


def _font(names: List[str], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        path = FONT_DIR / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                pass
    return ImageFont.load_default()


class InfoCardRenderer:
    """
    Renderizador de tarjetas estilo Pinterest / Bento Glassmorphism.
    """

    def __init__(self, frame_w: int, frame_h: int, theme: str = "dark"):
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.portrait = frame_h > frame_w

    @staticmethod
    def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int) -> List[str]:
        lines: List[str] = []
        for p in (text or "").split("\n"):
            p = p.strip()
            if not p:
                continue
            words = p.split()
            cur = ""
            for w in words:
                trial = f"{cur} {w}".strip()
                if draw.textlength(trial, font=font) <= max_w:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(" .,;:") + "…"
        return lines

    def _get_single_badge(self, card: InfoCard) -> Tuple[str, str]:
        verdict = (card.verdict or "").lower()
        if verdict == "contradicted":
            return ("CORRECCIÓN OFICIAL", "red")
        if verdict == "insufficient":
            return ("EN REVISIÓN", "amber")

        if card.stat_value:
            return (f"DATO CLAVE: {card.stat_value[:18]}", "amber")

        kind = (card.kind or "dato").lower()
        if kind in KIND_LABELS:
            return KIND_LABELS[kind]

        return ("DATO CONFIRMADO", "green")

    def _render_pinterest_glass_card(
        self,
        headline: str,
        body: str,
        badge_text: str,
        badge_tone: str = "white",
        image_path: Optional[str] = None,
        source_domain: str = "Registro oficial",
        out_path: Optional[Path] = None,
    ) -> Path:
        """
        Renderiza la tarjeta con estética Pinterest Glassmorphism compacta y elegante.
        """
        scale = 2  # Super-sampling para máxima nitidez

        # Fuentes calibradas de mayor escala y nitidez para Full HD
        f_badge = _font(["segoeuib.ttf", "arialbd.ttf"], 12 * scale)
        f_title = _font(["segoeuib.ttf", "arialbd.ttf"], 22 * scale)
        f_body = _font(["segoeui.ttf", "arial.ttf"], 16 * scale)
        f_src = _font(["segoeuib.ttf", "segoeui.ttf"], 12 * scale)

        # Paleta según tema
        if self.theme == "dark":
            # Negro mate puro (Strictly R=G=B, Zero azul, Zero morado) con blanco puro de alto contraste
            bg_card_top = (14, 14, 14, 252)
            bg_card_bot = (7, 7, 7, 254)
            border_top = (255, 255, 255, 60)
            title_color = (255, 255, 255, 255)
            body_color = (245, 245, 245, 255)
            src_color = (175, 175, 175, 245)
            shadow_color = (0, 0, 0, 180)
        else:
            bg_card_top = (255, 255, 255, 248)
            bg_card_bot = (245, 247, 250, 252)
            border_top = (255, 255, 255, 230)
            title_color = (15, 23, 42, 255)
            body_color = (51, 65, 85, 255)
            src_color = (100, 116, 139, 230)
            shadow_color = (15, 23, 42, 50)

        bcfg = BADGE_THEMES.get(badge_tone, BADGE_THEMES["white"])[self.theme]
        badge_bg = bcfg["bg"]
        badge_border = bcfg["border"]
        badge_txt_col = bcfg["text"]
        pip_col = bcfg["pip"]

        has_photo = bool(image_path and Path(image_path).exists())

        # Dimensiones de alto impacto visual y legibilidad óptima en Full HD
        card_w = 840 if not has_photo else 920
        if self.portrait:
            card_w = min(card_w, int(self.frame_w * 0.92))

        pad_x = 32
        pad_y = 28
        radius = 24

        # Layout horizontal si hay foto (Bento split)
        photo_w = 210 if has_photo else 0
        photo_gap = 26 if has_photo else 0

        text_avail_w = card_w - (pad_x * 2) - photo_w - photo_gap

        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        title_lines = self._wrap(probe, headline, f_title, text_avail_w * scale, max_lines=2)
        body_lines = self._wrap(probe, body, f_body, text_avail_w * scale, max_lines=4)

        title_lh = int(32 * scale)
        body_lh = int(24 * scale)
        badge_h = int(28 * scale)

        content_h_px = (
            badge_h
            + int(12 * scale)
            + (len(title_lines) * title_lh)
            + int(8 * scale)
            + (len(body_lines) * body_lh)
            + int(12 * scale)
            + int(16 * scale)
        )
        content_h = content_h_px // scale

        if has_photo:
            photo_h = max(content_h, 140)
            card_h = max(content_h + (pad_y * 2), photo_h + (pad_y * 2))
        else:
            card_h = content_h + (pad_y * 2)

        W = card_w * scale
        H = card_h * scale
        R = radius * scale

        # 1. Gradiente translúcido
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card)
        for y in range(H):
            t = y / max(1, H - 1)
            r = int(bg_card_top[0] * (1 - t) + bg_card_bot[0] * t)
            g = int(bg_card_top[1] * (1 - t) + bg_card_bot[1] * t)
            b = int(bg_card_top[2] * (1 - t) + bg_card_bot[2] * t)
            a = int(bg_card_top[3] * (1 - t) + bg_card_bot[3] * t)
            c_draw.line([(0, y), (W, y)], fill=(r, g, b, a))

        # 2. Máscara redondeada
        round_mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(round_mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=R, fill=255)
        card_masked = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        card_masked.paste(card, (0, 0), round_mask)
        d = ImageDraw.Draw(card_masked)

        # 3. Foto a la izquierda si existe
        text_start_x = (pad_x + photo_w + photo_gap) * scale if has_photo else pad_x * scale
        if has_photo:
            pw = photo_w * scale
            ph = (card_h - (pad_y * 2)) * scale
            px_pos = pad_x * scale
            py_pos = pad_y * scale
            pr = 12 * scale

            try:
                raw = Image.open(image_path).convert("RGB")
                ratio = max(pw / raw.width, ph / raw.height)
                resized = raw.resize((int(raw.width * ratio) + 1, int(raw.height * ratio) + 1), Image.LANCZOS)
                left = (resized.width - pw) // 2
                top = (resized.height - ph) // 2
                cropped = resized.crop((left, top, left + pw, top + ph)).convert("RGBA")

                pmask = Image.new("L", (pw, ph), 0)
                ImageDraw.Draw(pmask).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=pr, fill=255)
                card_masked.paste(cropped, (px_pos, py_pos), pmask)

                # Borde sutil a la miniatura
                d.rounded_rectangle(
                    (px_pos, py_pos, px_pos + pw - 1, py_pos + ph - 1),
                    radius=pr,
                    outline=(255, 255, 255, 50) if self.theme == "dark" else (0, 0, 0, 25),
                    width=1 * scale,
                )
            except Exception as exc:
                print(f"[CardRenderer] Error procesando imagen {image_path}: {exc}")

        # 4. Texto
        cur_y = pad_y * scale

        # Micro-badge estilo Pinterest
        b_text = badge_text.upper()
        tw = d.textlength(b_text, font=f_badge)
        b_w = int(tw + (24 * scale))
        b_rect = (text_start_x, cur_y, text_start_x + b_w, cur_y + badge_h)
        d.rounded_rectangle(b_rect, radius=badge_h // 2, fill=badge_bg, outline=badge_border, width=1 * scale)

        # Indicador luminoso
        dot_r = 3 * scale
        dot_cx = text_start_x + (8 * scale)
        dot_cy = cur_y + (badge_h // 2)
        d.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=pip_col)

        # Etiqueta de badge
        d.text((text_start_x + (16 * scale), dot_cy), b_text, font=f_badge, fill=badge_txt_col, anchor="lm")
        cur_y += badge_h + int(10 * scale)

        # Titular Bold nítido
        for line in title_lines:
            d.text((text_start_x, cur_y), line, font=f_title, fill=title_color)
            cur_y += title_lh
        cur_y += int(6 * scale)

        # Cuerpo
        for line in body_lines:
            d.text((text_start_x, cur_y), line, font=f_body, fill=body_color)
            cur_y += body_lh
        cur_y += int(10 * scale)

        # Fuente
        src_text = f"Fuente: {source_domain}"
        d.text((text_start_x, cur_y), src_text, font=f_src, fill=src_color)

        # Downscale con Lanczos
        card_final = card_masked.resize((card_w, card_h), Image.LANCZOS)

        # 5. Sombra difusa multicapa (ambient drop shadow)
        margin = 24
        shadow = Image.new("RGBA", (card_w + 2 * margin, card_h + 2 * margin), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rounded_rectangle(
            (margin, margin + 6, margin + card_w, margin + card_h + 6),
            radius=radius,
            fill=shadow_color,
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))

        # Compuesto final
        out_img = Image.new("RGBA", (card_w + 2 * margin, card_h + 2 * margin), (0, 0, 0, 0))
        out_img.paste(shadow, (0, 0), shadow)
        out_img.paste(card_final, (margin, margin), card_final)

        # Borde de cristal con luz superior
        border_img = Image.new("RGBA", (card_w + 2 * margin, card_h + 2 * margin), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(border_img)
        b_draw.rounded_rectangle(
            (margin, margin, margin + card_w - 1, margin + card_h - 1),
            radius=radius,
            outline=border_top,
            width=1,
        )
        out_img = Image.alpha_composite(out_img, border_img)

        target_out = out_path or Path("card_output.png")
        target_out.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(target_out, "PNG")
        return target_out

    def _render_stat_hero_card(
        self,
        headline: str,
        stat_value: str,
        body: str,
        badge_text: str = "DATO CLAVE",
        badge_tone: str = "amber",
        image_path: Optional[str] = None,
        source_domain: str = "Registro oficial",
        out_path: Optional[Path] = None,
    ) -> Path:
        """
        Renderiza una tarjeta Bento HUD de alto impacto visual para datos y estadísticas,
        con Cifra Gigante (Hero Stat), gráfico infográfico renderizado con Matplotlib,
        diseño Obsidian Glassmorphism y tipografía de estudio broadcast.
        """
        import re
        scale = 2  # Super-sampling para máxima nitidez

        # Fuentes calibradas de gran escala para legibilidad en Full HD
        f_badge = _font(["segoeuib.ttf", "arialbd.ttf"], 13 * scale)
        f_stat = _font(["segoeuib.ttf", "arialbd.ttf"], 44 * scale)   # Cifra masiva de alto impacto
        f_title = _font(["segoeuib.ttf", "arialbd.ttf"], 25 * scale)  # Titular nítido
        f_body = _font(["segoeui.ttf", "arial.ttf"], 16 * scale)      # Síntesis
        f_src = _font(["segoeuib.ttf", "segoeui.ttf"], 12 * scale)    # Pie

        # Colores Obsidian Glass Pro / Neon Studio
        # Fondo translúcido con gradiente de cristal ahumado profundo (sin opacar el video de fondo como bloque negro tosco)
        bg_card_top = (15, 23, 42, 225)
        bg_card_bot = (10, 15, 30, 238)
        border_top = (148, 163, 184, 110)
        stat_color = (251, 191, 36, 255) if badge_tone == "amber" else (56, 189, 248, 255)
        title_color = (255, 255, 255, 255)
        body_color = (203, 213, 225, 255)
        src_color = (148, 163, 184, 210)
        shadow_color = (0, 0, 0, 140)

        bcfg = BADGE_THEMES.get(badge_tone, BADGE_THEMES["white"])[self.theme]
        badge_bg = (30, 41, 59, 240)
        badge_border = (56, 189, 248, 120)
        badge_txt_col = (255, 255, 255, 255)
        pip_col = (56, 189, 248, 255) if badge_tone != "amber" else (251, 191, 36, 255)

        # 1. Renderizar gráfico infográfico profesional o mapa geopolítico (mayor tamaño y legibilidad)
        chart_w_logical = 340
        chart_h_logical = 260
        chart_img: Optional[Image.Image] = None
        try:
            from core.chart_generator import BroadcastChartGenerator
            # Enriquecer el contexto con body y headline para que detecte países (ej. México, EE.UU.) y datos
            enriched_context = f"{headline} {body}".strip()
            chart_img = BroadcastChartGenerator.render_chart_image(
                stat_value=stat_value,
                headline=enriched_context,
                width_px=chart_w_logical * scale,
                height_px=chart_h_logical * scale,
                dpi=150
            )
        except Exception as exc:
            print(f"[CardRenderer] Info: Matplotlib chart no disponible para esta métrica: {exc}")

        has_chart = chart_img is not None
        has_photo = bool(image_path and Path(image_path).exists()) and not has_chart

        # Proporción Bento heroica centrada calibrada para Full HD 1920x1080 (1060px de presencia cinematográfica)
        card_w = 1060
        if self.portrait:
            card_w = min(card_w, int(self.frame_w * 0.94))

        pad_x = 36
        pad_y = 32
        radius = 28

        visual_w = chart_w_logical if has_chart else (260 if has_photo else 0)
        visual_gap = 36 if (has_chart or has_photo) else 0

        text_avail_w = card_w - (pad_x * 2) - visual_w - visual_gap

        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        # Resumen limpio: extraer solo la parte informativa sin redundancias
        clean_body = body
        if clean_body.startswith(f"Cifra confirmada: {stat_value}."):
            clean_body = clean_body.replace(f"Cifra confirmada: {stat_value}.", "").strip()
        elif clean_body.startswith("Cifra confirmada:"):
            clean_body = re.sub(r"^Cifra confirmada:.*?\.\s*", "", clean_body).strip()

        title_lines = self._wrap(probe, headline, f_title, text_avail_w * scale, max_lines=2)
        body_lines = self._wrap(probe, clean_body or body, f_body, text_avail_w * scale, max_lines=3)

        badge_h = int(28 * scale)
        stat_h = int(52 * scale)
        title_lh = int(34 * scale)
        body_lh = int(24 * scale)
        src_lh = int(18 * scale)

        # Altura calculada para textos con espaciado respirable
        text_content_h_px = (
            badge_h
            + int(14 * scale)
            + stat_h
            + int(10 * scale)
            + (len(title_lines) * title_lh)
            + (int(10 * scale) if body_lines else 0)
            + (len(body_lines) * body_lh)
            + int(16 * scale)
            + src_lh
        )
        text_content_h = text_content_h_px // scale

        if has_chart or has_photo:
            visual_h = chart_h_logical if has_chart else 240
            card_h = max(text_content_h + (pad_y * 2), visual_h + (pad_y * 2) + 16)
        else:
            card_h = text_content_h + (pad_y * 2)

        W = card_w * scale
        H = card_h * scale
        R = radius * scale

        # Fondo con gradiente Obsidian Glass
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card)
        for y in range(H):
            t = y / max(1, H - 1)
            r = int(bg_card_top[0] * (1 - t) + bg_card_bot[0] * t)
            g = int(bg_card_top[1] * (1 - t) + bg_card_bot[1] * t)
            b = int(bg_card_top[2] * (1 - t) + bg_card_bot[2] * t)
            a = int(bg_card_top[3] * (1 - t) + bg_card_bot[3] * t)
            c_draw.line([(0, y), (W, y)], fill=(r, g, b, a))

        # Máscara redondeada
        round_mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(round_mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=R, fill=255)
        card_masked = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        card_masked.paste(card, (0, 0), round_mask)
        d = ImageDraw.Draw(card_masked)

        # Insertar gráfico o foto a la izquierda con bezel independiente enmarcado
        text_start_x = (pad_x + visual_w + visual_gap) * scale if (has_chart or has_photo) else pad_x * scale
        if has_chart and chart_img is not None:
            cw = visual_w * scale
            ch = chart_h_logical * scale
            cx_pos = pad_x * scale
            cy_pos = int((H - ch) / 2)
            # Enmarcar en una sub-caja con fondo de cristal sutil y borde neón para que no flote suelto
            bezel_box = (cx_pos, cy_pos, cx_pos + cw - 1, cy_pos + ch - 1)
            d.rounded_rectangle(bezel_box, radius=12 * scale, fill=(15, 23, 42, 180), outline=(56, 189, 248, 60), width=1 * scale)
            resized_chart = chart_img.resize((cw, ch), Image.LANCZOS)
            card_masked.paste(resized_chart, (cx_pos, cy_pos), resized_chart)
        elif has_photo and image_path:
            pw = visual_w * scale
            ph = (card_h - (pad_y * 2)) * scale
            px_pos = pad_x * scale
            py_pos = pad_y * scale
            pr = 14 * scale
            try:
                raw = Image.open(image_path).convert("RGB")
                ratio = max(pw / raw.width, ph / raw.height)
                resized = raw.resize((int(raw.width * ratio) + 1, int(raw.height * ratio) + 1), Image.LANCZOS)
                left = (resized.width - pw) // 2
                top = (resized.height - ph) // 2
                cropped = resized.crop((left, top, left + pw, top + ph)).convert("RGBA")
                pmask = Image.new("L", (pw, ph), 0)
                ImageDraw.Draw(pmask).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=pr, fill=255)
                card_masked.paste(cropped, (px_pos, py_pos), pmask)
                d.rounded_rectangle((px_pos, py_pos, px_pos + pw - 1, py_pos + ph - 1), radius=pr, outline=(255, 255, 255, 50), width=1 * scale)
            except Exception as exc:
                print(f"[CardRenderer] Error insertando foto en stat card: {exc}")

        # Textos
        cur_y = pad_y * scale

        # Micro-badge
        b_text = badge_text.upper()
        tw = d.textlength(b_text, font=f_badge)
        b_w = int(tw + (26 * scale))
        b_rect = (text_start_x, cur_y, text_start_x + b_w, cur_y + badge_h)
        d.rounded_rectangle(b_rect, radius=badge_h // 2, fill=badge_bg, outline=badge_border, width=1 * scale)
        dot_r = 3 * scale
        dot_cx = text_start_x + (9 * scale)
        dot_cy = cur_y + (badge_h // 2)
        d.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=pip_col)
        d.text((text_start_x + (18 * scale), dot_cy), b_text, font=f_badge, fill=badge_txt_col, anchor="lm")
        cur_y += badge_h + int(10 * scale)

        # Cifra Gigante (Hero Stat)
        d.text((text_start_x, cur_y), stat_value, font=f_stat, fill=stat_color)
        cur_y += stat_h + int(4 * scale)

        # Titular Bold
        for line in title_lines:
            d.text((text_start_x, cur_y), line, font=f_title, fill=title_color)
            cur_y += title_lh
        cur_y += int(6 * scale)

        # Explicación / Resumen
        for line in body_lines:
            d.text((text_start_x, cur_y), line, font=f_body, fill=body_color)
            cur_y += body_lh
        cur_y += int(8 * scale)

        # Fuente
        src_text = f"Fuente: {source_domain}  |  Datos Verificados"
        d.text((text_start_x, cur_y), src_text, font=f_src, fill=src_color)

        # Downscale final con Lanczos
        card_final = card_masked.resize((card_w, card_h), Image.LANCZOS)

        # Sombra ambiental difusa
        margin = 26
        shadow = Image.new("RGBA", (card_w + 2 * margin, card_h + 2 * margin), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rounded_rectangle(
            (margin, margin + 8, margin + card_w, margin + card_h + 8),
            radius=radius,
            fill=shadow_color,
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))

        out_img = Image.new("RGBA", (card_w + 2 * margin, card_h + 2 * margin), (0, 0, 0, 0))
        out_img.paste(shadow, (0, 0), shadow)
        out_img.paste(card_final, (margin, margin), card_final)

        # Borde de cristal con luz superior
        border_img = Image.new("RGBA", (card_w + 2 * margin, card_h + 2 * margin), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(border_img)
        b_draw.rounded_rectangle(
            (margin, margin, margin + card_w - 1, margin + card_h - 1),
            radius=radius,
            outline=border_top,
            width=1,
        )
        out_img = Image.alpha_composite(out_img, border_img)

        target_out = out_path or Path("stat_card_output.png")
        target_out.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(target_out, "PNG")
        return target_out

    def render(self, card: InfoCard, out_path: Path) -> str:
        """Renderiza la tarjeta con el diseño unificado 2026 Matte Dark + Ámbar Glow."""
        domain = card.sources[0].domain if card.sources else "Registro Oficial 2026"
        badge_text, badge_tone = self._get_single_badge(card)
        out_target = Path(out_path)
        out_target.parent.mkdir(parents=True, exist_ok=True)
        img_path = Path(card.image_path) if getattr(card, "image_path", None) and Path(card.image_path).exists() else None

        try:
            from core.web_card_renderer import WebCardRenderer
            web_ren = WebCardRenderer()

            headline = card.headline or ""
            body = card.body or card.claim or ""
            stat_val = card.stat_value or ""

            if card.verdict == "contradicted":
                badge_text = "CORRECCIÓN OFICIAL"
                correction_text = card.correction or card.corrected_value or card.note
                if correction_text:
                    body = f"«{card.claim}» — Confirmado: {correction_text}"
                c_style = "quote"
            elif card.verdict == "insufficient":
                badge_text = "EN REVISIÓN"
                c_style = "auto"
            elif stat_val:
                c_style = "auto"
            else:
                c_style = "auto"

            res = web_ren.render_to_image(
                headline=headline,
                out_png=out_target,
                stat_value=stat_val,
                stat_label=getattr(card, "stat_label", "") or ("Cifra Verificada" if stat_val else ""),
                body=body,
                badge=badge_text,
                source=domain,
                style=c_style,
                image_path=img_path,
            )
            return str(res)
        except Exception as _we:
            return str(self._render_pinterest_glass_card(
                headline=card.headline or "",
                body=card.body or card.claim or "",
                badge_text=badge_text,
                badge_tone=badge_tone,
                image_path=card.image_path,
                source_domain=domain,
                out_path=out_target,
            ))

    def render_photo_frame(self, image_path: str, label: str, out_path: Path) -> Optional[Path]:
        """Foto contextual enmarcada en formato Bento Matte Dark con badge de apoyo visual."""
        try:
            from core.web_card_renderer import WebCardRenderer
            web_ren = WebCardRenderer()
            out_p = Path(out_path)
            img_p = Path(image_path) if image_path and Path(image_path).exists() else None
            return web_ren.render_to_image(
                headline=label.strip(),
                out_png=out_p,
                body="Apoyo visual contextual integrado para ilustrar el argumento expuesto.",
                badge="APOYO VISUAL",
                source="Registro Visual 2026",
                style="photo" if img_p else "auto",
                image_path=img_p,
            )
        except Exception as exc:
            print(f"[CardRenderer] No se pudo enmarcar la foto: {exc}")
            return None

    def _render_myth_cards(self, card: InfoCard, out_path: Path) -> str:
        """Renderiza dos tarjetas: MITO y REALIDAD."""
        path_mito = out_path.with_name(f"{out_path.stem}_mito.png")
        path_real = out_path.with_name(f"{out_path.stem}_real.png")
        domain = card.correction_source or (card.sources[0].domain if card.sources else "Registro oficial")

        self._render_pinterest_glass_card(
            headline="Mito Popular",
            body=f"«{card.claim}»",
            badge_text="MITO POPULAR",
            badge_tone="amber",
            image_path=card.image_path,
            source_domain=domain,
            out_path=path_mito,
        )

        self._render_pinterest_glass_card(
            headline=card.headline or "Realidad Verificada",
            body=card.correction or card.corrected_value or card.body,
            badge_text="REALIDAD CONFIRMADA",
            badge_tone="green",
            image_path=card.image_path,
            source_domain=domain,
            out_path=path_real,
        )

        return f"{path_mito}|{path_real}"

    def render_broadcast_lower_third(
        self,
        headline: str,
        subtitle: str = "",
        tag: str = "EN VIVO",
        out_path: Optional[Path] = None,
    ) -> Path:
        """
        Rótulo de televisión broadcast (Lower Third) estilo documental contemporáneo:
        - Franja de vidrio ahumado (Glassmorphism Obsidian / Slate)
        - Badge lateral luminoso (ej: EN VIVO, ANÁLISIS GLOBAL, DATO CLAVE)
        - Titular nítido de alto impacto + subtítulo explicativo o ubicación
        - Sombra ambiental difusa y rim highlight superior
        """
        scale = 2
        card_w = int(self.frame_w * (0.86 if self.portrait else 0.48))
        card_h = 104 if not subtitle else 126

        W = card_w * scale
        H = card_h * scale
        radius = 18 * scale

        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        # Fondo Obsidian Glass
        bg_col = (16, 17, 22, 235) if self.theme == "dark" else (248, 249, 250, 240)
        border_col = (255, 255, 255, 55) if self.theme == "dark" else (200, 205, 215, 255)
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=radius, fill=bg_col, outline=border_col, width=1 * scale)

        # Tipografías Segoe UI
        f_tag = _font(["segoeuib.ttf", "arialbd.ttf"], 11 * scale)
        f_title = _font(["segoeuib.ttf", "arialbd.ttf"], 18 * scale)
        f_sub = _font(["segoeui.ttf", "arial.ttf"], 13 * scale)

        pad_x = 22 * scale
        cur_y = 16 * scale

        # 1. Tag / Badge superior
        clean_tag = (tag or "ANÁLISIS").strip().upper()
        tw = d.textlength(clean_tag, font=f_tag)
        badge_w = int(tw + (24 * scale))
        badge_h = 22 * scale
        badge_bg = (30, 32, 40, 255) if self.theme == "dark" else (230, 234, 242, 255)
        badge_border = (255, 255, 255, 60) if self.theme == "dark" else (190, 195, 205, 255)
        d.rounded_rectangle((pad_x, cur_y, pad_x + badge_w, cur_y + badge_h), radius=badge_h // 2, fill=badge_bg, outline=badge_border, width=1 * scale)
        
        # Punto luminoso
        dot_r = 3 * scale
        dot_cx = pad_x + (8 * scale)
        dot_cy = cur_y + (badge_h // 2)
        d.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=(52, 211, 153, 255))
        d.text((pad_x + (16 * scale), dot_cy), clean_tag, font=f_tag, fill=(255, 255, 255, 255) if self.theme == "dark" else (20, 20, 20, 255), anchor="lm")
        cur_y += badge_h + (8 * scale)

        # 2. Titular principal
        title_txt = headline.strip()
        if d.textlength(title_txt, font=f_title) > (W - pad_x * 2):
            # Recortar con elipsis si excede
            while title_txt and d.textlength(title_txt + "…", font=f_title) > (W - pad_x * 2):
                title_txt = title_txt[:-1]
            title_txt = title_txt.strip() + "…"
        d.text((pad_x, cur_y), title_txt, font=f_title, fill=(255, 255, 255, 255) if self.theme == "dark" else (15, 17, 23, 255))
        cur_y += int(24 * scale)

        # 3. Subtítulo o ubicación si existe
        if subtitle:
            sub_txt = subtitle.strip()
            if d.textlength(sub_txt, font=f_sub) > (W - pad_x * 2):
                while sub_txt and d.textlength(sub_txt + "…", font=f_sub) > (W - pad_x * 2):
                    sub_txt = sub_txt[:-1]
                sub_txt = sub_txt.strip() + "…"
            d.text((pad_x, cur_y), sub_txt, font=f_sub, fill=(180, 185, 195, 255) if self.theme == "dark" else (100, 105, 115, 255))

        # Downscale con Lanczos
        final_w = W // scale
        final_h = H // scale
        comp_card = im.resize((final_w, final_h), Image.LANCZOS)

        # Sombra ambiental difusa
        margin = 20
        shadow = Image.new("RGBA", (final_w + 2 * margin, final_h + 2 * margin), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rounded_rectangle((margin, margin + 4, margin + final_w, margin + final_h + 4), radius=radius // scale, fill=(0, 0, 0, 160))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))

        out_img = Image.new("RGBA", (final_w + 2 * margin, final_h + 2 * margin), (0, 0, 0, 0))
        out_img.paste(shadow, (0, 0), shadow)
        out_img.paste(comp_card, (margin, margin), comp_card)

        target = out_path or Path("lower_third.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(target, "PNG")
        return target

    def render_info_popup(
        self,
        text: str,
        kind: str = "fact",
        out_path: Optional[Path] = None,
    ) -> Path:
        """
        Micro Pop-up HUD reactivo sincronizado con la frase:
        - Pastilla compacta Obsidian Glass con brillo de borde
        - Indicador luminoso de color según categoría (stat=ámbar, fact=cian, alert=rojo, quote=esmeralda)
        - Tipografía de alta fidelidad, padding respirable y sombra difusa suave
        """
        scale = 2
        pad_x = 26 * scale
        h_logical = 64
        H = h_logical * scale
        radius = (h_logical // 2) * scale

        palette = {
            "stat": ((251, 191, 36, 255), "DATO"),
            "fact": ((56, 189, 248, 255), "CLAVE"),
            "alert": ((248, 113, 113, 255), "ALERTA"),
            "quote": ((52, 211, 153, 255), "CITA"),
        }
        pip_col, tag_label = palette.get(kind.lower(), ((56, 189, 248, 255), "CLAVE"))

        f_txt = _font(["segoeuib.ttf", "arialbd.ttf"], 20 * scale)
        f_tag = _font(["segoeuib.ttf", "arialbd.ttf"], 13 * scale)

        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        clean_text = text.strip()
        txt_w = int(probe.textlength(clean_text, font=f_txt))
        tag_w = int(probe.textlength(tag_label, font=f_tag))

        W = pad_x * 2 + tag_w + (28 * scale) + txt_w
        W = max(int(280 * scale), W)

        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        # Fondo obsidian con borde sutil
        d.rounded_rectangle(
            (0, 0, W - 1, H - 1),
            radius=radius,
            fill=(14, 15, 20, 240) if self.theme == "dark" else (248, 249, 252, 245),
            outline=(255, 255, 255, 65) if self.theme == "dark" else (200, 205, 220, 255),
            width=1 * scale,
        )

        cur_x = pad_x
        # Punto de luz
        dot_r = 3.5 * scale
        dot_cy = H // 2
        d.ellipse((cur_x, dot_cy - dot_r, cur_x + dot_r * 2, dot_cy + dot_r), fill=pip_col)
        cur_x += int(11 * scale)

        # Etiqueta mini badge
        d.text((cur_x, dot_cy), tag_label, font=f_tag, fill=pip_col, anchor="lm")
        cur_x += tag_w + int(12 * scale)

        # Divisor vertical sutil
        d.line([(cur_x, int(10 * scale)), (cur_x, H - int(10 * scale))], fill=(255, 255, 255, 40), width=1 * scale)
        cur_x += int(12 * scale)

        # Texto informativo
        text_fill = (255, 255, 255, 255) if self.theme == "dark" else (15, 23, 42, 255)
        d.text((cur_x, dot_cy), clean_text, font=f_txt, fill=text_fill, anchor="lm")

        final_w = W // scale
        final_h = H // scale
        comp = im.resize((final_w, final_h), Image.LANCZOS)

        margin = 12
        shadow = Image.new("RGBA", (final_w + 2 * margin, final_h + 2 * margin), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (margin, margin + 3, margin + final_w, margin + final_h + 3),
            radius=h_logical // 2,
            fill=(0, 0, 0, 160),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))

        out_img = Image.new("RGBA", (final_w + 2 * margin, final_h + 2 * margin), (0, 0, 0, 0))
        out_img.paste(shadow, (0, 0), shadow)
        out_img.paste(comp, (margin, margin), comp)

        target = out_path or Path("info_popup.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(target, "PNG")
        return target

    def render_all(self, cards: List[InfoCard], workdir: Path) -> List[InfoCard]:
        for card in cards:
            if not card.enabled or card.verdict not in ("supported", "contradicted", "insufficient"):
                continue
            try:
                card.card_path = str(self.render(card, workdir / f"{card.card_id}_card.png"))
            except Exception as exc:
                print(f"[CardRenderer] Error dibujando {card.card_id}: {exc}")
        return cards
