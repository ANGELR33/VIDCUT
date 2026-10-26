"""
WebCardRenderer - Motor de Renderizado Gráfico Basado en Web (HTML5/CSS3/SVG + Headless Chromium).
Produce tarjetas Bento cuadradas y rectangulares de estándar profesional 2026.
"""

from __future__ import annotations

import os
import subprocess
import re
import base64
from pathlib import Path
from typing import Optional, Dict, Any


HTML_FONTS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700;800&family=Syne:wght@700;800&family=Playfair+Display:ital,wght@1,700;1,900&display=swap" rel="stylesheet">
"""

# Paletas bicolor firma para la tipografía cinética viral (degradado de dos colores).
KINETIC_DUOTONES = [
    ("#FFB703", "#FB8500"),  # Ámbar Eléctrico → Oro Solar (impacto de firma)
    ("#FF9436", "#FFE500"),  # Ámbar Naranja → Oro Puro
    ("#FF007F", "#7928CA"),  # Magenta Neón → Violeta Profundo
    ("#CCFF00", "#FF9436"),  # Acid Lime → Ámbar Vibrante
    ("#FFD166", "#EF476F"),  # Oro Cálido → Coral Neón
    ("#FF4D00", "#FF0055"),  # Solar Flare → Carmesí Viral
    ("#FFB703", "#FF5500"),  # Oro Brillante → Naranja Profundo
    ("#05FFA1", "#10B981"),  # Emerald Spark → Esmeralda Profundo
]


def _get_browser_bin() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "chrome"


class WebCardRenderer:
    """Renderizador moderno de tarjetas estilo Bento Square & Pro HUD."""

    def __init__(self, browser_bin: Optional[str] = None):
        self.browser_bin = browser_bin or _get_browser_bin()

    @staticmethod
    def _bento_bar_heights(stat_value: str) -> list:
        """Alturas de las barras del Bento a partir del dato real.

        Con un porcentaje interpretable, la última barra (la activa) marca el
        valor EXACTO y las anteriores suben hacia él. Sin porcentaje, las barras
        se dibujan planas: textura visual neutra que no insinúa una tendencia
        falsa. El gráfico decorativo hardcodeado (35-95%) ya no miente.
        """
        import re as _re
        m = _re.search(r"(\d+(?:[.,]\d+)?)\s*%", str(stat_value or ""))
        if not m:
            return [42, 42, 42, 42, 42]
        try:
            val = float(m.group(1).replace(",", "."))
        except ValueError:
            return [42, 42, 42, 42, 42]
        val = max(8.0, min(100.0, val))
        factors = [0.55, 0.68, 0.80, 0.90, 1.0]
        return [max(8, round(val * f)) for f in factors]

    def _resolve_image_data_uri(self, image_path: Optional[Union[str, Path]]) -> Optional[str]:
        """Convierte una ruta de imagen o video local en un Data URI base64 seguro para Chromium."""
        if not image_path:
            return None
        try:
            p = Path(image_path)
            if not p.exists():
                s = str(image_path)
                if s.startswith("data:image/") or s.startswith("http"):
                    return s
                return None

            # Si es un video, extraer un fotograma nítido con FFmpeg
            if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm", ".avi"):
                frame_out = p.parent / f"_card_frame_{p.stem}.jpg"
                if not frame_out.exists() or frame_out.stat().st_size == 0:
                    cmd = ["ffmpeg", "-y", "-ss", "00:00:01", "-i", str(p), "-vframes", "1", "-q:v", "2", str(frame_out)]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if frame_out.exists() and frame_out.stat().st_size > 0:
                    p = frame_out
                else:
                    return None

            # Leer bytes y codificar a Base64
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None

    def generate_html(
        self,
        headline: str,
        stat_value: str = "",
        stat_label: str = "",
        body: str = "",
        badge: str = "INFO",
        source: str = "Registro Oficial 2026",
        style: str = "auto",
        image_path: Optional[Union[str, Path]] = None,
        step_number: Optional[str] = None,
        meta_pill: Optional[str] = None,
        trend_text: Optional[str] = None,
        progress_pct: Optional[float] = None,
    ) -> str:
        """Genera HTML5/CSS3 de alta gama: Matte Dark Obsidian Glass con acento Ámbar Glow.
        
        Diseño unificado 2026 que sustituye a las tarjetas antiguas. Soporta 7 variantes
        visuales con máscara de fusión fotográfica suave hacia el fondo negro mate.
        """
        # Sanitizar textos
        headline = (headline or "").replace("<", "&lt;").replace(">", "&gt;")
        stat_value = (stat_value or "").replace("<", "&lt;").replace(">", "&gt;")
        stat_label = (stat_label or "").replace("<", "&lt;").replace(">", "&gt;")
        body = (body or "").replace("<", "&lt;").replace(">", "&gt;")
        badge = (badge or "INFO").replace("<", "&lt;").replace(">", "&gt;").upper()
        source = (source or "Registro Oficial 2026").replace("<", "&lt;").replace(">", "&gt;")

        # Si el estilo solicita explícitamente bandera geopolítica
        if style in ("flag", "pais", "entidad") or any(k in badge for k in ("PAIS", "BANDERA", "GEOPOLITICA")):
            c_code = "us"
            low_h = (headline + " " + body).lower()
            for k, code in [
                ("china", "cn"), ("rusia", "ru"), ("ucrania", "ua"), ("europa", "eu"),
                ("taiwan", "tw"), ("españa", "es"), ("mexico", "mx"), ("méxico", "mx"),
                ("israel", "il"), ("turquía", "tr"), ("turquia", "tr"), ("otan", "un")
            ]:
                if k in low_h:
                    c_code = code
                    break
            return self.generate_entity_flag_html(
                country_name=headline,
                country_code=c_code,
                role_label=badge or "ANÁLISIS ESTRATÉGICO",
                metric_stat=stat_value or "DATOS CLAVE",
                detail=body,
            )

        # Resolver imagen si fue provista
        img_uri = self._resolve_image_data_uri(image_path)

        # Detección inteligente de variante según contenido
        variant = style
        if variant in ("auto", "matte_amber", "obsidian_bento", "tactical_amber", "default"):
            b_up = badge.upper()
            h_up = headline.upper()
            if step_number or "PASO" in b_up or "PASO" in h_up:
                variant = "step"
            elif "TIP" in b_up or "CONSEJO" in b_up:
                variant = "tip"
            elif "HECHO" in b_up or "SABÍAS" in h_up or "SABIAS" in h_up or "CURIOSIDAD" in b_up:
                variant = "fact"
            elif "DEFINICIÓN" in b_up or "DEFINICION" in b_up or "CONCEPTO" in b_up or "QUÉ ES" in h_up or "QUE ES" in h_up:
                variant = "definition"
            elif "CITA" in b_up or "QUOTE" in b_up:
                variant = "quote"
            elif stat_value and (any(c.isdigit() for c in stat_value) or "%" in stat_value or "ESTADÍSTICA" in b_up or "ESTADISTICA" in b_up or "CIFRA" in b_up):
                variant = "statistic"
            elif img_uri:
                variant = "info_image"
            else:
                variant = "info_image"

        # Pip y resplandor en el borde superior según variante
        pip_left = {
            "info_image": "58%",
            "statistic": "48%",
            "tip": "70%",
            "definition": "52%",
            "fact": "58%",
            "step": "64%",
            "quote": "54%",
        }.get(variant, "56%")

        glow_left = {
            "info_image": "46%",
            "statistic": "36%",
            "tip": "58%",
            "definition": "40%",
            "fact": "46%",
            "step": "52%",
            "quote": "42%",
        }.get(variant, "44%")

        content_html = ""
        visual_html = ""

        # --- 1. VARIANTE info_image: Entidad / Tópico con imagen real fundida ---
        if variant == "info_image":
            tag_text = badge if badge not in ("DATO VERIFICADO", "DATO CLAVE") else "INFO"
            pill_txt = meta_pill or (f"{stat_value} · {stat_label}" if stat_value and stat_label else "Dato verificado · 2026")
            content_html = f"""
            <div class="text-col">
              <div class="card-tag"><span class="card-tag-dot"></span> {tag_text}</div>
              <div class="card-title">{headline}</div>
              <div class="card-desc">{body}</div>
              <div class="card-meta-pill">
                <span class="card-meta-icon">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                  </svg>
                </span>
                <span>{pill_txt}</span>
              </div>
            </div>
            """
            if img_uri:
                visual_html = f"""
                <div class="card-image-wrap">
                  <img src="{img_uri}" alt="{headline}">
                </div>
                """
            else:
                visual_html = """
                <div class="card-ambient-orb">
                  <div class="orb-core"></div>
                </div>
                """

        # --- 2. VARIANTE statistic: Cifra gigante, barra de progreso naranja, tendencia ---
        elif variant == "statistic":
            tag_text = badge if badge not in ("DATO VERIFICADO", "DATO CLAVE") else "ESTADÍSTICA"
            stat_big = stat_value or "8.1B"
            unit_lbl = stat_label or "personas"
            pct = progress_pct if progress_pct is not None else 52.0
            trend = trend_text or "+0.9% vs. 2023"
            content_html = f"""
            <div class="text-col">
              <div class="card-tag"><span class="card-tag-dot"></span> {tag_text}</div>
              <div class="card-title">{headline}</div>
              <div class="card-stat-row">
                <span class="card-stat-big">{stat_big}</span>
                <span class="card-stat-unit">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#94a3b8" stroke-width="2" style="display:inline; vertical-align:middle; margin-right:2px;">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                  </svg>
                  {unit_lbl}
                </span>
              </div>
              <div class="card-stat-progress">
                <div class="card-stat-bar" style="width: {pct}%;"></div>
              </div>
              <div>
                <span class="card-stat-trend">↑ {trend}</span>
              </div>
            </div>
            """
            visual_html = """
            <div class="globe-visual-wrap">
              <div class="globe-orbit-ring"></div>
              <div class="globe-sphere">
                <svg viewBox="0 0 24 24" width="46" height="46" fill="none" stroke="#ffa048" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 0 10px rgba(255,140,40,0.5));">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                  <path d="M2 12h20"/>
                </svg>
              </div>
            </div>
            """

        # --- 3. VARIANTE tip: Dato útil con tile de bombilla ---
        elif variant == "tip":
            tag_text = badge if badge not in ("DATO VERIFICADO", "DATO CLAVE") else "TIP"
            content_html = f"""
            <div class="text-col">
              <div class="card-tag"><span class="card-tag-dot"></span> {tag_text}</div>
              <div class="card-title">{headline}</div>
              <div class="card-desc">{body}</div>
            </div>
            """
            visual_html = """
            <div class="card-icon-tile">
              <svg viewBox="0 0 24 24" fill="none" stroke="#ff9436" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 18h6M10 22h4M12 2v1M12 7a5 5 0 0 0-3 9h6a5 5 0 0 0-3-9z"/>
              </svg>
            </div>
            """

        # --- 4. VARIANTE definition: Definición / Concepto / IA ---
        elif variant == "definition":
            tag_text = badge if badge not in ("DATO VERIFICADO", "DATO CLAVE") else "DEFINICIÓN"
            content_html = f"""
            <div class="text-col">
              <div class="card-tag"><span class="card-tag-dot"></span> {tag_text}</div>
              <div class="card-title">{headline}</div>
              <div class="card-desc">{body}</div>
            </div>
            """
            if img_uri:
                visual_html = f"""
                <div class="card-image-wrap">
                  <img src="{img_uri}" alt="{headline}">
                </div>
                """
            else:
                visual_html = """
                <div class="neural-visual-wrap">
                  <svg viewBox="0 0 48 48" fill="none" stroke="#ff9436" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width:44px; height:44px; filter: drop-shadow(0 0 14px rgba(255,120,20,0.6));">
                    <path d="M20 10c-3-2-8-1-10 3s-1 8 2 11c-3 2-3 6 0 9s7 4 10 2"/>
                    <path d="M28 10c3-2 8-1 10 3s1 8-2 11c3 2 3 6 0 9s-7 4-10 2"/>
                    <circle cx="17" cy="18" r="2" fill="#ff9436"/>
                    <circle cx="31" cy="18" r="2" fill="#ff9436"/>
                    <circle cx="16" cy="28" r="2" fill="#ff9436"/>
                    <circle cx="32" cy="28" r="2" fill="#ff9436"/>
                    <circle cx="24" cy="24" r="2.5" fill="#ff9436"/>
                    <path d="M17 18l7 6 7-6M16 28l8-4 8 4" stroke-width="1.5" stroke-dasharray="2 2"/>
                  </svg>
                </div>
                """

        # --- 5. VARIANTE fact: Hecho / ¿Sabías que? con icono elefante outline ---
        elif variant == "fact":
            tag_text = badge if badge not in ("DATO VERIFICADO", "DATO CLAVE") else "HECHO"
            content_html = f"""
            <div class="text-col">
              <div class="card-tag"><span class="card-tag-dot"></span> {tag_text}</div>
              <div class="card-title">{headline}</div>
              <div class="card-desc">{body}</div>
            </div>
            """
            visual_html = """
            <div class="card-icon-tile" style="width:72px; height:72px; border-radius:20px;">
              <svg viewBox="0 0 48 48" fill="none" stroke="#ff9436" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width:42px; height:42px; filter: drop-shadow(0 0 10px rgba(255,140,40,0.5));">
                <path d="M16 14C10 14 5 18 5 25c0 7 6 12 11 11"/>
                <path d="M32 14c6 0 11 4 11 11 0 7-6 12-11 11"/>
                <path d="M16 16c0-6 3.5-10 8-10s8 4 8 10c0 5-1.5 9-3 15v8c0 2-1 3-2.5 3s-2.5-1-2.5-3v-8c-1.5-6-3-10-3-15z"/>
                <path d="M17 32c-2 2-3 4-3 6"/>
                <path d="M31 32c2 2 3 4 3 6"/>
                <circle cx="20" cy="20" r="1.5" fill="#ff9436"/>
                <circle cx="28" cy="20" r="1.5" fill="#ff9436"/>
              </svg>
            </div>
            """

        # --- 6. VARIANTE step: Paso numerado con insignia 03 e icono sol ---
        elif variant == "step":
            tag_text = badge if badge not in ("DATO VERIFICADO", "DATO CLAVE") else "PASO"
            st_match = re.search(r"[0-9]+", headline)
            st_num = step_number or (st_match.group(0) if st_match else "01")
            st_num = f"{int(st_num):02d}" if st_num.isdigit() else st_num
            content_html = f"""
            <div style="display:flex; align-items:center; gap:18px; z-index:5;">
              <div>
                <div class="card-tag" style="margin-bottom:6px;"><span class="card-tag-dot"></span> {tag_text}</div>
                <div class="card-step-badge">{st_num}</div>
              </div>
              <div class="text-col" style="max-width:280px;">
                <div class="card-title">{headline}</div>
                <div class="card-desc">{body}</div>
              </div>
            </div>
            """
            visual_html = """
            <div class="card-icon-tile">
              <svg viewBox="0 0 24 24" fill="none" stroke="#ff9436" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            </div>
            """

        # --- 7. VARIANTE quote: Cita con comillas gigantes e icono libro ---
        elif variant == "quote":
            tag_text = badge if badge not in ("DATO VERIFICADO", "DATO CLAVE") else "DATO"
            quote_body = body or headline
            content_html = f"""
            <div class="text-col">
              <div class="card-tag"><span class="card-tag-dot"></span> {tag_text}</div>
              <span class="card-quote-mark">“</span>
              <div class="card-quote-text">{quote_body}”</div>
            </div>
            """
            visual_html = """
            <div class="card-icon-tile">
              <svg viewBox="0 0 24 24" fill="none" stroke="#ff9436" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
              </svg>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #fff;
  }}

  .card-container {{
    width: 600px;
    min-height: 205px;
    background: linear-gradient(145deg, #101217 0%, #0a0b0e 100%);
    border: 1px solid rgba(255, 140, 40, 0.26);
    box-shadow: 0 24px 56px rgba(0, 0, 0, 0.90),
                0 0 32px rgba(255, 120, 20, 0.08),
                inset 0 1px 0 rgba(255, 255, 255, 0.12),
                inset 0 0 20px rgba(255, 120, 20, 0.03);
    border-radius: 24px;
    padding: 24px 28px;
    position: relative;
    overflow: hidden;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  /* Punto brillante naranja en el borde superior */
  .card-top-pip {{
    position: absolute;
    top: -4px;
    left: {pip_left};
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ff7a18;
    box-shadow: 0 0 10px #ff7a18, 0 0 4px #ffb060;
    z-index: 10;
  }}
  .card-top-glow {{
    position: absolute;
    top: -1px;
    left: {glow_left};
    width: 140px;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(255, 140, 40, 0.65), #ff7a18, rgba(255, 140, 40, 0.65), transparent);
    pointer-events: none;
    z-index: 9;
  }}

  .text-col {{
    z-index: 5;
    position: relative;
    max-width: 320px;
  }}

  /* Tag superior */
  .card-tag {{
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.13em;
    color: #ff8a34;
    text-transform: uppercase;
    margin-bottom: 10px;
  }}
  .card-tag-dot {{
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #ff7a18;
    box-shadow: 0 0 6px #ff7a18;
    display: inline-block;
  }}

  /* Título y texto */
  .card-title {{
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.25;
    letter-spacing: -0.01em;
    margin-bottom: 8px;
  }}
  .card-desc {{
    font-size: 13.5px;
    line-height: 1.55;
    color: #94a3b8;
    font-weight: 400;
  }}

  /* Píldora inferior de metadatos */
  .card-meta-pill {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
    padding: 5px 14px 5px 6px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.07);
    font-size: 12px;
    color: #cbd5e1;
  }}
  .card-meta-icon {{
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #ff7a18;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
  }}

  /* MÁSCARA DE FUSIÓN SUAVE: imagen real a la derecha con fundido perfecto */
  .card-image-wrap {{
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 48%;
    overflow: hidden;
    border-top-right-radius: 24px;
    border-bottom-right-radius: 24px;
    pointer-events: none;
    z-index: 2;
  }}
  .card-image-wrap img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    -webkit-mask-image: linear-gradient(to right, transparent 0%, rgba(0,0,0,0.15) 16%, rgba(0,0,0,0.85) 45%, black 75%);
    mask-image: linear-gradient(to right, transparent 0%, rgba(0,0,0,0.15) 16%, rgba(0,0,0,0.85) 45%, black 75%);
  }}

  /* Tile de vidrio oscuro para iconos (Tip, Step, Quote) */
  .card-icon-tile {{
    width: 62px;
    height: 62px;
    border-radius: 18px;
    background: rgba(255, 122, 24, 0.05);
    border: 1px solid rgba(255, 140, 40, 0.28);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 0 16px rgba(255, 122, 24, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ff9436;
    flex-shrink: 0;
    position: relative;
    z-index: 5;
  }}
  .card-icon-tile svg {{
    width: 28px;
    height: 28px;
  }}

  /* Estadísticas */
  .card-stat-big {{
    font-size: 38px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1;
    letter-spacing: -0.02em;
  }}
  .card-stat-row {{
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin: 8px 0 12px;
  }}
  .card-stat-unit {{
    font-size: 12px;
    color: #94a3b8;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }}
  .card-stat-progress {{
    width: 210px;
    height: 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
    margin-bottom: 12px;
  }}
  .card-stat-bar {{
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #ff6b10 0%, #ffa048 100%);
    box-shadow: 0 0 10px rgba(255, 120, 20, 0.6);
  }}
  .card-stat-trend {{
    font-size: 12px;
    color: #ff9436;
    font-weight: 700;
  }}

  /* Globo / Visual de datos */
  .globe-visual-wrap {{
    position: relative;
    width: 130px;
    height: 130px;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 4;
  }}
  .globe-orbit-ring {{
    position: absolute;
    width: 120px;
    height: 120px;
    border-radius: 50%;
    border: 1px dashed rgba(255,140,40,0.32);
  }}
  .globe-sphere {{
    width: 90px;
    height: 90px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #2a2c36 0%, #0d0e14 80%);
    border: 1px solid rgba(255,140,40,0.4);
    box-shadow: 0 0 25px rgba(255,120,20,0.22), inset 0 0 15px rgba(255,120,20,0.15);
    display: flex;
    align-items: center;
    justify-content: center;
  }}

  /* Holograma Neural */
  .neural-visual-wrap {{
    position: relative;
    width: 120px;
    height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 4;
    background: radial-gradient(circle, rgba(255,120,20,0.15) 0%, transparent 70%);
  }}

  /* Paso */
  .card-step-badge {{
    width: 52px;
    height: 52px;
    border-radius: 50%;
    border: 1.5px solid rgba(255, 140, 40, 0.55);
    box-shadow: 0 0 16px rgba(255, 122, 24, 0.25), inset 0 0 8px rgba(255, 122, 24, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 800;
    color: #ffffff;
    flex-shrink: 0;
  }}

  /* Cita */
  .card-quote-mark {{
    font-size: 38px;
    line-height: 0.7;
    color: #ff7a18;
    font-family: Georgia, serif;
    margin-bottom: 8px;
    display: block;
    text-shadow: 0 0 10px rgba(255, 122, 24, 0.4);
  }}
  .card-quote-text {{
    font-size: 18px;
    font-style: italic;
    color: #f8fafc;
    line-height: 1.4;
    font-weight: 500;
  }}
</style>
</head>
<body>
  <div class="card-container">
    <div class="card-top-pip"></div>
    <div class="card-top-glow"></div>
    {content_html}
    {visual_html}
  </div>
</body>
</html>"""

    def generate_quote_html(
        self,
        quote_text: str,
        highlight_words: str = "",
        author: str = "Afirmación Destacada",
        badge: str = "DATO",
    ) -> str:
        """Tarjeta de cita estilizada según la referencia Matte Dark + Ámbar Glow."""
        return self.generate_html(
            headline=author,
            body=quote_text,
            badge=badge or "DATO",
            style="quote"
        )


    def generate_entity_flag_html(
        self,
        country_name: str,
        country_code: str = "us",
        role_label: str = "ANÁLISIS ESTRATÉGICO",
        metric_stat: str = "DATOS CLAVE",
        detail: str = "Evaluación geopolítica y balance operativo en tiempo real.",
        flag_emoji: str = "",
    ) -> str:
        """Tarjeta de entidad geopolítica o país con bandera oficial de alta definición y métrica destacada (sin emojis)."""
        c_clean = country_name.replace("<", "&lt;").replace(">", "&gt;")
        code_clean = (country_code or "us").lower().strip()
        role_clean = role_label.replace("<", "&lt;").replace(">", "&gt;")
        stat_clean = metric_stat.replace("<", "&lt;").replace(">", "&gt;")
        det_clean = detail.replace("<", "&lt;").replace(">", "&gt;")

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  /* Floating HUD container — NO enclosing background card */
  .floating-entity {{
    width: 680px;
    padding: 12px 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    position: relative;
  }}
  .floating-meta-row {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .floating-role-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 4px;
    background: rgba(8, 9, 12, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.85), 0 0 20px rgba(12, 24, 48, 0.4);
    color: #38bdf8;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
  }}
  .floating-stat-pill {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #f59e0b;
    background: rgba(8, 9, 12, 0.92);
    padding: 5px 12px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.85), 0 0 20px rgba(12, 24, 48, 0.3);
    letter-spacing: 0.5px;
  }}
  .floating-identity-row {{
    display: flex;
    align-items: center;
    gap: 20px;
  }}
  .floating-flag-box {{
    width: 68px;
    height: 46px;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.95), 0 0 24px rgba(12, 24, 48, 0.5);
    border: 1.5px solid rgba(255, 255, 255, 0.20);
    background: #08090c;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }}
  .floating-flag-img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .floating-name-col {{
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .floating-country-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 38px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.05;
    letter-spacing: -0.6px;
    text-shadow: 0 4px 25px rgba(0, 0, 0, 0.98), 0 1px 4px rgba(0, 0, 0, 0.9);
  }}
  .floating-iso-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.65);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.95);
  }}
  .floating-detail-text {{
    font-size: 15px;
    line-height: 1.55;
    color: #e2e8f0;
    text-shadow: 0 3px 18px rgba(0, 0, 0, 0.98), 0 1px 3px rgba(0, 0, 0, 0.9);
    max-width: 640px;
    padding-left: 2px;
  }}
</style>
</head>
<body>
  <div class="floating-entity">
    <div class="floating-meta-row">
      <div class="floating-role-badge">● {role_clean}</div>
      <div class="floating-stat-pill">{stat_clean}</div>
    </div>
    <div class="floating-identity-row">
      <div class="floating-flag-box">
        <img class="floating-flag-img" src="https://flagcdn.com/w160/{code_clean}.png" alt="{code_clean}" onerror="this.style.display='none'" />
      </div>
      <div class="floating-name-col">
        <div class="floating-country-title">{c_clean}</div>
        <div class="floating-iso-badge">{code_clean.upper()} // ENTIDAD RECONOCIDA</div>
      </div>
    </div>
    <div class="floating-detail-text">{det_clean}</div>
  </div>
</body>
</html>"""

    def generate_popup_html(
        self,
        text: str,
        tag_label: str = "CLAVE",
        kind: str = "fact",
    ) -> str:
        """Micro Pop-up HUD reactivo estilo pastilla moderna."""
        # Sanitizar SIEMPRE: el texto llega directo del LLM director. Sin esto,
        # un "<" rompía el marcado y una etiqueta inyectada se ejecutaba en el
        # Chromium headless que renderiza este HTML (file://).
        text = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        tag_label = str(tag_label or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        kind_colors = {
            "stat": ("#f59e0b", "rgba(245, 158, 11, 0.15)", "rgba(245, 158, 11, 0.35)"),
            "fact": ("#ff9436", "rgba(255, 148, 54, 0.15)", "rgba(255, 148, 54, 0.35)"),
            "alert": ("#f43f5e", "rgba(244, 63, 94, 0.15)", "rgba(244, 63, 94, 0.35)"),
            "quote": ("#10b981", "rgba(16, 185, 129, 0.15)", "rgba(16, 185, 129, 0.35)"),
        }
        accent, bg, border = kind_colors.get(kind.lower(), kind_colors["fact"])

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  .pill {{
    display: inline-flex;
    align-items: center;
    gap: 14px;
    background: rgba(9, 10, 13, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.10);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.92), 0 0 30px rgba(12, 24, 48, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    padding: 10px 24px;
    color: #ffffff;
  }}
  .badge {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: {accent};
    letter-spacing: 1px;
    padding: 4px 10px;
    border-radius: 999px;
    background: {bg};
    border: 1px solid {border};
  }}
  .dot {{
    width: 6px; height: 6px; border-radius: 50%; background: {accent}; box-shadow: 0 0 8px {accent};
  }}
  .divider {{
    width: 1px; height: 18px; background: rgba(255, 255, 255, 0.15);
  }}
  .text {{
    font-size: 15px;
    font-weight: 600;
    color: #f8fafc;
    white-space: nowrap;
    letter-spacing: -0.2px;
  }}
</style>
</head>
<body>
  <div class="pill">
    <div class="badge"><span class="dot"></span>{tag_label}</div>
    <div class="divider"></div>
    <div class="text">{text}</div>
  </div>
</body>
</html>"""

    def generate_lower_third_html(
        self,
        title: str,
        subtitle: str,
        tag: str = "INFORME ESPECIAL",
    ) -> str:
        """Rótulo Broadcast Lower Third panorámico de alta fidelidad."""
        # Sanitizar SIEMPRE (texto del LLM: nombres de escena y extractos del guion).
        title = str(title or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        subtitle = str(subtitle or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        tag = str(tag or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  .lt-container {{
    width: 780px;
    background: linear-gradient(90deg, rgba(9, 10, 13, 0.98) 0%, rgba(9, 10, 13, 0.88) 75%, transparent 100%);
    border-left: 4px solid #38bdf8;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.92), 0 0 35px rgba(12, 24, 48, 0.35);
    border-radius: 0 10px 10px 0;
    padding: 16px 26px;
    color: #ffffff;
    position: relative;
  }}
  .lt-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #38bdf8;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .lt-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.2;
    margin-bottom: 4px;
  }}
  .lt-sub {{
    font-size: 13.5px;
    color: #cbd5e1;
    font-weight: 500;
  }}
</style>
</head>
<body>
  <div class="lt-container">
    <div class="lt-tag">● {tag}</div>
    <div class="lt-title">{title}</div>
    <div class="lt-sub">{subtitle}</div>
  </div>
</body>
</html>"""


    def render_to_image(
        self,
        headline: str,
        out_png: Path,
        stat_value: str = "",
        stat_label: str = "",
        body: str = "",
        badge: str = "DATO VERIFICADO",
        source: str = "Registro Oficial 2026",
        style: str = "auto",
        image_path: Optional[Union[str, Path]] = None,
        step_number: Optional[str] = None,
        meta_pill: Optional[str] = None,
        trend_text: Optional[str] = None,
        progress_pct: Optional[float] = None,
    ) -> Path:
        """Renderiza la tarjeta a un archivo PNG con fondo transparente utilizando Headless Chromium."""
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")

        html_content = self.generate_html(
            headline=headline,
            stat_value=stat_value,
            stat_label=stat_label,
            body=body,
            badge=badge,
            source=source,
            style=style,
            image_path=image_path,
            step_number=step_number,
            meta_pill=meta_pill,
            trend_text=trend_text,
            progress_pct=progress_pct,
        )
        html_file.write_text(html_content, encoding="utf-8")

        file_uri = html_file.resolve().as_uri()

        # Configurar dimensiones de captura según el estilo
        win_size = "900,600" if style != "square_emerald" else "700,700"

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--screenshot={out_png.resolve()}",
            f"--window-size={win_size}",
            file_uri,
        ]

        subprocess.run(args, capture_output=True, check=True, timeout=15)

        # Auto-recorte inteligente para ajustar los bordes transparentes conservando la sombra suave
        try:
            from PIL import Image
            im = Image.open(out_png)
            bbox = im.getbbox()
            if bbox:
                pad = 14
                b = (max(0, bbox[0]-pad), max(0, bbox[1]-pad), min(im.width, bbox[2]+pad), min(im.height, bbox[3]+pad))
                cropped = im.crop(b)
                cropped.save(out_png)
        except Exception:
            pass

        return out_png

    def render_quote_to_image(
        self,
        quote_text: str,
        out_png: Path,
        highlight_words: str = "",
        author: str = "Afirmación Destacada",
        badge: str = "ÉNFASIS CLAVE",
    ) -> Path:
        """Renderiza una tarjeta de énfasis en frase / cita cinética."""
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")
        html_content = self.generate_quote_html(quote_text, highlight_words, author, badge)
        html_file.write_text(html_content, encoding="utf-8")
        file_uri = html_file.resolve().as_uri()

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--screenshot={out_png.resolve()}",
            "--window-size=1000,600",
            file_uri,
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=15)
        self._crop_transparent(out_png)
        return out_png

    def render_entity_flag_to_image(
        self,
        country_name: str,
        out_png: Path,
        country_code: str = "us",
        role_label: str = "ANÁLISIS ESTRATÉGICO",
        metric_stat: str = "DATOS CLAVE",
        detail: str = "Evaluación geopolítica y balance operativo en tiempo real.",
        flag_emoji: str = "",
    ) -> Path:
        """Renderiza una tarjeta táctica de país o entidad geopolítica con bandera (sin emojis)."""
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")
        html_content = self.generate_entity_flag_html(
            country_name=country_name,
            country_code=country_code,
            role_label=role_label,
            metric_stat=metric_stat,
            detail=detail,
            flag_emoji=flag_emoji,
        )
        html_file.write_text(html_content, encoding="utf-8")
        file_uri = html_file.resolve().as_uri()

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--screenshot={out_png.resolve()}",
            "--window-size=900,500",
            file_uri,
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=15)
        self._crop_transparent(out_png)
        return out_png

    def render_popup_to_image(
        self,
        text: str,
        out_png: Path,
        tag_label: str = "CLAVE",
        kind: str = "fact",
    ) -> Path:
        """Renderiza un micro Pop-up HUD reactivo estilo pastilla moderna."""
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")
        html_content = self.generate_popup_html(text, tag_label, kind)
        html_file.write_text(html_content, encoding="utf-8")
        file_uri = html_file.resolve().as_uri()

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--screenshot={out_png.resolve()}",
            "--window-size=800,300",
            file_uri,
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=15)
        self._crop_transparent(out_png)
        return out_png

    def render_lower_third_to_image(
        self,
        title: str,
        subtitle: str,
        out_png: Path,
        tag: str = "INFORME ESPECIAL",
    ) -> Path:
        """Renderiza un rótulo broadcast panorámico de alta gama."""
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")
        html_content = self.generate_lower_third_html(title, subtitle, tag)
        html_file.write_text(html_content, encoding="utf-8")
        file_uri = html_file.resolve().as_uri()

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--screenshot={out_png.resolve()}",
            "--window-size=1100,400",
            file_uri,
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=15)
        self._crop_transparent(out_png)
        return out_png

    def generate_chips_html(self, chips: list) -> str:
        """Fila horizontal de chips Glassmorphism con banderas y datos de referencia."""
        import re
        COUNTRY_CODES = {
            "estados unidos": "us", "ee.uu": "us", "eeuu": "us", "usa": "us", "us": "us",
            "china": "cn", "cn": "cn", "rusia": "ru", "ru": "ru", "ucrania": "ua", "ua": "ua",
            "alemania": "de", "francia": "fr", "reino unido": "gb", "uk": "gb", "españa": "es",
            "japón": "jp", "japon": "jp", "corea": "kr", "taiwan": "tw", "taiwán": "tw",
        }

        chips_html = []
        for c in chips[:5]:
            raw = str(c).strip()
            if not raw:
                continue
            clean = raw
            c_code = None
            m = re.match(r"^([A-Za-z]{2})\s+(.+)$", raw)
            if m and m.group(1).lower() in COUNTRY_CODES:
                c_code = COUNTRY_CODES[m.group(1).lower()]
                clean = m.group(2).strip()
            else:
                low = raw.lower()
                for k, code in COUNTRY_CODES.items():
                    # Solo coincidencia de PALABRA COMPLETA: "us" dentro de
                    # "Museo" o "Discusión" jamás debe pintar la bandera de EE.UU.,
                    # ni "rusia" dentro de "Prusia" la de Rusia.
                    m_flag = re.search(rf"\b{re.escape(k)}\b", low)
                    if not m_flag:
                        continue
                    # Claves cortas (us/usa/cn/ru...) solo valen como SIGLAS en
                    # mayúsculas: "Usa energía" es el verbo español, no EE.UU.
                    if len(k) <= 4 and not raw[m_flag.start():m_flag.end()].isupper():
                        continue
                    c_code = code
                    break

            # El texto del chip viene del LLM: escapar siempre (mismo criterio
            # que las tarjetas y popups).
            clean = clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            if c_code:
                flag_markup = f'<img src="https://flagcdn.com/w80/{c_code}.png" class="flag-thumb" alt="{c_code}">'
            else:
                flag_markup = '<span class="chip-dot"></span>'

            chips_html.append(f"""
              <div class="glass-chip">
                {flag_markup}
                <span class="chip-text">{clean}</span>
              </div>
            """)

        joined = "".join(chips_html)
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  .chips-track {{
    display: inline-flex;
    align-items: center;
    gap: 12px;
    padding: 10px;
  }}
  .glass-chip {{
    display: inline-flex;
    align-items: center;
    gap: 12px;
    background: rgba(9, 10, 13, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.10);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.90), 0 0 25px rgba(12, 24, 48, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 22px;
    color: #f8fafc;
  }}
  .flag-thumb {{
    /* Bandera protagonista del chip (estilo tag de ubicación de noticiero):
       grande, con borde y sombra propia. Antes era 22x15px — ilegible en 1080p. */
    width: 46px;
    height: 31px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.30);
    object-fit: cover;
    box-shadow: 0 3px 10px rgba(0,0,0,0.55);
  }}
  .chip-dot {{
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 10px #38bdf8;
  }}
  .chip-text {{
    font-size: 19px;
    font-weight: 700;
    letter-spacing: 0.2px;
    white-space: nowrap;
  }}
