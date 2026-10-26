"""
Visual Templates Library (AetherCut Pro Design System)
Colección completa de componentes gráficos, distintivos virales, tarjetas técnicas
y ayudas visuales cinéticas estilo Orange Noir y variantes profesionales.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.visual_templates_extra import ExtraTemplatesMixin

logger = logging.getLogger("aethercut.visual_templates")

HTML_FONTS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,600;1,700&family=Space+Grotesk:wght@500;700;800&family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
"""

# Paletas de color firma con enfoque "Orange Noir" y variantes
THEME_PALETTES = {
    "orange_noir": {
        "bg": "rgba(12, 13, 18, 0.88)",
        "card_bg": "#0c0d12",
        "border": "rgba(255, 148, 54, 0.40)",
        "accent": "#ff9436",
        "accent_gradient": "linear-gradient(135deg, #ff9436 0%, #ff5500 100%)",
        "text": "#ffffff",
        "text_sub": "#cbd5e1",
        "glow": "rgba(255, 148, 54, 0.35)",
        "badge_border": "3px solid rgba(255, 148, 54, 0.90)",
        "pill_bg": "rgba(255, 148, 54, 0.14)",
        "grid_dot": "rgba(255, 148, 54, 0.16)",
    },
    "frosted_white": {
        "bg": "rgba(20, 22, 30, 0.50)",
        "card_bg": "rgba(18, 20, 28, 0.65)",
        "border": "rgba(255, 255, 255, 0.85)",
        "accent": "#ffffff",
        "accent_gradient": "linear-gradient(135deg, #ffffff 0%, #e2e8f0 100%)",
        "text": "#ffffff",
        "text_sub": "#94a3b8",
        "glow": "rgba(255, 255, 255, 0.20)",
        "badge_border": "3.5px solid rgba(255, 255, 255, 0.95)",
        "pill_bg": "rgba(255, 255, 255, 0.15)",
        "grid_dot": "rgba(255, 255, 255, 0.14)",
    },
    "emerald_matrix": {
        "bg": "rgba(10, 18, 14, 0.90)",
        "card_bg": "#0a130e",
        "border": "rgba(0, 245, 160, 0.45)",
        "accent": "#00f5a0",
        "accent_gradient": "linear-gradient(135deg, #00f5a0 0%, #00bb77 100%)",
        "text": "#ffffff",
        "text_sub": "#a7f3d0",
        "glow": "rgba(0, 245, 160, 0.30)",
        "badge_border": "3px solid rgba(0, 245, 160, 0.90)",
        "pill_bg": "rgba(0, 245, 160, 0.15)",
        "grid_dot": "rgba(0, 245, 160, 0.18)",
    },
    "crimson_hazard": {
        "bg": "rgba(20, 10, 12, 0.92)",
        "card_bg": "#140a0e",
        "border": "rgba(255, 51, 102, 0.50)",
        "accent": "#ff3366",
        "accent_gradient": "linear-gradient(135deg, #ff3366 0%, #cc0033 100%)",
        "text": "#ffffff",
        "text_sub": "#fecdd3",
        "glow": "rgba(255, 51, 102, 0.35)",
        "badge_border": "3px solid rgba(255, 51, 102, 0.95)",
        "pill_bg": "rgba(255, 51, 102, 0.16)",
        "grid_dot": "rgba(255, 51, 102, 0.20)",
    },
    "cyber_cyan": {
        "bg": "rgba(12, 13, 18, 0.88)",
        "card_bg": "#0c0d12",
        "border": "rgba(255, 148, 54, 0.45)",
        "accent": "#ff9436",
        "accent_gradient": "linear-gradient(135deg, #ff9436 0%, #ffe500 100%)",
        "text": "#ffffff",
        "text_sub": "#cbd5e1",
        "glow": "rgba(255, 148, 54, 0.35)",
        "badge_border": "3px solid rgba(255, 148, 54, 0.90)",
        "pill_bg": "rgba(255, 148, 54, 0.14)",
        "grid_dot": "rgba(255, 148, 54, 0.16)",
    },
    "royal_gold": {
        "bg": "rgba(18, 14, 8, 0.90)",
        "card_bg": "#141009",
        "border": "rgba(255, 183, 3, 0.45)",
        "accent": "#ffb703",
        "accent_gradient": "linear-gradient(135deg, #ffb703 0%, #fb8500 100%)",
        "text": "#ffffff",
        "text_sub": "#fde68a",
        "glow": "rgba(255, 183, 3, 0.35)",
        "badge_border": "3px solid rgba(255, 183, 3, 0.90)",
        "pill_bg": "rgba(255, 183, 3, 0.15)",
        "grid_dot": "rgba(255, 183, 3, 0.18)",
    },
    "editorial_cream": {
        "bg": "rgba(244, 239, 234, 0.98)",
        "card_bg": "#ffffff",
        "border": "rgba(20, 20, 20, 0.12)",
        "accent": "#e63946",
        "accent_gradient": "linear-gradient(135deg, #e63946 0%, #d62828 100%)",
        "text": "#121212",
        "text_sub": "#64748b",
        "glow": "rgba(230, 57, 70, 0.20)",
        "badge_border": "2.5px solid rgba(230, 57, 70, 0.85)",
        "pill_bg": "rgba(230, 57, 70, 0.08)",
        "grid_dot": "rgba(0, 0, 0, 0.08)",
        "grid_line": "rgba(0, 0, 0, 0.06)",
    },
    "editorial_slate": {
        "bg": "rgba(18, 20, 24, 0.96)",
        "card_bg": "#14151a",
        "border": "rgba(255, 148, 54, 0.35)",
        "accent": "#ff9436",
        "accent_gradient": "linear-gradient(135deg, #ff9436 0%, #ff5500 100%)",
        "text": "#f8fafc",
        "text_sub": "#cbd5e1",
        "glow": "rgba(255, 148, 54, 0.25)",
        "badge_border": "2.5px solid rgba(255, 148, 54, 0.85)",
        "pill_bg": "rgba(255, 148, 54, 0.12)",
        "grid_dot": "rgba(255, 255, 255, 0.08)",
        "grid_line": "rgba(255, 255, 255, 0.06)",
    },
    "sunset_warm": {
        "bg": "rgba(255, 248, 244, 0.98)",
        "card_bg": "#ffffff",
        "border": "rgba(224, 122, 95, 0.25)",
        "accent": "#e07a5f",
        "accent_gradient": "linear-gradient(135deg, #e07a5f 0%, #c85a32 100%)",
        "text": "#241712",
        "text_sub": "#78665f",
        "glow": "rgba(224, 122, 95, 0.20)",
        "badge_border": "2.5px solid rgba(224, 122, 95, 0.85)",
        "pill_bg": "rgba(224, 122, 95, 0.10)",
        "grid_dot": "rgba(224, 122, 95, 0.10)",
        "grid_line": "rgba(224, 122, 95, 0.07)",
    },
    "sage_minimal": {
        "bg": "rgba(244, 247, 245, 0.98)",
        "card_bg": "#ffffff",
        "border": "rgba(45, 106, 79, 0.20)",
        "accent": "#2d6a4f",
        "accent_gradient": "linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%)",
        "text": "#0a1c14",
        "text_sub": "#4d6b5e",
        "glow": "rgba(45, 106, 79, 0.22)",
        "badge_border": "2.5px solid rgba(45, 106, 79, 0.85)",
        "pill_bg": "rgba(45, 106, 79, 0.10)",
        "grid_dot": "rgba(45, 106, 79, 0.09)",
        "grid_line": "rgba(45, 106, 79, 0.06)",
    },
}


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


class VisualTemplatesLibrary(ExtraTemplatesMixin):
    """Librería y motor de plantillas visuales cinéticas de alta gama."""

    def __init__(self, browser_bin: Optional[str] = None):
        self.browser_bin = browser_bin or _get_browser_bin()

    def get_palette(self, variant: str = "orange_noir") -> Dict[str, str]:
        var_key = (variant or "orange_noir").lower().strip()
        return THEME_PALETTES.get(var_key, THEME_PALETTES["orange_noir"])

    @staticmethod
    def _crop_transparent(png_path: Path):
        try:
            from PIL import Image
            im = Image.open(png_path)
            bbox = im.getbbox()
            if bbox:
                pad = 16
                b = (
                    max(0, bbox[0] - pad),
                    max(0, bbox[1] - pad),
                    min(im.width, bbox[2] + pad),
                    min(im.height, bbox[3] + pad),
                )
                im.crop(b).save(png_path)
        except Exception:
            pass

    # =========================================================================
    # 1. PLANTILLA: VERDICT BADGE (Distintivo / Sello Inclinado)
    # =========================================================================
    def build_verdict_badge_html(
        self,
        headline: str,
        icon: str = "✓",
        variant: str = "orange_noir",
        tilt_deg: float = -3.5,
        subtitle: str = "",
    ) -> str:
        p = self.get_palette(variant)
        clean_headline = (headline or "Verificado").strip()
        clean_icon = (icon or "✓").strip()
        sub_html = f'<div class="badge-sub">{subtitle}</div>' if subtitle else ""

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
    overflow: hidden;
  }}
  .badge-wrap {{
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    transform: rotate({tilt_deg:.1f}deg);
  }}
  .badge-stamp {{
    display: inline-flex;
    align-items: center;
    gap: 18px;
    padding: 18px 44px;
    border: {p['badge_border']};
    border-radius: 24px;
    background: {p['bg']};
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    box-shadow: 0 24px 50px rgba(0, 0, 0, 0.55), 0 0 30px {p['glow']}, inset 0 1px 1px rgba(255, 255, 255, 0.35);
    color: {p['text']};
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 56px;
    font-weight: 700;
    letter-spacing: -0.5px;
    text-shadow: 0 3px 14px rgba(0, 0, 0, 0.65);
    white-space: nowrap;
  }}
  .badge-icon {{
    font-size: 46px;
    font-weight: 900;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: {p['accent']};
    display: inline-flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
    filter: drop-shadow(0 0 8px {p['glow']});
  }}
  .badge-sub {{
    margin-top: 10px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: {p['text_sub']};
    background: rgba(0, 0, 0, 0.50);
    padding: 4px 16px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.10);
  }}
</style>
</head>
<body>
  <div class="badge-wrap">
    <div class="badge-stamp">
      <span class="badge-icon">{clean_icon}</span>
      <span>{clean_headline}</span>
    </div>
    {sub_html}
  </div>
</body>
</html>"""

    # =========================================================================
    # 2. PLANTILLA: TECH HEADER CARD (Tarjeta Técnica Superior)
    # =========================================================================
    def build_tech_header_card_html(
        self,
        title: str,
        subtitle: str = "",
        author: str = "",
        repo_or_tag: str = "",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_title = (title or "tech-specification").strip()

        clean_sub = subtitle.strip()
        if not author and not repo_or_tag and "·" in clean_sub:
            parts = [x.strip() for x in clean_sub.split("·", 1)]
            author = parts[0][4:].strip() if parts[0].lower().startswith("por ") else parts[0]
            repo_or_tag = parts[1]
        elif not author and clean_sub:
            author = clean_sub

        meta_parts = []
        if author:
            meta_parts.append(f'<span>por <span class="tech-author">{author}</span></span>')
        if repo_or_tag:
            if meta_parts:
                meta_parts.append('<span class="tech-sep">·</span>')
            meta_parts.append(f'<span class="tech-repo">{repo_or_tag}</span>')
        meta_html = "".join(meta_parts) if meta_parts else f'<span>{clean_sub or "verified-engine"}</span>'

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
    overflow: hidden;
  }}
  .tech-card {{
    position: relative;
    width: 720px;
    padding: 34px 44px;
    border-radius: 22px;
    background: {p['card_bg']};
    background-image: radial-gradient({p['grid_dot']} 1.2px, transparent 1.2px);
    background-size: 18px 18px;
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 60px rgba(0, 0, 0, 0.65), 0 0 25px {p['glow']}, inset 0 1px 0 rgba(255, 255, 255, 0.12);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 10px;
  }}
  .tech-tag-indicator {{
    position: absolute;
    top: -12px;
    left: 40px;
    background: {p['accent_gradient']};
    color: #000000;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 3px 12px;
    border-radius: 8px;
    box-shadow: 0 4px 12px {p['glow']};
  }}
  .tech-title {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 50px;
    font-weight: 800;
    color: {p['text']};
    letter-spacing: -1.2px;
    line-height: 1.15;
    text-shadow: 0 3px 12px rgba(0, 0, 0, 0.60);
    word-break: break-word;
  }}
  .tech-meta {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px;
    font-weight: 500;
    color: {p['text_sub']};
    letter-spacing: -0.2px;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .tech-author {{
    color: {p['accent']};
    font-weight: 700;
  }}
  .tech-sep {{
    color: rgba(255, 255, 255, 0.30);
  }}
  .tech-repo {{
    color: #e2e8f0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px;
  }}
</style>
</head>
<body>
  <div class="tech-card">
    <div class="tech-tag-indicator">SYS // SPEC</div>
    <div class="tech-title">{clean_title}</div>
    <div class="tech-meta">
      {meta_html}
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 3. PLANTILLA: STAT COUNTER CARD (Cifra de Impacto / Métrica Clave)
    # =========================================================================
    def build_stat_counter_html(
        self,
        stat_value: str,
        stat_label: str,
        headline: str = "",
        tag: str = "MÉTRICA CLAVE",
        trend_text: str = "",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_stat = (stat_value or "100%").strip()
        clean_lbl = (stat_label or "Dato Verificado").strip()
        clean_hl = headline.strip()
        clean_trend = (trend_text or "").strip()

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
    overflow: hidden;
  }}
  .stat-card {{
    position: relative;
    max-width: 480px;
    padding: 22px 32px;
    border-radius: 22px;
    background: rgba(14, 15, 20, 0.75);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1.5px solid rgba(255, 148, 54, 0.35);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.75), 0 0 25px rgba(255, 148, 54, 0.20), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 10px;
  }}
  .top-row {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
  }}
  .stat-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 999px;
    background: rgba(255, 148, 54, 0.12);
    border: 1px solid rgba(255, 148, 54, 0.30);
    color: #ff9436;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }}
  .dot-pulse {{
    width: 5px; height: 5px;
    border-radius: 50%;
    background: #ff9436;
    box-shadow: 0 0 8px #ff9436;
  }}
  .trend-pill {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12px;
    font-weight: 700;
    color: #10b981;
    background: rgba(16, 185, 129, 0.12);
    padding: 3px 10px;
    border-radius: 999px;
    border: 1px solid rgba(16, 185, 129, 0.25);
  }}
  .headline-txt {{
    font-family: 'Outfit', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.25;
  }}
  .number-row {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }}
  .stat-number {{
    font-family: 'Outfit', sans-serif;
    font-size: 64px;
    font-weight: 900;
    background: linear-gradient(135deg, #ffffff 0%, #ff9436 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
    letter-spacing: -1.5px;
    filter: drop-shadow(0 4px 16px rgba(255, 148, 54, 0.30));
  }}
  .stat-unit {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #cbd5e1;
    line-height: 1.35;
    max-width: 380px;
  }}
  .meter-bar {{
    width: 60px;
    height: 3px;
    background: rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    overflow: hidden;
    margin-top: 4px;
  }}
  .meter-fill {{
    height: 100%;
    width: 100%;
    background: linear-gradient(90deg, #ff9436 0%, #ffe500 100%);
    border-radius: 2px;
  }}
</style>
</head>
<body>
  <div class="stat-card">
    <div class="top-row">
      <div class="stat-badge"><span class="dot-pulse"></span><span>{tag}</span></div>
      {f'<div class="trend-pill">▲ {clean_trend}</div>' if clean_trend else ''}
    </div>
    {f'<div class="headline-txt">{clean_hl}</div>' if clean_hl else ''}
    <div class="number-row">
      <div class="stat-number">{clean_stat}</div>
      <div class="stat-unit">{clean_lbl}</div>
    </div>
    <div class="meter-bar">
      <div class="meter-fill"></div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 4. PLANTILLA: VERSUS SPLIT (Comparativa Dual)
    # =========================================================================
    def build_versus_split_html(
        self,
        side_a: str,
        side_b: str,
        stat_a: str = "",
        stat_b: str = "",
        tag: str = "ANÁLISIS COMPARATIVO",
        variant: str = "auto",
    ) -> str:
        """Genera la tarjeta comparativa en uno de 3 estilos editoriales profesionales.

        Variantes:
        - 'editorial'  : Tipografía limpia fondo negro, línea divisora blanca, estilo NYT/BBC
        - 'broadcast'  : Franja inferior tipo ticker periodístico, serif bold, fondo carbón
        - 'minimal'    : Dos bloques blancos sobre negro, solo texto, sin glow ni bordes decorativos
        - 'auto'       : Rota automáticamente entre las 3 según hash del tag
        """
        import hashlib
        styles = ["editorial", "broadcast", "minimal"]
        if variant == "auto":
            idx = int(hashlib.md5((tag + side_a).encode()).hexdigest(), 16) % len(styles)
            variant = styles[idx]

        # ──────────────────────────────────────────
        # VARIANTE 1: EDITORIAL (NYT / The Guardian / Atlantic)
        # Fondo sólido obsidiana carbón, bordes sutiles 1px,
        # separador vertical con micro-badge VS y tipografía serif.
        # ──────────────────────────────────────────
        if variant == "editorial":
            label_a = "LADO A"
            label_b = "LADO B"
            stat_a_block = f'<div class="stat">{stat_a}</div>' if stat_a else ""
            stat_b_block = f'<div class="stat">{stat_b}</div>' if stat_b else ""
            return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
  }}
  .card {{
    width: 700px;
    background: #0c0d12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    overflow: hidden;
    font-family: 'Inter', sans-serif;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }}
  .card-header {{
    background: #12141c;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    padding: 12px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .card-header-left {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .card-header .dot {{
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #94a3b8;
  }}
  .card-header .tag {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.20em;
    text-transform: uppercase;
    color: #94a3b8;
  }}
  .card-header .pill {{
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #64748b;
  }}
  .body {{
    display: flex;
    align-items: stretch;
  }}
  .side {{
    flex: 1;
    padding: 26px 32px 30px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 8px;
  }}
  .side-label {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.20em;
    text-transform: uppercase;
    color: #64748b;
  }}
  .name {{
    font-family: 'Playfair Display', Georgia, serif;
    font-style: italic;
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.25;
  }}
  .stat {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 38px;
    font-weight: 800;
    color: #f1f5f9;
    letter-spacing: -1px;
    margin-top: 4px;
  }}
  .divider {{
    width: 1px;
    background: rgba(255, 255, 255, 0.07);
    margin: 16px 0;
    flex-shrink: 0;
    position: relative;
  }}
  .divider::after {{
    content: 'vs';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: #171a23;
    border: 1px solid rgba(255, 255, 255, 0.10);
    color: #8a96a7;
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 999px;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="card-header">
    <div class="card-header-left">
      <div class="dot"></div>
      <div class="tag">{tag}</div>
    </div>
    <div class="pill">COMPARATIVA</div>
  </div>
  <div class="body">
    <div class="side">
      <div class="side-label">{label_a}</div>
      <div class="name">{side_a}</div>
      {stat_a_block}
    </div>
    <div class="divider"></div>
    <div class="side">
      <div class="side-label">{label_b}</div>
      <div class="name">{side_b}</div>
      {stat_b_block}
    </div>
  </div>
</div>
</body></html>"""

        # ──────────────────────────────────────────
        # VARIANTE 2: BROADCAST (Bloomberg TV / Axios / DW)
        # Filas horizontales apiladas en contenedor sólido,
        # borde 1px sutil, indicador fino de 2px y datos alineados.
        # ──────────────────────────────────────────
        if variant == "broadcast":
            rows = []
            bars = ["#94a3b8", "#475569"]
            for idx, (label, name, stat) in enumerate([("A", side_a, stat_a), ("B", side_b, stat_b)]):
                stat_part = f'<div class="bstat">{stat}</div>' if stat else ""
                bar_color = bars[idx % len(bars)]
                rows.append(f"""
    <div class="brow">
      <div class="bbar" style="background: {bar_color};"></div>
      <div class="bcontent">
        <div class="binfo">
          <span class="blabel">OPCIÓN {label}</span>
          <div class="bname">{name}</div>
        </div>
        {stat_part}
      </div>
    </div>""")
            rows_html = "".join(rows)
            return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
  }}
  .card {{
    width: 700px;
    background: #0d0f16;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    overflow: hidden;
    font-family: 'Inter', sans-serif;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }}
  .card-top {{
    padding: 12px 24px;
    background: #12151e;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .card-tag {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.20em;
    text-transform: uppercase;
    color: #94a3b8;
  }}
  .card-status {{
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #64748b;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    padding: 2px 8px;
    border-radius: 4px;
  }}
  .brow {{
    display: flex;
    align-items: stretch;
  }}
  .brow + .brow {{
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }}
  .bbar {{
    width: 2px;
    flex-shrink: 0;
  }}
  .bcontent {{
    flex: 1;
    padding: 22px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
  }}
  .binfo {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .blabel {{
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #64748b;
  }}
  .bname {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.25;
  }}
  .bstat {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 28px;
    font-weight: 800;
    color: #f8fafc;
    letter-spacing: -0.5px;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="card-top">
    <span class="card-tag">{tag}</span>
    <span class="card-status">MÉTRICAS</span>
  </div>
  {rows_html}
</div>
</body></html>"""

        # ──────────────────────────────────────────
        # VARIANTE 3: MINIMAL (Swiss / Linear / Apple)
        # Dos bloques sólidos independientes con bordes 1px,
        # micro chip numérico 01/02 y espaciado arquitectónico.
        # ──────────────────────────────────────────
        stat_a_m = f'<div class="mstat">{stat_a}</div>' if stat_a else ""
        stat_b_m = f'<div class="mstat">{stat_b}</div>' if stat_b else ""
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
  }}
  .card {{
    width: 700px;
    font-family: 'Inter', sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
  }}
  .mtop {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.20em;
    text-transform: uppercase;
    color: #8e98a8;
    background: #12141c;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 6px 16px;
    border-radius: 999px;
    margin-bottom: 16px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
  }}
  .mrow {{
    display: flex;
    gap: 14px;
    width: 100%;
  }}
  .mblock {{
    flex: 1;
    background: #0f121a;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 24px 26px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 160px;
    gap: 12px;
    box-shadow: 0 20px 48px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }}
  .mnumber {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.14em;
    color: #64748b;
    background: #161a24;
    border: 1px solid rgba(255, 255, 255, 0.06);
    padding: 3px 8px;
    border-radius: 4px;
    width: fit-content;
    text-transform: uppercase;
  }}
  .mname {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 21px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.3;
  }}
  .mstat {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 34px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.5px;
    margin-top: 2px;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="mtop">{tag}</div>
  <div class="mrow">
    <div class="mblock">
      <div class="mnumber">01</div>
      <div class="mname">{side_a}</div>
      {stat_a_m}
    </div>
    <div class="mblock">
      <div class="mnumber">02</div>
      <div class="mname">{side_b}</div>
      {stat_b_m}
    </div>
  </div>
</div>
</body></html>"""

    # =========================================================================
    # 5. PLANTILLA: QUOTE & EVIDENCE (Cita Resaltada Vox Style)
    # =========================================================================
    def build_quote_evidence_html(
        self,
        quote_text: str,
        source: str = "Registro Oficial",
        highlight_phrase: str = "",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_quote = (quote_text or "La evidencia documental confirma el hallazgo.").strip()

        # Si se especifica highlight_phrase, rodear con tag de resaltador fosforescente
        if highlight_phrase and highlight_phrase in clean_quote:
            clean_quote = clean_quote.replace(
                highlight_phrase,
                f'<span class="highlighter">{highlight_phrase}</span>',
            )

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
    overflow: hidden;
  }}
  .quote-card {{
    position: relative;
    width: 740px;
    padding: 42px 46px;
    border-radius: 24px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 65px rgba(0, 0, 0, 0.70), 0 0 25px {p['glow']}, inset 0 1px 0 rgba(255, 255, 255, 0.14);
    display: flex;
    flex-direction: column;
    gap: 18px;
  }}
  .quote-icon {{
    position: absolute;
    top: 26px;
    right: 36px;
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 90px;
    line-height: 0.6;
    color: {p['accent']};
    opacity: 0.25;
  }}
  .source-header {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: {p['accent']};
  }}
  .quote-body {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 32px;
    font-weight: 600;
    font-style: italic;
    color: #ffffff;
    line-height: 1.35;
    letter-spacing: -0.2px;
  }}
  .highlighter {{
    background: rgba(255, 148, 54, 0.35);
    color: #ffffff;
    padding: 2px 8px;
    border-radius: 4px;
    box-shadow: 0 0 12px rgba(255, 148, 54, 0.40);
  }}
  .source-footer {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: {p['text_sub']};
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 14px;
  }}
  .verified-badge {{
    color: #10b981;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    font-weight: 700;
    background: rgba(16, 185, 129, 0.12);
    padding: 3px 10px;
    border-radius: 6px;
  }}
