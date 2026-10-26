"""Sistema editorial de tarjetas para AetherCut.

Objetivo: sustituir el look "AI dashboard" (glassmorphism, glows, gradientes
neón, pills, badges en mayúsculas) por un lenguaje editorial sobrio:

- Panel casi opaco, borde de acento a la izquierda, sin blur ni glow.
- Tipografía con jerarquía fija: kicker pequeno, dato/titular grande, fuente.
- Máximo 7 palabras en el titular y una sola idea por tarjeta.
- Cero emojis. Cero inventar fuentes: si no hay fuente, no se muestra.

La IA sigue decidiendo QUÉ decir (params), pero CÓMO se ve queda fijo aquí.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from string import Template
from typing import Any, Dict, Optional

# Alias desde los nombres que ya usa el director/SceneEngine.
TEMPLATE_ALIASES: Dict[str, str] = {
    "stat_counter": "data_hero",
    "stat_card": "data_hero",
    "metrics_dashboard": "data_hero",
    "versus_split": "versus",
    "versus": "versus",
    "vs": "versus",
    "quote_evidence": "quote",
    "quote": "quote",
    "citation": "quote",
    "tech_card": "text_card",
    "tech_header": "text_card",
    "alert_banner": "text_card",
    "alert": "text_card",
    "warning": "text_card",
    "bento": "text_card",
    "auto": "text_card",
    "text_card": "text_card",
    "lower_third": "lower_third",
    "source_chip": "lower_third",
    "step_badge": "step",
    "step": "step",
    "phase": "step",
    "timeline_milestone": "timeline",
    "timeline": "timeline",
    "cronologia": "timeline",
    # Todas las plantillas antiguas pasan al sistema editorial (sin pills, iconos ni HUD).
    "verdict_badge": "text_card",
    "document_evidence_split": "text_card",
    "document_evidence": "text_card",
    "split_evidence": "text_card",
    "platzi_evidence": "text_card",
    "informe_split": "text_card",
    "newspaper_clipping": "quote",
    "newspaper": "quote",
    "press_clipping": "quote",
    "titular_prensa": "quote",
    "social_post": "quote",
    "tweet": "quote",
    "x_post": "quote",
    "comunicado_social": "quote",
    "terminal_hud": "text_card",
    "terminal": "text_card",
    "cli_console": "text_card",
    "code_terminal": "text_card",
    "consola_codigo": "text_card",
    "spec_matrix": "text_card",
    "benchmark_table": "versus",
    "matrix_table": "versus",
    "comparativa_metricas": "versus",
    "benchmark": "versus",
    "workflow_diagram": "text_card",
    "workflow": "text_card",
    "router_pattern": "text_card",
    "agent_graph": "text_card",
    "nodos_agente": "text_card",
    "diagrama_flujo": "text_card",
    "map": "text_card",
    "geointel_map": "text_card",
    "person_spotlight": "lower_third",
    "hitos": "timeline",
}

KICKERS = {
    "data_hero": "DATO",
    "quote": "CITA",
    "versus": "COMPARATIVA",
    "timeline": "CRONOLOGÍA",
    "step": "PASO",
    "lower_third": "FUENTE",
    "text_card": "",
}

_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")
_WS_RE = re.compile(r"\s+")


def _clean(value: Any, limit: int = 0) -> str:
    text = _EMOJI_RE.sub("", str(value or ""))
    text = _WS_RE.sub(" ", text).strip(" -–—·•|")
    if limit and len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = (cut or text[:limit]).rstrip(".,;:") + "…"
    return text


def _font_size(text: str, base: int, floor: int, per_char: float = 1.0) -> int:
    if not text:
        return base
    size = int(base - max(0, len(text) - 18) * per_char)
    return max(floor, size)


def _palette(variant: str) -> Dict[str, str]:
    variant = (variant or "").lower()
    light = any(k in variant for k in ("light", "cream", "paper", "frosted_white"))
    if light:
        return {
            "panel": "rgba(246, 243, 236, 0.97)",
            "text": "#141414",
            "muted": "#5b5b5b",
            "rule": "rgba(20, 20, 20, 0.16)",
            "accent": "#D9480F",
        }
    return {
        "panel": "rgba(10, 11, 13, 0.96)",
        "text": "#F7F5F0",
        "muted": "#A8A29E",
        "rule": "rgba(255, 255, 255, 0.14)",
        "accent": "#F2542D",
    }


_PAGE = Template(
    """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { background: transparent; }
  body {
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; padding: 40px;
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .card {
    width: $width; max-width: 90vw;
    background: $panel;
    border-left: 7px solid $accent;
    border-top: 1px solid $rule;
    border-right: 1px solid $rule;
    border-bottom: 1px solid $rule;
    padding: 40px 48px 34px 48px;
    color: $text;
    display: flex; flex-direction: column; gap: 14px;
  }
  .kicker {
    font-size: 13px; font-weight: 700; letter-spacing: .22em;
    text-transform: uppercase; color: $accent;
  }
  .stat {
    font-size: $stat_size; line-height: .95; font-weight: 800;
    letter-spacing: -.045em; font-variant-numeric: tabular-nums;
  }
  .headline {
    font-size: $headline_size; line-height: 1.12; font-weight: 700;
    letter-spacing: -.015em;
  }
  .body {
    font-size: 21px; line-height: 1.45; color: $muted; font-weight: 500;
  }
  .quote {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 40px; line-height: 1.22; font-weight: 400; font-style: italic;
    letter-spacing: -.01em;
  }
  .foot {
    margin-top: 10px; padding-top: 14px; border-top: 1px solid $rule;
    font-size: 14px; letter-spacing: .04em; color: $muted; font-weight: 600;
    text-transform: uppercase;
  }
  .vs-grid { display: grid; grid-template-columns: 1fr 1px 1fr; gap: 26px; align-items: center; }
  .vs-div { background: $rule; height: 100%; min-height: 90px; }
  .vs-name { font-size: 24px; font-weight: 700; line-height: 1.2; }
  .vs-value { font-size: 54px; font-weight: 800; letter-spacing: -.03em; margin-top: 8px; }
  .vs-tag { font-size: 13px; letter-spacing: .18em; text-transform: uppercase; color: $accent; font-weight: 700; }
  .tl { display: flex; flex-direction: column; gap: 12px; }
  .tl-row { display: grid; grid-template-columns: 120px 1fr; gap: 18px; align-items: baseline; }
  .tl-year { font-size: 22px; font-weight: 800; color: $accent; font-variant-numeric: tabular-nums; }
  .tl-text { font-size: 20px; line-height: 1.4; }
  .step-num { font-size: 92px; font-weight: 800; line-height: .9; color: $accent; letter-spacing: -.05em; }
  .name { font-size: 38px; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; }
  .role { font-size: 19px; color: $muted; font-weight: 600; }
</style></head>
<body><div class="card">$inner</div></body></html>"""
)


def _timeline_items(params: Dict[str, Any]) -> list:
    raw = params.get("items") or params.get("milestones")
    if isinstance(raw, list) and raw:
        return raw
    body = _clean(params.get("body") or params.get("subtitle") or "", 240)
    parts = [p.strip() for p in re.split(r"[|•\n;]+", body) if p.strip()]
    return parts[:4]


def build_html(kind: str, params: Dict[str, Any], variant: str = "orange_noir", vertical: bool = True) -> str:
    p = _palette(variant)
    width = 880 if vertical else 1060

    headline = _clean(
        params.get("headline") or params.get("title") or params.get("step_title")
        or params.get("source_name") or params.get("side_a") or params.get("author_name")
        or params.get("command") or "",
        92,
    )
    body = _clean(
        params.get("body") or params.get("subtitle") or params.get("stat_label")
        or params.get("excerpt") or params.get("post_text") or params.get("body_lead")
        or params.get("note") or "",
        190,
    )
    stat = _clean(params.get("stat_value") or params.get("stat_a") or params.get("step_number") or params.get("stat") or "", 14)
    source = _clean(
        params.get("source") or params.get("citation") or params.get("institution")
        or params.get("date_str") or params.get("handle") or params.get("newspaper") or "",
        70,
    )
    kicker = KICKERS.get(kind, "")

    head_size = _font_size(headline, 44, 28, 0.55)
    stat_size = _font_size(stat, 118, 64, 5.0)
    foot = f'<div class="foot">{source}</div>' if source else ""

    if kind == "quote" and not (params.get("quote_text") or body or headline):
        kind = "text_card"
        kicker = ""

    if kind == "data_hero":
        inner = (
            (f'<div class="kicker">{kicker}</div>' if kicker else "")
            + (f'<div class="stat">{stat}</div>' if stat else "")
            + (f'<div class="headline" style="font-size:{head_size}px">{headline}</div>' if headline else "")
            + (f'<div class="body">{body}</div>' if body else "")
            + foot
        )
    elif kind == "quote":
        quote = _clean(params.get("quote_text") or body or headline, 210)
        author = _clean(params.get("source") or params.get("author") or source, 70)
        inner = (
            (f'<div class="kicker">{kicker}</div>' if kicker else "")
            + f'<div class="quote">“{quote}”</div>'
            + (f'<div class="foot">{author}</div>' if author else "")
        )
    elif kind == "versus":
        a = _clean(params.get("side_a") or headline, 46)
        b = _clean(params.get("side_b") or params.get("secondary_entity") or body, 46)
        va = _clean(params.get("stat_a") or "", 14)
        vb = _clean(params.get("stat_b") or "", 14)
        if not a or not b:
            inner = (
                (f'<div class="headline" style="font-size:{head_size}px">{a or headline}</div>' if (a or headline) else "")
                + (f'<div class="body">{body}</div>' if body else "")
                + foot
            )
        else:
            inner = (
                (f'<div class="kicker">{kicker}</div>' if kicker else "")
                + '<div class="vs-grid">'
                + f'<div><div class="vs-name">{a}</div>' + (f'<div class="vs-value">{va}</div>' if va else "") + "</div>"
                + '<div class="vs-div"></div>'
                + f'<div><div class="vs-name">{b}</div>' + (f'<div class="vs-value">{vb}</div>' if vb else "") + "</div>"
                + "</div>"
                + foot
            )
    elif kind == "timeline":
        items = _timeline_items(params)
        rows = []
        for item in items:
            if isinstance(item, dict):
                year = _clean(item.get("year") or item.get("date") or "", 12)
                text = _clean(item.get("text") or item.get("label") or item.get("title") or "", 90)
            else:
                text = _clean(item, 90)
                match = re.match(r"^(\d{3,4}[^:\-–—]*)[:\-–—]\s*(.+)$", text)
                year, text = (match.group(1).strip(), match.group(2).strip()) if match else ("", text)
            rows.append(f'<div class="tl-row"><div class="tl-year">{year}</div><div class="tl-text">{text}</div></div>')
        if len(rows) < 2:
            # Sin hitos suficientes no fingimos una cronología: se usa el layout de texto.
            inner = (
                (f'<div class="headline" style="font-size:{head_size}px">{headline}</div>' if headline else "")
                + (f'<div class="body">{body}</div>' if body else "")
                + foot
            )
        else:
            inner = (
                (f'<div class="kicker">{kicker}</div>' if kicker else "")
                + '<div class="tl">' + "".join(rows) + "</div>"
                + foot
            )
    elif kind == "step":
        inner = (
            (f'<div class="kicker">{kicker}</div>' if kicker else "")
            + (f'<div class="step-num">{stat or "01"}</div>' if stat else "")
            + (f'<div class="headline" style="font-size:{head_size}px">{headline}</div>' if headline else "")
            + (f'<div class="body">{body}</div>' if body else "")
            + foot
        )
    elif kind == "lower_third":
        kicker = _clean(params.get("tag") or "", 26) or kicker
        role = _clean(params.get("subtitle") or body or "", 70)
        inner = (
            (f'<div class="kicker">{kicker}</div>' if kicker else "")
            + (f'<div class="name">{headline}</div>' if headline else "")
            + (f'<div class="role">{role}</div>' if role else "")
            + foot
        )
    else:  # text_card
        inner = (
            (f'<div class="kicker">{kicker}</div>' if kicker else "")
            + (f'<div class="headline" style="font-size:{head_size}px">{headline}</div>' if headline else "")
            + (f'<div class="body">{body}</div>' if body else "")
            + foot
        )

    # width se resuelve en CSS con unidades; el Template evita chocar con las llaves.
    html = _PAGE.substitute(
        width=f"{width}px",
        panel=p["panel"],
        text=p["text"],
        muted=p["muted"],
        rule=p["rule"],
        accent=p["accent"],
        stat_size=f"{stat_size}px",
        headline_size=f"{head_size}px",
        inner=inner,
    )
    return html


def render_editorial(
    template_name: str,
    out_png: Path,
    params: Optional[Dict[str, Any]] = None,
    variant: str = "orange_noir",
    vertical: bool = True,
    browser_bin: Optional[str] = None,
) -> Optional[Path]:
    """Renderiza una tarjeta editorial. Devuelve None si el tipo no está soportado."""
    key = (template_name or "").lower().strip()
    kind = TEMPLATE_ALIASES.get(key)
    if not kind:
        return None

    try:
        from core.web_card_renderer import _get_browser_bin
    except Exception:
        _get_browser_bin = lambda: None  # type: ignore

    bin_path = browser_bin or _get_browser_bin()
    if not bin_path:
        return None

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    html_path = out_png.with_suffix(".html")
    html_path.write_text(
        build_html(kind, params or {}, variant=variant, vertical=vertical),
        encoding="utf-8",
    )

    win_size = "1200,1500" if vertical else "1500,1100"
    args = [
        bin_path,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--default-background-color=00000000",
        f"--screenshot={out_png.resolve()}",
        f"--window-size={win_size}",
        html_path.resolve().as_uri(),
    ]
    try:
        subprocess.run(args, capture_output=True, check=True, timeout=20)
    except Exception:
        return None

    if not out_png.exists() or out_png.stat().st_size < 500:
        return None

    try:
        from core.visual_templates import VisualTemplatesLibrary
        VisualTemplatesLibrary._crop_transparent(out_png)
    except Exception:
        pass

    return out_png