</style>
</head>
<body>
  <div class="chips-track">
    {joined}
  </div>
</body>
</html>"""

    def render_chips_to_image(self, chips: list, out_png: Path) -> Path:
        """Renderiza una fila de chips moderna con banderas e indicadores de luz."""
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")
        html_content = self.generate_chips_html(chips)
        html_file.write_text(html_content, encoding="utf-8")
        file_uri = html_file.resolve().as_uri()

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            # Render a 2x de resolución nativa: el PNG sale nítido y el overlay
            # puede reducirlo sin pixelado (banderas y texto grandes y legibles).
            "--force-device-scale-factor=2",
            f"--screenshot={out_png.resolve()}",
            "--window-size=1200,300",
            file_uri,
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=15)
        self._crop_transparent(out_png)
        return out_png

    def generate_ranking_number_html(
        self,
        number: str = "03",
        title: str = "Puesto Destacado",
        subtitle: str = "Análisis e Impacto Clave",
        badge: str = "TOP RANKING",
    ) -> str:
        """Diseño cinematográfico para hitos de cuenta regresiva (Top 10, Puestos, Cifras de Impacto)."""
        num_clean = number.replace("<", "&lt;").replace(">", "&gt;")
        tit_clean = title.replace("<", "&lt;").replace(">", "&gt;")
        sub_clean = subtitle.replace("<", "&lt;").replace(">", "&gt;")
        bdg_clean = badge.replace("<", "&lt;").replace(">", "&gt;")

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  .ranking-card {{
    width: 660px;
    background: linear-gradient(145deg, rgba(9, 10, 13, 0.98) 0%, rgba(4, 5, 7, 0.99) 100%);
    border: 1px solid rgba(255, 255, 255, 0.10);
    box-shadow: 0 32px 80px rgba(0, 0, 0, 0.95), 0 0 45px rgba(12, 24, 48, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 30px 36px;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 30px;
    position: relative;
    overflow: hidden;
  }}
  .ranking-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; width: 140px;
    height: 2px;
    background: linear-gradient(90deg, #38bdf8, transparent);
  }}
  .number-box {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 120px;
    height: 120px;
    background: rgba(14, 18, 26, 0.85);
    border: 1px solid rgba(56, 189, 248, 0.25);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6), inset 0 0 20px rgba(56, 189, 248, 0.06);
    border-radius: 12px;
    position: relative;
  }}
  .big-number {{
    font-family: 'Outfit', sans-serif;
    font-size: 76px;
    font-weight: 800;
    line-height: 1;
    background: linear-gradient(180deg, #ffffff 30%, #38bdf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 4px 14px rgba(56, 189, 248, 0.35));
    letter-spacing: -2px;
  }}
  .info-content {{
    flex: 1;
  }}
  .rank-badge {{
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 4px 11px;
    border-radius: 4px;
    background: rgba(56, 189, 248, 0.08);
    border: 1px solid rgba(56, 189, 248, 0.25);
    color: #38bdf8;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 10px;
  }}
  .rank-badge svg {{ flex-shrink: 0; }}
  .rank-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 26px;
    font-weight: 800;
    color: #f1f5f9;
    line-height: 1.2;
    letter-spacing: -0.4px;
    margin-bottom: 7px;
  }}
  .rank-sub {{
    font-size: 13.5px;
    color: #94a3b8;
    line-height: 1.45;
  }}
</style>
</head>
<body>
  <div class="ranking-card">
    <div class="number-box">
      <div class="big-number">{num_clean}</div>
    </div>
    <div class="info-content">
      <div class="rank-badge">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="5" cy="5" r="3" fill="#38bdf8"/><circle cx="5" cy="5" r="4.5" stroke="#38bdf8" stroke-opacity="0.5"/></svg>
        <span>{bdg_clean}</span>
      </div>
      <div class="rank-title">{tit_clean}</div>
      <div class="rank-sub">{sub_clean}</div>
    </div>
  </div>
</body>
</html>"""

    def generate_free_kinetic_text_html(
        self,
        main_title: str,
        number: str = "",
        tag: str = "",
        subtitle: str = "",
        highlight: str = "",
        accent_color: str = "#ff9436",
    ) -> str:
        """
        Texto libre cinematográfico flotante (Kinetic Typography):
        - CERO cajas, CERO fondos, CERO tarjetas.
        - Tipografía de escala cinematográfica con sombreado multicapa para máxima legibilidad.
        - Soporta números gigantes de ranking (03), hitos numerados (1. 2. 3.), etiquetas tácticas y palabras clave con resplandor.
        """
        import re
        t_clean = main_title.replace("<", "&lt;").replace(">", "&gt;")
        n_clean = number.replace("<", "&lt;").replace(">", "&gt;") if number else ""
        tag_clean = tag.replace("<", "&lt;").replace(">", "&gt;") if tag else ""
        sub_clean = subtitle.replace("<", "&lt;").replace(">", "&gt;") if subtitle else ""

        if highlight and highlight.lower() in t_clean.lower():
            pat = re.compile(re.escape(highlight), re.IGNORECASE)
            t_formatted = pat.sub(f'<span class="hl">{highlight}</span>', t_clean)
        else:
            t_formatted = t_clean

        tag_markup = f'<div class="free-tag">● {tag_clean}</div>' if tag_clean else ""
        num_markup = f'<div class="free-num">{n_clean}</div>' if n_clean else ""
        sub_markup = f'<div class="free-sub">{sub_clean}</div>' if sub_clean else ""

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  .free-wrap {{
    text-align: center;
    max-width: 1400px;
    padding: 30px;
  }}
  .free-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 14.5px;
    font-weight: 800;
    letter-spacing: 4px;
    color: #ffffff;
    background: rgba(8, 11, 16, 0.85);
    border: 1px solid {accent_color}88;
    border-radius: 999px;
    padding: 6px 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.85), 0 0 20px {accent_color}44;
    text-shadow: 0 0 10px {accent_color};
    text-transform: uppercase;
    margin-bottom: 12px;
    display: inline-block;
  }}
  .free-num {{
    font-family: 'Outfit', sans-serif;
    font-size: 144px;
    font-weight: 900;
    line-height: 0.90;
    background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 30%, {accent_color} 75%, {accent_color}cc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    -webkit-text-stroke: 2px rgba(255, 255, 255, 0.35);
    filter: drop-shadow(0 18px 50px rgba(0,0,0,0.98)) drop-shadow(0 0 40px {accent_color}99);
    letter-spacing: -5px;
    margin-bottom: 10px;
  }}
  .free-title {{
    font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif;
    font-size: 74px;
    font-weight: 900;
    line-height: 1.05;
    color: #ffffff;
    text-shadow: 0 12px 50px rgba(0,0,0,0.98), 0 4px 18px rgba(0,0,0,0.92);
    letter-spacing: -1.6px;
    text-transform: uppercase;
  }}
  .hl {{
    color: {accent_color};
    text-shadow: 0 0 30px {accent_color}, 0 0 60px {accent_color}aa, 0 4px 20px rgba(0,0,0,0.95);
  }}
  .free-sub {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
    background: rgba(8, 11, 16, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 999px;
    padding: 8px 24px;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.7);
    margin-top: 16px;
    letter-spacing: 0.3px;
    display: inline-block;
  }}
