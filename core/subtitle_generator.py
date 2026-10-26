import re
from pathlib import Path
from typing import List

from core.models import CaptionItem


def _ass_time(sec: float) -> str:
    cs = int(round(max(0.0, sec) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


class SubtitleGenerator:
    """Subtítulos SRT y ASS de Estándar Universal Unificado.
    
    Características Premium:
    1. Tipografía elegante y equilibrada (Segoe UI Bold, tamaño no invasivo ~48px para 9:16).
    2. Safe-Zone garantizada: MarginV=380 en vertical para que los botones y textos inferiores de Reels no los tapen.
    3. Efecto Karaoke palabra por palabra: Cada palabra brilla en dorado (#FFE500 / &H0000E5FF&) al ser pronunciada,
       manteniendo el resto de la frase en blanco con contorno y sombra limpia.
    """

    @staticmethod
    def generate_ass(
        captions: List[CaptionItem],
        output_path: Path,
        width: int = 1920,
        height: int = 1080,
        karaoke: bool = True,
        highlight_color: str = "&H0000E5FF&",  # Dorado cálido brillante (BGR)
    ) -> Path:
        is_vertical = height > width
        # Tamaños equilibrados y profesionales
        size = 48 if is_vertical else 36
        outline = 3 if is_vertical else 2
        shadow = 2
        # Margen vertical seguro (380px en vertical para no chocar con la UI de Reels)
        margin_v = 380 if is_vertical else int(height * 0.08)
        margin_side = int(width * 0.08)

        header = f"""[Script Info]
Title: AetherCut Unified Captions
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Segoe UI,{size},&H00FFFFFF,&H0000E5FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_side},{margin_side},{margin_v},1
Style: Main2,Segoe UI,{size},&H0000E5FF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_side},{margin_side},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []

        for c in captions:
            raw_text = _escape(c.text)
            if not raw_text:
                continue

            # Censura de palabras si aplica
            for cw in getattr(c, "censor_words", []):
                cw_esc = _escape(cw)
                safe_word = cw_esc[0] + "*" * (len(cw_esc) - 2) + cw_esc[-1] if len(cw_esc) > 2 else "**"
                raw_text = re.sub(rf"(?i)\b({re.escape(cw_esc)})\b", safe_word, raw_text)

            words = raw_text.split()
            if not words:
                continue

            style = "Main" if getattr(c, "speaker_id", 1) == 1 else "Main2"
            start = max(0.0, float(c.start_sec))
            end = max(start + 0.2, float(c.end_sec))
            total_dur = end - start

            if karaoke and len(words) > 1 and total_dur >= 0.4:
                # Efecto Karaoke Palabra por Palabra
                total_chars = sum(max(1, len(w)) for w in words)
                cur_t = start
                for idx, w in enumerate(words):
                    w_dur = total_dur * (max(1, len(w)) / total_chars)
                    w_start = cur_t
                    w_end = min(end, cur_t + w_dur) if idx < len(words) - 1 else end
                    cur_t = w_end

                    # Construir la frase resaltando solo la palabra activa
                    line_parts = []
                    for j, other_w in enumerate(words):
                        if j == idx:
                            # Palabra activa brillando en dorado con un ligero scale pop (108%)
                            line_parts.append(rf"{{\c{highlight_color}\fscx108\fscy108}}{other_w}{{\r\s1\fnSegoe UI\fs{size}\b1\c&H00FFFFFF&}}")
                        else:
                            line_parts.append(other_w)

                    event_text = " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{_ass_time(w_start)},{_ass_time(w_end)},{style},,0,0,0,,{event_text}"
                    )
            else:
                # Frase completa con animación de entrada suave
                fx = r"{\fad(60,40)\fscx95\fscy95\t(0,100,\fscx100\fscy100)}"
                # Resaltado estático para palabras clave si existen
                hl_text = raw_text
                for hw in getattr(c, "highlight_words", []):
                    hw_esc = _escape(hw)
                    if hw_esc:
                        hl_text = re.sub(
                            rf"(?i)\b({re.escape(hw_esc)})\b",
                            rf"{{\\c{highlight_color}\\fscx106\\fscy106}}\1{{\\r\\s1\\fnSegoe UI\\fs{size}\\b1\\c&H00FFFFFF&}}",
                            hl_text,
                            count=1,
                        )
                events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{fx}{hl_text}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
        return output_path