</style>
</head>
<body>
  <div class="quote-card">
    <div class="quote-icon">“</div>
    <div class="source-header">EVIDENCIA DOCUMENTAL</div>
    <div class="quote-body">“{clean_quote}”</div>
    <div class="source-footer">
      <span>Fuente: <strong>{source}</strong></span>
      <span class="verified-badge">✓ Verificado</span>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 6. PLANTILLA: STEP BADGE (Fase / Paso / Hito)
    # =========================================================================
    def build_step_badge_html(
        self,
        step_number: str,
        step_title: str,
        subtitle: str = "",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_num = str(step_number or "01").zfill(2)
        clean_title = (step_title or "Paso Clave").strip()
        sub_html = f'<div class="step-sub">{subtitle}</div>' if subtitle else ""

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
    overflow: hidden;
  }}
  .step-pill {{
    display: inline-flex;
    align-items: center;
    gap: 22px;
    padding: 16px 36px 16px 20px;
    border-radius: 24px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 24px 50px rgba(0, 0, 0, 0.65), 0 0 25px {p['glow']}, inset 0 1px 0 rgba(255, 255, 255, 0.15);
  }}
  .step-num-circle {{
    width: 60px;
    height: 60px;
    border-radius: 18px;
    background: {p['accent_gradient']};
    box-shadow: 0 0 16px {p['glow']};
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Outfit', sans-serif;
    font-size: 32px;
    font-weight: 900;
    color: #000000;
  }}
  .step-texts {{
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .step-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 38px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.5px;
    line-height: 1.1;
  }}
  .step-sub {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: {p['text_sub']};
  }}
</style>
</head>
<body>
  <div class="step-pill">
    <div class="step-num-circle">{clean_num}</div>
    <div class="step-texts">
      <div class="step-title">{clean_title}</div>
      {sub_html}
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 7. PLANTILLA: ALERT BANNER (Alerta Crítica / Warning HUD)
    # =========================================================================
    def build_alert_banner_html(
        self,
        headline: str,
        body: str = "",
        tag: str = "ADVERTENCIA CRÍTICA",
        variant: str = "crimson_hazard",
    ) -> str:
        p = self.get_palette(variant)
        clean_hl = (headline or "PUNTO DE QUIEBRE").strip()
        body_html = f'<div class="alert-body">{body}</div>' if body else ""

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
    overflow: hidden;
  }}
  .alert-banner {{
    width: 720px;
    padding: 32px 40px;
    border-radius: 22px;
    background: {p['card_bg']};
    border: 2px solid {p['border']};
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.70), 0 0 35px {p['glow']}, inset 0 1px 0 rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: flex-start;
    gap: 22px;
  }}
  .alert-icon-box {{
    width: 54px;
    height: 54px;
    border-radius: 14px;
    background: {p['pill_bg']};
    border: 1.5px solid {p['border']};
    display: flex;
    align-items: center;
    justify-content: center;
    color: {p['accent']};
    font-size: 28px;
    flex-shrink: 0;
    box-shadow: 0 0 16px {p['glow']};
  }}
  .alert-content {{
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .alert-tag {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.18em;
    color: {p['accent']};
    text-transform: uppercase;
  }}
  .alert-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 34px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.15;
    letter-spacing: -0.5px;
  }}
  .alert-body {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 18px;
    font-weight: 500;
    color: {p['text_sub']};
    line-height: 1.35;
    margin-top: 4px;
  }}
</style>
</head>
<body>
  <div class="alert-banner">
    <div class="alert-icon-box">⚠️</div>
    <div class="alert-content">
      <div class="alert-tag">⚡ {tag}</div>
      <div class="alert-title">{clean_hl}</div>
      {body_html}
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 8. PLANTILLA: SOURCE CHIP (Pastilla de Fuente / Atribución)
    # =========================================================================
    def build_source_chip_html(
        self,
        source_name: str,
        tag: str = "FUENTE OFICIAL",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_src = (source_name or "Registro Internacional").strip()

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
    overflow: hidden;
  }}
  .source-chip {{
    display: inline-flex;
    align-items: center;
    gap: 14px;
    padding: 12px 28px;
    border-radius: 18px;
    background: {p['card_bg']};
    border: 1px solid {p['border']};
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55), 0 0 18px {p['glow']};
  }}
  .chip-tag {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.16em;
    color: {p['accent']};
    text-transform: uppercase;
    background: {p['pill_bg']};
    padding: 3px 10px;
    border-radius: 6px;
  }}
  .chip-title {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.2px;
  }}
  .chip-icon {{
    color: {p['accent']};
    font-size: 18px;
  }}
</style>
</head>
<body>
  <div class="source-chip">
    <span class="chip-icon">🛡️</span>
    <span class="chip-tag">{tag}</span>
    <span class="chip-title">{clean_src}</span>
  </div>