</style>
</head>
<body>
  <div class="free-wrap">
    {tag_markup}
    {num_markup}
    <div class="free-title">{t_formatted}</div>
    {sub_markup}
  </div>
</body>
</html>"""

    def render_free_kinetic_text_to_image(
        self,
        main_title: str,
        out_png: Path,
        number: str = "",
        tag: str = "",
        subtitle: str = "",
        highlight: str = "",
        accent_color: str = "#ff9436",
    ) -> Path:
        """Renderiza texto libre cinematográfico animable (sin card, 100% transparente)."""
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")
        html_content = self.generate_free_kinetic_text_html(
            main_title=main_title,
            number=number,
            tag=tag,
            subtitle=subtitle,
            highlight=highlight,
            accent_color=accent_color,
        )
        html_file.write_text(html_content, encoding="utf-8")
        file_uri = html_file.resolve().as_uri()

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--screenshot={out_png.resolve()}",
            "--window-size=1920,1080",
            file_uri,
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=15)
        self._crop_transparent(out_png)
        return out_png

    def generate_kinetic_word_html(self, word: str, duo_a: str = "#FFB703", duo_b: str = "#FB8500") -> str:
        """Una palabra gigante estilo tipografía cinética viral moderna con tamaño adaptativo anti-recorte."""
        w_clean = str(word or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        w_len = len(w_clean)
        if w_len >= 13:
            f_size = 135
        elif w_len >= 9:
            f_size = 165
        elif w_len >= 6:
            f_size = 190
        else:
            f_size = 215

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
  }}
  .word {{
    font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif;
    font-weight: 900;
    text-transform: uppercase;
    font-size: {f_size}px;
    line-height: 0.94;
    letter-spacing: -2px;
    white-space: nowrap;
    background: linear-gradient(180deg, #ffffff 0%, {duo_a} 45%, {duo_b} 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 14px 35px rgba(0,0,0,0.96)) drop-shadow(0 0 28px {duo_a}77) drop-shadow(0 0 55px {duo_b}44);
    padding: 20px 60px;
  }}
</style>
</head>
<body>
  <div class="word">{w_clean}</div>
</body>
</html>"""

    def render_kinetic_word_series(
        self,
        title: str,
        out_dir: Path,
        duo: tuple = None,
        max_words: int = 4,
    ) -> list:
        """Renderiza cada palabra del título como PNG individual bicolor.

        El scene engine las estalla en pantalla una a una (pop con rise) al ritmo
        de la locución: tipografía cinética viral palabra por palabra.
        Devuelve la lista de rutas PNG (vacía si algo falla).
        """
        import re as _re
        try:
            words = _re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñüÜ0-9']+", str(title or ""))[:max_words]
            if not words:
                return []
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            duo_a, duo_b = duo or KINETIC_DUOTONES[0]
            paths = []
            for i, word in enumerate(words):
                out_png = out_dir / f"kinetic_word_{i}.png"
                html_file = out_png.with_suffix(".html")
                html_file.write_text(self.generate_kinetic_word_html(word, duo_a, duo_b), encoding="utf-8")
                args = [
                    self.browser_bin,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--hide-scrollbars",
                    "--default-background-color=00000000",
                    "--force-device-scale-factor=2",
                    f"--screenshot={out_png.resolve()}",
                    "--window-size=2600,600",
                    html_file.resolve().as_uri(),
                ]
                subprocess.run(args, capture_output=True, check=True, timeout=15)
                self._crop_transparent(out_png)
                paths.append(out_png)
            return paths
        except Exception:
            return []

    def generate_document_citation_html(
        self,
        source_name: str,
        title: str,
        excerpt: str,
        highlighted_phrase: str = "",
        date_str: str = "REGISTRO OFICIAL",
        badge: str = "EVIDENCIA DOCUMENTAL",
    ) -> str:
        """Cita oficial / evidencia documental 100% unificada al nuevo diseño Matte Dark + Ámbar Glow."""
        return self.generate_html(
            headline=title or source_name,
            body=excerpt,
            badge=badge or "EVIDENCIA DOCUMENTAL",
            source=f"{source_name} · {date_str}" if source_name else date_str,
            style="quote",
        )

    def render_document_citation_to_image(
        self,
        source_name: str,
        title: str,
        excerpt: str,
        out_png: Path,
        highlighted_phrase: str = "",
        date_str: str = "REGISTRO OFICIAL",
        badge: str = "EVIDENCIA DOCUMENTAL",
    ) -> Path:
        """Renderiza cita documental oficial con el nuevo estándar Matte Dark + Ámbar Glow."""
        return self.render_to_image(
            headline=title or source_name,
            out_png=out_png,
            body=excerpt,
            badge=badge or "EVIDENCIA DOCUMENTAL",
            source=f"{source_name} · {date_str}" if source_name else date_str,
            style="quote",
        )

    def generate_split_versus_html(
        self,
        left_name: str,
        left_stat: str,
        right_name: str,
        right_stat: str,
        left_sub: str = "",
        right_sub: str = "",
        badge: str = "COMPARATIVA DIRECTA",
    ) -> str:
        """Diseño comparativa doble 100% unificado al nuevo estándar Matte Dark + Ámbar Glow."""
        from core.visual_templates import VisualTemplatesLibrary
        return VisualTemplatesLibrary(browser_bin=self.browser_bin).build_versus_split_html(
            side_a=left_name,
            side_b=right_name,
            stat_a=left_stat,
            stat_b=right_stat,
            tag=badge,
        )

    def render_split_versus_to_image(
        self,
        left_name: str,
        left_stat: str,
        right_name: str,
        right_stat: str,
        out_png: Path,
        left_sub: str = "",
        right_sub: str = "",
        badge: str = "COMPARATIVA DIRECTA",
    ) -> Path:
        """Renderiza la tarjeta split versus delegando a VisualTemplatesLibrary."""
        res = self.render_visual_template(
            template_name="versus_split",
            out_png=out_png,
            params={
                "side_a": left_name,
                "side_b": right_name,
                "stat_a": left_stat,
                "stat_b": right_stat,
                "tag": badge,
            },
        )
        return res or out_png

    def generate_chapter_tracker_html(
        self,
        chapters: list,
        current_index: int = 0,
    ) -> str:
        """Barra superior discreta de seguimiento de capítulos / temas (Chapter Progress Tracker)."""
        svg_check = '<svg width="12" height="10" viewBox="0 0 12 10" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M1 5L4.2 8.5L11 1.5" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        pills_html = []
        for idx, ch in enumerate(chapters):
            ch_clean = str(ch).replace("<", "&lt;").replace(">", "&gt;")
            if idx == current_index:
                pills_html.append(f'<div class="ch-pill active"><span class="pulse-dot"></span><span>{ch_clean}</span></div>')
            elif idx < current_index:
                pills_html.append(f'<div class="ch-pill past"><span class="check-icon">{svg_check}</span><span>{ch_clean}</span></div>')
            else:
                pills_html.append(f'<div class="ch-pill future"><span>{ch_clean}</span></div>')

        joined = '<div class="divider-line"></div>'.join(pills_html)

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  .tracker-bar {{
    display: inline-flex;
    align-items: center;
    gap: 16px;
    background: linear-gradient(145deg, rgba(9, 10, 13, 0.96) 0%, rgba(4, 5, 7, 0.98) 100%);
    border: 1px solid rgba(255, 255, 255, 0.10);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.9), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    padding: 9px 26px;
    color: #ffffff;
  }}
  .ch-pill {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 14.5px;
    font-weight: 600;
    letter-spacing: 0.3px;
    white-space: nowrap;
  }}
  .ch-pill.active {{
    color: #38bdf8;
    font-weight: 800;
    font-size: 15px;
    text-shadow: 0 0 14px rgba(56, 189, 248, 0.5);
  }}
  .ch-pill.past {{
    color: #cbd5e1;
    font-weight: 500;
  }}
  .check-icon {{
    display: inline-flex;
    align-items: center;
  }}
  .ch-pill.future {{
    color: #64748b;
    font-weight: 500;
  }}
  .pulse-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 10px #38bdf8;
  }}
  .divider-line {{
    width: 14px;
    height: 1px;
    background: rgba(255, 255, 255, 0.15);
  }}
