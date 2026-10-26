"""Renderizador visual del Avatar Copiloto IA (KAI) con dinámicas humanas.

Genera clips de video transparentes (.webm con canal alfa yuva420p) con:
1. Lip-sync reactivo al volumen real de la voz (análisis RMS del audio).
2. Parpadeo ocular natural cada 2.5 - 3 segundos (blink).
3. Micro-movimiento corporal de respiración y habla (sway/bobbing orgánico).
4. Anillo de audio HUD neón que pulsa según la energía de la voz.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DEFAULT_AVATAR_DIR = Path("assets/avatars/kai")
FONT_DIR = Path("C:/Windows/Fonts")


def _get_font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        p = FONT_DIR / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


class AvatarRenderer:
    """Genera animaciones fluidas y orgánicas del avatar sincronizadas con la voz."""

    def __init__(self, avatar_dir: Optional[Path] = None, badge_size: int = 500):
        self.avatar_dir = avatar_dir or DEFAULT_AVATAR_DIR
        self.size = badge_size

        self.idle_path = self.avatar_dir / "idle.jpg"
        self.talk_half_path = self.avatar_dir / "talking_half.jpg"
        self.talk_path = self.avatar_dir / "talking.jpg"
        self.point_path = self.avatar_dir / "pointing.jpg"
        self.blink_path = self.avatar_dir / "blink.jpg"
        self.think_path = self.avatar_dir / "thinking.jpg"
        self.happy_path = self.avatar_dir / "happy.jpg"

        self.idle_img = self._load_img(self.idle_path)
        self.talk_img = self._load_img(self.talk_path)
        self.talk_half_img = self._load_img(self.talk_half_path, fallback=self.talk_img)
        self.blink_img = self._load_img(self.blink_path, fallback=self.idle_img)
        self.point_img = self._load_img(self.point_path, fallback=self.idle_img)
        self.think_img = self._load_img(self.think_path, fallback=self.idle_img)
        self.happy_img = self._load_img(self.happy_path, fallback=self.talk_img)

    def _load_img(self, path: Path, fallback: Optional[Image.Image] = None) -> Image.Image:
        if path.exists():
            return Image.open(path).convert("RGBA")
        if fallback:
            return fallback.copy()
        canvas = Image.new("RGBA", (self.size, self.size), (24, 30, 48, 255))
        d = ImageDraw.Draw(canvas)
        d.ellipse((20, 20, self.size - 20, self.size - 20), fill=(56, 189, 248, 200))
        return canvas

    @staticmethod
    def _extract_audio_envelope(audio_path: Optional[Path], fps: int, total_frames: int) -> List[float]:
        """Calcula la curva de energía acústica RMS por fotograma para Lip-Sync reactivo."""
        if not audio_path or not Path(audio_path).exists():
            return []
        wav_tmp = audio_path.with_suffix(".tmp.wav")
        try:
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_path),
                "-ar", "16000", "-ac", "1", "-f", "wav", str(wav_tmp)
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)
            if not wav_tmp.exists():
                return []
            with wave.open(str(wav_tmp), "rb") as wf:
                raw = wf.readframes(wf.getnframes())
            samples = np.frombuffer(raw, dtype=np.int16)
            if len(samples) == 0:
                return []
            chunk_len = max(1, 16000 // fps)
            rms_list: List[float] = []
            for i in range(0, len(samples), chunk_len):
                chunk = samples[i:i + chunk_len]
                if len(chunk):
                    rms_list.append(float(np.sqrt(np.mean(chunk.astype(float) ** 2))))
            if not rms_list:
                return []
            max_rms = max(rms_list) + 1e-5
            # Normalizar con umbral dinámico para captar consonantes y vocales con precisión
            norm = [min(1.0, (r / (max_rms * 0.55)) ** 1.1) for r in rms_list]
            # Suavizado responsivo inmediato para que la boca se mueva exactamente en el fonema
            smoothed: List[float] = []
            for idx, val in enumerate(norm):
                prev_val = smoothed[-1] if smoothed else val
                smoothed.append(0.80 * val + 0.20 * prev_val)
            if len(smoothed) < total_frames:
                smoothed.extend([0.0] * (total_frames - len(smoothed)))
            return smoothed[:total_frames]
        except Exception as exc:
            print(f"[AvatarRenderer] No se pudo extraer envolvente de audio: {exc}")
            return []
        finally:
            wav_tmp.unlink(missing_ok=True)

    def render_reaction_clip(
        self,
        duration_sec: float,
        out_path: Path,
        audio_path: Optional[Path] = None,
        fps: int = 24
    ) -> Optional[Path]:
        """Crea un clip WebM transparente con avatar mirando fijo de frente y lip-sync sutil."""
        dur = min(60.0, max(2.0, float(duration_sec)))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = out_path.parent / f"_avatar_tmp_{out_path.stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        size = self.size
        total_frames = max(1, int(dur * fps))

        # 1. Extraer energía real del audio para sincronía labial
        envelope = self._extract_audio_envelope(audio_path, fps, total_frames)

        # Máscara circular con antialiasing
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((6, 6, size - 6, size - 6), fill=255)

        # Pre-redimensionar imágenes base mirando de frente
        img_idle = self.idle_img.resize((size, size), Image.Resampling.LANCZOS)
        img_half = self.talk_half_img.resize((size, size), Image.Resampling.LANCZOS)
        img_talk = self.talk_img.resize((size, size), Image.Resampling.LANCZOS)
        img_blink = self.blink_img.resize((size, size), Image.Resampling.LANCZOS)

        f_tag = _get_font(["segoeuib.ttf", "arialbd.ttf"], 13)

        try:
            for i in range(total_frames):
                # Parpadeo natural cada ~3 segundos (3 fotogramas de duración)
                blink_interval = int(fps * 3.2)
                is_blinking = (i % blink_interval) in (18, 19, 20)

                # Selección precisa de articulación bucal (solo menea la boca, postura fija de frente)
                if is_blinking:
                    current_img = img_blink
                    energy = envelope[i] if envelope else 0.15
                elif envelope:
                    energy = envelope[i]
                    if energy > 0.32:
                        current_img = img_talk       # Fonemas vocálicos abiertos y enfáticos
                    elif energy > 0.08:
                        current_img = img_half       # Fonemas semi-abiertos y consonantes
                    else:
                        current_img = img_idle       # Cierre labial exacto en pausas y silencios
                else:
                    # Si no hay pista de audio, cadencia suave de habla sin aspavientos
                    cadence = (i // 3) % 4
                    if cadence == 0:
                        current_img = img_idle
                    elif cadence in (1, 3):
                        current_img = img_half
                    else:
                        current_img = img_talk
                    energy = 0.35

                # Postura fija mirando a la cámara, con respiración subpíxel imperceptible (1px máx)
                subtle_breath_y = int(math.sin(i / (fps * 1.2)) * 1.0)

                canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                # Pegar avatar fijo y centrado
                canvas.paste(current_img, (0, subtle_breath_y), mask)
                d = ImageDraw.Draw(canvas)

                # Borde elegante y sutil de vidrio / HUD
                alpha_cyan = int(140 + 75 * energy)
                d.ellipse((4, 4, size - 4, size - 4), outline=(56, 189, 248, alpha_cyan), width=3)
                d.ellipse((8, 8, size - 8, size - 8), outline=(99, 102, 241, int(80 + 50 * energy)), width=1)

                # Insignia KAI RODRIGUEZ en la parte inferior
                tag_w = 142
                tag_h = 24
                tx = (size - tag_w) // 2
                ty = size - 34

                # Visualizador de Ondas de Audio (Waveform Spectrum) reactivo a la voz de KAI
                bars_count = 14
                bar_w = 4
                gap = 3
                total_wf_w = (bars_count * bar_w) + ((bars_count - 1) * gap)
                wf_start_x = (size - total_wf_w) // 2
                wf_y_center = ty - 8

                for b in range(bars_count):
                    # Frecuencia espectral y dinámica por barra
                    b_phase = math.sin((i / (fps * 0.4)) + (b * 0.75))
                    b_factor = 0.35 + 0.65 * abs(b_phase)
                    bar_h = max(3, int((14 * energy * b_factor) + (2 if energy > 0.05 else 0)))
                    bx_pos = wf_start_x + b * (bar_w + gap)
                    b_top = wf_y_center - (bar_h // 2)
                    b_bot = wf_y_center + (bar_h // 2)
                    
                    # Gradiente dinámico de cian a violeta neón
                    bar_alpha = int(120 + 135 * energy)
                    b_color = (56, 189, 248, bar_alpha) if b < (bars_count // 2) else (129, 140, 248, bar_alpha)
                    d.rounded_rectangle((bx_pos, b_top, bx_pos + bar_w, b_bot), radius=2, fill=b_color)

                d.rounded_rectangle(
                    (tx, ty, tx + tag_w, ty + tag_h),
                    radius=12,
                    fill=(10, 14, 22, 235),
                    outline=(56, 189, 248, 200),
                    width=1,
                )
                # Logo 'R' futurista vectorial geométrico
                bx = tx + 13
                by = ty + 12
                # Tronco vertical de la R
                d.polygon([(bx - 5, by - 6), (bx - 2, by - 6), (bx - 2, by + 6), (bx - 5, by + 6)], fill=(56, 189, 248, 255))
                # Bucle superior estilizado
                d.polygon([(bx - 2, by - 6), (bx + 4, by - 6), (bx + 6, by - 3), (bx + 4, by), (bx - 2, by)], fill=(56, 189, 248, 255))
                d.polygon([(bx - 1, by - 4), (bx + 2, by - 4), (bx + 3, by - 3), (bx + 2, by - 1), (bx - 1, by - 1)], fill=(10, 14, 22, 255))
                # Pata diagonal futurista de la R
                d.polygon([(bx - 1, by), (bx + 2, by), (bx + 6, by + 6), (bx + 2, by + 6)], fill=(255, 255, 255, 255))
                
                d.text(
                    (tx + 26, ty + 12),
                    "KAI RODRIGUEZ",
                    font=f_tag,
                    fill=(255, 255, 255, 255),
                    anchor="lm",
                )

                canvas.save(temp_dir / f"f_{i:04d}.png")

            if out_path.suffix.lower() == ".mov":
                cmd = [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", str(temp_dir / "f_%04d.png"),
                    "-c:v", "qtrle",
                    str(out_path),
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", str(temp_dir / "f_%04d.png"),
                    "-c:v", "libvpx-vp9",
                    "-pix_fmt", "yuva420p",
                    "-auto-alt-ref", "0",
                    "-deadline", "realtime",
                    "-cpu-used", "4",
                    "-threads", "4",
                    "-b:v", "0",
                    "-crf", "25",
                    str(out_path),
                ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and out_path.exists():
                return out_path
            print(f"[AvatarRenderer] Falló codificación de avatar: {res.stderr[-400:]}")
            return None
        except Exception as exc:
            print(f"[AvatarRenderer] Error renderizando avatar: {exc}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
