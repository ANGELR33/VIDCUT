"""
Motion Graphics Engine (HyperFrames, Remotion & Native WebM/SVG Adapter)
Genera capas cinéticas sutiles de microelementos (partículas de luz ambiental,
esquineros geométricos finos, marcadores técnicos y destellos fugaces) diseñados por GLM-5.3.
"""

import json
import logging
import math
import random
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("aethercut.motion_engine")


class MotionGraphicsEngine:
    def __init__(self, web_renderer=None, is_vertical: bool = False):
        self.web_renderer = web_renderer
        self.is_vertical = is_vertical
        self.W = 1080 if is_vertical else 1920
        self.H = 1920 if is_vertical else 1080

    def build_composition_html(
        self,
        motion_spec: Dict[str, Any],
        duration: float,
        palette_color: str = "#ff9436",
    ) -> str:
        """
        Genera la composición HTML5/SVG/CSS determinista con microelementos sutiles.
        Mantiene despejado el centro y la esquina inferior derecha.
        """
        particles_cfg = motion_spec.get("particles", {})
        p_count = min(24, max(8, int(particles_cfg.get("count", 16))))
        p_color = particles_cfg.get("color", palette_color)
        geo_accents = motion_spec.get("geometric_accents", [])
        fleeting = motion_spec.get("fleeting_accents", [])

        # Generar posiciones aleatorias deterministas para las partículas en zonas periféricas seguras
        random.seed(int(duration * 100) + len(str(motion_spec)))
        particles_html = []
        for i in range(p_count):
            # Zonas periféricas: top bar (y: 60-180), left bar (x: 40-280), right bar (x: W-320 a W-40)
            zone = random.choice(["top", "left", "right", "bottom_left"])
            if zone == "top":
                x = random.randint(120, self.W - 120)
                y = random.randint(70, 200)
            elif zone == "left":
                x = random.randint(60, 260)
                y = random.randint(180, self.H - 220)
            elif zone == "right":
                x = random.randint(self.W - 280, self.W - 70)
                y = random.randint(120, int(self.H * 0.55))  # evitar tapar avatar PIP
            else:
                x = random.randint(80, int(self.W * 0.40))
                y = random.randint(self.H - 240, self.H - 80)

            size = random.uniform(3.5, 6.5)
            opac = random.uniform(0.18, 0.42)
            dur_anim = random.uniform(2.8, 4.5)
            delay = random.uniform(0.0, 2.0)
            drift_y = random.choice([-16, -24, 18])
            drift_x = random.choice([-8, 8, 12, -12])

            particles_html.append(
                f'<div class="p-dot" style="width:{size:.1f}px;height:{size:.1f}px;'
                f'left:{x}px;top:{y}px;--opac:{opac:.2f};--dy:{drift_y}px;--dx:{drift_x}px;'
                f'animation: pDrift {dur_anim:.2f}s ease-in-out {delay:.2f}s infinite alternate;"></div>'
            )

        # Generar esquineros y marcadores HUD finos
        geo_html = []
        for g in geo_accents:
            g_type = g.get("type", "")
            g_col = g.get("color", palette_color)
            if g_type == "corner_brackets":
                geo_html.append(f"""
                <div class="hud-bracket b-tl" style="border-color:{g_col};"></div>
                <div class="hud-bracket b-tr" style="border-color:{g_col};"></div>
                <div class="hud-bracket b-bl" style="border-color:{g_col};"></div>
                """)
            elif g_type == "tech_marker":
                txt = g.get("text", "REC // SYS")
                geo_html.append(f"""
                <div class="hud-marker" style="color:{g_col};">
                  <span class="m-dot" style="background:{g_col};"></span>
                  <span>{txt}</span>
                </div>
                """)

        # Elementos fugaces
        fleeting_html = []
        for fl in fleeting:
            st = float(fl.get("start_sec", 4.0))
            fdur = float(fl.get("duration_sec", 2.0))
            fcol = fl.get("color", palette_color)
            fleeting_html.append(f"""
            <div class="fleeting-accent" style="border-color:{fcol};animation: fleetingAnim {fdur:.2f}s ease-out {st:.2f}s forwards;">
              <div class="f-pulse" style="background:{fcol};box-shadow:0 0 16px {fcol};"></div>
            </div>
            """)

        # Insignias secuenciales escalonadas (Países, fechas, empresas) diseñadas por DeepSeek
        seq_badges = motion_spec.get("sequential_badges", [])
        badges_html = []
        if seq_badges and isinstance(seq_badges, list):
            b_items = []
            for b in seq_badges:
                lbl = b.get("label", "")
                emoji = b.get("emoji", "")
                del_s = float(b.get("delay_sec", 1.0))
                display_txt = f"{emoji} {lbl}".strip() if emoji else lbl
                if display_txt:
                    b_items.append(f'<div class="badge-item" style="animation-delay:{del_s:.2f}s;">{display_txt}</div>')
            if b_items:
                badges_html.append(f'<div class="badges-rack">{"".join(b_items)}</div>')

        # Estadística cinética destacada
        stat_cfg = motion_spec.get("kinetic_stat", {})
        stat_html = []
        if stat_cfg.get("enabled") and stat_cfg.get("value"):
            val = stat_cfg.get("value", "")
            lbl = stat_cfg.get("label", "DATO DESTACADO")
            del_s = float(stat_cfg.get("delay_sec", 1.5))
            stat_html.append(f"""
            <div class="kinetic-stat-card" style="animation-delay:{del_s:.2f}s;">
              <div class="stat-val">{val}</div>
              <div class="stat-lbl">{lbl}</div>
            </div>
            """)

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width={self.W}, height={self.H}">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{
      width: {self.W}px; height: {self.H}px;
      background: transparent;
      overflow: hidden;
      font-family: 'Space Grotesk', -apple-system, sans-serif;
    }}
    .p-dot {{
      position: absolute;
      border-radius: 50%;
      background: {p_color};
      box-shadow: 0 0 10px {p_color};
      pointer-events: none;
    }}
    @keyframes pDrift {{
      0% {{ transform: translate(0, 0) scale(0.9); opacity: calc(var(--opac) * 0.6); }}
      100% {{ transform: translate(var(--dx), var(--dy)) scale(1.15); opacity: var(--opac); }}
    }}
    .hud-bracket {{
      position: absolute;
      width: 32px; height: 32px;
      pointer-events: none;
      opacity: 0.40;
      animation: bracketPulse 3.5s ease-in-out infinite alternate;
    }}
    .b-tl {{ top: 44px; left: 44px; border-top: 1.5px solid; border-left: 1.5px solid; }}
    .b-tr {{ top: 44px; right: 44px; border-top: 1.5px solid; border-right: 1.5px solid; }}
    .b-bl {{ bottom: 44px; left: 44px; border-bottom: 1.5px solid; border-left: 1.5px solid; }}
    @keyframes bracketPulse {{
      from {{ opacity: 0.25; transform: scale(0.98); }}
      to {{ opacity: 0.50; transform: scale(1.02); }}
    }}
    .hud-marker {{
      position: absolute;
      top: 50px; left: 88px;
      display: inline-flex; align-items: center; gap: 8px;
      font-size: 11px; font-weight: 700; letter-spacing: 0.20em;
      opacity: 0.35; pointer-events: none;
    }}
    .m-dot {{
      width: 5px; height: 5px; border-radius: 50%;
      box-shadow: 0 0 6px currentColor;
    }}
    .fleeting-accent {{
      position: absolute;
      top: 35%; left: 15%;
      width: 80px; height: 2px;
      background: linear-gradient(90deg, transparent, currentColor, transparent);
      opacity: 0; pointer-events: none;
    }}
    @keyframes fleetingAnim {{
      0% {{ opacity: 0; transform: scaleX(0.2) translateX(-20px); }}
      30% {{ opacity: 0.65; transform: scaleX(1.0) translateX(0); }}
      80% {{ opacity: 0.50; transform: scaleX(1.1) translateX(15px); }}
      100% {{ opacity: 0; transform: scaleX(0.8) translateX(25px); }}
    }}
    .badges-rack {{
      position: absolute;
      bottom: 260px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 12px;
      max-width: 90%;
      z-index: 50;
    }}
    .badge-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 22px;
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(16px);
      border: 1.5px solid rgba(255, 255, 255, 0.22);
      border-radius: 9999px;
      color: #ffffff;
      font-size: 24px;
      font-weight: 800;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
      opacity: 0;
      animation: badgePop 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    @keyframes badgePop {{
      0% {{ opacity: 0; transform: scale(0.65) translateY(24px); }}
      70% {{ transform: scale(1.08) translateY(-4px); }}
      100% {{ opacity: 1; transform: scale(1) translateY(0); }}
    }}
    .kinetic-stat-card {{
      position: absolute;
      top: 420px;
      left: 50%;
      transform: translateX(-50%);
      padding: 18px 36px;
      background: rgba(10, 15, 30, 0.88);
      backdrop-filter: blur(20px);
      border: 1.5px solid rgba(255, 255, 255, 0.20);
      border-radius: 24px;
      text-align: center;
      opacity: 0;
      animation: statPop 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65);
      z-index: 45;
    }}
    .stat-val {{
      font-size: 68px;
      font-weight: 900;
      color: #FFE500;
      letter-spacing: -0.02em;
      text-shadow: 0 0 28px rgba(255, 229, 0, 0.45);
    }}
    .stat-lbl {{
      font-size: 17px;
      font-weight: 700;
      color: rgba(255, 255, 255, 0.85);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-top: 4px;
    }}
    @keyframes statPop {{
      0% {{ opacity: 0; transform: translateX(-50%) scale(0.75); }}
      100% {{ opacity: 1; transform: translateX(-50%) scale(1); }}
    }}
  </style>