</body>
</html>"""

    # =========================================================================
    # 9. PLANTILLA: NEWSPAPER CLIPPING (Recorte de Prensa / Adrià Solà Pastor)
    # =========================================================================
    def build_newspaper_clipping_html(
        self,
        headline: str,
        newspaper: str = "FINANCIAL TIMES",
        date_str: str = "OCTUBRE 2026",
        highlight_text: str = "",
        body_lead: str = "",
        tag: str = "EVIDENCIA EDITORIAL",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_headline = (headline or "Titular de Investigación").strip()
        clean_news = (newspaper or "FINANCIAL TIMES").strip().upper()
        clean_body = (body_lead or "").strip()

        # Resaltado fluorescente auténtico estilo marcador sobre el texto clave
        if highlight_text and highlight_text in clean_headline:
            clean_headline = clean_headline.replace(
                highlight_text,
                f'<mark class="highlighter-marker">{highlight_text}</mark>',
            )
        elif highlight_text and clean_body and highlight_text in clean_body:
            clean_body = clean_body.replace(
                highlight_text,
                f'<mark class="highlighter-marker">{highlight_text}</mark>',
            )
        else:
            # Resaltar automáticamente la primera frase de impacto si no se especificó
            words = clean_headline.split()
            if len(words) >= 4:
                hl_target = " ".join(words[-3:])
                clean_headline = clean_headline.replace(
                    hl_target,
                    f'<mark class="highlighter-marker">{hl_target}</mark>',
                )

        body_html = f'<div class="paper-body">{clean_body}</div>' if clean_body else ""

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
    overflow: hidden;
  }}
  .clipping-card {{
    position: relative;
    width: 820px;
    background: #0d0f14;
    border: 1.5px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    padding: 34px 44px;
    box-shadow: 0 35px 80px rgba(0, 0, 0, 0.85), 0 0 40px rgba(255, 148, 54, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    display: flex;
    flex-direction: column;
    gap: 18px;
    transform: rotate(-1.2deg);
  }}
  .masthead-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 2px solid rgba(255, 255, 255, 0.22);
    padding-bottom: 12px;
  }}
  .masthead-logo {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 26px;
    font-weight: 900;
    letter-spacing: 0.18em;
    color: #ffffff;
    text-transform: uppercase;
  }}
  .masthead-meta {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .meta-tag {{
    background: {p['pill_bg']};
    border: 1px solid {p['border']};
    color: {p['accent']};
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.16em;
    padding: 3px 10px;
    border-radius: 6px;
    text-transform: uppercase;
  }}
  .meta-date {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #94a3b8;
    letter-spacing: 0.08em;
  }}
  .paper-headline {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 38px;
    line-height: 1.22;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.7);
  }}
  .highlighter-marker {{
    background: linear-gradient(104deg, rgba(255, 230, 0, 0) 0.5%, rgba(255, 235, 59, 0.92) 2.5%, rgba(255, 235, 59, 0.95) 92%, rgba(255, 230, 0, 0) 98%);
    color: #0b0c10;
    font-weight: 900;
    padding: 2px 10px;
    border-radius: 4px;
    box-shadow: 0 0 20px rgba(255, 235, 59, 0.65);
    display: inline;
    line-height: 1.35;
  }}
  .paper-body {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 18px;
    line-height: 1.55;
    color: #cbd5e1;
    border-left: 3px solid {p['accent']};
    padding-left: 16px;
    margin-top: 4px;
  }}
  .clipping-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 14px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 12px;
    color: #64748b;
    letter-spacing: 0.12em;
  }}
</style>
</head>
<body>
  <div class="clipping-card">
    <div class="masthead-bar">
      <div class="masthead-logo">{clean_news}</div>
      <div class="masthead-meta">
        <span class="meta-tag">{tag}</span>
        <span class="meta-date">{date_str}</span>
      </div>
    </div>
    <div class="paper-headline">{clean_headline}</div>
    {body_html}
    <div class="clipping-footer">
      <span>ARCHIVADO &bull; EDICIÓN VERIFICADA</span>
      <span style="color:{p['accent']}; font-weight:700;">AETHERCUT RESEARCH &bull; 2026</span>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 10. PLANTILLA: SOCIAL POST (Publicación Verificada X / Twitter)
    # =========================================================================
    def build_social_post_html(
        self,
        author_name: str,
        handle: str,
        post_text: str,
        highlight_phrase: str = "",
        verified: bool = True,
        metrics_likes: str = "128K",
        metrics_reposts: str = "24.2K",
        date_str: str = "Reciente",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_author = (author_name or "Declaración Oficial").strip()
        clean_handle = (handle or "@oficial").strip()
        clean_text = (post_text or "Declaración pública contrastada.").strip()
        initial = clean_author[0].upper() if clean_author else "A"

        if highlight_phrase and highlight_phrase in clean_text:
            clean_text = clean_text.replace(
                highlight_phrase,
                f'<span class="post-hl">{highlight_phrase}</span>',
            )

        verif_svg = """<svg class="v-badge" viewBox="0 0 24 24" width="20" height="20" fill="#1d9bf0"><path d="M22.25 12c0-1.43-.88-2.67-2.19-3.34.46-1.39.2-2.9-.81-3.91s-2.52-1.27-3.91-.81c-.67-1.31-1.91-2.19-3.34-2.19s-2.67.88-3.33 2.19c-1.4-.46-2.91-.2-3.92.81s-1.26 2.52-.8 3.91c-1.31.67-2.2 1.91-2.2 3.34s.89 2.67 2.2 3.34c-.46 1.39-.21 2.9.8 3.91s2.52 1.26 3.91.81c.67 1.31 1.91 2.19 3.34 2.19s2.67-.88 3.34-2.19c1.39.45 2.9.2 3.91-.81s1.27-2.52.81-3.91c1.31-.67 2.19-1.91 2.19-3.34zm-11.71 4.2L6.8 12.46l1.41-1.42 2.33 2.33 4.99-4.99 1.41 1.42-6.4 6.4z"/></svg>""" if verified else ""

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
    overflow: hidden;
  }}
  .social-card {{
    position: relative;
    width: 780px;
    background: rgba(13, 16, 22, 0.94);
    border: 1.5px solid rgba(255, 255, 255, 0.12);
    border-radius: 22px;
    padding: 32px 38px;
    box-shadow: 0 30px 75px rgba(0, 0, 0, 0.85), 0 0 35px rgba(29, 155, 240, 0.20);
    display: flex;
    flex-direction: column;
    gap: 18px;
  }}
  .author-row {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .avatar-circle {{
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: {p['accent_gradient']};
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Outfit', sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: #000000;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  }}
  .author-meta {{
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .name-row {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .author-name {{
    font-family: 'Outfit', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.3px;
  }}
  .author-handle {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 15px;
    color: #94a3b8;
  }}
  .post-body {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 24px;
    line-height: 1.45;
    color: #f1f5f9;
    letter-spacing: -0.2px;
  }}
  .post-hl {{
    color: {p['accent']};
    font-weight: 700;
    background: {p['pill_bg']};
    padding: 2px 8px;
    border-radius: 6px;
  }}
  .metrics-row {{
    display: flex;
    align-items: center;
    gap: 28px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 14px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 14px;
    color: #94a3b8;
  }}
  .metric-item {{
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .metric-bold {{
    color: #ffffff;
    font-weight: 700;
  }}
</style>
</head>
<body>
  <div class="social-card">
    <div class="author-row">
      <div class="avatar-circle">{initial}</div>
      <div class="author-meta">
        <div class="name-row">
          <span class="author-name">{clean_author}</span>
          {verif_svg}
        </div>
        <div class="author-handle">{clean_handle} &bull; {date_str}</div>
      </div>
    </div>
    <div class="post-body">{clean_text}</div>
    <div class="metrics-row">
      <div class="metric-item"><span class="metric-bold">{metrics_reposts}</span> Reposts</div>
      <div class="metric-item"><span class="metric-bold">{metrics_likes}</span> Me gusta</div>
      <div class="metric-item"><span class="metric-bold">Verificado</span> por AetherCut</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 11. PLANTILLA: TIMELINE MILESTONES (Hitos Cronológicos / Documental)
    # =========================================================================
    def build_timeline_milestone_html(
        self,
        milestones: Optional[List[Dict[str, str]]] = None,
        active_index: int = 1,
        title: str = "HITOS CLAVE",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        milestones = milestones or [
            {"year": "2008", "label": "Crisis Subprime"},
            {"year": "2015", "label": "Algoritmo Aladdin"},
            {"year": "2026", "label": "Dominio Global $10T"},
        ]

        nodes_html = []
        for idx, m in enumerate(milestones):
            is_active = (idx == active_index)
            cls_active = "active-node" if is_active else ""
            nodes_html.append(f"""
            <div class="t-node {cls_active}">
              <div class="t-circle"></div>
              <div class="t-year">{m.get('year', '')}</div>
              <div class="t-label">{m.get('label', '')}</div>
            </div>
            """)

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
    overflow: hidden;
  }}
  .timeline-card {{
    position: relative;
    width: 860px;
    background: #0d0f14;
    border: 1.5px solid rgba(255, 255, 255, 0.14);
    border-radius: 22px;
    padding: 34px 44px;
    box-shadow: 0 35px 80px rgba(0, 0, 0, 0.85), 0 0 40px rgba(255, 148, 54, 0.20);
    display: flex;
    flex-direction: column;
    gap: 28px;
  }}
  .timeline-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .timeline-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.20em;
    color: {p['accent']};
    text-transform: uppercase;
  }}
  .timeline-track {{
    position: relative;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 10px 0;
  }}
  .timeline-track::before {{
    content: '';
    position: absolute;
    top: 24px;
    left: 40px;
    right: 40px;
    height: 3px;
    background: rgba(255, 255, 255, 0.16);
    z-index: 1;
  }}
  .t-node {{
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 8px;
    width: 180px;
  }}
  .t-circle {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #141824;
    border: 3px solid #64748b;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.8);
    transition: all 0.3s ease;
  }}
  .active-node .t-circle {{
    background: {p['accent']};
    border-color: #ffffff;
    box-shadow: 0 0 25px {p['glow']}, 0 0 10px {p['accent']};
    transform: scale(1.3);
  }}
  .t-year {{
    font-family: 'Outfit', sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: #94a3b8;
  }}
  .active-node .t-year {{
    color: #ffffff;
  }}
  .t-label {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.35;
  }}
  .active-node .t-label {{
    color: {p['accent']};
    font-weight: 700;
  }}
</style>
</head>
<body>
  <div class="timeline-card">
    <div class="timeline-header">
      <div class="timeline-title">{title}</div>
      <div style="font-family:'JetBrains Mono'; font-size:12px; color:#64748b;">EVOLUCIÓN DOCUMENTADA</div>
    </div>
    <div class="timeline-track">
      {"".join(nodes_html)}
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 12. PLANTILLA: WORKFLOW DIAGRAM (Arquitectura Agéntica / Nodos / Santa IA)
    # =========================================================================
    def build_workflow_diagram_html(
        self,
        title: str = "THE ROUTER PATTERN",
        tag: str = "PATRÓN AGÉNTICO",
        input_label: str = "Consulta del Usuario",
        input_sub: str = "Prompt / Tarea entrante",
        router_label: str = "ROUTER CENTRAL",
        router_sub: str = "Clasificador Semántico LLM",
        routes: Optional[List[Dict[str, Any]]] = None,
        active_index: int = 1,
        note: str = "Aislamiento de contexto: solo el agente seleccionado consume tokens.",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        routes = routes or [
            {"name": "Agente Ventas", "desc": "Tarifas y compras", "badge": "DISPONIBLE"},
            {"name": "Agente Reclamos", "desc": "Políticas y devoluciones", "badge": "RUTA ACTIVA"},
            {"name": "Agente Operaciones", "desc": "Estado de vuelos y soporte", "badge": "DISPONIBLE"},
        ]

        routes_html = []
        for idx, r in enumerate(routes):
            is_active = (idx == active_index)
            r_name = r.get("name", f"Especialista {idx+1}")
            r_desc = r.get("desc", "")
            r_badge = "RUTA SELECCIONADA" if is_active else r.get("badge", "DISPONIBLE")
            cls = "route-card active-route" if is_active else "route-card"
            badge_icon = "● DISPATCHED" if is_active else "○ STANDBY"
            routes_html.append(f"""
            <div class="{cls}">
              <div class="route-top">
                <span class="route-badge">{r_badge}</span>
                <span class="route-status">{badge_icon}</span>
              </div>
              <div class="route-title">{r_name}</div>
              <div class="route-desc">{r_desc}</div>
              {f'<div class="route-metric"><span>TOKEN CONTEXT: ISOLATED</span><span>MATCH: 99.4%</span></div>' if is_active else ''}
            </div>
            """)

        # Calcular coordenadas para los cables SVG según índice activo
        branch_y_targets = [48, 150, 252]
        active_y = branch_y_targets[active_index] if active_index < len(branch_y_targets) else 150

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
    overflow: hidden;
  }}
  .diagram-container {{
    position: relative;
    width: 980px;
    background: #07090e;
    background-image: radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px);
    background-size: 24px 24px;
    border: 1.5px solid rgba(255, 255, 255, 0.12);
    border-radius: 24px;
    padding: 30px 40px;
    box-shadow: 0 45px 100px rgba(0, 0, 0, 0.92), inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 0 50px {p['glow']};
    display: flex;
    flex-direction: column;
    gap: 22px;
  }}
  .diagram-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 14px;
  }}
  .header-left {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .tag-pill {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.18em;
    color: {p['accent']};
    background: rgba(255, 148, 54, 0.12);
    border: 1px solid {p['accent']};
    padding: 4px 12px;
    border-radius: 8px;
    text-transform: uppercase;
    box-shadow: 0 0 12px {p['glow']};
  }}
  .diagram-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.02em;
    background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .header-note {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #64748b;
    display: flex;
    align-items: center;
    gap: 6px;
    letter-spacing: 0.08em;
  }}
  .live-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
  }}
  .flow-canvas {{
    position: relative;
    width: 100%;
    height: 300px;
    display: flex;
    align-items: center;
  }}
  .flow-wires {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
  }}
  .input-node {{
    position: absolute;
    left: 0;
    top: 75px;
    width: 210px;
    height: 150px;
    background: rgba(15, 18, 28, 0.85);
    backdrop-filter: blur(16px);
    border: 1.5px solid rgba(255, 255, 255, 0.12);
    border-radius: 18px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.10);
    z-index: 2;
  }}
  .node-mini-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9.5px;
    font-weight: 700;
    color: #94a3b8;
    letter-spacing: 0.12em;
    display: flex;
    align-items: center;
    gap: 5px;
  }}
  .input-node-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.25;
  }}
  .input-node-sub {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 11.5px;
    color: #64748b;
  }}
  .node-footer-spec {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.08);
    padding: 3px 6px;
    border-radius: 5px;
    border: 1px solid rgba(56, 189, 248, 0.20);
    display: inline-block;
  }}
  .router-node {{
    position: absolute;
    left: 310px;
    top: 60px;
    width: 220px;
    height: 180px;
    background: linear-gradient(145deg, #161b28, #0c1018);
    border: 2px solid {p['accent']};
    border-radius: 20px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    text-align: center;
    box-shadow: 0 0 45px {p['glow']}, 0 20px 40px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255, 255, 255, 0.2);
    z-index: 2;
  }}
  .router-icon-wrap {{
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: rgba(255, 148, 54, 0.16);
    border: 1px solid {p['accent']};
    color: {p['accent']};
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 900;
    box-shadow: 0 0 18px {p['glow']};
  }}
  .router-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 14.5px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }}
  .router-sub {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 11px;
    color: #94a3b8;
  }}
  .router-badge-spec {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    color: {p['accent']};
    background: rgba(255, 148, 54, 0.10);
    border: 1px solid rgba(255, 148, 54, 0.30);
    padding: 3px 8px;
    border-radius: 6px;
    letter-spacing: 0.05em;
  }}
  .branches-column {{
    position: absolute;
    right: 0;
    top: 5px;
    width: 270px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    z-index: 2;
  }}
  .route-card {{
    background: rgba(18, 22, 34, 0.65);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 14px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    opacity: 0.45;
    transition: all 0.3s ease;
  }}
  .active-route {{
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.18), rgba(6, 78, 59, 0.30));
    border: 1.8px solid #10b981;
    box-shadow: 0 0 30px rgba(16, 185, 129, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.2);
    opacity: 1.0;
    transform: scale(1.02);
  }}
  .route-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .route-badge {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.14em;
    color: #64748b;
  }}
  .active-route .route-badge {{
    color: #10b981;
  }}
  .route-status {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    font-weight: 700;
    color: #64748b;
  }}
  .active-route .route-status {{
    color: #10b981;
    text-shadow: 0 0 8px #10b981;
  }}
  .route-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 14.5px;
    font-weight: 700;
    color: #ffffff;
  }}
  .route-desc {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 11px;
    color: #94a3b8;
  }}
  .route-metric {{
    margin-top: 2px;
    padding-top: 4px;
    border-top: 1px solid rgba(16, 185, 129, 0.25);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: 8.5px;
    color: #34d399;
    font-weight: 700;
  }}
  .diagram-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255, 255, 255, 0.02);
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 12px;
  }}
  .footer-note {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12.5px;
    color: #cbd5e1;
  }}
  .footer-note strong {{
    color: {p['accent']};
  }}
  .footer-logo {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 10.5px;
    color: #475569;
    letter-spacing: 0.16em;
  }}
</style>
</head>
<body>
  <div class="diagram-container">
    <div class="diagram-header">
      <div class="header-left">
        <span class="tag-pill">{tag}</span>
        <span class="diagram-title">{title}</span>
      </div>
      <div class="header-note">
        <span class="live-dot"></span>
        <span>BLUEPRINT AGÉNTICO // ACTIVO</span>
      </div>
    </div>
    <div class="flow-canvas">
      <!-- CABLES VECTORIALES SVG CURVOS CON BRILLO NEÓN -->
      <svg class="flow-wires" viewBox="0 0 900 300" fill="none">
        <defs>
          <linearGradient id="wireInputGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{p['accent']}" stop-opacity="0.4" />
            <stop offset="100%" stop-color="{p['accent']}" stop-opacity="1.0" />
          </linearGradient>
          <linearGradient id="activeWireGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{p['accent']}" />
            <stop offset="100%" stop-color="#10b981" />
          </linearGradient>
          <filter id="glowGreen" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        <!-- Cable 1: Ingestion -> Router -->
        <path d="M 210 150 C 260 150, 260 150, 310 150" stroke="url(#wireInputGrad)" stroke-width="2.5" />
        <circle cx="210" cy="150" r="4.5" fill="{p['accent']}" />
        <circle cx="310" cy="150" r="4.5" fill="{p['accent']}" />

        <!-- Micro-píldora sobre cable 1 -->
        <rect x="236" y="141" width="48" height="18" rx="4" fill="#0b0e17" stroke="{p['accent']}" stroke-width="1" />
        <text x="260" y="153" fill="{p['accent']}" font-size="8.5" font-family="'JetBrains Mono'" text-anchor="middle" font-weight="bold">INPUT</text>

        <!-- Cables Router -> Agentes -->
        <!-- Rama 0 (Y=48) -->
        <path d="M 530 150 C 575 150, 585 48, 630 48"
              stroke="{'#10b981' if active_index == 0 else 'rgba(255,255,255,0.14)'}"
              stroke-width="{'3' if active_index == 0 else '1.5'}"
              stroke-dasharray="{'none' if active_index == 0 else '4 4'}"
              filter="{'url(#glowGreen)' if active_index == 0 else 'none'}" />

        <!-- Rama 1 (Y=150) -->
        <path d="M 530 150 C 575 150, 585 150, 630 150"
              stroke="{'#10b981' if active_index == 1 else 'rgba(255,255,255,0.14)'}"
              stroke-width="{'3' if active_index == 1 else '1.5'}"
              stroke-dasharray="{'none' if active_index == 1 else '4 4'}"
              filter="{'url(#glowGreen)' if active_index == 1 else 'none'}" />

        <!-- Rama 2 (Y=252) -->
        <path d="M 530 150 C 575 150, 585 252, 630 252"
              stroke="{'#10b981' if active_index == 2 else 'rgba(255,255,255,0.14)'}"
              stroke-width="{'3' if active_index == 2 else '1.5'}"
              stroke-dasharray="{'none' if active_index == 2 else '4 4'}"
              filter="{'url(#glowGreen)' if active_index == 2 else 'none'}" />

        <!-- Puerto origen del router -->
        <circle cx="530" cy="150" r="5" fill="#10b981" />

        <!-- Puertos destino en tarjetas de agentes -->
        <circle cx="630" cy="48" r="{'5' if active_index == 0 else '3.5'}" fill="{'#10b981' if active_index == 0 else '#64748b'}" />
        <circle cx="630" cy="150" r="{'5' if active_index == 1 else '3.5'}" fill="{'#10b981' if active_index == 1 else '#64748b'}" />
        <circle cx="630" cy="252" r="{'5' if active_index == 2 else '3.5'}" fill="{'#10b981' if active_index == 2 else '#64748b'}" />

        <!-- Píldora de MATCH activa en el cable seleccionado -->
        <rect x="562" y="{active_y - 9}" width="50" height="18" rx="4" fill="#07281d" stroke="#10b981" stroke-width="1.2" />
        <text x="587" y="{active_y + 3}" fill="#10b981" font-size="8.5" font-family="'JetBrains Mono'" text-anchor="middle" font-weight="bold">MATCH</text>
      </svg>

      <!-- Nodo Entrada -->
      <div class="input-node">
        <div class="node-mini-tag"><span>01</span> ENTRADA USUARIO</div>
        <div>
          <div class="input-node-title">{input_label}</div>
          <div class="input-node-sub">{input_sub}</div>
        </div>
        <div class="node-footer-spec">payload: prompt_stream</div>
      </div>

      <!-- Nodo Router Central -->
      <div class="router-node">
        <div class="router-icon-wrap">🔀</div>
        <div>
          <div class="router-title">{router_label}</div>
          <div class="router-sub">{router_sub}</div>
        </div>
        <div class="router-badge-spec">EMBEDDINGS 1536-D</div>
      </div>

      <!-- Columna de Especialistas -->
      <div class="branches-column">
        {"".join(routes_html)}
      </div>
    </div>
    <div class="diagram-footer">
      <div class="footer-note"><strong>Principio Clave:</strong> {note}</div>
      <div class="footer-logo">AETHERCUT ARCHITECTURE // AGENTIC LABS</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 13. PLANTILLA: TERMINAL HUD / CODE CONSOLE (Claude Code / Dev / Santa IA)
    # =========================================================================
    def build_terminal_hud_html(
        self,
        window_title: str = "claude-code — ~/projects/router-pattern",
        command: str = "claude-code --pattern router --agent claims",
        output_lines: Optional[List[str]] = None,
        tag: str = "CLI RUNTIME",
        status_info: str = "Python 3.11 · Sonnet 3.7 · Context: Isolated",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        output_lines = output_lines or [
            '<span class="t-cyan">[01/03] [INTENT]</span> Query: "Necesito tramitar el reembolso de mi vuelo"',
            '<span class="t-green">[02/03] [MATCH]</span> Target identified: Agent_RefundClaims (Confidence: 99.4%)',
            '<span class="t-amber">[03/03] [DISPATCH]</span> Context injection: airline_policy_v2.json (1,240 tokens)',
            '<span class="t-white">[EXEC]</span> Multi-step synthesis delivered in 340ms (88 tok/s)',
            '<span class="t-verified">✔ TAREA COMPLETADA · CERO ALUCINACIONES VERIFICADO</span>'
        ]

        formatted_lines = []
        for line in output_lines:
            if "✔" in line or "COMPLETADA" in line:
                formatted_lines.append(f'<div class="log-row success-box">{line}</div>')
            else:
                formatted_lines.append(f'<div class="log-row"><span class="line-pipe">│</span> {line}</div>')

        body_html = "".join(formatted_lines)

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
    overflow: hidden;
  }}
  .terminal-window {{
    position: relative;
    width: 940px;
    background: #080a0f;
    border: 1.5px solid rgba(255, 255, 255, 0.14);
    border-radius: 20px;
    box-shadow: 0 45px 100px rgba(0, 0, 0, 0.94), 0 0 50px rgba(0, 245, 160, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }}
  .terminal-topbar {{
    background: #0e1118;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 12px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .window-controls {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.45), inset 0 -1px 1px rgba(0, 0, 0, 0.35);
  }}
  .dot-red {{ background: #ff5f56; }}
  .dot-yellow {{ background: #ffbd2e; }}
  .dot-green {{ background: #27c93f; }}
  .tabs-group {{
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: 12px;
  }}
  .tab {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
    color: #64748b;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
  }}
  .active-tab {{
    color: #f1f5f9;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.14);
    font-weight: 600;
  }}
  .top-right-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .git-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    color: #a855f7;
    background: rgba(168, 85, 247, 0.10);
    border: 1px solid rgba(168, 85, 247, 0.25);
    padding: 3px 8px;
    border-radius: 6px;
  }}
  .top-tag {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 10px;
    font-weight: 800;
    color: {p['accent']};
    background: rgba(255, 148, 54, 0.12);
    border: 1px solid rgba(255, 148, 54, 0.35);
    padding: 3px 10px;
    border-radius: 6px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }}
  .terminal-body {{
    padding: 24px 28px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13.5px;
    line-height: 1.75;
    color: #e2e8f0;
    background: #080a0f;
  }}
  .prompt-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-weight: 600;
  }}
  .prompt-path {{
    color: #38bdf8;
  }}
  .prompt-symbol {{
    color: #10b981;
    font-weight: 800;
  }}
  .prompt-cmd {{
    color: #ffffff;
    font-weight: 700;
  }}
  .cursor {{
    display: inline-block;
    width: 8px;
    height: 16px;
    background: #10b981;
    margin-left: 4px;
    vertical-align: middle;
    animation: blink 1s infinite;
    box-shadow: 0 0 8px #10b981;
  }}
  @keyframes blink {{
    0%, 49% {{ opacity: 1; }}
    50%, 100% {{ opacity: 0; }}
  }}
  .log-tree {{
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }}
  .log-row {{
    display: flex;
    align-items: baseline;
    gap: 6px;
    color: #cbd5e1;
  }}
  .line-pipe {{
    color: #334155;
    font-weight: 700;
  }}
  .success-box {{
    margin-top: 10px;
    padding: 8px 14px;
    background: rgba(16, 185, 129, 0.10);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 8px;
    color: #10b981;
    font-weight: 700;
    letter-spacing: 0.04em;
    box-shadow: 0 0 15px rgba(16, 185, 129, 0.15);
  }}
  .t-cyan {{ color: #38bdf8; font-weight: 700; }}
  .t-green {{ color: #34d399; font-weight: 700; }}
  .t-amber {{ color: #fbbf24; font-weight: 700; }}
  .t-white {{ color: #f8fafc; font-weight: 600; }}
  .t-verified {{ color: #10b981; font-weight: 700; }}
  .terminal-statusbar {{
    background: #0b0d14;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding: 8px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #64748b;
  }}
  .status-left {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .status-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
  }}
  .status-right {{
    color: #10b981;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
</style>
</head>
<body>
  <div class="terminal-window">
    <div class="terminal-topbar">
      <div style="display: flex; align-items: center;">
        <div class="window-controls">
          <div class="dot dot-red"></div>
          <div class="dot dot-yellow"></div>
          <div class="dot dot-green"></div>
        </div>
        <div class="tabs-group">
          <div class="tab active-tab">📄 router_agent.py ×</div>
          <div class="tab">⚙️ settings.env</div>
          <div class="tab">📊 telemetry.json</div>
        </div>
      </div>
      <div class="top-right-meta">
        <span class="git-badge">git:(main ⚡)</span>
        <span class="top-tag">{tag}</span>
      </div>
    </div>
    <div class="terminal-body">
      <div class="prompt-row">
        <span class="prompt-path">~/aethercut/agents</span>
        <span class="prompt-symbol">❯</span>
        <span class="prompt-cmd">{command}</span>
        <span class="cursor"></span>
      </div>
      <div class="log-tree">
        {body_html}
      </div>
    </div>
    <div class="terminal-statusbar">
      <div class="status-left">
        <span class="status-dot"></span>
        <span>STREAMING 88 tok/s · CONTEXTO: 1.2k / 200k (0.6%)</span>
      </div>
      <div>UTF-8 · Python 3.11</div>
      <div class="status-right">
        <span>🔒 CERO ALUCINACIÓN VERIFICADO</span>
      </div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 13B. PLANTILLA: SPEC MATRIX / BENCHMARK COMPARATIVO (Santa IA / Tech)
    # =========================================================================
    def build_spec_matrix_html(
        self,
        title: str = "MONOLÍTICO vs ROUTER PATTERN",
        tag: str = "BENCHMARK DE ARQUITECTURA",
        subtitle: str = "Métricas reales medidas en producción bajo carga continua",
        col_a_name: str = "Agente Monolítico",
        col_b_name: str = "The Router Pattern",
        rows: Optional[List[Dict[str, Any]]] = None,
        winner_col: str = "b",
        footer_note: str = "Validado en producción con +100k consultas y evaluación continua.",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        rows = rows or [
            {"metric": "Latencia de Respuesta", "val_a": "2,450 ms", "val_b": "320 ms", "delta": "-87% ⚡", "winner": "b"},
            {"metric": "Consumo de Tokens", "val_a": "8,200 tok/req", "val_b": "1,150 tok/req", "delta": "-86% ⚡", "winner": "b"},
            {"metric": "Tasa de Alucinación", "val_a": "14.2% (Riesgo)", "val_b": "0.1% (Verificado)", "delta": "Resuelto ✓", "winner": "b"},
            {"metric": "Aislamiento de Contexto", "val_a": "✕ Mega-prompt único", "val_b": "✓ 100% Desacoplado", "delta": "Modular ✓", "winner": "b"},
            {"metric": "Escalabilidad", "val_a": "Cuello de botella", "val_b": "N Agentes Paralelos", "delta": "Ilimitada", "winner": "b"},
        ]

        table_rows_html = []
        for r in rows:
            m = r.get("metric", "")
            va = r.get("val_a", "")
            vb = r.get("val_b", "")
            delta = r.get("delta", "")
            is_b_winner = (r.get("winner", winner_col) == "b")

            table_rows_html.append(f"""
            <tr class="matrix-row">
              <td class="col-metric">{m}</td>
              <td class="col-val-a">{va}</td>
              <td class="col-val-b {'cell-winner' if is_b_winner else ''}">
                <div class="winner-val-wrap">
                  <span class="main-val">{vb}</span>
                  {f'<span class="delta-badge">{delta}</span>' if delta else ''}
                </div>
              </td>
            </tr>
            """)

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
    overflow: hidden;
  }}
  .matrix-card {{
    position: relative;
    width: 960px;
    background: #07090e;
    background-image: radial-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px);
    background-size: 24px 24px;
    border: 1.5px solid rgba(255, 255, 255, 0.12);
    border-radius: 24px;
    padding: 32px 42px;
    box-shadow: 0 45px 100px rgba(0, 0, 0, 0.94), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    display: flex;
    flex-direction: column;
    gap: 22px;
  }}
  .matrix-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 14px;
  }}
  .header-left {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .tag-pill {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.18em;
    color: {p['accent']};
    background: rgba(255, 148, 54, 0.12);
    border: 1px solid {p['accent']};
    padding: 4px 12px;
    border-radius: 8px;
    text-transform: uppercase;
  }}
  .matrix-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.02em;
  }}
  .matrix-sub {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12px;
    color: #94a3b8;
  }}
  .matrix-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 8px;
  }}
  .matrix-table th {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11.5px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #64748b;
    padding: 10px 18px;
    text-align: left;
  }}
  .th-winner {{
    color: #10b981 !important;
    background: rgba(16, 185, 129, 0.08);
    border-radius: 10px 10px 0 0;
  }}
  .matrix-row {{
    background: rgba(18, 22, 34, 0.60);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.07);
    transition: all 0.2s ease;
  }}
  .matrix-row td {{
    padding: 14px 18px;
  }}
  .matrix-row td:first-child {{
    border-radius: 12px 0 0 12px;
  }}
  .matrix-row td:last-child {{
    border-radius: 0 12px 12px 0;
  }}
  .col-metric {{
    font-family: 'Outfit', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #f1f5f9;
  }}
  .col-val-a {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13.5px;
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.015);
  }}
  .col-val-b {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    color: #ffffff;
  }}
  .cell-winner {{
    background: rgba(16, 185, 129, 0.12) !important;
    border-left: 2px solid #10b981;
  }}
  .winner-val-wrap {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .main-val {{
    font-weight: 700;
    color: #10b981;
  }}
  .delta-badge {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 10.5px;
    font-weight: 800;
    color: #34d399;
    background: rgba(16, 185, 129, 0.20);
    border: 1px solid rgba(16, 185, 129, 0.40);
    padding: 3px 8px;
    border-radius: 6px;
    letter-spacing: 0.06em;
  }}
  .matrix-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255, 255, 255, 0.02);
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 12px;
  }}
  .footer-note {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12px;
    color: #cbd5e1;
  }}
  .footer-logo {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 10.5px;
    color: #475569;
    letter-spacing: 0.16em;
  }}
</style>
</head>
<body>
  <div class="matrix-card">
    <div class="matrix-header">
      <div class="header-left">
        <span class="tag-pill">{tag}</span>
        <div>
          <div class="matrix-title">{title}</div>
          <div class="matrix-sub">{subtitle}</div>
        </div>
      </div>
      <div style="font-family:'JetBrains Mono'; font-size:11px; color:#10b981; font-weight:700;">
        ⚡ 8.4x MÁS EFICIENTE
      </div>
    </div>
    <table class="matrix-table">
      <thead>
        <tr>
          <th style="width: 38%;">PARÁMETRO CLAVE</th>
          <th style="width: 31%;">{col_a_name}</th>
          <th style="width: 31%;" class="th-winner">{col_b_name} ★</th>
        </tr>
      </thead>
      <tbody>
        {"".join(table_rows_html)}
      </tbody>
    </table>
    <div class="matrix-footer">
      <div class="footer-note"><strong>Evidencia Documentada:</strong> {footer_note}</div>
      <div class="footer-logo">AETHERCUT BENCHMARK LABS // 2026</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 14. PLANTILLA: EDITORIAL RETENTION HEADER (Gamificación de Pasos + Handle)
    # =========================================================================
    def build_editorial_retention_header_html(
        self,
        step_number: str = "03",
        total_steps: str = "10",
        step_prefix: str = "PASO",
        code_comment: str = "cómo abrirlo",
        handle: str = "@antonspain_ia",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)
        clean_num = str(step_number or "01").zfill(2) if str(step_number).isdigit() and len(str(step_number)) < 2 else str(step_number or "01")
        clean_total = str(total_steps or "10")
        clean_prefix = (step_prefix or "PASO").upper().strip()
        comment_text = f"// {clean_num} — {code_comment}" if code_comment and not code_comment.startswith("//") else (code_comment or f"// {clean_num}")
        handle_text = handle if handle.startswith("@") else f"@{handle}" if handle else "@aethercut"

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .retention-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 980px;
    padding: 12px 18px;
  }}
  .step-cluster {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .code-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 19px;
    font-weight: 700;
    color: {p['text_sub']};
    letter-spacing: -0.3px;
  }}
  .step-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'Inter', sans-serif;
    font-size: 22px;
    font-weight: 900;
    color: {p['accent']};
    letter-spacing: 0.8px;
    text-transform: uppercase;
  }}
  .creator-pill {{
    display: inline-flex;
    align-items: center;
    gap: 12px;
    padding: 10px 22px;
    border-radius: 9999px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
  }}
  .creator-icon {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: {p['accent_gradient']};
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-size: 14px;
    font-weight: 800;
  }}
  .creator-handle {{
    font-family: 'Inter', sans-serif;
    font-size: 19px;
    font-weight: 700;
    color: {p['text']};
    letter-spacing: -0.3px;
  }}
</style>
</head>
<body>
  <div class="retention-bar">
    <div class="step-cluster">
      <div class="code-tag">{comment_text}</div>
      <div class="step-badge">{clean_prefix} {clean_num}/{clean_total}</div>
    </div>
    <div class="creator-pill">
      <div class="creator-icon">✦</div>
      <div class="creator-handle">{handle_text}</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 15. PLANTILLA: EDITORIAL DUAL TITLE (Bold Sans + Italic Serif Accent)
    # =========================================================================
    def build_editorial_dual_title_html(
        self,
        main_text: str = "Pulsas + y eliges",
        accent_text: str = "Tesseract",
        subtitle: str = "",
        variant: str = "editorial_cream",
        align: str = "center",
    ) -> str:
        p = self.get_palette(variant)
        clean_main = (main_text or "").strip()
        clean_accent = (accent_text or "").strip()
        sub_html = f'<div class="title-sub">{subtitle.strip()}</div>' if subtitle else ""

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .title-wrap {{
    display: flex;
    flex-direction: column;
    align-items: {'center' if align == 'center' else 'flex-start'};
    text-align: {align};
    gap: 8px;
    max-width: 980px;
  }}
  .headline-row {{
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: {'center' if align == 'center' else 'flex-start'};
    gap: 14px;
    line-height: 1.15;
  }}
  .main-text {{
    font-family: 'Inter', sans-serif;
    font-size: 58px;
    font-weight: 900;
    letter-spacing: -1.5px;
    color: {p['text']};
  }}
  .accent-text {{
    font-family: 'Playfair Display', serif;
    font-style: italic;
    font-size: 64px;
    font-weight: 700;
    color: {p['accent']};
    letter-spacing: -0.5px;
  }}
  .title-sub {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 22px;
    font-weight: 600;
    color: {p['text_sub']};
    margin-top: 4px;
  }}
</style>
</head>
<body>
  <div class="title-wrap">
    <div class="headline-row">
      <span class="main-text">{clean_main}</span>
      <span class="accent-text">{clean_accent}</span>
    </div>
    {sub_html}
  </div>
</body>
</html>"""

    # =========================================================================
    # 16. PLANTILLA: EDITORIAL SOFTWARE WINDOW (Mockup macOS / App Flotante)
    # =========================================================================
    def build_editorial_software_window_html(
        self,
        window_title: str = "ChatGPT",
        window_type: str = "chat_input",
        highlight_button: str = "+",
        placeholder_text: str = "Pregunta lo que quieras...",
        body_text: str = "",
        tag: str = "INTERFAZ",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)
        clean_title = (window_title or "ChatGPT").strip()
        clean_placeholder = (placeholder_text or "Pregunta lo que quieras...").strip()
        btn = highlight_button or "+"

        if window_type == "chat_input":
            inner_html = f"""
            <div class="chat-canvas">
              <div class="chat-empty-space"></div>
              <div class="input-bar-container">
                <div class="action-btn-highlight">{btn}</div>
                <div class="input-placeholder">{clean_placeholder}</div>
                <div class="input-end-icons">
                  <div class="mic-circle">🎙</div>
                </div>
              </div>
            </div>
            """
        else:
            inner_html = f"""
            <div class="custom-card-body">
              <div class="body-content">{body_text or clean_placeholder}</div>
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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .macos-window {{
    width: 820px;
    border-radius: 22px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 70px rgba(0, 0, 0, 0.14), 0 2px 8px rgba(0, 0, 0, 0.04);
    overflow: hidden;
  }}
  .window-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 22px;
    border-bottom: 1px solid {p['border']};
    background: {p['card_bg']};
  }}
  .traffic-lights {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .dot {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
  }}
  .dot-red {{ background: #FF5F56; }}
  .dot-yellow {{ background: #FFBD2E; }}
  .dot-green {{ background: #27C93F; }}
  .win-title {{
    font-family: 'Inter', sans-serif;
    font-size: 17px;
    font-weight: 700;
    color: {p['text_sub']};
  }}
  .win-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    color: {p['accent']};
  }}
  .chat-canvas {{
    padding: 28px;
    min-height: 260px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
  }}
  .input-bar-container {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 20px;
    border-radius: 9999px;
    background: {p['bg']};
    border: 1.5px solid {p['border']};
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.03);
  }}
  .action-btn-highlight {{
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: {p['accent_gradient']};
    box-shadow: 0 4px 14px {p['glow']};
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-size: 26px;
    font-weight: 900;
  }}
  .input-placeholder {{
    flex: 1;
    font-family: 'Inter', sans-serif;
    font-size: 20px;
    color: {p['text_sub']};
  }}
  .mic-circle {{
    font-size: 20px;
    opacity: 0.6;
  }}
  .custom-card-body {{
    padding: 32px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 22px;
    line-height: 1.5;
    color: {p['text']};
  }}
</style>
</head>
<body>
  <div class="macos-window">
    <div class="window-topbar">
      <div class="traffic-lights">
        <div class="dot dot-red"></div>
        <div class="dot dot-yellow"></div>
        <div class="dot dot-green"></div>
      </div>
      <div class="win-title">{clean_title}</div>
      <div class="win-tag">{tag}</div>
    </div>
    {inner_html}
  </div>
</body>
</html>"""


    # =========================================================================
    # 17. PLANTILLA: EDITORIAL CODE TERMINAL (Código & Prompting Pro)
    # =========================================================================
    def build_editorial_code_terminal_html(
        self,
        filename: str = "main.py",
        command: str = "python run_studio.py --local",
        tag: str = "TERMINAL PRO",
        status_info: str = "200 OK (28ms) · 0 Tokens desperdiciados",
        status_badge: str = "LOCAL ACTIVE",
        variant: str = "editorial_cream",
        code_lines: list = None,
    ) -> str:
        p = self.get_palette(variant)
        lines = code_lines or [
            '<span class="kwd">import</span> { Agent, Pipeline } <span class="kwd">from</span> <span class="str">"aethercut"</span>',
            '<span class="kwd">const</span> engine = <span class="kwd">new</span> <span class="fn">Pipeline</span>({ model: <span class="str">"local"</span> })',
            '<span class="kwd">const</span> video = <span class="kwd">await</span> engine.<span class="fn">assemble</span>({ hook: <span class="str">"2s"</span> })',
            '<span class="fn">console</span>.<span class="fn">log</span>(<span class="str">`✓ Renderizado exitoso: ${video.path}`</span>)',
        ]
        formatted_lines = ""
        for i, l in enumerate(lines, 1):
            is_active = (i == 3)
            active_cls = " line-active" if is_active else ""
            formatted_lines += f'<div class="code-line{active_cls}"><span class="line-num">{str(i).zfill(2)}</span><span class="line-code">{l}</span></div>'

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .code-window {{
    width: 900px;
    border-radius: 22px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 70px rgba(0, 0, 0, 0.14), 0 2px 8px rgba(0, 0, 0, 0.04);
    overflow: hidden;
  }}
  .win-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 22px;
    border-bottom: 1px solid {p['border']};
    background: {p['card_bg']};
  }}
  .controls-tab {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .traffic-dots {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .tdot {{ width: 14px; height: 14px; border-radius: 50%; }}
  .tdot-red {{ background: #FF5F56; }}
  .tdot-yellow {{ background: #FFBD2E; }}
  .tdot-green {{ background: #27C93F; }}
  .file-tab {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 8px;
    background: {p['bg']};
    border: 1px solid {p['border']};
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    font-weight: 700;
    color: {p['text']};
  }}
  .win-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    color: {p['accent']};
    letter-spacing: 0.5px;
  }}
  .code-body {{
    padding: 24px 28px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px;
    line-height: 1.8;
  }}
  .code-line {{
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 3px 8px;
    border-radius: 6px;
  }}
  .line-active {{
    background: {p['pill_bg']};
    border-left: 3px solid {p['accent']};
  }}
  .line-num {{
    color: {p['text_sub']};
    opacity: 0.6;
    user-select: none;
    font-size: 15px;
    width: 24px;
  }}
  .line-code {{
    color: {p['text']};
  }}
  .kwd {{ color: {p['accent']}; font-weight: 700; }}
  .str {{ color: #10b981; }}
  .fn {{ color: #0284c7; font-weight: 600; }}
  .statusbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 22px;
    border-top: 1px solid {p['border']};
    background: {p['bg']};
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: {p['text_sub']};
  }}
  .status-badge {{
    color: #10b981;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
</style>
</head>
<body>
  <div class="code-window">
    <div class="win-topbar">
      <div class="controls-tab">
        <div class="traffic-dots">
          <div class="tdot tdot-red"></div>
          <div class="tdot tdot-yellow"></div>
          <div class="tdot tdot-green"></div>
        </div>
        <div class="file-tab">📄 {filename}</div>
      </div>
      <div class="win-tag">{tag}</div>
    </div>
    <div class="code-body">
      {formatted_lines}
    </div>
    <div class="statusbar">
      <div>✓ {status_info}</div>
      <div class="status-badge">● {status_badge}</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 18. PLANTILLA: EDITORIAL VERSUS FIX (Antes vs Después / Error vs Pro)
    # =========================================================================
    def build_editorial_versus_fix_html(
        self,
        bad_label: str = "ERROR COMÚN (MÉTODO ANTIGUO)",
        bad_text: str = 'Prompt genérico: "Hazme un video viral de 30 segundos sobre IA"',
        bad_stat: str = "⏱ 4 horas perdidas · 📉 12% Retención",
        good_label: str = "FÓRMULA OPTIMIZADA (KAI DIRECTOR)",
        good_text: str = 'Arquitectura por roles: "Hook 2s Zeigarnik + Micro-zooms + B-Roll"',
        good_stat: str = "⚡ 12 Segundos · 🚀 88% Retención · 0€",
        tag: str = "COMPARATIVA DE RETENCIÓN",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .versus-wrap {{
    width: 900px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}
  .v-card {{
    border-radius: 20px;
    padding: 22px 28px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .card-bad {{
    background: rgba(239, 68, 68, 0.05);
    border: 1.5px solid rgba(239, 68, 68, 0.25);
  }}
  .card-good {{
    background: {p['card_bg']};
    border: 2px solid {p['accent']};
    box-shadow: 0 16px 45px rgba(0, 0, 0, 0.10), 0 0 20px {p['glow']};
  }}
  .v-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .pill-bad {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    color: #ef4444;
    text-transform: uppercase;
  }}
  .pill-good {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    color: {p['accent']};
    text-transform: uppercase;
  }}
  .v-stat {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 14px;
    font-weight: 700;
    color: {p['text_sub']};
  }}
  .stat-good-color {{
    color: #10b981;
  }}
  .v-text {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 21px;
    font-weight: 700;
    line-height: 1.35;
  }}
  .text-bad {{
    color: {p['text_sub']};
    text-decoration: line-through;
    opacity: 0.8;
  }}
  .text-good {{
    color: {p['text']};
  }}
  .vs-divider {{
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    height: 14px;
  }}
  .vs-badge {{
    background: {p['accent_gradient']};
    color: #ffffff;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 900;
    padding: 3px 14px;
    border-radius: 9999px;
    box-shadow: 0 4px 12px {p['glow']};
  }}
</style>
</head>
<body>
  <div class="versus-wrap">
    <div class="v-card card-bad">
      <div class="v-header">
        <div class="pill-bad">✕ {bad_label}</div>
        <div class="v-stat">{bad_stat}</div>
      </div>
      <div class="v-text text-bad">{bad_text}</div>
    </div>

    <div class="vs-divider">
      <div class="vs-badge">VS</div>
    </div>

    <div class="v-card card-good">
      <div class="v-header">
        <div class="pill-good">✓ {good_label}</div>
        <div class="v-stat stat-good-color">{good_stat}</div>
      </div>
      <div class="v-text text-good">{good_text}</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 19. PLANTILLA: EDITORIAL WORKFLOW PIPELINE (Diagrama de Pasos Conectados)
    # =========================================================================
    def build_editorial_workflow_pipeline_html(
        self,
        title: str = "PIPELINE AUTOMATIZADO 2026",
        tag: str = "ARQUITECTURA LOCAL",
        node1_title: str = "Prompt / Idea",
        node1_sub: str = "Entrada en lenguaje natural",
        node2_title: str = "KAI Director IA",
        node2_sub: str = "Guion, cortes y b-roll",
        node3_title: str = "Video Master 4K",
        node3_sub: str = "Render 60fps con Whisper",
        footer_note: str = "Conexión 100% en local mediante API REST · Sin cuotas ni suscripciones",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .flow-card {{
    width: 920px;
    border-radius: 24px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 70px rgba(0, 0, 0, 0.12);
    padding: 32px 36px;
    display: flex;
    flex-direction: column;
    gap: 28px;
  }}
  .flow-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .flow-title {{
    font-size: 24px;
    font-weight: 900;
    letter-spacing: -0.5px;
    color: {p['text']};
  }}
  .flow-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    color: {p['accent']};
  }}
  .nodes-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  .node-box {{
    flex: 1;
    border-radius: 18px;
    background: {p['bg']};
    border: 1.5px solid {p['border']};
    padding: 20px 18px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 8px;
  }}
  .node-active {{
    border: 2px solid {p['accent']};
    box-shadow: 0 10px 30px {p['glow']};
    background: {p['card_bg']};
  }}
  .node-pill {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 800;
    color: {p['text_sub']};
    text-transform: uppercase;
  }}
  .node-pill-active {{
    color: {p['accent']};
  }}
  .node-h {{
    font-size: 19px;
    font-weight: 800;
    color: {p['text']};
  }}
  .node-s {{
    font-size: 13px;
    font-weight: 600;
    color: {p['text_sub']};
  }}
  .flow-arrow {{
    font-size: 24px;
    color: {p['accent']};
    font-weight: 900;
  }}
  .flow-foot {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: {p['text_sub']};
    border-top: 1px solid {p['border']};
    padding-top: 18px;
  }}
</style>
</head>
<body>
  <div class="flow-card">
    <div class="flow-top">
      <div class="flow-title">{title}</div>
      <div class="flow-tag">{tag}</div>
    </div>
    <div class="nodes-row">
      <div class="node-box">
        <div class="node-pill">01 · INPUT</div>
        <div class="node-h">{node1_title}</div>
        <div class="node-s">{node1_sub}</div>
      </div>
      <div class="flow-arrow">➔</div>
      <div class="node-box node-active">
        <div class="node-pill node-pill-active">02 · MOTOR ACTIVO</div>
        <div class="node-h">{node2_title}</div>
        <div class="node-s">{node2_sub}</div>
      </div>
      <div class="flow-arrow">➔</div>
      <div class="node-box">
        <div class="node-pill">03 · OUTPUT</div>
        <div class="node-h">{node3_title}</div>
        <div class="node-s">{node3_sub}</div>
      </div>
    </div>
    <div class="flow-foot">
      <span>🔒 {footer_note}</span>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 20. PLANTILLA: EDITORIAL FEATURE CHECKLIST (3 Claves / Lista Bento)
    # =========================================================================
    def build_editorial_feature_checklist_html(
        self,
        title: str = "3 REQUISITOS INDISPENSABLES",
        tag: str = "CHECKLIST TÉCNICO",
        item1_title: str = "Ollama o LM Studio instalado",
        item1_desc: str = "Modelo LLM ejecutándose en tu GPU sin pagar cuotas mensuales",
        item1_badge: str = "0€ / MES",
        item2_title: str = "AetherCut AI conectado por API",
        item2_desc: str = "Generación agéntica de cortes, b-roll y plantillas visuales",
        item2_badge: str = "AUTOMÁTICO",
        item3_title: str = "Whisper Large para subtítulos",
        item3_desc: str = "Sincronización palabra por palabra con precisión milimétrica",
        item3_badge: str = "OFFLINE",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .checklist-wrap {{
    width: 900px;
    border-radius: 24px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 70px rgba(0, 0, 0, 0.12);
    padding: 32px 36px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }}
  .c-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }}
  .c-title {{
    font-size: 24px;
    font-weight: 900;
    color: {p['text']};
    letter-spacing: -0.5px;
  }}
  .c-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    color: {p['accent']};
  }}
  .c-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-radius: 16px;
    background: {p['bg']};
    border: 1px solid {p['border']};
    gap: 18px;
  }}
  .c-row-active {{
    border: 1.5px solid {p['accent']};
    background: {p['pill_bg']};
  }}
  .c-left {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .check-circle {{
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: {p['accent_gradient']};
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 900;
  }}
  .c-texts {{
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .c-h {{
    font-size: 18px;
    font-weight: 800;
    color: {p['text']};
  }}
  .c-d {{
    font-size: 14px;
    font-weight: 600;
    color: {p['text_sub']};
  }}
  .c-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 800;
    padding: 6px 14px;
    border-radius: 9999px;
    background: {p['card_bg']};
    border: 1px solid {p['border']};
    color: {p['accent']};
  }}
</style>
</head>
<body>
  <div class="checklist-wrap">
    <div class="c-top">
      <div class="c-title">{title}</div>
      <div class="c-tag">{tag}</div>
    </div>
    <div class="c-row c-row-active">
      <div class="c-left">
        <div class="check-circle">✓</div>
        <div class="c-texts">
          <div class="c-h">{item1_title}</div>
          <div class="c-d">{item1_desc}</div>
        </div>
      </div>
      <div class="c-badge">{item1_badge}</div>
    </div>
    <div class="c-row">
      <div class="c-left">
        <div class="check-circle">✓</div>
        <div class="c-texts">
          <div class="c-h">{item2_title}</div>
          <div class="c-d">{item2_desc}</div>
        </div>
      </div>
      <div class="c-badge">{item2_badge}</div>
    </div>
    <div class="c-row">
      <div class="c-left">
        <div class="check-circle">✓</div>
        <div class="c-texts">
          <div class="c-h">{item3_title}</div>
          <div class="c-d">{item3_desc}</div>
        </div>
      </div>
      <div class="c-badge">{item3_badge}</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 21. PLANTILLA: EDITORIAL STAT BENCHMARK (Métrica Monumental & Impacto)
    # =========================================================================
    def build_editorial_stat_benchmark_html(
        self,
        stat_number: str = "12s",
        stat_label: str = "Tiempo Total de Renderizado",
        comparison_text: str = "frente a 4 horas y 30 minutos de edición manual en Premiere",
        trend_pct: str = "+890% MÁS RÁPIDO",
        citation: str = "Validado en local con AetherCut AI & GPU RTX 4090",
        tag: str = "BENCHMARK OFICIAL // 2026",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .bench-card {{
    width: 900px;
    border-radius: 24px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 70px rgba(0, 0, 0, 0.12);
    padding: 36px 42px;
    display: flex;
    flex-direction: column;
    gap: 22px;
  }}
  .bench-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .bench-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    color: {p['text_sub']};
    letter-spacing: 0.5px;
  }}
  .trend-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    padding: 6px 14px;
    border-radius: 9999px;
    background: #10b981;
    color: #ffffff;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
  }}
  .bench-main {{
    display: flex;
    align-items: baseline;
    gap: 24px;
  }}
  .stat-num {{
    font-family: 'Outfit', sans-serif;
    font-size: 104px;
    font-weight: 900;
    line-height: 1;
    letter-spacing: -3px;
    background: {p['accent_gradient']};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .stat-col {{
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .stat-h {{
    font-size: 26px;
    font-weight: 800;
    color: {p['text']};
    line-height: 1.2;
  }}
  .stat-c {{
    font-size: 16px;
    font-weight: 600;
    color: {p['text_sub']};
  }}
  .bench-bar {{
    width: 100%;
    height: 10px;
    border-radius: 9999px;
    background: {p['bg']};
    overflow: hidden;
    position: relative;
  }}
  .bar-fill {{
    height: 100%;
    width: 94%;
    background: {p['accent_gradient']};
    border-radius: 9999px;
    box-shadow: 0 0 12px {p['glow']};
  }}
  .bench-foot {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 600;
    color: {p['text_sub']};
  }}
</style>
</head>
<body>
  <div class="bench-card">
    <div class="bench-top">
      <div class="bench-tag">{tag}</div>
      <div class="trend-pill">▲ {trend_pct}</div>
    </div>
    <div class="bench-main">
      <div class="stat-num">{stat_number}</div>
      <div class="stat-col">
        <div class="stat-h">{stat_label}</div>
        <div class="stat-c">{comparison_text}</div>
      </div>
    </div>
    <div class="bench-bar">
      <div class="bar-fill"></div>
    </div>
    <div class="bench-foot">🛡 {citation}</div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 22. PLANTILLA: EDITORIAL FILE TREE (Explorador de Archivos & Rutas)
    # =========================================================================
    def build_editorial_file_tree_html(
        self,
        root_folder: str = "ai-video-editor/workspace",
        target_filename: str = "tu_video_crudo.mp4",
        highlight_label: str = "COLOCA AQUÍ TU VÍDEO",
        tag: str = "ESTRUCTURA DE ARCHIVOS",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)

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
    padding: 30px;
    font-family: 'Inter', sans-serif;
  }}
  .tree-window {{
    width: 900px;
    border-radius: 22px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 28px 70px rgba(0, 0, 0, 0.12);
    overflow: hidden;
  }}
  .tree-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 22px;
    border-bottom: 1px solid {p['border']};
  }}
  .tree-path {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    font-weight: 700;
    color: {p['text']};
  }}
  .tree-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    color: {p['accent']};
  }}
  .tree-body {{
    padding: 24px 30px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 17px;
  }}
  .tree-line {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 12px;
    border-radius: 8px;
    color: {p['text']};
  }}
  .line-indent-1 {{ margin-left: 28px; }}
  .line-indent-2 {{ margin-left: 56px; }}
  .line-folder {{ font-weight: 800; color: {p['accent']}; }}
  .line-target {{
    background: {p['pill_bg']};
    border: 1.5px solid {p['accent']};
    font-weight: 800;
  }}
  .target-badge {{
    margin-left: auto;
    font-size: 12px;
    font-weight: 900;
    padding: 4px 12px;
    border-radius: 9999px;
    background: {p['accent_gradient']};
    color: #ffffff;
  }}
