"""Renderizador visual de Overlay de Chat en Vivo para Modo Streamer.

Diseño:
- Contenedor flotante en Negro Mate Glassmorphism con reborde blanco sutil.
- Cabecera con indicador luminoso en rojo: ● CHAT EN VIVO.
- Mensajes estilo Twitch/YouTube Live con avatares de colores y nombres de usuario.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = Path("C:/Windows/Fonts")


def _font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        p = FONT_DIR / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


class LiveChatRenderer:
    """Renderiza una ventana de chat en vivo translúcida con estética de transmisión."""

    def __init__(self, width: int = 340):
        self.width = width

    def render(self, comments: List[Tuple[str, str, str]], out_path: Path) -> Path:
        """
        comments: Lista de tuplas (username, color_hex_or_rgb, message)
        """
        scale = 2
        w = self.width * scale
        pad_x = 16 * scale
        pad_y = 14 * scale

        f_hdr = _font(["segoeuib.ttf", "arialbd.ttf"], 10 * scale)
        f_user = _font(["segoeuib.ttf", "arialbd.ttf"], 11 * scale)
        f_msg = _font(["segoeui.ttf", "arial.ttf"], 11 * scale)

        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        max_txt_w = w - (pad_x * 2) - (12 * scale)

        # Medir altura
        hdr_h = 24 * scale
        msg_items = []
        cur_h = pad_y + hdr_h + (8 * scale)

        for user, col, text in comments[:4]:
            # Wrap text
            words = text.split()
            lines = []
            cur_line = ""
            for word in words:
                trial = f"{cur_line} {word}".strip()
                if probe.textlength(trial, font=f_msg) <= max_txt_w:
                    cur_line = trial
                else:
                    if cur_line:
                        lines.append(cur_line)
                    cur_line = word
            if cur_line:
                lines.append(cur_line)

            lines = lines[:2]
            lh = 15 * scale
            block_h = (16 * scale) + (len(lines) * lh) + (8 * scale)
            msg_items.append((user, col, lines, lh))
            cur_h += block_h

        cur_h += pad_y
        total_h = cur_h

        # 1. Fondo negro mate translúcido
        card = Image.new("RGBA", (w, total_h), (0, 0, 0, 0))
        d_card = ImageDraw.Draw(card)
        d_card.rounded_rectangle(
            (0, 0, w - 1, total_h - 1),
            radius=14 * scale,
            fill=(12, 12, 14, 230),
            outline=(255, 255, 255, 45),
            width=1 * scale,
        )

        # 2. Cabecera Chat en Vivo
        cy = pad_y
        # Indicador rojo pulsante
        d_card.ellipse((pad_x, cy + (3 * scale), pad_x + (8 * scale), cy + (11 * scale)), fill=(239, 68, 68, 255))
        d_card.text((pad_x + (14 * scale), cy + (7 * scale)), "CHAT EN DIRECTO", font=f_hdr, fill=(255, 255, 255, 220), anchor="lm")
        
        # Divisor sutil
        cy += hdr_h
        d_card.line([(pad_x, cy), (w - pad_x, cy)], fill=(255, 255, 255, 30), width=1 * scale)
        cy += 8 * scale

        # 3. Comentarios
        for user, col_name, lines, lh in msg_items:
            # Color tag
            tag_color = (56, 189, 248, 255) if col_name == "cyan" else (251, 191, 36, 255) if col_name == "amber" else (52, 211, 153, 255)
            d_card.text((pad_x, cy), user, font=f_user, fill=tag_color)
            cy += 16 * scale

            for line in lines:
                d_card.text((pad_x + (4 * scale), cy), line, font=f_msg, fill=(240, 240, 245, 255))
                cy += lh
            cy += 8 * scale

        # 4. Reducción Lanczos y sombra
        final_w = self.width
        final_h = total_h // scale
        card_resized = card.resize((final_w, final_h), Image.LANCZOS)

        margin = 16
        shadow = Image.new("RGBA", (final_w + 2 * margin, final_h + 2 * margin), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rounded_rectangle(
            (margin, margin + 4, margin + final_w, margin + final_h + 4),
            radius=14,
            fill=(0, 0, 0, 160),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))

        out_img = Image.new("RGBA", (final_w + 2 * margin, final_h + 2 * margin), (0, 0, 0, 0))
        out_img.paste(shadow, (0, 0), shadow)
        out_img.paste(card_resized, (margin, margin), card_resized)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(out_path, "PNG")
        return out_path