</head>
<body data-duration="{duration:.1f}" data-fps="25">
  {"".join(geo_html)}
  {"".join(particles_html)}
  {"".join(fleeting_html)}
  {"".join(badges_html)}
  {"".join(stat_html)}
</body>
</html>"""
        return html

    def render_individual_badge_sync(
        self,
        label: str,
        emoji: str,
        out_png: Path,
        accent_color: str = "#ff9436",
    ) -> Optional[Dict[str, Any]]:
        """Renderiza una insignia individual como PNG transparente recortado de alta definición."""
        try:
            out_png = Path(out_png)
            html_p = out_png.with_suffix(".html")
            display_txt = label.strip()
            emoji_txt = emoji.strip() if emoji else "•"

            html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{
      background: transparent;
      display: inline-block;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    }}
    .badge-pill {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 12px 28px;
      background: rgba(11, 16, 28, 0.94);
      border: 2px solid {accent_color};
      border-radius: 9999px;
      color: #ffffff;
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.01em;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.7), 0 0 22px rgba(255, 148, 54, 0.28);
      white-space: nowrap;
    }}
    .badge-emoji {{
      font-size: 30px;
      line-height: 1;
    }}
    .badge-text {{
      text-transform: capitalize;
    }}
  </style>
</head>
<body>
  <div class="badge-pill">
    <span class="badge-emoji">{emoji_txt}</span>
    <span class="badge-text">{display_txt}</span>
  </div>
</body>
</html>"""
            html_p.write_text(html, encoding="utf-8")

            from core.web_card_renderer import _get_browser_bin
            browser_bin = _get_browser_bin()
            args = [
                browser_bin,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--default-background-color=00000000",
                f"--screenshot={out_png.resolve()}",
                "--window-size=800,260",
                html_p.resolve().as_uri(),
            ]
            subprocess.run(args, capture_output=True, check=True, timeout=12)

            from PIL import Image
            im = Image.open(out_png)
            bbox = im.getbbox()
            if bbox:
                pad = 4
                cropped = im.crop((
                    max(0, bbox[0] - pad),
                    max(0, bbox[1] - pad),
                    min(im.width, bbox[2] + pad),
                    min(im.height, bbox[3] + pad),
                ))
                cropped.save(out_png)
                w, h = cropped.size
            else:
                w, h = im.size

            try:
                html_p.unlink(missing_ok=True)
            except Exception:
                pass

            return {"path": out_png, "width": w, "height": h, "label": display_txt, "emoji": emoji_txt}
        except Exception as exc:
            logger.warning(f"[MotionEngine] Error renderizando insignia individual '{label}': {exc}")
            return None

    def render_kinetic_stat_card_sync(
        self,
        value: str,
        label: str,
        out_png: Path,
        accent_color: str = "#FFE500",
    ) -> Optional[Dict[str, Any]]:
        """Renderiza una tarjeta de estadística cinética destacada como PNG transparente."""
        try:
            out_png = Path(out_png)
            html_p = out_png.with_suffix(".html")
            val_txt = value.strip()
            lbl_txt = (label or "MÉTRICA CLAVE").strip().upper()

            html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{
      background: transparent;
      display: inline-block;
      padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    .stat-card {{
      display: inline-flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 18px 42px;
      background: rgba(14, 15, 20, 0.78);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1.5px solid rgba(255, 148, 54, 0.35);
      border-radius: 24px;
      text-align: center;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.80), 0 0 30px rgba(255, 148, 54, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.15);
      white-space: nowrap;
    }}
    .stat-val {{
      font-size: 64px;
      font-weight: 900;
      color: {accent_color};
      letter-spacing: -0.02em;
      text-shadow: 0 0 24px rgba(255, 229, 0, 0.40);
      line-height: 1.1;
    }}
    .stat-lbl {{
      font-size: 16px;
      font-weight: 800;
      color: rgba(255, 255, 255, 0.88);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      margin-top: 6px;
    }}
  </style>