</style>
</head>
<body>
  <div class="tree-window">
    <div class="tree-topbar">
      <div class="tree-path">📁 {root_folder}</div>
      <div class="tree-tag">{tag}</div>
    </div>
    <div class="tree-body">
      <div class="tree-line line-folder">📁 assets/</div>
      <div class="tree-line line-indent-1">🎵 audio_fondo.mp3</div>
      <div class="tree-line line-indent-1">🖼 logo_canal.png</div>
      <div class="tree-line line-folder">📁 inputs/</div>
      <div class="tree-line line-indent-1 line-target">
        <span>🎬 {target_filename}</span>
        <span class="target-badge">{highlight_label}</span>
      </div>
      <div class="tree-line line-folder">📁 outputs/</div>
      <div class="tree-line line-indent-1">✨ video_final_master.mp4</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 24. PLANTILLA: EDITORIAL PROMPT DIFF (Studio de Prompt Engineering)
    # =========================================================================
    def build_editorial_prompt_diff_html(
        self,
        title: str = "STUDIO DE PROMPT ENGINEERING",
        tag: str = "OPTIMIZACIÓN AGÉNTICA",
        bad_prompt: str = "hazme un video viral de 30s sobre finanzas para tiktok",
        bad_critique: str = "📉 Alucinación alta · Sin formato ni roles definidos · Tasa de retención < 15%",
        good_role: str = "Senior Video Director & Viral Architect",
        good_framework: str = "Zeigarnik Hook (0-2s) + Curiosity Gap",
        good_pacing: str = "Micro-cuts dynamic 2.4s + Adaptive zooms",
        good_output: str = "Strict JSON schema with timed scene cues",
        stat_score: str = "99.4% PRECISIÓN",
        stat_tokens: str = "42 TOKENS UTILIZADOS",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)
        from scratch.test_batch_2 import build_editorial_prompt_diff_html as _raw
        return _raw(
            p=p,
            title=title,
            tag=tag,
            bad_prompt=bad_prompt,
            bad_critique=bad_critique,
            good_role=good_role,
            good_framework=good_framework,
            good_pacing=good_pacing,
            good_output=good_output,
            stat_score=stat_score,
            stat_tokens=stat_tokens,
        )

    # =========================================================================
    # 25. PLANTILLA: EDITORIAL AGENT MATRIX (Orquestación Multi-Agente Swarm)
    # =========================================================================
    def build_editorial_agent_matrix_html(
        self,
        title: str = "ORQUESTACIÓN MULTI-AGENTE (SWARM)",
        tag: str = "ARQUITECTURA DE ROLES",
        agent1_name: str = "Research & Data Miner",
        agent1_task: str = "Extracción semántica y validación de fuentes",
        agent1_badge: str = "DEEPSEEK-R1",
        agent2_name: str = "Viral Scriptwriter",
        agent2_task: str = "Gancho 2s Zeigarnik + Pacing de alta retención",
        agent2_badge: str = "SONNET 3.7",
        agent3_name: str = "KAI Video Director",
        agent3_task: str = "Ensamblado 60fps de cortes, b-roll y subtítulos",
        agent3_badge: str = "GPU RTX 4090",
        footer_stats: str = "⚡ 340ms Latencia Total · 100% Consenso Agéntico · 0.00€ Coste API",
        variant: str = "editorial_slate",
    ) -> str:
        p = self.get_palette(variant)
        from scratch.test_batch_2 import build_editorial_agent_matrix_html as _raw
        return _raw(
            p=p,
            title=title,
            tag=tag,
            agent1_name=agent1_name,
            agent1_task=agent1_task,
            agent1_badge=agent1_badge,
            agent2_name=agent2_name,
            agent2_task=agent2_task,
            agent2_badge=agent2_badge,
            agent3_name=agent3_name,
            agent3_task=agent3_task,
            agent3_badge=agent3_badge,
            footer_stats=footer_stats,
        )

    # =========================================================================
    # 26. PLANTILLA: EDITORIAL PRICING ROI (Calculadora de Costes & ROI)
    # =========================================================================
    def build_editorial_pricing_roi_html(
        self,
        title: str = "ANÁLISIS DE COSTES & RETORNO DE INVERSIÓN",
        tag: str = "ROI FINANCIERO",
        old_title: str = "Agencia / Freelance Tradicional",
        old_price: str = "1.850€",
        old_period: str = "/ mes",
        old_item1: str = "⏱ 3 a 5 días de espera por vídeo",
        old_item2: str = "✕ Máximo 2 rondas de correcciones",
        old_item3: str = "💸 22.200€ gastados cada año",
        new_title: str = "Sistema Autónomo AetherCut AI",
        new_price: str = "0€",
        new_period: str = "/ mes (100% Local)",
        new_item1: str = "⚡ 12 segundos por vídeo terminado",
        new_item2: str = "✓ Revisiones ilimitadas sin pagar más",
        new_item3: str = "🚀 Amortizado desde el primer minuto",
        savings_badge: str = "AHORRO ANUAL ESTIMADO: 22.200€",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)
        from scratch.test_batch_2 import build_editorial_pricing_roi_html as _raw
        return _raw(
            p=p,
            title=title,
            tag=tag,
            old_title=old_title,
            old_price=old_price,
            old_period=old_period,
            old_item1=old_item1,
            old_item2=old_item2,
            old_item3=old_item3,
            new_title=new_title,
            new_price=new_price,
            new_period=new_period,
            new_item1=new_item1,
            new_item2=new_item2,
            new_item3=new_item3,
            savings_badge=savings_badge,
        )

    # =========================================================================
    # 27. PLANTILLA: EDITORIAL HARDWARE SPEC (Monitor de Recursos & Inferencia)
    # =========================================================================
    def build_editorial_hardware_spec_html(
        self,
        title: str = "MONITOR DE HARDWARE & INFERENCIA LOCAL",
        tag: str = "GPU RUNTIME 2026",
        model_name: str = "DeepSeek-R1-8B-Q4_K_M (GGUF)",
        vram_used: str = "8.2 GB",
        vram_total: str = "12 GB",
        vram_pct: str = "68%",
        tokens_speed: str = "54.8 tokens/s",
        gpu_temp: str = "52°C",
        gpu_power: str = "165W",
        footer_note: str = "100% Offline · Procesamiento confidencial sin enviar datos a la nube",
        variant: str = "editorial_slate",
    ) -> str:
        p = self.get_palette(variant)
        from scratch.test_batch_2 import build_editorial_hardware_spec_html as _raw
        return _raw(
            p=p,
            title=title,
            tag=tag,
            model_name=model_name,
            vram_used=vram_used,
            vram_total=vram_total,
            vram_pct=vram_pct,
            tokens_speed=tokens_speed,
            gpu_temp=gpu_temp,
            gpu_power=gpu_power,
            footer_note=footer_note,
        )

    # =========================================================================
    # 28. PLANTILLA: EDITORIAL RETENTION GRAPH (Curva de Retención de YouTube)
    # =========================================================================
    def build_editorial_retention_graph_html(
        self,
        title: str = "CURVA DE RETENCIÓN DE AUDIENCIA (ALGORITMO YOUTUBE)",
        tag: str = "MÉTRICA VIRAL",
        metric_headline: str = "84.6% Retención Media",
        metric_sub: str = "Supera al 99% de creadores en los primeros 30 segundos",
        point1_label: str = "Hook Zeigarnik (0-2s)",
        point2_label: str = "B-Roll Dinámico (8s)",
        point3_label: str = "Micro-Pacing (22s)",
        bad_line_note: str = "Video Promedio (Cae al 22%)",
        footer_benchmark: str = "Validado en +120 canales optimizados con AetherCut AI",
        variant: str = "sunset_warm",
    ) -> str:
        p = self.get_palette(variant)
        from scratch.test_batch_2 import build_editorial_retention_graph_html as _raw
        return _raw(
            p=p,
            title=title,
            tag=tag,
            metric_headline=metric_headline,
            metric_sub=metric_sub,
            point1_label=point1_label,
            point2_label=point2_label,
            point3_label=point3_label,
            bad_line_note=bad_line_note,
            footer_benchmark=footer_benchmark,
        )

    # =========================================================================
    # 29. PLANTILLA: EDITORIAL SEARCH MOCKUP (Radar de Demanda & Autocomplete)
    # =========================================================================
    def build_editorial_search_mockup_html(
        self,
        title: str = "RADAR DE BÚSQUEDA & VOLUMEN VIRAL",
        tag: str = "DEMANDA EN TIEMPO REAL",
        search_query: str = "como automatizar videos con ia...",
        result1_text: str = "como automatizar videos con ia en local",
        result1_vol: str = "148.000 / mes",
        result1_badge: str = "🔥 TENDENCIA #1",
        result2_text: str = "hacer shorts virales con python y deepseek",
        result2_vol: str = "92.400 / mes",
        result2_badge: str = "🚀 ALTO CTR",
        result3_text: str = "descargar aethercut ai gratis tutorial",
        result3_vol: str = "64.100 / mes",
        result3_badge: str = "⚡ BAJA COMPETENCIA",
        footer_source: str = "Datos consolidados de YouTube Trends & Google Keyword Planner",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)
        from scratch.test_batch_2 import build_editorial_search_mockup_html as _raw
        return _raw(
            p=p,
            title=title,
            tag=tag,
            search_query=search_query,
            result1_text=result1_text,
            result1_vol=result1_vol,
            result1_badge=result1_badge,
            result2_text=result2_text,
            result2_vol=result2_vol,
            result2_badge=result2_badge,
            result3_text=result3_text,
            result3_vol=result3_vol,
            result3_badge=result3_badge,
            footer_source=footer_source,
        )

    # =========================================================================
    # 23. PLANTILLA: EDITORIAL FULL CANVAS (Lienzo Completo 1080x1920 con Centro Dinámico)
    # =========================================================================
    def build_editorial_full_canvas_html(
        self,
        step_number: str = "03",
        total_steps: str = "10",
        step_prefix: str = "PASO",
        code_comment: str = "cómo abrirlo",
        handle: str = "@antonspain_ia",
        main_text: str = "Pulsas + y eliges",
        accent_text: str = "Tesseract",
        grid_style: str = "grid_paper",
        canvas_type: str = "chat",
        # Parámetros para cada variante central:
        window_title: str = "ChatGPT",
        highlight_button: str = "+",
        placeholder_text: str = "Pregunta lo que quieras...",
        filename: str = "pipeline.py",
        bad_label: str = "ERROR COMÚN (MÉTODO ANTIGUO)",
        bad_text: str = 'Prompt genérico: "Hazme un video viral de 30s"',
        bad_stat: str = "⏱ 4 horas perdidas · 📉 12% Retención",
        good_label: str = "FÓRMULA OPTIMIZADA (KAI DIRECTOR)",
        good_text: str = 'Arquitectura por roles: "Hook 2s Zeigarnik + B-Roll"',
        good_stat: str = "⚡ 12 Segundos · 🚀 88% Retención · 0€",
        pipeline_title: str = "PIPELINE AUTOMATIZADO 2026",
        node1_title: str = "Prompt / Idea",
        node1_sub: str = "Entrada en lenguaje natural",
        node2_title: str = "KAI Director IA",
        node2_sub: str = "Guion, cortes y b-roll",
        node3_title: str = "Video Master 4K",
        node3_sub: str = "Render 60fps con Whisper",
        item1_title: str = "Ollama o LM Studio instalado",
        item1_desc: str = "Modelo LLM ejecutándose en tu GPU sin pagar cuotas mensuales",
        item1_badge: str = "0€ / MES",
        item2_title: str = "AetherCut AI conectado por API",
        item2_desc: str = "Generación agéntica de cortes, b-roll y plantillas visuales",
        item2_badge: str = "AUTOMÁTICO",
        item3_title: str = "Whisper Large para subtítulos",
        item3_desc: str = "Sincronización palabra por palabra con precisión milimétrica",
        item3_badge: str = "OFFLINE",
        stat_number: str = "12s",
        stat_label: str = "Tiempo Total de Renderizado",
        comparison_text: str = "frente a 4 horas y 30 minutos de edición manual en Premiere",
        trend_pct: str = "+890% MÁS RÁPIDO",
        target_filename: str = "tu_video_crudo.mp4",
        highlight_label: str = "COLOCA AQUÍ TU VÍDEO",
        variant: str = "editorial_cream",
    ) -> str:
        p = self.get_palette(variant)
        clean_num = str(step_number or "1")
        clean_total = str(total_steps or "10")
        clean_prefix = (step_prefix or "PASO").upper().strip()
        comment_text = f"// {clean_num.zfill(2)} — {code_comment}" if code_comment and not code_comment.startswith("//") else (code_comment or f"// {clean_num.zfill(2)}")
        handle_text = handle if handle.startswith("@") else f"@{handle}" if handle else "@aethercut"

        if grid_style == "grid_paper":
            grid_css = f"""
            background-color: {p['bg']};
            background-image: 
              linear-gradient({p.get('grid_line', 'rgba(0,0,0,0.05)')} 1.5px, transparent 1.5px),
              linear-gradient(90deg, {p.get('grid_line', 'rgba(0,0,0,0.05)')} 1.5px, transparent 1.5px);
            background-size: 36px 36px;
            """
        elif grid_style == "dots":
            grid_css = f"""
            background-color: {p['bg']};
            background-image: radial-gradient({p.get('grid_dot', 'rgba(0,0,0,0.08)')} 1.5px, transparent 1.5px);
            background-size: 32px 32px;
            """
        else:
            grid_css = f"background: {p['bg']};"

        # Generar el componente central dinámico según canvas_type
        c_type = (canvas_type or "chat").lower().strip()
        if c_type in ("code", "terminal"):
            center_html = f"""
            <div class="macos-window code-window">
              <div class="window-topbar">
                <div class="traffic-lights">
                  <div class="dot dot-red"></div>
                  <div class="dot dot-yellow"></div>
                  <div class="dot dot-green"></div>
                </div>
                <div class="file-tab">📄 {filename}</div>
                <div class="win-tag">CLI LOCAL</div>
              </div>
              <div class="code-body" style="padding: 26px 30px; font-family: 'JetBrains Mono', monospace; font-size: 19px; line-height: 1.8;">
                <div class="code-line"><span class="line-num" style="opacity: 0.5; margin-right: 18px;">01</span><span style="color: {p['accent']}; font-weight: 700;">import</span> {{ Agent, Pipeline }} <span style="color: {p['accent']}; font-weight: 700;">from</span> <span style="color: #10b981;">"aethercut"</span></div>
                <div class="code-line"><span class="line-num" style="opacity: 0.5; margin-right: 18px;">02</span><span style="color: {p['accent']}; font-weight: 700;">const</span> engine = <span style="color: {p['accent']}; font-weight: 700;">new</span> <span style="color: #0284c7; font-weight: 700;">Pipeline</span>({{ model: <span style="color: #10b981;">"local"</span> }})</div>
                <div class="code-line" style="background: {p['pill_bg']}; border-left: 3px solid {p['accent']}; padding: 4px 8px; border-radius: 6px;"><span class="line-num" style="opacity: 0.5; margin-right: 18px;">03</span><span style="color: {p['accent']}; font-weight: 700;">const</span> video = <span style="color: {p['accent']}; font-weight: 700;">await</span> engine.<span style="color: #0284c7; font-weight: 700;">assemble</span>({{ hook: <span style="color: #10b981;">"2s"</span> }})</div>
                <div class="code-line"><span class="line-num" style="opacity: 0.5; margin-right: 18px;">04</span><span style="color: #0284c7; font-weight: 700;">console</span>.<span style="color: #0284c7; font-weight: 700;">log</span>(<span style="color: #10b981;">`✓ Renderizado exitoso: ${{video.path}}`</span>)</div>
              </div>
              <div class="window-statusbar" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 24px; border-top: 1px solid {p['border']}; background: {p['bg']}; font-family: 'JetBrains Mono', monospace; font-size: 14px; color: {p['text_sub']};">
                <div>✓ 200 OK (28ms) · 0 Tokens</div>
                <div style="color: #10b981; font-weight: 700;">● PYTHON 3.11</div>
              </div>
            </div>
            """
        elif c_type in ("versus", "vs", "fix"):
            center_html = f"""
            <div class="versus-wrap" style="width: 960px; display: flex; flex-direction: column; gap: 16px;">
              <div class="v-card card-bad" style="border-radius: 20px; padding: 22px 28px; background: rgba(239, 68, 68, 0.05); border: 1.5px solid rgba(239, 68, 68, 0.25); display: flex; flex-direction: column; gap: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 800; color: #ef4444;">✕ {bad_label}</span>
                  <span style="font-size: 14px; font-weight: 700; color: {p['text_sub']};">{bad_stat}</span>
                </div>
                <div style="font-size: 22px; font-weight: 700; color: {p['text_sub']}; text-decoration: line-through; opacity: 0.8;">{bad_text}</div>
              </div>
              <div style="display: flex; align-items: center; justify-content: center;">
                <span style="background: {p['accent_gradient']}; color: #ffffff; font-size: 14px; font-weight: 900; padding: 4px 16px; border-radius: 9999px;">VS</span>
              </div>
              <div class="v-card card-good" style="border-radius: 20px; padding: 24px 28px; background: {p['card_bg']}; border: 2px solid {p['accent']}; box-shadow: 0 16px 45px rgba(0, 0, 0, 0.10); display: flex; flex-direction: column; gap: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 800; color: {p['accent']};">✓ {good_label}</span>
                  <span style="font-size: 14px; font-weight: 800; color: #10b981;">{good_stat}</span>
                </div>
                <div style="font-size: 23px; font-weight: 800; color: {p['text']}; line-height: 1.35;">{good_text}</div>
              </div>
            </div>
            """
        elif c_type in ("workflow", "pipeline", "flow"):
            center_html = f"""
            <div class="flow-card" style="width: 960px; border-radius: 24px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 80px rgba(0, 0, 0, 0.12); padding: 32px 36px; display: flex; flex-direction: column; gap: 26px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 24px; font-weight: 900; color: {p['text']};">{pipeline_title}</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; color: {p['accent']};">PIPELINE AGÉNTICO</span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 14px;">
                <div style="flex: 1; border-radius: 18px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 20px 16px; text-align: center; display: flex; flex-direction: column; gap: 6px;">
                  <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['text_sub']};">01 · INPUT</span>
                  <span style="font-size: 20px; font-weight: 800; color: {p['text']};">{node1_title}</span>
                  <span style="font-size: 13px; font-weight: 600; color: {p['text_sub']};">{node1_sub}</span>
                </div>
                <div style="font-size: 26px; font-weight: 900; color: {p['accent']};">➔</div>
                <div style="flex: 1; border-radius: 18px; background: {p['card_bg']}; border: 2.5px solid {p['accent']}; box-shadow: 0 10px 30px {p['glow']}; padding: 20px 16px; text-align: center; display: flex; flex-direction: column; gap: 6px;">
                  <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['accent']};">02 · MOTOR ACTIVO</span>
                  <span style="font-size: 20px; font-weight: 800; color: {p['text']};">{node2_title}</span>
                  <span style="font-size: 13px; font-weight: 600; color: {p['text_sub']};">{node2_sub}</span>
                </div>
                <div style="font-size: 26px; font-weight: 900; color: {p['accent']};">➔</div>
                <div style="flex: 1; border-radius: 18px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 20px 16px; text-align: center; display: flex; flex-direction: column; gap: 6px;">
                  <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['text_sub']};">03 · OUTPUT</span>
                  <span style="font-size: 20px; font-weight: 800; color: {p['text']};">{node3_title}</span>
                  <span style="font-size: 13px; font-weight: 600; color: {p['text_sub']};">{node3_sub}</span>
                </div>
              </div>
              <div style="border-top: 1px solid {p['border']}; padding-top: 16px; font-size: 14px; font-weight: 600; color: {p['text_sub']};">🔒 Conexión 100% en local mediante API REST · Sin subir archivos a servidores externos</div>
            </div>
            """
        elif c_type in ("checklist", "keys", "claves"):
            center_html = f"""
            <div class="checklist-wrap" style="width: 960px; border-radius: 24px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 80px rgba(0, 0, 0, 0.12); padding: 30px 36px; display: flex; flex-direction: column; gap: 18px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 24px; font-weight: 900; color: {p['text']};">3 CLAVES INDISPENSABLES</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; color: {p['accent']};">CHECKLIST PRO</span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-radius: 16px; background: {p['pill_bg']}; border: 1.5px solid {p['accent']};">
                <div style="display: flex; align-items: center; gap: 16px;">
                  <div style="width: 32px; height: 32px; border-radius: 50%; background: {p['accent_gradient']}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 900;">✓</div>
                  <div><div style="font-size: 18px; font-weight: 800; color: {p['text']};">{item1_title}</div><div style="font-size: 14px; font-weight: 600; color: {p['text_sub']};">{item1_desc}</div></div>
                </div>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; padding: 6px 14px; border-radius: 9999px; background: {p['card_bg']}; color: {p['accent']};">{item1_badge}</span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-radius: 16px; background: {p['bg']}; border: 1px solid {p['border']};">
                <div style="display: flex; align-items: center; gap: 16px;">
                  <div style="width: 32px; height: 32px; border-radius: 50%; background: {p['accent_gradient']}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 900;">✓</div>
                  <div><div style="font-size: 18px; font-weight: 800; color: {p['text']};">{item2_title}</div><div style="font-size: 14px; font-weight: 600; color: {p['text_sub']};">{item2_desc}</div></div>
                </div>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; padding: 6px 14px; border-radius: 9999px; background: {p['card_bg']}; color: {p['accent']};">{item2_badge}</span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-radius: 16px; background: {p['bg']}; border: 1px solid {p['border']};">
                <div style="display: flex; align-items: center; gap: 16px;">
                  <div style="width: 32px; height: 32px; border-radius: 50%; background: {p['accent_gradient']}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 900;">✓</div>
                  <div><div style="font-size: 18px; font-weight: 800; color: {p['text']};">{item3_title}</div><div style="font-size: 14px; font-weight: 600; color: {p['text_sub']};">{item3_desc}</div></div>
                </div>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; padding: 6px 14px; border-radius: 9999px; background: {p['card_bg']}; color: {p['accent']};">{item3_badge}</span>
              </div>
            </div>
            """
        elif c_type in ("stat", "benchmark", "metric"):
            center_html = f"""
            <div class="bench-card" style="width: 960px; border-radius: 24px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 80px rgba(0, 0, 0, 0.12); padding: 36px 42px; display: flex; flex-direction: column; gap: 20px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; color: {p['text_sub']};">BENCHMARK OFICIAL // 2026</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; padding: 6px 14px; border-radius: 9999px; background: #10b981; color: #ffffff;">▲ {trend_pct}</span>
              </div>
              <div style="display: flex; align-items: baseline; gap: 28px;">
                <div style="font-family: 'Outfit', sans-serif; font-size: 104px; font-weight: 900; line-height: 1; letter-spacing: -3px; background: {p['accent_gradient']}; -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{stat_number}</div>
                <div>
                  <div style="font-size: 26px; font-weight: 800; color: {p['text']};">{stat_label}</div>
                  <div style="font-size: 16px; font-weight: 600; color: {p['text_sub']};">{comparison_text}</div>
                </div>
              </div>
              <div style="width: 100%; height: 10px; border-radius: 9999px; background: {p['bg']}; overflow: hidden;">
                <div style="height: 100%; width: 94%; background: {p['accent_gradient']}; border-radius: 9999px; box-shadow: 0 0 12px {p['glow']};"></div>
              </div>
              <div style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 600; color: {p['text_sub']};">🛡 Validado en local con AetherCut AI & GPU RTX 4090</div>
            </div>
            """
        elif c_type in ("file_tree", "tree", "files"):
            center_html = f"""
            <div class="tree-window" style="width: 960px; border-radius: 24px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 80px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 18px 24px; border-bottom: 1.5px solid {p['border']};">
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; color: {p['text']};">📁 workspace/ai-video-editor</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; color: {p['accent']};">ESTRUCTURA DE ARCHIVOS</span>
              </div>
              <div style="padding: 26px 32px; display: flex; flex-direction: column; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 18px;">
                <div style="color: {p['accent']}; font-weight: 800;">📁 assets/</div>
                <div style="margin-left: 28px; color: {p['text']};">🎵 audio_fondo.mp3</div>
                <div style="margin-left: 28px; color: {p['text']};">🖼 logo_canal.png</div>
                <div style="color: {p['accent']}; font-weight: 800;">📁 inputs/</div>
                <div style="margin-left: 28px; background: {p['pill_bg']}; border: 2px solid {p['accent']}; padding: 8px 14px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; font-weight: 800;">
                  <span>🎬 {target_filename}</span>
                  <span style="font-size: 12px; font-weight: 900; padding: 4px 14px; border-radius: 9999px; background: {p['accent_gradient']}; color: #ffffff;">{highlight_label}</span>
                </div>
                <div style="color: {p['accent']}; font-weight: 800;">📁 outputs/</div>
                <div style="margin-left: 28px; color: {p['text']};">✨ video_final_master.mp4</div>
              </div>
            </div>
            """
        elif c_type in ("prompt_diff", "diff", "prompt"):
            center_html = f"""
            <div class="diff-card" style="width: 960px; border-radius: 26px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 85px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 18px 28px; border-bottom: 1.5px solid {p['border']}; background: {p['bg']};">
                <div style="font-size: 15px; font-weight: 900; color: {p['text']};">STUDIO DE PROMPT ENGINEERING</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 9999px; background: {p['pill_bg']}; color: {p['accent']}; border: 1px solid {p['accent']};">OPTIMIZACIÓN AGÉNTICA</div>
              </div>
              <div style="padding: 24px 30px; display: flex; flex-direction: column; gap: 16px;">
                <div style="border-radius: 18px; background: rgba(239, 68, 68, 0.05); border: 1.5px dashed rgba(239, 68, 68, 0.35); padding: 16px 20px;">
                  <div style="display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 900; color: #ef4444; margin-bottom: 6px;">✕ PROMPT NOVATO (VAGO) <span style="font-weight: 700;">📉 Alucinación alta</span></div>
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; color: {p['text_sub']}; text-decoration: line-through;">"{bad_text}"</div>
                </div>
                <div style="border-radius: 20px; background: {p['card_bg']}; border: 2px solid {p['accent']}; box-shadow: 0 12px 35px {p['glow']}; padding: 18px 22px;">
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 900; color: {p['accent']}; margin-bottom: 10px;">✓ ARQUITECTURA POR ROLES & TOKENS</div>
                  <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                    <span style="padding: 6px 12px; border-radius: 10px; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; background: {p['pill_bg']}; border: 1px solid {p['accent']}; color: {p['accent']};">ROLE: Video Director</span>
                    <span style="padding: 6px 12px; border-radius: 10px; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; background: {p['bg']}; border: 1px solid {p['border']}; color: {p['text']};">HOOK: Zeigarnik 2s</span>
                    <span style="padding: 6px 12px; border-radius: 10px; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800; background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; color: #10b981;">SCHEMA: Strict JSON</span>
                  </div>
                </div>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 14px 28px; border-top: 1px solid {p['border']}; background: {p['bg']}; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: {p['text_sub']};">
                <span style="color: #10b981; font-weight: 800;">✓ 99.4% PRECISIÓN</span>
                <span>42 TOKENS UTILIZADOS</span>
              </div>
            </div>
            """
        elif c_type in ("agent_matrix", "swarm", "agents"):
            center_html = f"""
            <div class="swarm-card" style="width: 960px; border-radius: 26px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 85px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 18px 28px; border-bottom: 1.5px solid {p['border']}; background: {p['bg']};">
                <div style="font-size: 18px; font-weight: 900; color: {p['text']};">ORQUESTACIÓN MULTI-AGENTE (SWARM)</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 800; padding: 4px 14px; border-radius: 9999px; background: {p['pill_bg']}; color: {p['accent']};">ROLES PARALELOS</div>
              </div>
              <div style="padding: 22px 28px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;">
                <div style="border-radius: 16px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 16px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="font-size: 20px;">🧠</span><span style="font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 900; padding: 2px 6px; border-radius: 6px; background: {p['card_bg']}; color: {p['text_sub']};">DEEPSEEK-R1</span></div>
                  <div style="font-size: 16px; font-weight: 800; color: {p['text']};">Research Agent</div>
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: #10b981;">● COMPLETADO</div>
                </div>
                <div style="border-radius: 16px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 16px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="font-size: 20px;">✍️</span><span style="font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 900; padding: 2px 6px; border-radius: 6px; background: {p['card_bg']}; color: {p['text_sub']};">SONNET 3.7</span></div>
                  <div style="font-size: 16px; font-weight: 800; color: {p['text']};">Scriptwriter</div>
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: #10b981;">● COMPLETADO</div>
                </div>
                <div style="border-radius: 16px; background: {p['card_bg']}; border: 2.5px solid {p['accent']}; box-shadow: 0 10px 30px {p['glow']}; padding: 16px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="font-size: 20px;">🎬</span><span style="font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 900; padding: 2px 6px; border-radius: 6px; background: {p['accent_gradient']}; color: #ffffff;">RTX 4090</span></div>
                  <div style="font-size: 16px; font-weight: 800; color: {p['accent']};">KAI Director IA</div>
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['accent']};">⚡ RENDERIZANDO...</div>
                </div>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 14px 28px; border-top: 1px solid {p['border']}; background: {p['bg']}; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: {p['text_sub']};">
                <span>⚡ 340ms Latencia Total · 100% Consenso Agéntico</span>
                <span style="color: #10b981; font-weight: 900;">● SWARM ACTIVO</span>
              </div>
            </div>
            """
        elif c_type in ("pricing_roi", "roi", "pricing", "costes"):
            center_html = f"""
            <div class="roi-card" style="width: 960px; border-radius: 26px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 85px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 18px 28px; border-bottom: 1.5px solid {p['border']}; background: {p['bg']};">
                <div style="font-size: 18px; font-weight: 900; color: {p['text']};">ANÁLISIS DE COSTES & ROI</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 800; padding: 4px 14px; border-radius: 9999px; background: {p['pill_bg']}; color: {p['accent']};">ROI FINANCIERO</div>
              </div>
              <div style="padding: 22px 28px; display: grid; grid-template-columns: 1fr 1fr; gap: 18px;">
                <div style="border-radius: 18px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 20px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['text_sub']};">MÉTODO TRADICIONAL</div>
                  <div style="font-size: 18px; font-weight: 800; color: {p['text']};">Agencia / Freelance</div>
                  <div style="font-size: 38px; font-weight: 900; color: #ef4444; font-family: 'Outfit', sans-serif;">1.850€<span style="font-size: 14px; color: {p['text_sub']};">/mes</span></div>
                  <div style="font-size: 13px; font-weight: 700; color: #ef4444;">⏱ 5 días espera · 💸 22.200€/año</div>
                </div>
                <div style="border-radius: 18px; background: {p['card_bg']}; border: 2.5px solid {p['accent']}; box-shadow: 0 14px 40px {p['glow']}; padding: 20px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 900; color: {p['accent']};">★ RECOMENDADO</div>
                  <div style="font-size: 18px; font-weight: 800; color: {p['text']};">AetherCut AI Local</div>
                  <div style="font-size: 38px; font-weight: 900; background: {p['accent_gradient']}; -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-family: 'Outfit', sans-serif;">0€<span style="font-size: 14px; color: {p['text_sub']};">/mes</span></div>
                  <div style="font-size: 13px; font-weight: 700; color: #10b981;">⚡ 12 segundos · 🚀 Revisiones ilimitadas</div>
                </div>
              </div>
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 28px; border-top: 1px solid {p['border']}; background: {p['bg']};">
                <span style="padding: 6px 16px; border-radius: 9999px; background: #10b981; color: #ffffff; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 900;">💰 AHORRO ANUAL: 22.200€</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 800; color: {p['text_sub']};">✓ 100% AMORTIZADO</span>
              </div>
            </div>
            """
        elif c_type in ("hardware_spec", "gpu", "hardware", "spec"):
            center_html = f"""
            <div class="hud-card" style="width: 960px; border-radius: 26px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 85px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 18px 28px; border-bottom: 1.5px solid {p['border']}; background: {p['bg']};">
                <div style="font-size: 18px; font-weight: 900; color: {p['text']};">MONITOR DE HARDWARE & INFERENCIA</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 800; padding: 4px 14px; border-radius: 9999px; background: {p['pill_bg']}; color: {p['accent']};">GPU RUNTIME</div>
              </div>
              <div style="padding: 22px 28px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;">
                <div style="border-radius: 16px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 16px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['text_sub']};">VRAM GPU</div>
                  <div style="font-size: 28px; font-weight: 900; color: {p['accent']}; font-family: 'Outfit', sans-serif;">8.2 GB <span style="font-size: 14px; color: {p['text_sub']};">/ 12 GB</span></div>
                  <div style="font-size: 12px; font-weight: 700; color: #10b981;">● 68% Consumo Óptimo</div>
                </div>
                <div style="border-radius: 16px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 16px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['text_sub']};">VELOCIDAD TOKENS</div>
                  <div style="font-size: 28px; font-weight: 900; color: #10b981; font-family: 'Outfit', sans-serif;">54.8 <span style="font-size: 14px;">t/s</span></div>
                  <div style="font-size: 12px; font-weight: 700; color: {p['text']};">DeepSeek-R1 Local</div>
                </div>
                <div style="border-radius: 16px; background: {p['bg']}; border: 1.5px solid {p['border']}; padding: 16px; display: flex; flex-direction: column; gap: 8px;">
                  <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 800; color: {p['text_sub']};">TELEMETRÍA</div>
                  <div style="font-size: 28px; font-weight: 900; color: {p['text']}; font-family: 'Outfit', sans-serif;">52°C</div>
                  <div style="font-size: 12px; font-weight: 700; color: #10b981;">❄️ Refrigeración Silenciosa</div>
                </div>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 14px 28px; border-top: 1px solid {p['border']}; background: {p['bg']}; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: {p['text_sub']};">
                <span>🔒 100% Offline · Procesamiento confidencial</span>
                <span style="color: #10b981; font-weight: 900;">RTX READY</span>
              </div>
            </div>
            """
        elif c_type in ("retention_graph", "graph", "curve", "retention"):
            center_html = f"""
            <div class="chart-card" style="width: 960px; border-radius: 26px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 85px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 18px 28px; border-bottom: 1.5px solid {p['border']}; background: {p['bg']};">
                <div style="font-size: 17px; font-weight: 900; color: {p['text']};">CURVA DE RETENCIÓN DE AUDIENCIA</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 800; padding: 4px 14px; border-radius: 9999px; background: {p['pill_bg']}; color: {p['accent']};">MÉTRICA VIRAL</div>
              </div>
              <div style="padding: 20px 28px; display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: baseline;">
                  <div style="font-size: 38px; font-weight: 900; background: {p['accent_gradient']}; -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-family: 'Outfit', sans-serif;">84.6% Retención Media</div>
                  <div style="font-size: 14px; font-weight: 700; color: {p['text_sub']};">Top 1% de YouTube Shorts</div>
                </div>
                <div style="width: 100%; height: 160px; background: {p['bg']}; border-radius: 16px; border: 1px solid {p['border']}; padding: 10px;">
                  <svg viewBox="0 0 880 140" width="100%" height="100%">
                    <path d="M 50 25 Q 120 90 220 110 L 860 120" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-dasharray="5,5" opacity="0.6"/>
                    <text x="240" y="104" fill="#ef4444" font-family="JetBrains Mono" font-size="11" font-weight="800">✕ Video Promedio (22%)</text>
                    <path d="M 50 25 C 100 32, 200 35, 400 35 C 600 35, 750 38, 860 40 L 860 130 L 50 130 Z" fill="{p['accent']}" opacity="0.12"/>
                    <path d="M 50 25 C 100 32, 200 35, 400 35 C 600 35, 750 38, 860 40" fill="none" stroke="{p['accent']}" stroke-width="4"/>
                    <circle cx="90" cy="30" r="5" fill="#ffffff" stroke="{p['accent']}" stroke-width="3"/>
                    <text x="90" y="18" fill="{p['text']}" font-family="Inter" font-size="10" font-weight="800" text-anchor="middle">★ Hook 2s</text>
                    <circle cx="420" cy="35" r="5" fill="#ffffff" stroke="{p['accent']}" stroke-width="3"/>
                    <text x="420" y="22" fill="{p['text']}" font-family="Inter" font-size="10" font-weight="800" text-anchor="middle">⚡ B-Roll 4K</text>
                  </svg>
                </div>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 14px 28px; border-top: 1px solid {p['border']}; background: {p['bg']}; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: {p['text_sub']};">
                <span>🛡 Validado en canales de alta retención</span>
                <span style="color: #10b981; font-weight: 800;">▲ +74% RETENCIÓN FRENTE A LA MEDIA</span>
              </div>
            </div>
            """
        elif c_type in ("search_mockup", "search", "autocomplete", "radar"):
            center_html = f"""
            <div class="search-card" style="width: 960px; border-radius: 26px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 85px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 28px; border-bottom: 1.5px solid {p['border']}; background: {p['bg']};">
                <div style="font-size: 16px; font-weight: 900; color: {p['text']};">RADAR DE DEMANDA & BÚSQUEDA</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 800; padding: 4px 14px; border-radius: 9999px; background: {p['pill_bg']}; color: {p['accent']};">KEYWORDS 2026</div>
              </div>
              <div style="padding: 22px 28px; display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; align-items: center; gap: 14px; padding: 16px 22px; border-radius: 16px; background: {p['bg']}; border: 2px solid {p['accent']}; box-shadow: 0 8px 24px {p['glow']};">
                  <span style="font-size: 20px;">🔍</span>
                  <div style="font-size: 19px; font-weight: 700; color: {p['text']};">como automatizar videos con ia... <span style="display: inline-block; width: 2.5px; height: 20px; background: {p['accent']}; vertical-align: middle;"></span></div>
                </div>
                <div style="display: flex; flex-direction: column; gap: 6px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; border-radius: 12px; background: {p['pill_bg']}; border: 1px solid {p['accent']}; font-weight: 800; color: {p['text']};">
                    <span>🔍 como automatizar videos con ia en local</span>
                    <span style="padding: 4px 10px; border-radius: 9999px; background: {p['accent_gradient']}; color: #ffffff; font-size: 11px;">🔥 148K / mes</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; border-radius: 12px; background: {p['bg']}; border: 1px solid {p['border']}; font-weight: 700; color: {p['text']};">
                    <span>🔍 hacer shorts virales con python y deepseek</span>
                    <span style="padding: 4px 10px; border-radius: 9999px; background: #10b981; color: #ffffff; font-size: 11px;">🚀 ALTO CTR</span>
                  </div>
                </div>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 14px 28px; border-top: 1px solid {p['border']}; background: {p['bg']}; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: {p['text_sub']};">
                <span>📊 Tendencias YouTube Shorts en tiempo real</span>
                <span style="color: {p['accent']}; font-weight: 800;">● KEYWORDS ACTIVAS</span>
              </div>
            </div>
            """
        else:
            # Default chat interface (macOS ChatGPT window)
            center_html = f"""
            <div class="macos-window" style="width: 960px; border-radius: 26px; background: {p['card_bg']}; border: 2px solid {p['border']}; box-shadow: 0 35px 80px rgba(0, 0, 0, 0.12); overflow: hidden;">
              <div class="window-topbar" style="display: flex; align-items: center; justify-content: space-between; padding: 20px 28px; border-bottom: 1.5px solid {p['border']};">
                <div class="traffic-lights" style="display: flex; align-items: center; gap: 10px;">
                  <div class="dot dot-red" style="width: 16px; height: 16px; border-radius: 50%; background: #FF5F56;"></div>
                  <div class="dot dot-yellow" style="width: 16px; height: 16px; border-radius: 50%; background: #FFBD2E;"></div>
                  <div class="dot dot-green" style="width: 16px; height: 16px; border-radius: 50%; background: #27C93F;"></div>
                </div>
                <div class="win-title" style="font-size: 20px; font-weight: 700; color: {p['text_sub']};">{window_title}</div>
                <div class="win-tag" style="font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; color: {p['accent']};">PASO ACTIVO</div>
              </div>
              <div class="chat-canvas" style="padding: 36px; min-height: 380px; display: flex; flex-direction: column; justify-content: flex-end;">
                <div class="input-bar-container" style="display: flex; align-items: center; gap: 20px; padding: 18px 26px; border-radius: 9999px; background: {p['bg']}; border: 2px solid {p['border']};">
                  <div class="action-btn-highlight" style="width: 52px; height: 52px; border-radius: 50%; background: {p['accent_gradient']}; box-shadow: 0 6px 18px {p['glow']}; display: flex; align-items: center; justify-content: center; color: #ffffff; font-size: 32px; font-weight: 900;">{highlight_button}</div>
                  <div class="input-placeholder" style="flex: 1; font-size: 24px; color: {p['text_sub']};">{placeholder_text}</div>
                  <div class="mic-circle" style="font-size: 26px; opacity: 0.6;">🎙</div>
                </div>
              </div>
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
    margin: 0;
    padding: 0;
    width: 1080px;
    height: 1920px;
    overflow: hidden;
    {grid_css}
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    font-family: 'Inter', sans-serif;
  }}
  .canvas-top {{
    padding: 80px 60px 20px 60px;
    display: flex;
    flex-direction: column;
    gap: 36px;
  }}
  .retention-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .step-cluster {{
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .code-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 700;
    color: {p['text_sub']};
  }}
  .step-badge {{
    font-family: 'Inter', sans-serif;
    font-size: 28px;
    font-weight: 900;
    color: {p['accent']};
    letter-spacing: 1px;
    text-transform: uppercase;
  }}
  .creator-pill {{
    display: inline-flex;
    align-items: center;
    gap: 14px;
    padding: 12px 28px;
    border-radius: 9999px;
    background: {p['card_bg']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.08);
  }}
  .creator-icon {{
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: {p['accent_gradient']};
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-size: 16px;
    font-weight: 800;
  }}
  .creator-handle {{
    font-size: 22px;
    font-weight: 700;
    color: {p['text']};
  }}
  .title-area {{
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 16px;
    line-height: 1.15;
  }}
  .main-text {{
    font-size: 64px;
    font-weight: 900;
    letter-spacing: -1.5px;
    color: {p['text']};
  }}
  .accent-text {{
    font-family: 'Playfair Display', serif;
    font-style: italic;
    font-size: 72px;
    font-weight: 700;
    color: {p['accent']};
  }}
  .canvas-center {{
    padding: 0 60px;
    display: flex;
    justify-content: center;
  }}
  .canvas-bottom {{
    height: 600px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    position: relative;
  }}
  .speaker-placeholder {{
    width: 440px;
    height: 540px;
    border-radius: 220px 220px 0 0;
    border: 2px dashed {p['border']};
    background: linear-gradient(to top, rgba(0,0,0,0.04), transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    color: {p['text_sub']};
    font-size: 18px;
    font-weight: 600;
  }}
</style>
</head>
<body>
  <div class="canvas-top">
    <div class="retention-bar">
      <div class="step-cluster">
        <div class="code-tag">{comment_text}</div>
        <div class="step-badge">{clean_prefix} {clean_num}/{clean_total}</div>
      </div>
      <div class="creator-pill">
        <div class="creator-icon">✦</div>
        <div class="creator-handle">{handle_text}</div>
      </div>
    </div>
    <div class="title-area">
      <span class="main-text">{main_text}</span>
      <span class="accent-text">{accent_text}</span>
    </div>
  </div>

  <div class="canvas-center">
    {center_html}
  </div>

  <div class="canvas-bottom">
    <div class="speaker-placeholder">Zona Presentador / Rotoscope</div>
  </div>
</body>
</html>"""

    # =========================================================================
    # 24. PLANTILLA: DOCUMENT EVIDENCE SPLIT (Estilo Platzi + Agustín Laje)
    # Pantalla dividida con Pod del Presentador a la izquierda y Panel Documental
    # con imagen/gráfico, fecha, titular editorial y cita con marcador fluorescente neón.
    # =========================================================================
    def build_document_evidence_split_html(
        self,
        headline: str = "INFORME DE CULTIVOS ILÍCITOS 2026",
        excerpt: str = "Los cultivos de coca alcanzaron un récord de 253.000 hectáreas según la ONU, mientras los combatientes ilegales crecieron un 90%.",
        institution: str = "UNODC · NACIONES UNIDAS",
        date_str: str = "INFORME JUNIO 2026",
        highlight_phrase: str = "récord de 253.000 hectáreas",
        image_path: Optional[str] = None,
        stat_value: str = "+90%",
        stat_label: str = "Combatientes Ilegales",
        stat_value2: str = "253K ha",
        stat_label2: str = "Cultivos Totales",
        tag: str = "EVIDENCIA DOCUMENTAL",
        presenter_name: str = "ANÁLISIS DOCUMENTAL",
        presenter_tag: str = "● EN VIVO",
        variant: str = "orange_noir",
        layout_mode: str = "split",  # "split" (1920x1080) o "card_only" (1240x960)
    ) -> str:
        """Construye HTML de pantalla dividida editorial estilo Platzi / Agustín Laje."""
        import html as _html_mod
        p = self.get_palette(variant)
        clean_headline = _html_mod.escape(str(headline or "DOCUMENTO OFICIAL"))
        clean_excerpt = _html_mod.escape(str(excerpt or ""))
        clean_inst = _html_mod.escape(str(institution or "ORGANISMO OFICIAL"))
        clean_date = _html_mod.escape(str(date_str or "REGISTRO OFICIAL"))
        clean_tag = _html_mod.escape(str(tag or "EVIDENCIA DOCUMENTAL").upper())
        clean_pres_name = _html_mod.escape(str(presenter_name or "DIRECTOR"))
        clean_pres_tag = _html_mod.escape(str(presenter_tag or "● EN VIVO"))

        clean_stat1 = _html_mod.escape(str(stat_value or ""))
        clean_stat_lbl1 = _html_mod.escape(str(stat_label or ""))
        clean_stat2 = _html_mod.escape(str(stat_value2 or ""))
        clean_stat_lbl2 = _html_mod.escape(str(stat_label2 or ""))

        # Aplicar resaltador fluorescente estilo marcador real sobre highlight_phrase
        if highlight_phrase:
            esc_hl = _html_mod.escape(str(highlight_phrase).strip())
            if esc_hl and esc_hl.lower() in clean_excerpt.lower():
                patt = re.compile(re.escape(esc_hl), re.IGNORECASE)
                clean_excerpt = patt.sub(lambda m: f'<mark class="highlighter-marker">{m.group(0)}</mark>', clean_excerpt)

        # Resolver imagen de documento incrustada
        img_html = ""
        if image_path and os.path.exists(str(image_path)):
            try:
                with open(str(image_path), "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("utf-8")
                ext = Path(image_path).suffix.lower().replace(".", "")
                mime = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "webp") else "image/jpeg"
                img_html = f'<img src="data:{mime};base64,{b64_data}" class="doc-embed-img" alt="Document Evidence" />'
            except Exception:
                img_html = ""

        if not img_html:
            # Fallback a gráfica editorial SVG de alta fidelidad con aspecto de expediente oficial
            img_html = f"""
            <div class="doc-mockup-graphic">
              <svg width="100%" height="100%" viewBox="0 0 1140 380" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="1140" height="380" fill="rgba(18, 22, 32, 0.95)"/>
                <line x1="60" y1="310" x2="1080" y2="310" stroke="rgba(255,255,255,0.15)" stroke-width="2"/>
                <line x1="60" y1="210" x2="1080" y2="210" stroke="rgba(255,255,255,0.08)" stroke-width="1.5" stroke-dasharray="6 6"/>
                <line x1="60" y1="110" x2="1080" y2="110" stroke="rgba(255,255,255,0.08)" stroke-width="1.5" stroke-dasharray="6 6"/>
                <!-- Barras comparativas de tendencia -->
                <rect x="140" y="240" width="70" height="70" rx="8" fill="rgba(255,255,255,0.12)"/>
                <text x="175" y="225" text-anchor="middle" fill="#94a3b8" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="700">140k</text>
                <text x="175" y="340" text-anchor="middle" fill="#64748b" font-family="'Inter', sans-serif" font-size="14" font-weight="600">2021</text>
                
                <rect x="310" y="200" width="70" height="110" rx="8" fill="rgba(255,255,255,0.18)"/>
                <text x="345" y="185" text-anchor="middle" fill="#94a3b8" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="700">172k</text>
                <text x="345" y="340" text-anchor="middle" fill="#64748b" font-family="'Inter', sans-serif" font-size="14" font-weight="600">2022</text>
                
                <rect x="480" y="160" width="70" height="150" rx="8" fill="rgba(255,255,255,0.25)"/>
                <text x="515" y="145" text-anchor="middle" fill="#94a3b8" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="700">204k</text>
                <text x="515" y="340" text-anchor="middle" fill="#64748b" font-family="'Inter', sans-serif" font-size="14" font-weight="600">2023</text>
                
                <rect x="650" y="110" width="70" height="200" rx="8" fill="rgba(255, 148, 54, 0.40)" stroke="{p['accent']}" stroke-width="2"/>
                <text x="685" y="95" text-anchor="middle" fill="{p['accent']}" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="800">230k</text>
                <text x="685" y="340" text-anchor="middle" fill="{p['accent']}" font-family="'Inter', sans-serif" font-size="14" font-weight="700">2024</text>
                
                <rect x="820" y="60" width="70" height="250" rx="8" fill="{p['accent_gradient']}" stroke="#ffffff" stroke-width="2.5"/>
                <text x="855" y="45" text-anchor="middle" fill="#ffffff" font-family="'JetBrains Mono', monospace" font-size="19" font-weight="900">253k ha</text>
                <text x="855" y="340" text-anchor="middle" fill="#ffffff" font-family="'Inter', sans-serif" font-size="15" font-weight="800">2026 (MÁXIMO)</text>
                
                <!-- Sello de agua oficial -->
                <circle cx="1010" cy="110" r="45" stroke="rgba(255, 148, 54, 0.35)" stroke-width="2.5" stroke-dasharray="5 4"/>
                <text x="1010" y="105" text-anchor="middle" fill="{p['accent']}" font-family="'Outfit', sans-serif" font-size="11" font-weight="900" letter-spacing="1">OFICIAL</text>
                <text x="1010" y="122" text-anchor="middle" fill="{p['accent']}" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="700">VERIFICADO</text>
              </svg>
              <div class="mockup-watermark-tag">MONITOREO DE CULTIVOS ILÍCITOS · SISTEMA SIMCI</div>
            </div>
            """

        stats_html = ""
        if clean_stat1 or clean_stat2:
            s1_box = f"""
            <div class="doc-stat-pill">
              <span class="stat-num">{clean_stat1}</span>
              <span class="stat-lbl">{clean_stat_lbl1}</span>
            </div>
            """ if clean_stat1 else ""
            s2_box = f"""
            <div class="doc-stat-pill">
              <span class="stat-num">{clean_stat2}</span>
              <span class="stat-lbl">{clean_stat_lbl2}</span>
            </div>
            """ if clean_stat2 else ""
            stats_html = f"""
            <div class="doc-stats-footer">
              {s1_box}
              {s2_box}
              <div class="doc-ref-badge">Cotejado con Base de Datos Oficial</div>
            </div>
            """

        # Generar código según modo: split (1920x1080) o card_only (1240x960)
        is_split = (layout_mode == "split")

        left_pod_html = f"""
        <div class="presenter-pod">
          <div class="pod-header">
            <div class="pod-live-badge"><span class="pulsing-dot">●</span> {clean_pres_tag}</div>
            <div class="pod-channel-tag">AETHERCUT PRO</div>
          </div>
          <div class="pod-aperture">
            <div class="pod-scanline"></div>
            <div class="pod-watermark-icon">✦</div>
            <div class="pod-crosshair ch-tl"></div>
            <div class="pod-crosshair ch-tr"></div>
            <div class="pod-crosshair ch-bl"></div>
            <div class="pod-crosshair ch-br"></div>
          </div>
          <div class="pod-footer">
            <div class="presenter-avatar-tag">
              <span class="pres-check">✓</span>
              <span class="pres-name">{clean_pres_name}</span>
            </div>
            <div class="pres-sub">EMISIÓN EN DIRECTO</div>
          </div>
        </div>
        """ if is_split else ""

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{HTML_FONTS}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1920px;
    height: 1080px;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Plus Jakarta Sans', sans-serif;
    overflow: hidden;
  }}
  .split-master-canvas {{
    width: 1920px;
    height: 1080px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 32px;
    padding: 60px 55px;
    background: transparent;
    position: relative;
  }}
  
  /* ================= PRESENTADOR POD (IZQUIERDA) ================= */
  .presenter-pod {{
    width: 530px;
    height: 960px;
    border-radius: 40px;
    background: rgba(12, 14, 20, 0.40);
    border: 2px solid {p['border']};
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55), 0 0 40px {p['glow']}, inset 0 1px 0 rgba(255, 255, 255, 0.12);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 24px 22px;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(12px);
  }}
  .pod-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 10;
  }}
  .pod-live-badge {{
    background: rgba(239, 68, 68, 0.20);
    border: 1.5px solid rgba(239, 68, 68, 0.70);
    color: #ef4444;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    padding: 6px 14px;
    border-radius: 9999px;
    display: flex;
    align-items: center;
    gap: 8px;
    letter-spacing: 0.5px;
  }}
  .pulsing-dot {{
    font-size: 14px;
    animation: livePulse 1.4s infinite ease-in-out;
  }}
  @keyframes livePulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.4; transform: scale(0.85); }}
  }}
  .pod-channel-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 700;
    color: {p['text_sub']};
    letter-spacing: 1px;
    opacity: 0.75;
  }}
  .pod-aperture {{
    flex: 1;
    margin: 16px 0;
    border-radius: 28px;
    border: 1.5px dashed rgba(255, 255, 255, 0.15);
    background: rgba(0, 0, 0, 0.15);
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }}
  .pod-watermark-icon {{
    font-size: 80px;
    color: {p['accent']};
    opacity: 0.08;
    user-select: none;
  }}
  .pod-crosshair {{
    position: absolute;
    width: 14px;
    height: 14px;
    border-color: {p['accent']};
    opacity: 0.5;
  }}
  .ch-tl {{ top: 12px; left: 12px; border-top: 2px solid; border-left: 2px solid; }}
  .ch-tr {{ top: 12px; right: 12px; border-top: 2px solid; border-right: 2px solid; }}
  .ch-bl {{ bottom: 12px; left: 12px; border-bottom: 2px solid; border-left: 2px solid; }}
  .ch-br {{ bottom: 12px; right: 12px; border-bottom: 2px solid; border-right: 2px solid; }}
  
  .pod-footer {{
    background: rgba(18, 20, 28, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 20px;
    padding: 12px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 10;
  }}
  .presenter-avatar-tag {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .pres-check {{
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: {p['accent']};
    color: #ffffff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 900;
  }}
  .pres-name {{
    font-size: 15px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.2px;
  }}
  .pres-sub {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: {p['text_sub']};
  }}

  /* ================= PANEL DOCUMENTAL (DERECHA) ================= */
  .document-evidence-panel {{
    width: {1240 if is_split else 1200}px;
    height: 960px;
    border-radius: 40px;
    background: {p['card_bg']};
    border: 2px solid {p['border']};
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.60), 0 0 50px {p['glow']}, inset 0 1px 0 rgba(255, 255, 255, 0.15);
    padding: 42px 48px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
  }}
  .document-evidence-panel::before {{
    content: "";
    position: absolute;
    top: -120px;
    right: -120px;
    width: 450px;
    height: 450px;
    background: radial-gradient(circle, {p['glow']} 0%, transparent 70%);
    opacity: 0.35;
    pointer-events: none;
  }}
  
  .doc-topbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 18px;
  }}
  .doc-institution-badge {{
    background: {p['pill_bg']};
    border: 1.5px solid {p['accent']};
    color: {p['accent']};
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    font-weight: 800;
    padding: 8px 18px;
    border-radius: 9999px;
    display: flex;
    align-items: center;
    gap: 10px;
    letter-spacing: 0.5px;
    box-shadow: 0 0 20px {p['glow']};
  }}
  .doc-date-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    color: {p['text_sub']};
    background: rgba(255, 255, 255, 0.06);
    padding: 7px 16px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.10);
  }}
  
  .doc-headline {{
    font-size: 38px;
    font-weight: 800;
    color: {p['text']};
    line-height: 1.25;
    letter-spacing: -0.02em;
    margin-bottom: 20px;
    text-shadow: 0 2px 10px rgba(0,0,0,0.4);
  }}
  
  .doc-media-container {{
    width: 100%;
    height: 380px;
    border-radius: 24px;
    border: 1.5px solid rgba(255, 255, 255, 0.12);
    overflow: hidden;
    position: relative;
    background: rgba(10, 12, 18, 0.90);
    margin-bottom: 22px;
    box-shadow: inset 0 2px 8px rgba(0,0,0,0.4);
  }}
  .doc-embed-img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .doc-mockup-graphic {{
    width: 100%;
    height: 100%;
    position: relative;
  }}
  .mockup-watermark-tag {{
    position: absolute;
    bottom: 14px;
    right: 20px;
    background: rgba(0, 0, 0, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 4px 12px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8;
  }}
  
  .doc-excerpt-box {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 23px;
    font-style: italic;
    color: #f1f5f9;
    line-height: 1.55;
    border-left: 4px solid {p['accent']};
    padding-left: 22px;
    margin-bottom: 22px;
  }}
  
  /* Resaltador fluorescente amarillo/ámbar de alto impacto */
  .highlighter-marker {{
    background: linear-gradient(104deg, rgba(255, 235, 59, 0.20) 0%, rgba(255, 235, 59, 0.82) 3%, rgba(255, 215, 0, 0.90) 95%, rgba(255, 235, 59, 0.30) 100%);
    color: #0b0f19;
    font-weight: 800;
    font-style: normal;
    padding: 3px 8px;
    border-radius: 6px;
    box-shadow: 0 0 25px rgba(255, 215, 0, 0.50);
    display: inline;
    text-shadow: 0 0 1px rgba(0,0,0,0.4);
  }}
  
  .doc-stats-footer {{
    display: flex;
    align-items: center;
    gap: 20px;
    padding-top: 14px;
    border-top: 1.5px solid rgba(255, 255, 255, 0.08);
  }}
  .doc-stat-pill {{
    background: rgba(255, 255, 255, 0.04);
    border: 1.5px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 10px 22px;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .doc-stat-pill .stat-num {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px;
    font-weight: 900;
    background: {p['accent_gradient']};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .doc-stat-pill .stat-lbl {{
    font-size: 13px;
    font-weight: 700;
    color: {p['text_sub']};
  }}
  .doc-ref-badge {{
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #64748b;
    font-weight: 600;
  }}
</style>
</head>
<body>
  <div class="split-master-canvas">
    {left_pod_html}
    <div class="document-evidence-panel">
      <div class="doc-topbar">
        <div class="doc-institution-badge">🏛️ {clean_inst}</div>
        <div class="doc-date-badge">📅 {clean_date}</div>
      </div>
      <div class="doc-headline">{clean_headline}</div>
      <div class="doc-media-container">
        {img_html}
      </div>
      <div class="doc-excerpt-box">
        "{clean_excerpt}"
      </div>
      {stats_html}
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # PLANTILLA: PERSON SPOTLIGHT (Tarjeta Destacada de Persona con Foto)
    # =========================================================================
    def build_person_spotlight_html(
        self,
        name: str,
        role: str = "",
        image_path: Optional[str] = None,
        tag: str = "PROTAGONISTA",
        variant: str = "orange_noir",
    ) -> str:
        p = self.get_palette(variant)
        clean_name = (name or "Personaje").strip()
        clean_role = (role or "Figura Pública").strip()
        clean_tag = (tag or "PROTAGONISTA").strip().upper()

        initials = "".join(w[0] for w in clean_name.split()[:2]).upper() if clean_name else "P"
        img_tag = ""
        if image_path and Path(image_path).exists():
            try:
                raw_bytes = Path(image_path).read_bytes()
                mime = "image/png" if str(image_path).lower().endswith(".png") else "image/jpeg"
                b64 = base64.b64encode(raw_bytes).decode("ascii")
                img_tag = f'<img src="data:{mime};base64,{b64}" class="spotlight-avatar-img" />'
            except Exception:
                img_tag = f'<div class="spotlight-initials">{initials}</div>'
        else:
            img_tag = f'<div class="spotlight-initials">{initials}</div>'

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
    overflow: hidden;
  }}
  .spotlight-card {{
    position: relative;
    width: 680px;
    padding: 16px 24px;
    background: {p['card_bg']};
    border: 1.8px solid {p['border']};
    border-radius: 24px;
    box-shadow: 0 24px 50px rgba(0, 0, 0, 0.70), 0 0 35px {p['glow']}, inset 0 1px 0 rgba(255, 255, 255, 0.20);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    display: flex;
    align-items: center;
    gap: 22px;
  }}
  .spotlight-card::before {{
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 24px;
    background: radial-gradient(circle at 18% 50%, {p['glow']} 0%, transparent 65%);
    pointer-events: none;
    opacity: 0.6;
  }}
  .spotlight-avatar-wrap {{
    position: relative;
    flex-shrink: 0;
    width: 98px;
    height: 98px;
    border-radius: 50%;
    padding: 3.5px;
    background: {p['accent_gradient']};
    box-shadow: 0 0 24px {p['glow']}, 0 4px 14px rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .spotlight-avatar-inner {{
    width: 100%;
    height: 100%;
    border-radius: 50%;
    overflow: hidden;
    background: #090a0f;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .spotlight-avatar-img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }}
  .spotlight-initials {{
    font-family: 'Outfit', sans-serif;
    font-size: 38px;
    font-weight: 900;
    color: {p['text']};
    letter-spacing: -1px;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8);
  }}
  .spotlight-info {{
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex-grow: 1;
    min-width: 0;
  }}
  .spotlight-top-badge {{
    display: inline-flex;
    align-items: center;
    gap: 7px;
    align-self: flex-start;
    padding: 4px 12px;
    border-radius: 999px;
    background: {p['pill_bg']};
    border: 1px solid {p['border']};
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.16em;
    color: {p['accent']};
    text-transform: uppercase;
  }}
  .spotlight-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: {p['accent']};
    box-shadow: 0 0 8px {p['accent']};
  }}
  .spotlight-name {{
    font-family: 'Outfit', sans-serif;
    font-size: 30px;
    font-weight: 800;
    color: {p['text']};
    letter-spacing: -0.5px;
    line-height: 1.15;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.8);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .spotlight-role {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: {p['text_sub']};
    line-height: 1.25;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
</style>
</head>
<body>
  <div class="spotlight-card">
    <div class="spotlight-avatar-wrap">
      <div class="spotlight-avatar-inner">
        {img_tag}
      </div>
    </div>
    <div class="spotlight-info">
      <div class="spotlight-top-badge">
        <span class="spotlight-dot"></span>
        <span>{clean_tag}</span>
      </div>
      <div class="spotlight-name">{clean_name}</div>
      <div class="spotlight-role">{clean_role}</div>
    </div>
  </div>
</body>
</html>"""

    # =========================================================================
    # MÉTODO MAESTRO DE RENDERIZADO A PNG
    # =========================================================================
    def render_template_to_image(
        self,
        template_name: str,
        out_png: Path,
        params: Optional[Dict[str, Any]] = None,
        variant: str = "orange_noir",
    ) -> Optional[Path]:
        """Renderiza cualquier plantilla a PNG transparente mediante Headless Chromium."""
        params = params or {}
        tmpl = (template_name or "verdict_badge").lower().strip()

        # Generar HTML correspondiente
        if tmpl in ("verdict_badge", "badge", "stamp"):
            html = self.build_verdict_badge_html(
                headline=params.get("headline") or params.get("title") or "Verificado",
                icon=params.get("icon", "✓"),
                variant=variant,
                tilt_deg=float(params.get("tilt_deg", -3.5)),
                subtitle=params.get("subtitle", ""),
            )
        elif tmpl in ("tech_card", "tech_header", "code_spec"):
            html = self.build_tech_header_card_html(
                title=params.get("title") or params.get("headline") or "tech-specification",
                subtitle=params.get("subtitle", ""),
                author=params.get("author", ""),
                repo_or_tag=params.get("repo_or_tag", ""),
                variant=variant,
            )
        elif tmpl in ("stat_counter", "stat_card", "metric"):
            html = self.build_stat_counter_html(
                stat_value=params.get("stat_value") or params.get("stat") or "8.2B",
                stat_label=params.get("stat_label") or params.get("label") or "Total",
                headline=params.get("headline", ""),
                tag=params.get("tag", "MÉTRICA CLAVE"),
                trend_text=params.get("trend_text", ""),
                variant=variant,
            )
        elif tmpl in ("versus_split", "versus", "vs"):
            html = self.build_versus_split_html(
                side_a=params.get("side_a") or params.get("headline") or "Entidad A",
                side_b=params.get("side_b") or params.get("body") or "Entidad B",
                stat_a=params.get("stat_a", ""),
                stat_b=params.get("stat_b", ""),
                tag=params.get("tag", "COMPARATIVA DIRECTA"),
                variant=variant,
            )
        elif tmpl in ("quote_evidence", "quote", "citation"):
            html = self.build_quote_evidence_html(
                quote_text=params.get("quote_text") or params.get("body") or params.get("headline") or "Cita oficial",
                source=params.get("source", "Registro Oficial"),
                highlight_phrase=params.get("highlight_phrase", ""),
                variant=variant,
            )
        elif tmpl in ("step_badge", "step", "phase"):
            html = self.build_step_badge_html(
                step_number=params.get("step_number") or params.get("number") or "01",
                step_title=params.get("step_title") or params.get("title") or params.get("headline") or "Paso Clave",
                subtitle=params.get("subtitle", ""),
                variant=variant,
            )
        elif tmpl in ("alert_banner", "alert", "warning"):
            html = self.build_alert_banner_html(
                headline=params.get("headline") or params.get("title") or "PUNTO CRÍTICO",
                body=params.get("body", ""),
                tag=params.get("tag", "ADVERTENCIA CRÍTICA"),
                variant=variant,
            )
        elif tmpl in ("source_chip", "chip", "source"):
            html = self.build_source_chip_html(
                source_name=params.get("source_name") or params.get("source") or params.get("headline") or "Registro Oficial",
                tag=params.get("tag", "FUENTE OFICIAL"),
                variant=variant,
            )
        elif tmpl in ("newspaper_clipping", "newspaper", "press_clipping", "titular_prensa"):
            html = self.build_newspaper_clipping_html(
                headline=params.get("headline") or params.get("title") or "Titular de Investigación",
                newspaper=params.get("newspaper") or params.get("source") or "FINANCIAL TIMES",
                date_str=params.get("date_str") or params.get("date") or "EDICIÓN ESPECIAL 2026",
                highlight_text=params.get("highlight_text") or params.get("highlight") or "",
                body_lead=params.get("body_lead") or params.get("body") or "",
                tag=params.get("tag", "EVIDENCIA EDITORIAL"),
                variant=variant,
            )
        elif tmpl in ("social_post", "tweet", "x_post", "comunicado_social"):
            html = self.build_social_post_html(
                author_name=params.get("author_name") or params.get("author") or "Declaración Oficial",
                handle=params.get("handle") or "@oficial",
                post_text=params.get("post_text") or params.get("body") or params.get("headline") or "Declaración pública contrastada.",
                highlight_phrase=params.get("highlight_phrase") or params.get("highlight") or "",
                verified=bool(params.get("verified", True)),
                metrics_likes=params.get("metrics_likes", "128K"),
                metrics_reposts=params.get("metrics_reposts", "24.2K"),
                date_str=params.get("date_str", "Reciente"),
                variant=variant,
            )
        elif tmpl in ("timeline_milestone", "timeline", "cronologia", "hitos"):
            html = self.build_timeline_milestone_html(
                milestones=params.get("milestones"),
                active_index=int(params.get("active_index", 1)),
                title=params.get("title", "HITOS CLAVE"),
                variant=variant,
            )
        elif tmpl in ("workflow_diagram", "workflow", "router_pattern", "agent_graph", "nodos_agente", "diagrama_flujo"):
            html = self.build_workflow_diagram_html(
                title=params.get("title") or params.get("headline") or "THE ROUTER PATTERN",
                tag=params.get("tag", "PATRÓN AGÉNTICO"),
                input_label=params.get("input_label") or params.get("input") or "Consulta del Usuario",
                input_sub=params.get("input_sub", "Prompt / Tarea entrante"),
                router_label=params.get("router_label") or params.get("router") or "ROUTER CENTRAL",
                router_sub=params.get("router_sub", "Clasificador Semántico LLM"),
                routes=params.get("routes"),
                active_index=int(params.get("active_index", 1)),
                note=params.get("note") or params.get("body") or "Aislamiento de contexto: solo el agente seleccionado consume tokens.",
                variant=variant,
            )
        elif tmpl in ("terminal_hud", "terminal", "cli_console", "code_terminal", "consola_codigo"):
            html = self.build_terminal_hud_html(
                window_title=params.get("window_title") or params.get("title") or "claude-code — ~/projects/router-pattern",
                command=params.get("command") or params.get("headline") or "claude-code --pattern router --agent claims",
                output_lines=params.get("output_lines") or (params.get("body").split("\n") if params.get("body") else None),
                tag=params.get("tag", "CLI RUNTIME"),
                status_info=params.get("status_info", "Python 3.11 · Sonnet 3.7 · Context: Isolated"),
                variant=variant,
            )
        elif tmpl in ("spec_matrix", "benchmark_table", "matrix_table", "comparativa_metricas", "benchmark"):
            html = self.build_spec_matrix_html(
                title=params.get("title") or params.get("headline") or "MONOLÍTICO vs ROUTER PATTERN",
                tag=params.get("tag", "BENCHMARK DE ARQUITECTURA"),
                subtitle=params.get("subtitle", "Métricas reales medidas en producción bajo carga continua"),
                col_a_name=params.get("col_a_name") or params.get("left_title") or "Agente Monolítico",
                col_b_name=params.get("col_b_name") or params.get("right_title") or "The Router Pattern",
                rows=params.get("rows"),
                winner_col=params.get("winner_col", "b"),
                footer_note=params.get("footer_note") or params.get("note") or "Validado en producción con +100k consultas y evaluación continua.",
                variant=variant,
            )
        elif tmpl in ("editorial_step_header", "step_header", "retention_header"):
            html = self.build_editorial_retention_header_html(
                step_number=params.get("step_number") or params.get("number") or "03",
                total_steps=params.get("total_steps") or params.get("total") or "10",
                step_prefix=params.get("step_prefix") or "PASO",
                code_comment=params.get("code_comment") or params.get("comment") or params.get("subtitle") or "cómo abrirlo",
                handle=params.get("handle") or "@antonspain_ia",
                variant=variant,
            )
        elif tmpl in ("editorial_dual_title", "dual_title", "editorial_caption", "dual_caption"):
            html = self.build_editorial_dual_title_html(
                main_text=params.get("main_text") or params.get("headline") or params.get("title") or "Pulsas + y eliges",
                accent_text=params.get("accent_text") or params.get("accent") or params.get("highlight") or "Tesseract",
                subtitle=params.get("subtitle", ""),
                variant=variant,
                align=params.get("align", "center"),
            )
        elif tmpl in ("editorial_software_window", "software_window", "macos_window", "app_mockup", "chat_window"):
            html = self.build_editorial_software_window_html(
                window_title=params.get("window_title") or params.get("title") or "ChatGPT",
                window_type=params.get("window_type", "chat_input"),
                highlight_button=params.get("highlight_button") or params.get("button") or "+",
                placeholder_text=params.get("placeholder_text") or params.get("placeholder") or "Pregunta lo que quieras...",
                body_text=params.get("body_text") or params.get("body") or "",
                tag=params.get("tag", "INTERFAZ"),
                variant=variant,
            )
        elif tmpl in ("editorial_code_terminal", "code_terminal", "terminal_pro", "code_pro"):
            html = self.build_editorial_code_terminal_html(
                filename=params.get("filename", "main.py"),
                command=params.get("command", "python run_studio.py --local"),
                tag=params.get("tag", "TERMINAL PRO"),
                status_info=params.get("status_info", "200 OK (28ms) · 0 Tokens desperdiciados"),
                status_badge=params.get("status_badge", "LOCAL ACTIVE"),
                variant=variant,
                code_lines=params.get("code_lines"),
            )
        elif tmpl in ("editorial_versus_fix", "versus_fix", "versus_pro", "antes_despues", "comparativa_pro"):
            html = self.build_editorial_versus_fix_html(
                bad_label=params.get("bad_label", "ERROR COMÚN (MÉTODO ANTIGUO)"),
                bad_text=params.get("bad_text", 'Prompt genérico: "Hazme un video viral de 30 segundos sobre IA"'),
                bad_stat=params.get("bad_stat", "⏱ 4 horas perdidas · 📉 12% Retención"),
                good_label=params.get("good_label", "FÓRMULA OPTIMIZADA (KAI DIRECTOR)"),
                good_text=params.get("good_text", 'Arquitectura por roles: "Hook 2s Zeigarnik + Micro-zooms + B-Roll"'),
                good_stat=params.get("good_stat", "⚡ 12 Segundos · 🚀 88% Retención · 0€"),
                tag=params.get("tag", "COMPARATIVA DE RETENCIÓN"),
                variant=variant,
            )
        elif tmpl in ("editorial_workflow_pipeline", "workflow_pipeline", "pipeline_pro", "diagrama_pipeline"):
            html = self.build_editorial_workflow_pipeline_html(
                title=params.get("title", "PIPELINE AUTOMATIZADO 2026"),
                tag=params.get("tag", "ARQUITECTURA LOCAL"),
                node1_title=params.get("node1_title", "Prompt / Idea"),
                node1_sub=params.get("node1_sub", "Entrada en lenguaje natural"),
                node2_title=params.get("node2_title", "KAI Director IA"),
                node2_sub=params.get("node2_sub", "Guion, cortes y b-roll"),
                node3_title=params.get("node3_title", "Video Master 4K"),
                node3_sub=params.get("node3_sub", "Render 60fps con Whisper"),
                footer_note=params.get("footer_note", "Conexión 100% en local mediante API REST · Sin cuotas ni suscripciones"),
                variant=variant,
            )
        elif tmpl in ("editorial_feature_checklist", "feature_checklist", "checklist_pro", "claves_pro"):
            html = self.build_editorial_feature_checklist_html(
                title=params.get("title", "3 REQUISITOS INDISPENSABLES"),
                tag=params.get("tag", "CHECKLIST TÉCNICO"),
                item1_title=params.get("item1_title", "Ollama o LM Studio instalado"),
                item1_desc=params.get("item1_desc", "Modelo LLM ejecutándose en tu GPU sin pagar cuotas mensuales"),
                item1_badge=params.get("item1_badge", "0€ / MES"),
                item2_title=params.get("item2_title", "AetherCut AI conectado por API"),
                item2_desc=params.get("item2_desc", "Generación agéntica de cortes, b-roll y plantillas visuales"),
                item2_badge=params.get("item2_badge", "AUTOMÁTICO"),
                item3_title=params.get("item3_title", "Whisper Large para subtítulos"),
                item3_desc=params.get("item3_desc", "Sincronización palabra por palabra con precisión milimétrica"),
                item3_badge=params.get("item3_badge", "OFFLINE"),
                variant=variant,
            )
        elif tmpl in ("editorial_stat_benchmark", "stat_benchmark", "benchmark_pro", "metrica_pro"):
            html = self.build_editorial_stat_benchmark_html(
                stat_number=params.get("stat_number", "12s"),
                stat_label=params.get("stat_label", "Tiempo Total de Renderizado"),
                comparison_text=params.get("comparison_text", "frente a 4 horas y 30 minutos de edición manual en Premiere"),
                trend_pct=params.get("trend_pct", "+890% MÁS RÁPIDO"),
                citation=params.get("citation", "Validado en local con AetherCut AI & GPU RTX 4090"),
                tag=params.get("tag", "BENCHMARK OFICIAL // 2026"),
                variant=variant,
            )
        elif tmpl in ("editorial_file_tree", "file_tree", "tree_pro", "rutas_pro"):
            html = self.build_editorial_file_tree_html(
                root_folder=params.get("root_folder", "ai-video-editor/workspace"),
                target_filename=params.get("target_filename", "tu_video_crudo.mp4"),
                highlight_label=params.get("highlight_label", "COLOCA AQUÍ TU VÍDEO"),
                tag=params.get("tag", "ESTRUCTURA DE ARCHIVOS"),
                variant=variant,
            )
        elif tmpl in ("editorial_prompt_diff", "prompt_diff", "diff_prompt", "prompts_pro"):
            html = self.build_editorial_prompt_diff_html(
                title=params.get("title", "STUDIO DE PROMPT ENGINEERING"),
                tag=params.get("tag", "OPTIMIZACIÓN AGÉNTICA"),
                bad_prompt=params.get("bad_prompt", "hazme un video viral de 30s sobre finanzas para tiktok"),
                bad_critique=params.get("bad_critique", "📉 Alucinación alta · Sin formato ni roles definidos · Tasa de retención < 15%"),
                good_role=params.get("good_role", "Senior Video Director & Viral Architect"),
                good_framework=params.get("good_framework", "Zeigarnik Hook (0-2s) + Curiosity Gap"),
                good_pacing=params.get("good_pacing", "Micro-cuts dynamic 2.4s + Adaptive zooms"),
                good_output=params.get("good_output", "Strict JSON schema with timed scene cues"),
                stat_score=params.get("stat_score", "99.4% PRECISIÓN"),
                stat_tokens=params.get("stat_tokens", "42 TOKENS UTILIZADOS"),
                variant=variant,
            )
        elif tmpl in ("editorial_agent_matrix", "agent_matrix", "swarm_matrix", "agentes_pro", "orquestacion_ia"):
            html = self.build_editorial_agent_matrix_html(
                title=params.get("title", "ORQUESTACIÓN MULTI-AGENTE (SWARM)"),
                tag=params.get("tag", "ARQUITECTURA DE ROLES"),
                agent1_name=params.get("agent1_name", "Research & Data Miner"),
                agent1_task=params.get("agent1_task", "Extracción semántica y validación de fuentes"),
                agent1_badge=params.get("agent1_badge", "DEEPSEEK-R1"),
                agent2_name=params.get("agent2_name", "Viral Scriptwriter"),
                agent2_task=params.get("agent2_task", "Gancho 2s Zeigarnik + Pacing de alta retención"),
                agent2_badge=params.get("agent2_badge", "SONNET 3.7"),
                agent3_name=params.get("agent3_name", "KAI Video Director"),
                agent3_task=params.get("agent3_task", "Ensamblado 60fps de cortes, b-roll y subtítulos"),
                agent3_badge=params.get("agent3_badge", "GPU RTX 4090"),
                footer_stats=params.get("footer_stats", "⚡ 340ms Latencia Total · 100% Consenso Agéntico · 0.00€ Coste API"),
                variant=variant,
            )
        elif tmpl in ("editorial_pricing_roi", "pricing_roi", "roi_calculator", "ahorro_pro", "costes_pro"):
            html = self.build_editorial_pricing_roi_html(
                title=params.get("title", "ANÁLISIS DE COSTES & RETORNO DE INVERSIÓN"),
                tag=params.get("tag", "ROI FINANCIERO"),
                old_title=params.get("old_title", "Agencia / Freelance Tradicional"),
                old_price=params.get("old_price", "1.850€"),
                old_period=params.get("old_period", "/ mes"),
                old_item1=params.get("old_item1", "⏱ 3 a 5 días de espera por vídeo"),
                old_item2=params.get("old_item2", "✕ Máximo 2 rondas de correcciones"),
                old_item3=params.get("old_item3", "💸 22.200€ gastados cada año"),
                new_title=params.get("new_title", "Sistema Autónomo AetherCut AI"),
                new_price=params.get("new_price", "0€"),
                new_period=params.get("new_period", "/ mes (100% Local)"),
                new_item1=params.get("new_item1", "⚡ 12 segundos por vídeo terminado"),
                new_item2=params.get("new_item2", "✓ Revisiones ilimitadas sin pagar más"),
                new_item3=params.get("new_item3", "🚀 Amortizado desde el primer minuto"),
                savings_badge=params.get("savings_badge", "AHORRO ANUAL ESTIMADO: 22.200€"),
                variant=variant,
            )
        elif tmpl in ("editorial_hardware_spec", "hardware_spec", "gpu_monitor", "vram_spec", "recursos_pro"):
            html = self.build_editorial_hardware_spec_html(
                title=params.get("title", "MONITOR DE HARDWARE & INFERENCIA LOCAL"),
                tag=params.get("tag", "GPU RUNTIME 2026"),
                model_name=params.get("model_name", "DeepSeek-R1-8B-Q4_K_M (GGUF)"),
                vram_used=params.get("vram_used", "8.2 GB"),
                vram_total=params.get("vram_total", "12 GB"),
                vram_pct=params.get("vram_pct", "68%"),
                tokens_speed=params.get("tokens_speed", "54.8 tokens/s"),
                gpu_temp=params.get("gpu_temp", "52°C"),
                gpu_power=params.get("gpu_power", "165W"),
                footer_note=params.get("footer_note", "100% Offline · Procesamiento confidencial sin enviar datos a la nube"),
                variant=variant,
            )
        elif tmpl in ("editorial_retention_graph", "retention_graph", "grafica_retencion", "curva_viral"):
            html = self.build_editorial_retention_graph_html(
                title=params.get("title", "CURVA DE RETENCIÓN DE AUDIENCIA (ALGORITMO YOUTUBE)"),
                tag=params.get("tag", "MÉTRICA VIRAL"),
                metric_headline=params.get("metric_headline", "84.6% Retención Media"),
                metric_sub=params.get("metric_sub", "Supera al 99% de creadores en los primeros 30 segundos"),
                point1_label=params.get("point1_label", "Hook Zeigarnik (0-2s)"),
                point2_label=params.get("point2_label", "B-Roll Dinámico (8s)"),
                point3_label=params.get("point3_label", "Micro-Pacing (22s)"),
                bad_line_note=params.get("bad_line_note", "Video Promedio (Cae al 22%)"),
                footer_benchmark=params.get("footer_benchmark", "Validado en +120 canales optimizados con AetherCut AI"),
                variant=variant,
            )
        elif tmpl in ("editorial_search_mockup", "search_mockup", "radar_busqueda", "google_mockup", "youtube_search"):
            html = self.build_editorial_search_mockup_html(
                title=params.get("title", "RADAR DE BÚSQUEDA & VOLUMEN VIRAL"),
                tag=params.get("tag", "DEMANDA EN TIEMPO REAL"),
                search_query=params.get("search_query", "como automatizar videos con ia..."),
                result1_text=params.get("result1_text", "como automatizar videos con ia en local"),
                result1_vol=params.get("result1_vol", "148.000 / mes"),
                result1_badge=params.get("result1_badge", "🔥 TENDENCIA #1"),
                result2_text=params.get("result2_text", "hacer shorts virales con python y deepseek"),
                result2_vol=params.get("result2_vol", "92.400 / mes"),
                result2_badge=params.get("result2_badge", "🚀 ALTO CTR"),
                result3_text=params.get("result3_text", "descargar aethercut ai gratis tutorial"),
                result3_vol=params.get("result3_vol", "64.100 / mes"),
                result3_badge=params.get("result3_badge", "⚡ BAJA COMPETENCIA"),
                footer_source=params.get("footer_source", "Datos consolidados de YouTube Trends & Google Keyword Planner"),
                variant=variant,
            )
        elif tmpl in ("editorial_full_canvas", "editorial_canvas", "tech_breakdown_canvas", "canvas_editorial"):
            html = self.build_editorial_full_canvas_html(
                step_number=params.get("step_number") or params.get("number") or "03",
                total_steps=params.get("total_steps") or params.get("total") or "10",
                step_prefix=params.get("step_prefix") or "PASO",
                code_comment=params.get("code_comment") or params.get("comment") or "cómo abrirlo",
                handle=params.get("handle") or "@antonspain_ia",
                main_text=params.get("main_text") or params.get("headline") or "Pulsas + y eliges",
                accent_text=params.get("accent_text") or params.get("accent") or "Tesseract",
                grid_style=params.get("grid_style", "grid_paper"),
                canvas_type=params.get("canvas_type", "chat"),
                window_title=params.get("window_title", "ChatGPT"),
                highlight_button=params.get("highlight_button", "+"),
                placeholder_text=params.get("placeholder_text", "Pregunta lo que quieras..."),
                filename=params.get("filename", "pipeline.py"),
                bad_label=params.get("bad_label", "ERROR COMÚN (MÉTODO ANTIGUO)"),
                bad_text=params.get("bad_text", 'Prompt genérico: "Hazme un video viral de 30s"'),
                bad_stat=params.get("bad_stat", "⏱ 4 horas perdidas · 📉 12% Retención"),
                good_label=params.get("good_label", "FÓRMULA OPTIMIZADA (KAI DIRECTOR)"),
                good_text=params.get("good_text", 'Arquitectura por roles: "Hook 2s Zeigarnik + B-Roll"'),
                good_stat=params.get("good_stat", "⚡ 12 Segundos · 🚀 88% Retención · 0€"),
                pipeline_title=params.get("pipeline_title", "PIPELINE AUTOMATIZADO 2026"),
                node1_title=params.get("node1_title", "Prompt / Idea"),
                node1_sub=params.get("node1_sub", "Entrada en lenguaje natural"),
                node2_title=params.get("node2_title", "KAI Director IA"),
                node2_sub=params.get("node2_sub", "Guion, cortes y b-roll"),
                node3_title=params.get("node3_title", "Video Master 4K"),
                node3_sub=params.get("node3_sub", "Render 60fps con Whisper"),
                item1_title=params.get("item1_title", "Ollama o LM Studio instalado"),
                item1_desc=params.get("item1_desc", "Modelo LLM ejecutándose en tu GPU sin pagar cuotas mensuales"),
                item1_badge=params.get("item1_badge", "0€ / MES"),
                item2_title=params.get("item2_title", "AetherCut AI conectado por API"),
                item2_desc=params.get("item2_desc", "Generación agéntica de cortes, b-roll y plantillas visuales"),
                item2_badge=params.get("item2_badge", "AUTOMÁTICO"),
                item3_title=params.get("item3_title", "Whisper Large para subtítulos"),
                item3_desc=params.get("item3_desc", "Sincronización palabra por palabra con precisión milimétrica"),
                item3_badge=params.get("item3_badge", "OFFLINE"),
                stat_number=params.get("stat_number", "12s"),
                stat_label=params.get("stat_label", "Tiempo Total de Renderizado"),
                comparison_text=params.get("comparison_text", "frente a 4 horas y 30 minutos de edición manual en Premiere"),
                trend_pct=params.get("trend_pct", "+890% MÁS RÁPIDO"),
                target_filename=params.get("target_filename", "tu_video_crudo.mp4"),
                highlight_label=params.get("highlight_label", "COLOCA AQUÍ TU VÍDEO"),
                variant=variant,
            )
        elif tmpl in ("document_evidence_split", "document_evidence", "split_evidence", "platzi_evidence", "informe_split", "citacion_formal"):
            html = self.build_document_evidence_split_html(
                headline=params.get("headline") or params.get("title") or "INFORME DE CULTIVOS ILÍCITOS 2026",
                excerpt=params.get("excerpt") or params.get("body") or params.get("headline") or "",
                institution=params.get("institution") or params.get("source") or params.get("badge") or "ORGANISMO OFICIAL",
                date_str=params.get("date_str") or params.get("date") or "REGISTRO OFICIAL",
                highlight_phrase=params.get("highlight_phrase") or params.get("highlight") or params.get("stat") or "",
                image_path=params.get("image_path"),
                stat_value=params.get("stat_value") or params.get("stat") or "",
                stat_label=params.get("stat_label") or params.get("label") or "Métrica Clave",
                stat_value2=params.get("stat_value2", ""),
                stat_label2=params.get("stat_label2", ""),
                tag=params.get("tag") or params.get("badge") or "EVIDENCIA DOCUMENTAL",
                presenter_name=params.get("presenter_name", "ANÁLISIS DOCUMENTAL"),
                presenter_tag=params.get("presenter_tag", "● EN VIVO"),
                variant=variant,
                layout_mode=params.get("layout_mode", "split"),
            )
        elif tmpl in ("person_spotlight", "person_card", "speaker_callout", "speaker_card", "persona_spotlight"):
            html = self.build_person_spotlight_html(
                name=params.get("name") or params.get("headline") or "Personaje",
                role=params.get("role") or params.get("subtitle") or params.get("title") or "Figura Pública",
                image_path=params.get("image_path"),
                tag=params.get("tag") or "PROTAGONISTA",
                variant=variant,
            )
        elif self.build_extra_template_html(tmpl, params, variant) is not None:
            html = self.build_extra_template_html(tmpl, params, variant)
        else:
            # Fallback a verdict badge
            html = self.build_verdict_badge_html(
                headline=params.get("headline", "Dato Verificado"),
                variant=variant,
            )

        try:
            out_png = Path(out_png)
            out_png.parent.mkdir(parents=True, exist_ok=True)
            html_file = out_png.with_suffix(".html")
            html_file.write_text(html, encoding="utf-8")
            file_uri = html_file.resolve().as_uri()

            temp_profile = Path(tempfile.mkdtemp(prefix="chrome_tpl_"))
            is_horizontal_split = (
                tmpl in ("document_evidence_split", "document_evidence", "split_evidence", "platzi_evidence", "informe_split", "citacion_formal")
                or bool(params.get("horizontal"))
                or (params.get("layout_mode") == "split")
            )
            win_size = "1920,1080" if is_horizontal_split else "1080,1920"
            try:
                args = [
                    self.browser_bin,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    f"--user-data-dir={temp_profile}",
                    "--hide-scrollbars",
                    "--default-background-color=00000000",
                    f"--screenshot={out_png.resolve()}",
                    f"--window-size={win_size}",
                    file_uri,
                ]
                subprocess.run(args, capture_output=True, check=True, timeout=15)
            finally:
                shutil.rmtree(temp_profile, ignore_errors=True)

            if is_horizontal_split or tmpl in ("editorial_full_canvas", "editorial_canvas", "tech_breakdown_canvas", "canvas_editorial") or params.get("crop") is False:
                pass  # Conservar dimensiones 1920x1080 para la pantalla dividida completa
            else:
                self._crop_transparent(out_png)
            if out_png.exists() and out_png.stat().st_size > 500:
                return out_png
        except Exception as exc:
            logger.warning(f"Error renderizando template '{tmpl}': {exc}")
        return None

    # Catálogo introspectivo para el frontend y director
    @staticmethod
    def get_catalog() -> Dict[str, Any]:
        return {
            "themes": list(THEME_PALETTES.keys()),
            "templates": [
                {
                    "id": "verdict_badge",
                    "name": "Distintivo / Sello de Veredicto",
                    "description": "Píldora viral inclinada con borde brillante, ícono de verificación y tipografía serif editorial.",
                    "sfx": "pop",
                    "animation": "spring_bounce",
                    "default_variant": "orange_noir",
                    "sample_params": {"headline": "ganó Opus", "icon": "✓", "tilt_deg": -3.5},
                },
                {
                    "id": "tech_card",
                    "name": "Tarjeta Técnica de Cabecera",
                    "description": "Tarjeta flotante superior en dark slate con micro-matriz de puntos y tipografía mono.",
                    "sfx": "whoosh",
                    "animation": "top_slide_settle",
                    "default_variant": "orange_noir",
                    "sample_params": {"title": "find-skills", "subtitle": "por Vercel · vercel-labs/skills"},
                },
                {
                    "id": "stat_counter",
                    "name": "Métrica Clave / Cifra de Impacto",
                    "description": "Tarjeta Bento con número gigante en gradiente, medidor de barra y tendencia.",
                    "sfx": "chime",
                    "animation": "elastic_scale_pop",
                    "default_variant": "orange_noir",
                    "sample_params": {"stat_value": "+340%", "stat_label": "Crecimiento IA", "headline": "Récord Histórico"},
                },
                {
                    "id": "versus_split",
                    "name": "Comparativa Versus Dual",
                    "description": "Contenedor dividido lado A vs lado B con distintivo central circular VS en naranja eléctrico.",
                    "sfx": "impact",
                    "animation": "convergence_pop",
                    "default_variant": "orange_noir",
                    "sample_params": {"side_a": "Humano", "side_b": "IA Autónoma", "stat_a": "4h 20m", "stat_b": "12s"},
                },
                {
                    "id": "quote_evidence",
                    "name": "Cita y Evidencia Documental (Vox Style)",
                    "description": "Tarjeta periodística con comillas tipográficas gigantes y texto resaltado fluorescente.",
                    "sfx": "whoosh",
                    "animation": "smooth_rise",
                    "default_variant": "orange_noir",
                    "sample_params": {"quote_text": "Los datos demuestran un cambio irreversible en el fondo oceánico.", "source": "NOAA Research 2026"},
                },
                {
                    "id": "step_badge",
                    "name": "Insignia de Fase / Paso a Paso",
                    "description": "Píldora moderna con círculo numérico en naranja neón y titular de fase.",
                    "sfx": "pop",
                    "animation": "slide_in_left",
                    "default_variant": "orange_noir",
                    "sample_params": {"step_number": "01", "step_title": "Detección Acústica", "subtitle": "Frecuencia Ultra Baja"},
                },
                {
                    "id": "alert_banner",
                    "name": "Banner de Alerta Táctica HUD",
                    "description": "Banner de advertencia con ícono de peligro, bordes carmesí/ámbar y micro-etiqueta superior.",
                    "sfx": "alert",
                    "animation": "flash_impact",
                    "default_variant": "crimson_hazard",
                    "sample_params": {"headline": "CONTRADICCIÓN DETECTADA", "body": "La señal no coincide con actividad biológica conocida."},
                },
                {
                    "id": "source_chip",
                    "name": "Pastilla de Fuente Verificada",
                    "description": "Micro-chip discreto con escudo y atribución oficial para esquinas.",
                    "sfx": "pop",
                    "animation": "corner_pop",
                    "default_variant": "orange_noir",
                    "sample_params": {"source_name": "Laboratorio Acústico del Pacífico", "tag": "FUENTE OFICIAL"},
                },
                {
                    "id": "newspaper_clipping",
                    "name": "Recorte de Prensa / Periódico con Subrayador Neón (Estilo Adrià Solà Pastor / Vox)",
                    "description": "Recorte editorial de prensa (Financial Times, WSJ, Bloomberg) con cabecera periodística y rotulador fluorescente amarillo animado sobre el titular clave.",
                    "sfx": "whoosh",
                    "animation": "smooth_rise",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "headline": "BlackRock supera los 10 billones de dólares bajo gestión directa",
                        "newspaper": "FINANCIAL TIMES",
                        "highlight_text": "10 billones de dólares",
                        "body_lead": "El algoritmo Aladdin consolida el mayor monopolio financiero de la historia moderna.",
                        "tag": "EVIDENCIA EDITORIAL"
                    },
                },
                {
                    "id": "social_post",
                    "name": "Publicación Verificada en Redes (X / Twitter Card)",
                    "description": "Tarjeta oscura con insignia verificada, avatar, métricas y texto destacado para declaraciones de directivos, gobiernos o expertos.",
                    "sfx": "pop",
                    "animation": "spring_bounce",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "author_name": "Elon Musk",
                        "handle": "@elonmusk",
                        "post_text": "La escala de computación requerida para este avance superó todas nuestras proyecciones.",
                        "highlight_phrase": "superó todas nuestras proyecciones",
                        "metrics_likes": "142K",
                        "metrics_reposts": "31.8K"
                    },
                },
                {
                    "id": "timeline_milestone",
                    "name": "Línea de Tiempo / Hitos Cronológicos Documentales",
                    "description": "Cronología documental de 3 a 4 hitos con nodo activo pulsante y fechas clave para contextualizar la evolución del caso.",
                    "sfx": "impact",
                    "animation": "slide_in_left",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "title": "CRONOLOGÍA DEL CASO",
                        "active_index": 1,
                        "milestones": [
                            {"year": "2008", "label": "Colapso Financiero"},
                            {"year": "2015", "label": "Despliegue Aladdin"},
                            {"year": "2026", "label": "Control Sistémico"}
                        ]
                    },
                },
                {
                    "id": "workflow_diagram",
                    "name": "Diagrama de Arquitectura / Patrón de Enrutamiento (Estilo Santa IA)",
                    "description": "Lienzo de arquitectura con nodo de entrada, clasificador router central y ramas de agentes especializados con iluminación activa.",
                    "sfx": "chime",
                    "animation": "smooth_rise",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "title": "THE ROUTER PATTERN",
                        "tag": "PATRÓN AGÉNTICO",
                        "input_label": "Consulta de Pasajero",
                        "router_label": "ROUTER SEMÁNTICO",
                        "active_index": 1,
                        "note": "Aislamiento de contexto: solo el agente seleccionado consume tokens.",
                    },
                },
                {
                    "id": "terminal_hud",
                    "name": "Consola Terminal HUD / Claude Code CLI (Estilo Dev / Santa IA)",
                    "description": "Ventana de terminal oscura estilo macOS con comandos en vivo, resaltado de sintaxis y estado de ejecución para código e IA.",
                    "sfx": "pop",
                    "animation": "corner_pop",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "window_title": "claude-code — ~/projects/router-pattern",
                        "command": "claude-code --pattern router --agent claims",
                        "tag": "CLI RUNTIME",
                    },
                },
                {
                    "id": "spec_matrix",
                    "name": "Matriz de Especificaciones / Benchmark Comparativo (Estilo Santa IA)",
                    "description": "Tabla técnica de benchmarking comparativo (Monolítico vs Router / Local vs Cloud) con métricas reales de latencia, tokens y alucinación.",
                    "sfx": "impact",
                    "animation": "smooth_rise",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "title": "MONOLÍTICO vs ROUTER PATTERN",
                        "tag": "BENCHMARK DE ARQUITECTURA",
                        "col_a_name": "Agente Monolítico",
                        "col_b_name": "The Router Pattern",
                        "footer_note": "Medido en producción bajo carga continua."
                    },
                },
                {
                    "id": "editorial_step_header",
                    "name": "Encabezado Editorial con Gamificación de Pasos (Estilo Anton)",
                    "description": "Cabecera superior técnica con comentario de código (// 03 - paso), contador gamificado de pasos (PASO 3/10) para máxima retención y pastilla con @handle del creador.",
                    "sfx": "whoosh",
                    "animation": "top_slide_settle",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "step_number": "03",
                        "total_steps": "10",
                        "step_prefix": "PASO",
                        "code_comment": "cómo abrirlo",
                        "handle": "@antonspain_ia"
                    },
                },
                {
                    "id": "editorial_dual_title",
                    "name": "Titular Editorial Mixto (Bold Sans + Serif Italic)",
                    "description": "Fórmula tipográfica de alta conversión: frase de acción en Sans-serif Ultra-Bold y concepto clave o producto en Serif Cursiva en color de acento.",
                    "sfx": "pop",
                    "animation": "elastic_scale_pop",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "main_text": "Pulsas + y eliges",
                        "accent_text": "Tesseract",
                        "subtitle": "Plugin local gratuito sin suscripción"
                    },
                },
                {
                    "id": "editorial_software_window",
                    "name": "Ventana Flotante macOS de Software / Mockup B-Roll",
                    "description": "Ventana tipo macOS con botones semáforo, barra de interfaz de ChatGPT con botón de acción destacado y sombra difusa 3D de alta gama.",
                    "sfx": "pop",
                    "animation": "smooth_rise",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "window_title": "ChatGPT",
                        "highlight_button": "+",
                        "placeholder_text": "Pregunta lo que quieras...",
                        "tag": "PASO ACTIVO"
                    },
                },
                {
                    "id": "editorial_full_canvas",
                    "name": "Lienzo Completo Editorial Tech 9:16 (Fórmula Anton Viral Completa)",
                    "description": "Composición vertical completa (1080x1920) sobre papel milimetrado/blueprint con cabecera de retención, titular dual, ventana flotante y espacio reservado para busto parlante rotoscopeado.",
                    "sfx": "whoosh",
                    "animation": "convergence_pop",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "step_number": "03",
                        "total_steps": "10",
                        "step_prefix": "PASO",
                        "code_comment": "cómo abrirlo",
                        "handle": "@antonspain_ia",
                        "main_text": "Pulsas + y eliges",
                        "accent_text": "Tesseract",
                        "window_title": "ChatGPT",
                        "highlight_button": "+",
                        "grid_style": "grid_paper"
                    },
                },
                {
                    "id": "editorial_code_terminal",
                    "name": "Consola de Código & Terminal Pro (macOS Studio)",
                    "description": "Ventana de código estilo VS Code/Cursor con pestañas de archivo, números de línea, sintaxis coloreada, línea activa resaltada y barra de estado de ejecución.",
                    "sfx": "pop",
                    "animation": "corner_pop",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "filename": "pipeline.py",
                        "tag": "CLI LOCAL",
                        "status_info": "200 OK (28ms) · 0 Tokens",
                        "status_badge": "LOCAL ACTIVE"
                    },
                },
                {
                    "id": "editorial_versus_fix",
                    "name": "Comparativa Antes vs Después / Error vs Fórmula Pro",
                    "description": "Tarjeta dual de alto impacto que compara el método novato/antiguo (tachado y en rojo suave) contra la fórmula agéntica optimizada (iluminada en acento con métricas de retención).",
                    "sfx": "impact",
                    "animation": "convergence_pop",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "bad_label": "ERROR COMÚN (MÉTODO ANTIGUO)",
                        "bad_text": "Prompt genérico de 5 palabras sin roles ni estructura",
                        "bad_stat": "⏱ 4 horas perdidas · 📉 12% Retención",
                        "good_label": "FÓRMULA OPTIMIZADA (KAI DIRECTOR)",
                        "good_text": "Hook 2s Zeigarnik + Micro-zooms + B-Roll + Subtítulos",
                        "good_stat": "⚡ 12 Segundos · 🚀 88% Retención · 0€"
                    },
                },
                {
                    "id": "editorial_workflow_pipeline",
                    "name": "Diagrama de Pipeline / Flujo en 3 Nodos Conectados",
                    "description": "Diagrama de arquitectura con 3 nodos enlazados por flechas direccionales: Entrada (Input), Motor IA Activo con aura de iluminación (Director) y Resultado Final (Output).",
                    "sfx": "chime",
                    "animation": "smooth_rise",
                    "default_variant": "editorial_slate",
                    "sample_params": {
                        "title": "PIPELINE AUTOMATIZADO 2026",
                        "tag": "ARQUITECTURA LOCAL",
                        "node1_title": "Prompt / Idea",
                        "node2_title": "KAI Director IA",
                        "node3_title": "Video Master 4K"
                    },
                },
                {
                    "id": "editorial_feature_checklist",
                    "name": "Lista de 3 Claves / Checklist Bento de Requisitos",
                    "description": "Tres filas Bento satinadas con checks circulares de verificación, titular en negrita, micro-descripción y etiquetas de valor (0€/MES, AUTOMÁTICO, OFFLINE).",
                    "sfx": "pop",
                    "animation": "slide_in_left",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "title": "3 REQUISITOS INDISPENSABLES",
                        "item1_title": "Ollama o LM Studio instalado",
                        "item2_title": "AetherCut AI conectado por API",
                        "item3_title": "Whisper Large para subtítulos"
                    },
                },
                {
                    "id": "editorial_stat_benchmark",
                    "name": "Tarjeta Monumental de Rendimiento & Ahorro (Benchmark)",
                    "description": "Cifra monumental de impacto (96px) con gradiente temático, píldora de tendencia con flecha ascendente, comparativa de tiempo ahorrado y barra de progreso iluminada.",
                    "sfx": "impact",
                    "animation": "elastic_scale_pop",
                    "default_variant": "sunset_warm",
                    "sample_params": {
                        "stat_number": "12s",
                        "stat_label": "Tiempo Total de Renderizado",
                        "comparison_text": "frente a 4 horas y 30 minutos de edición manual en Premiere",
                        "trend_pct": "+890% MÁS RÁPIDO"
                    },
                },
                {
                    "id": "editorial_file_tree",
                    "name": "Explorador de Archivos / Estructura de Carpetas & Destino",
                    "description": "Explorador de archivos estilo macOS / VS Code que muestra las carpetas del proyecto y resalta la ruta exacta donde el usuario debe colocar su archivo de entrada.",
                    "sfx": "pop",
                    "animation": "corner_pop",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "root_folder": "ai-video-editor/workspace",
                        "target_filename": "tu_video_crudo.mp4",
                        "highlight_label": "COLOCA AQUÍ TU VÍDEO"
                    },
                },
                {
                    "id": "editorial_prompt_diff",
                    "name": "Studio de Prompt Engineering / Token Diff Pro",
                    "description": "Visualizador de ingeniería de prompts con tokens de roles coloreados (Role, Hook, Pacing, JSON Schema) contra prompt genérico tachado y métricas de precisión.",
                    "sfx": "pop",
                    "animation": "corner_pop",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "title": "STUDIO DE PROMPT ENGINEERING",
                        "bad_prompt": "hazme un video viral de 30s sobre finanzas para tiktok",
                        "good_role": "Senior Video Director & Viral Architect",
                        "stat_score": "99.4% PRECISIÓN"
                    },
                },
                {
                    "id": "editorial_agent_matrix",
                    "name": "Orquestación Multi-Agente Swarm (3 Agentes en Paralelo)",
                    "description": "Matriz de 3 agentes de inteligencia artificial coordinados en vivo (Research, Scriptwriter, KAI Director Activo iluminado) con latencias y estado de consenso.",
                    "sfx": "chime",
                    "animation": "smooth_rise",
                    "default_variant": "editorial_slate",
                    "sample_params": {
                        "title": "ORQUESTACIÓN MULTI-AGENTE (SWARM)",
                        "agent1_name": "Research & Data Miner",
                        "agent2_name": "Viral Scriptwriter",
                        "agent3_name": "KAI Video Director"
                    },
                },
                {
                    "id": "editorial_pricing_roi",
                    "name": "Calculadora de Costes & Retorno de Inversión (ROI)",
                    "description": "Comparativa financiera dual entre agencia tradicional (1.850€/mes, esperas, correcciones limitadas) vs sistema autónomo AetherCut (0€/mes, 12s, ilimitado) con cálculo de ahorro anual.",
                    "sfx": "impact",
                    "animation": "convergence_pop",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "old_price": "1.850€",
                        "new_price": "0€",
                        "savings_badge": "AHORRO ANUAL ESTIMADO: 22.200€"
                    },
                },
                {
                    "id": "editorial_hardware_spec",
                    "name": "Monitor de Hardware GPU & Telemetría en Local",
                    "description": "Panel de telemetría técnica estilo Apple/NVIDIA Studio con barra gráfica de VRAM usada, velocidad de inferencia en tokens/s, telemetría térmica y modo 100% offline.",
                    "sfx": "pop",
                    "animation": "smooth_rise",
                    "default_variant": "editorial_slate",
                    "sample_params": {
                        "vram_used": "8.2 GB",
                        "vram_total": "12 GB",
                        "tokens_speed": "54.8 tokens/s",
                        "gpu_temp": "52°C"
                    },
                },
                {
                    "id": "editorial_retention_graph",
                    "name": "Curva Vectorial de Retención de YouTube (Algoritmo 2026)",
                    "description": "Gráfica SVG vectorial de alta resolución que dibuja la curva de retención media del 85% con 3 hitos visuales clave (Hook 2s, B-Roll, Micro-Pacing) frente a la caída del vídeo medio.",
                    "sfx": "impact",
                    "animation": "smooth_rise",
                    "default_variant": "sunset_warm",
                    "sample_params": {
                        "metric_headline": "84.6% Retención Media",
                        "point1_label": "Hook Zeigarnik (0-2s)",
                        "point2_label": "B-Roll Dinámico (8s)"
                    },
                },
                {
                    "id": "editorial_search_mockup",
                    "name": "Radar de Búsqueda & Mockup de Autocompletado Viral",
                    "description": "Barra de búsqueda spotlight flotante con cursor pulsante y 3 filas de autocompletado de alto volumen con iconos de fuego, búsquedas mensuales y etiquetas de CTR.",
                    "sfx": "pop",
                    "animation": "slide_in_left",
                    "default_variant": "editorial_cream",
                    "sample_params": {
                        "search_query": "como automatizar videos con ia...",
                        "result1_text": "como automatizar videos con ia en local",
                        "result1_vol": "148.000 / mes"
                    },
                },
                {
                    "id": "document_evidence_split",
                    "name": "Pantalla Dividida Documental con Pod y Resaltador Neón (Estilo Platzi + Agustín Laje)",
                    "description": "Pantalla dividida 16:9 con Pod vertical del presentador en la izquierda (con insignia en vivo y marco de cámara) y en la derecha el documento oficial, artículo o informe formal con cabecera de organismo (ONU, OEA, ONG), fecha, titular editorial, imagen/gráfico incrustado, cita textual y rotulador fluorescente neón animado sobre las cifras y conclusiones clave.",
                    "sfx": "whoosh",
                    "animation": "smooth_rise",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "headline": "CULTIVOS DE COCA ALCANZAN MÁXIMO HISTÓRICO",
                        "excerpt": "De acuerdo con el informe oficial de la ONU (UNODC), los cultivos de coca alcanzaron un récord de 253.000 hectáreas, mientras los combatientes ilegales crecieron un 90% según Ideas para la Paz.",
                        "institution": "UNODC · NACIONES UNIDAS",
                        "date_str": "INFORME JUNIO 2026",
                        "highlight_phrase": "récord de 253.000 hectáreas",
                        "stat_value": "+90%",
                        "stat_label": "Combatientes Ilegales",
                        "stat_value2": "253K ha",
                        "stat_label2": "Cultivos Totales",
                        "tag": "EVIDENCIA DOCUMENTAL",
                        "presenter_name": "ANÁLISIS DOCUMENTAL"
                    },
                },
                {
                    "id": "person_spotlight",
                    "name": "Tarjeta Destacada de Persona / Protagonista con Foto (Spotlight Callout)",
                    "description": "Tarjeta flotante de glassmorphism con marco circular brillante para foto o avatar real de la persona, insignia de protagonista/mencionado, nombre en tipografía negrita y su cargo o rol oficial.",
                    "sfx": "pop",
                    "animation": "smooth_rise",
                    "default_variant": "orange_noir",
                    "sample_params": {
                        "name": "Gustavo Petro",
                        "role": "Presidente de Colombia",
                        "tag": "PROTAGONISTA"
                    },
                },
            ] + VisualTemplatesLibrary.get_extra_catalog()
        }