</style>
</head>
<body>
  <div class="tracker-bar">
    {joined}
  </div>
</body>
</html>"""

    def generate_geointel_map_html(
        self,
        location_title: str,
        country_name: str,
        sat_b64: str = "",
        target_x: int = 560,
        target_y: int = 280,
        coordinates_str: str = "39.702° N, 44.299° E",
        notes: str = "Análisis topográfico y geológico en tiempo real.",
        badge: str = "SAT RECON // ORBITAL FEED",
        accent_color: str = "#ff9436",
        lat: float = 39.702,
        lon: float = 44.299,
        zoom: float = 7.2,
        pitch: float = 38.0,
        bearing: float = -14.0,
        maplibre_js_uri: str = "",
        maplibre_css_uri: str = "",
    ) -> str:
        """Mapa satelital hiperrealista con MapLibre GL JS (WebGL 3D orbital) y HUD de telemetría estilo Bloomberg/Reuters."""
        loc_clean = location_title.replace("<", "&lt;").replace(">", "&gt;")
        c_clean = country_name.replace("<", "&lt;").replace(">", "&gt;")
        coord_clean = coordinates_str.replace("<", "&lt;").replace(">", "&gt;")
        n_clean = notes.replace("<", "&lt;").replace(">", "&gt;")
        b_clean = badge.replace("<", "&lt;").replace(">", "&gt;")

        js_src = maplibre_js_uri or "https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"
        css_src = maplibre_css_uri or "https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css"

        # SVG icon defs — profesionales y sin emojis
        svg_pin = '<svg width="11" height="13" viewBox="0 0 12 14" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 0C3.24 0 1 2.24 1 5c0 3.75 5 9 5 9s5-5.25 5-9c0-2.76-2.24-5-5-5Zm0 6.75A1.75 1.75 0 1 1 6 3.25a1.75 1.75 0 0 1 0 3.5Z" fill="currentColor"/></svg>'
        svg_target = '<svg width="10" height="10" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.5"/><circle cx="6" cy="6" r="2" fill="currentColor"/></svg>'

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<link rel="stylesheet" href="{css_src}" />
<script src="{js_src}"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
  }}
  .map-card {{
    width: 960px;
    height: 540px;
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.16);
    box-shadow: 0 36px 90px rgba(0,0,0,0.92);
    background: #06090e;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }}
  #map {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }}
  /* Subtle vignette around map edges for depth without obscuring center */
  .vignette-overlay {{
    position: absolute;
    inset: 0;
    box-shadow: inset 0 0 90px rgba(0, 0, 0, 0.65);
    pointer-events: none;
    z-index: 2;
  }}
  /* Subtle cartographic grid markers */
  .grid-overlay {{
    position: absolute;
    inset: 0;
    background-image: 
      radial-gradient(rgba(255, 255, 255, 0.15) 1px, transparent 1px);
    background-size: 80px 80px;
    pointer-events: none;
    z-index: 3;
    opacity: 0.4;
  }}
  /* Top-left North compass */
  .north-badge {{
    position: absolute;
    top: 20px; left: 24px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #e2e8f0;
    background: rgba(10, 16, 26, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 6px 10px;
    border-radius: 4px;
    backdrop-filter: blur(10px);
    z-index: 10;
    letter-spacing: 1px;
  }}
  /* Top-right telemetry live pill */
  .top-pill {{
    position: absolute;
    top: 20px; right: 24px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    font-weight: 700;
    color: #f1f5f9;
    background: rgba(10, 16, 26, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 6px 12px;
    border-radius: 4px;
    backdrop-filter: blur(10px);
    z-index: 10;
    letter-spacing: 1.2px;
    text-transform: uppercase;
  }}
  .live-dot {{
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
  }}
  .pill-sep {{ color: rgba(255, 255, 255, 0.25); }}
  .pill-dim {{ color: {accent_color}; font-weight: 600; }}

  /* Floating Editorial Chyron (bottom-left) */
  .chyron-card {{
    position: absolute;
    bottom: 24px; left: 24px;
    width: 370px;
    background: rgba(8, 14, 24, 0.86);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-left: 3.5px solid {accent_color};
    border-radius: 6px;
    padding: 18px 20px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    z-index: 10;
  }}
  .chyron-tag {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.8px;
    color: {accent_color};
    text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .chyron-title {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.25;
    margin-bottom: 8px;
    letter-spacing: -0.2px;
  }}
  .chyron-desc {{
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.5;
    margin-bottom: 14px;
  }}
  .telemetry-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    font-family: 'JetBrains Mono', monospace;
  }}
  .tele-item {{
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .tele-label {{
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: rgba(255, 255, 255, 0.38);
    text-transform: uppercase;
  }}
  .tele-val {{
    font-size: 10.5px;
    font-weight: 600;
    color: #e2e8f0;
    letter-spacing: 0.3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  /* Cartographic scale bar (bottom-right) */
  .scale-bar {{
    position: absolute;
    bottom: 24px; right: 24px;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    z-index: 10;
    font-family: 'JetBrains Mono', monospace;
    font-size: 9.5px;
    color: rgba(255,255,255,0.7);
    letter-spacing: 1.2px;
    background: rgba(10, 16, 26, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 6px 10px;
    border-radius: 4px;
    backdrop-filter: blur(8px);
  }}
  .scale-ticks {{
    width: 60px;
    height: 3px;
    border-left: 1.5px solid {accent_color};
    border-right: 1.5px solid {accent_color};
    border-bottom: 1.5px solid {accent_color};
  }}

  /* Minimal precision corner brackets */
  .corner {{
    position: absolute;
    width: 14px; height: 14px;
    border-color: rgba(255, 255, 255, 0.25);
    border-style: solid;
    z-index: 12;
  }}
  .corner-tl {{ top: 10px; left: 10px; border-width: 1.5px 0 0 1.5px; }}
  .corner-tr {{ top: 10px; right: 10px; border-width: 1.5px 1.5px 0 0; }}
  .corner-bl {{ bottom: 10px; left: 10px; border-width: 0 0 1.5px 1.5px; }}
  .corner-br {{ bottom: 10px; right: 10px; border-width: 0 1.5px 1.5px 0; }}

  /* Documentary Cartographic Reticle Marker with Johnny Harris / Vox Leader Line */
  .reticle-container {{
    position: relative;
    width: 32px;
    height: 32px;
    pointer-events: none;
  }}
  .reticle-ring {{
    position: absolute;
    top: 0; left: 0;
    width: 32px; height: 32px;
    border-radius: 50%;
    border: 1.5px solid {accent_color};
    background: rgba(56, 189, 248, 0.12);
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.35);
  }}
  .reticle-core {{
    position: absolute;
    top: 13px; left: 13px;
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 0 6px #ffffff, 0 0 10px {accent_color};
  }}
  .reticle-tick-top {{
    position: absolute;
    top: -6px; left: 15px;
    width: 2px; height: 6px;
    background: {accent_color};
  }}
  .reticle-tick-bottom {{
    position: absolute;
    bottom: -6px; left: 15px;
    width: 2px; height: 6px;
    background: {accent_color};
  }}
  .reticle-tick-left {{
    position: absolute;
    top: 15px; left: -6px;
    width: 6px; height: 2px;
    background: {accent_color};
  }}
  .reticle-tick-right {{
    position: absolute;
    top: 15px; right: -6px;
    width: 6px; height: 2px;
    background: {accent_color};
  }}
  /* 45-degree Leader line callout */
  .leader-svg {{
    position: absolute;
    top: -36px;
    left: 20px;
    width: 140px;
    height: 48px;
    overflow: visible;
  }}
  .leader-badge {{
    position: absolute;
    top: -46px;
    left: 76px;
    display: flex;
    align-items: center;
    gap: 5px;
    background: rgba(10, 16, 26, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 3px;
    padding: 3px 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: #f1f5f9;
    white-space: nowrap;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  }}
</style>
</head>
<body>
  <div class="map-card">
    <div id="map"></div>
    <div class="vignette-overlay"></div>
    <div class="grid-overlay"></div>

    <div class="corner corner-tl"></div>
    <div class="corner corner-tr"></div>
    <div class="corner corner-bl"></div>
    <div class="corner corner-br"></div>

    <div class="north-badge">
      <svg width="9" height="13" viewBox="0 0 10 14" fill="none">
        <path d="M5 0L10 14L5 10L0 14L5 0Z" fill="{accent_color}"/>
      </svg>
      <span>N</span>
    </div>

    <div class="top-pill">
      <div class="live-dot"></div>
      <span>{b_clean}</span>
      <span class="pill-sep">|</span>
      <span class="pill-dim">WGS-84</span>
    </div>

    <div class="chyron-card">
      <div class="chyron-tag">
        {svg_pin}
        <span>{c_clean}</span>
      </div>
      <div class="chyron-title">{loc_clean}</div>
      <div class="chyron-desc">{n_clean}</div>
      <div class="telemetry-grid">
        <div class="tele-item">
          <span class="tele-label">COORDENADAS</span>
          <span class="tele-val">{coord_clean}</span>
        </div>
        <div class="tele-item">
          <span class="tele-label">SENSOR ÓPTICO</span>
          <span class="tele-val">ESRI ORBITAL 0.5M</span>
        </div>
      </div>
    </div>

    <div class="scale-bar">
      <div class="scale-ticks"></div>
      <span>50 KM</span>
    </div>
  </div>

  <script>
    const map = new maplibregl.Map({{
      container: 'map',
      style: {{
        version: 8,
        sources: {{
          'esri-satellite': {{
            'type': 'raster',
            'tiles': ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'],
            'tileSize': 256
          }}
        }},
        layers: [{{
          id: 'satellite-layer',
          type: 'raster',
          source: 'esri-satellite'
        }}]
      }},
      center: [{lon}, {lat}],
      zoom: {zoom},
      pitch: {pitch},
      bearing: {bearing},
      interactive: false,
      attributionControl: false
    }});

    const el = document.createElement('div');
    el.className = 'reticle-container';
    el.innerHTML = `
      <div class="reticle-ring"></div>
      <div class="reticle-core"></div>
      <div class="reticle-tick-top"></div>
      <div class="reticle-tick-bottom"></div>
      <div class="reticle-tick-left"></div>
      <div class="reticle-tick-right"></div>
      <svg class="leader-svg" viewBox="0 0 140 48" fill="none">
        <polyline points="0,40 36,4 120,4" stroke="{accent_color}" stroke-width="1.2" stroke-dasharray="2 2"/>
        <circle cx="0" cy="40" r="2" fill="{accent_color}"/>
      </svg>
      <div class="leader-badge">
        {svg_target}
        <span>OBJETIVO</span>
      </div>
    `;

    new maplibregl.Marker({{ element: el, anchor: 'center' }})
      .setLngLat([{lon}, {lat}])
      .addTo(map);
  </script>
</body>
</html>"""

    def render_geointel_map_to_image(
        self,
        location_title: str,
        country_name: str,
        out_png: Path,
        coordinates_str: str = "",
        notes: str = "Análisis topográfico y teledetección en tiempo real.",
        badge: str = "SAT RECON // ORBITAL FEED",
        accent_color: str = "#ff9436",
        **kwargs,
    ) -> Path:
        """Renderiza un mapa satelital hiperrealista con MapLibre GL JS (WebGL 3D orbital) y HUD de telemetría."""
        import urllib.request
        from pathlib import Path

        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)

        # Base de datos global ampliada de coordenadas y metadatos
        GEO_COORDS = {
            "turquía": (39.702, 44.299, 7.2, "39.702° N, 44.299° E", "MONTE ARARAT / MESETA DE ARMENIA"),
            "turquia": (39.702, 44.299, 7.2, "39.702° N, 44.299° E", "MONTE ARARAT / MESETA DE ARMENIA"),
            "ararat": (39.702, 44.299, 7.2, "39.702° N, 44.299° E", "MONTE ARARAT / FORMACIÓN DURUPINAR"),
            "colombia": (4.609, -74.081, 6.8, "4.609° N, 74.081° W", "BOGOTÁ D.C. / CORDILLERA ORIENTAL"),
            "bogotá": (4.609, -74.081, 7.2, "4.609° N, 74.081° W", "BOGOTÁ D.C. / SABANA DE BOGOTÁ"),
            "bogota": (4.609, -74.081, 7.2, "4.609° N, 74.081° W", "BOGOTÁ D.C. / SABANA DE BOGOTÁ"),
            "estados unidos": (38.907, -77.036, 6.8, "38.907° N, 77.036° W", "WASHINGTON D.C. / REGIÓN CAPITAL"),
            "ee.uu": (38.907, -77.036, 6.8, "38.907° N, 77.036° W", "WASHINGTON D.C. / REGIÓN CAPITAL"),
            "eeuu": (38.907, -77.036, 6.8, "38.907° N, 77.036° W", "WASHINGTON D.C. / REGIÓN CAPITAL"),
            "usa": (38.907, -77.036, 6.8, "38.907° N, 77.036° W", "WASHINGTON D.C. / REGIÓN CAPITAL"),
            "china": (39.904, 116.407, 6.8, "39.904° N, 116.407° E", "BEIJING / CUENCA DE HEBEI"),
            "rusia": (55.755, 37.617, 6.8, "55.755° N, 37.617° E", "MOSCÚ / LLANURA EUROPEA"),
            "ucrania": (50.450, 30.523, 6.8, "50.450° N, 30.523° E", "KIEV / CUENCA DEL DNIEPER"),
            "israel": (31.768, 35.213, 8.0, "31.768° N, 35.213° E", "JERUSALÉN / VALLE DEL JORDÁN"),
            "argentina": (-34.603, -58.381, 6.8, "34.603° S, 58.381° W", "BUENOS AIRES / REGIÓN PAMPEANA"),
            "españa": (40.416, -3.703, 6.8, "40.416° N, 3.703° W", "MADRID / MESETA CENTRAL"),
            "espana": (40.416, -3.703, 6.8, "40.416° N, 3.703° W", "MADRID / MESETA CENTRAL"),
            "méxico": (19.432, -99.133, 6.8, "19.432° N, 99.133° W", "VALLE DE MÉXICO"),
            "mexico": (19.432, -99.133, 6.8, "19.432° N, 99.133° W", "VALLE DE MÉXICO"),
            "chile": (-33.448, -70.669, 6.8, "33.448° S, 70.669° W", "SANTIAGO / VALLE CENTRAL"),
            "brasil": (-15.797, -47.864, 6.5, "15.797° S, 47.864° W", "BRASILIA / PLANALTO CENTRAL"),
            "egipto": (30.044, 31.235, 7.2, "30.044° N, 31.235° E", "EL CAIRO / DELTA DEL NILO"),
            "japón": (35.676, 139.650, 7.0, "35.676° N, 139.650° E", "TOKIO / LLANURA DE KANTO"),
            "japon": (35.676, 139.650, 7.0, "35.676° N, 139.650° E", "TOKIO / LLANURA DE KANTO"),
        }

        c_key = country_name.lower().strip()
        l_key = location_title.lower().strip()
        matched = GEO_COORDS.get(c_key) or GEO_COORDS.get(l_key)
        if not matched:
            for k, val in GEO_COORDS.items():
                if k in c_key or k in l_key:
                    matched = val
                    break
        if not matched:
            # Sin entidad reconocida NO se fabrica un mapa. Mostrar el Monte
            # Ararat por defecto rotulado "ZONA DE INVESTIGACIÓN" presentaba una
            # ubicación inventada como real — desinformación en pantalla. La
            # escena degrada a tarjeta Bento estándar (ver llamador en scene_engine).
            return None

        lat, lon, zoom, default_coords, default_reg = matched
        coords_display = (
            coordinates_str
            if coordinates_str and len(coordinates_str) > 5 and "COORDENADAS" not in coordinates_str
            else default_coords
        )

        # Cache local de MapLibre GL JS para carga instantánea.
        # Ruta anclada a BASE_DIR (antes relativa al CWD: lanzar el servidor desde
        # otro directorio duplicaba el cache) y descargas CON timeout (urlretrieve
        # no admite timeout y con red degradada colgaba el render minutos).
        from config.settings import settings as _settings
        cache_dir = (_settings.BASE_DIR / "storage" / "cache" / "maplibre").resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        js_path = cache_dir / "maplibre-gl.js"
        css_path = cache_dir / "maplibre-gl.css"

        def _download_with_timeout(url: str, dest: Path) -> None:
            with urllib.request.urlopen(url, timeout=20) as response, open(dest, "wb") as out_f:
                out_f.write(response.read())

        if not js_path.exists():
            try:
                _download_with_timeout("https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js", js_path)
            except Exception:
                pass

        if not css_path.exists():
            try:
                _download_with_timeout("https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css", css_path)
            except Exception:
                pass

        js_uri = js_path.as_uri() if js_path.exists() else ""
        css_uri = css_path.as_uri() if css_path.exists() else ""

        html_file = out_png.with_suffix(".html")
        html_content = self.generate_geointel_map_html(
            location_title=location_title,
            country_name=country_name if country_name and "ZONA" not in country_name else default_reg,
            coordinates_str=coords_display,
            notes=notes,
            badge=badge,
            accent_color=accent_color,
            lat=lat,
            lon=lon,
            zoom=zoom,
            pitch=38.0,
            bearing=-14.0,
            maplibre_js_uri=js_uri,
            maplibre_css_uri=css_uri,
        )
        html_file.write_text(html_content, encoding="utf-8")
        file_uri = html_file.resolve().as_uri()

        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            "--virtual-time-budget=6000",
            f"--screenshot={out_png.resolve()}",
            "--window-size=1200,750",
            file_uri,
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=25)
        self._crop_transparent(out_png)
        return out_png

    @staticmethod
    def _crop_transparent(png_path: Path):
        try:
            from PIL import Image
            im = Image.open(png_path)
            bbox = im.getbbox()
            if bbox:
                pad = 12
                b = (max(0, bbox[0]-pad), max(0, bbox[1]-pad), min(im.width, bbox[2]+pad), min(im.height, bbox[3]+pad))
                im.crop(b).save(png_path)
        except Exception:
            pass

    def generate_viral_verdict_badge_html(
        self,
        headline: str,
        icon: str = "✓",
        tilt_deg: float = -3.5,
    ) -> str:
        """Genera el HTML del distintivo viral inclinado delegando en VisualTemplatesLibrary."""
        from core.visual_templates import VisualTemplatesLibrary
        return VisualTemplatesLibrary(browser_bin=self.browser_bin).build_verdict_badge_html(
            headline=headline,
            icon=icon,
            tilt_deg=tilt_deg,
        )

    def render_viral_verdict_badge_to_image(
        self,
        headline: str,
        out_png: Path,
        icon: str = "✓",
        tilt_deg: float = -3.5,
    ) -> Optional[Path]:
        """Renderiza a PNG transparente el distintivo viral inclinado delegando en VisualTemplatesLibrary."""
        return self.render_visual_template(
            template_name="verdict_badge",
            out_png=out_png,
            params={"headline": headline, "icon": icon, "tilt_deg": tilt_deg},
        )

    def generate_tech_header_card_html(
        self,
        title: str,
        subtitle: str = "",
        author: str = "",
        repo_or_tag: str = "",
    ) -> str:
        """Genera el HTML de la tarjeta técnica superior delegando en VisualTemplatesLibrary."""
        from core.visual_templates import VisualTemplatesLibrary
        sub = subtitle or (f"por {author} · {repo_or_tag}" if (author or repo_or_tag) else "")
        return VisualTemplatesLibrary(browser_bin=self.browser_bin).build_tech_header_card_html(
            title=title,
            subtitle=sub,
        )

    def render_tech_header_card_to_image(
        self,
        title: str,
        out_png: Path,
        subtitle: str = "",
        author: str = "",
        repo_or_tag: str = "",
    ) -> Optional[Path]:
        """Renderiza a PNG transparente la tarjeta técnica flotante superior delegando en VisualTemplatesLibrary."""
        sub = subtitle or (f"por {author} · {repo_or_tag}" if (author or repo_or_tag) else "")
        return self.render_visual_template(
            template_name="tech_card",
            out_png=out_png,
            params={"title": title, "subtitle": sub},
        )

    def render_visual_template(
        self,
        template_name: str,
        out_png: Path,
        params: Optional[Dict[str, Any]] = None,
        variant: str = "orange_noir",
    ) -> Optional[Path]:
        """Renderiza cualquier plantilla de la librería VisualTemplatesLibrary."""
        try:
            from core.editorial_cards import render_editorial
            editorial = render_editorial(
                template_name=template_name,
                out_png=Path(out_png),
                params=params or {},
                variant=variant,
                vertical=True,
                browser_bin=self.browser_bin,
            )
            if editorial is not None:
                return editorial
        except Exception as exc:
            import logging
            logging.getLogger("aethercut.web_renderer").warning(
                f"Editorial template '{template_name}' no disponible: {exc}"
            )

        try:
            from core.visual_templates import VisualTemplatesLibrary
            lib = VisualTemplatesLibrary(browser_bin=self.browser_bin)
            return lib.render_template_to_image(
                template_name=template_name,
                out_png=out_png,
                params=params,
                variant=variant,
            )
        except Exception as exc:
            import logging
            logging.getLogger("aethercut.web_renderer").warning(f"Error renderizando template '{template_name}': {exc}")
            return None