</head>
<body>
  <div class="stat-card">
    <div class="stat-val">{val_txt}</div>
    <div class="stat-lbl">{lbl_txt}</div>
  </div>
</body>
</html>"""
            html_p.write_text(html, encoding="utf-8")

            from core.web_card_renderer import _get_browser_bin
            browser_bin = _get_browser_bin()
            args = [
                browser_bin,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--default-background-color=00000000",
                f"--screenshot={out_png.resolve()}",
                "--window-size=800,400",
                html_p.resolve().as_uri(),
            ]
            subprocess.run(args, capture_output=True, check=True, timeout=12)

            from PIL import Image
            im = Image.open(out_png)
            bbox = im.getbbox()
            if bbox:
                pad = 4
                cropped = im.crop((
                    max(0, bbox[0] - pad),
                    max(0, bbox[1] - pad),
                    min(im.width, bbox[2] + pad),
                    min(im.height, bbox[3] + pad),
                ))
                cropped.save(out_png)
                w, h = cropped.size
            else:
                w, h = im.size

            try:
                html_p.unlink(missing_ok=True)
            except Exception:
                pass

            return {"path": out_png, "width": w, "height": h, "value": val_txt, "label": lbl_txt}
        except Exception as exc:
            logger.warning(f"[MotionEngine] Error renderizando stat card: {exc}")
            return None

    async def render_scene_motion_assets(
        self,
        motion_spec: Dict[str, Any],
        duration: float,
        scene_dir: Path,
        scene_id: int = 0,
        accent_color: str = "#ff9436",
    ) -> Dict[str, Any]:
        """
        Renderiza tanto la capa de fondo (partículas y HUD) como los elementos cinéticos
        interactivos individuales (insignias escalonadas y métricas) para composición en FFmpeg.
        """
        scene_dir = Path(scene_dir)
        result: Dict[str, Any] = {
            "bg_overlay": None,
            "badges": [],
            "stat": None,
        }

        # 1. Overlay de fondo (partículas sutiles y brackets)
        result["bg_overlay"] = await self.render_scene_motion_overlay(motion_spec, duration, scene_dir, scene_id)

        # 2. Insignias secuenciales escalonadas (Países, hitos, marcas)
        seq_badges = motion_spec.get("sequential_badges", [])
        if seq_badges and isinstance(seq_badges, list):
            for i, b in enumerate(seq_badges[:4]):
                lbl = b.get("label", "")
                emoji = b.get("emoji", "")
                del_s = float(b.get("delay_sec", 1.0 + i * 1.2))
                out_b_png = scene_dir / f"motion_badge_{scene_id}_{i}.png"
                badge_meta = self.render_individual_badge_sync(lbl, emoji, out_b_png, accent_color)
                if badge_meta and out_b_png.exists():
                    badge_meta["delay_sec"] = del_s
                    result["badges"].append(badge_meta)
            if result["badges"]:
                logger.info(f"[MotionEngine] ✓ {len(result['badges'])} insignias cinéticas escalonadas listas para escena {scene_id}")

        # 3. Estadística cinética animada (cifra o porcentaje)
        stat_cfg = motion_spec.get("kinetic_stat", {})
        if stat_cfg.get("enabled") and stat_cfg.get("value"):
            val = stat_cfg.get("value", "")
            lbl = stat_cfg.get("label", "MÉTRICA CLAVE")
            del_s = float(stat_cfg.get("delay_sec", 1.4))
            out_stat_png = scene_dir / f"motion_stat_{scene_id}.png"
            stat_meta = self.render_kinetic_stat_card_sync(val, lbl, out_stat_png, "#FFE500")
            if stat_meta and out_stat_png.exists():
                stat_meta["delay_sec"] = del_s
                result["stat"] = stat_meta
                logger.info(f"[MotionEngine] ✓ Métrica cinética animada '{val}' lista para escena {scene_id}")

        return result

    async def render_scene_motion_overlay(
        self,
        motion_spec: Dict[str, Any],
        duration: float,
        scene_dir: Path,
        scene_id: int = 0,
    ) -> Optional[Path]:
        """
        Renderiza la capa de motion graphics como PNG/WebM transparente de alta definición.
        Devuelve la ruta al archivo para componer en FFmpeg o None.
        """
        try:
            scene_dir = Path(scene_dir)
            out_png = scene_dir / f"motion_layer_{scene_id}.png"
            html_text = self.build_composition_html(motion_spec, duration)

            # Usar WebCardRenderer / Chromium para generar el overlay transparente nativo
            if self.web_renderer:
                try:
                    p = await self.web_renderer.export_html_screenshot(
                        html_content=html_text,
                        out_path=out_png,
                        width=self.W,
                        height=self.H,
                        transparent=True,
                    )
                    if p and p.exists() and p.stat().st_size > 1000:
                        return p
                except Exception as _we:
                    logger.debug(f"[MotionEngine] WebRenderer async export fallback: {_we}")

            # Renderizado nativo Headless Chromium / Edge con transparencia 100% garantizada
            html_file = scene_dir / f"motion_layer_{scene_id}.html"
            html_file.write_text(html_text, encoding="utf-8")
            
            from core.web_card_renderer import _get_browser_bin
            browser_bin = _get_browser_bin()
            args = [
                browser_bin,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--default-background-color=00000000",
                f"--screenshot={out_png.resolve()}",
                f"--window-size={self.W},{self.H}",
                html_file.resolve().as_uri(),
            ]
            subprocess.run(args, capture_output=True, check=True, timeout=15)

            if out_png.exists() and out_png.stat().st_size > 1000:
                logger.info(f"[MotionEngine] Capa de microelementos generada: {out_png}")
                return out_png

        except Exception as exc:
            logger.warning(f"[MotionEngine] Error renderizando motion overlay: {exc}")

        return None

