"""
Visual Templates Pack Extra (AetherCut Pro Design System)
Plantillas reutilizables y parametrizables: ranking, gráfico de barras/línea,
perfil, pros/contras, cuenta atrás y dashboard de métricas (heatmap).

Se integran en VisualTemplatesLibrary mediante mezcla (mixin) sin tocar las
plantillas existentes. Todas usan solo claves comunes de THEME_PALETTES, por lo
que funcionan con cualquier variante (oscura o clara).
"""

from __future__ import annotations

import html as _html
from typing import Any, Dict, List, Optional

# Fuentes: se importa de forma perezosa para evitar import circular
def _fonts() -> str:
    from core.visual_templates import HTML_FONTS
    return HTML_FONTS


def _e(v: Any) -> str:
    return _html.escape(str(v if v is not None else ""))


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).replace("%", "").replace(",", ".").strip())
    except Exception:
        return default


class ExtraTemplatesMixin:
    """Pack de plantillas reutilizables. Requiere self.get_palette()."""

    # ------------------------------------------------------------------ base
    def _x_page(self, p: Dict[str, str], tag: str, title: str, inner: str,
                footer: str = "", extra_css: str = "", width: int = 900) -> str:
        tag_html = f'<span class="x-tag">{_e(tag)}</span>' if tag else ""
        title_html = f'<h1 class="x-title">{_e(title)}</h1>' if title else ""
        foot_html = f'<div class="x-foot">{_e(footer)}</div>' if footer else ""
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{_fonts()}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: transparent; display: flex; align-items: center;
         justify-content: center; padding: 40px; font-family: 'Inter', sans-serif; }}
  .x-card {{
    width: {width}px; padding: 34px 38px 28px; border-radius: 28px;
    background: {p['card_bg']}; color: {p['text']};
    border: 1.5px solid {p['border']};
    box-shadow: 0 30px 70px rgba(0,0,0,.45), 0 0 40px {p['glow']},
                inset 0 1px 0 rgba(255,255,255,.08);
    position: relative; overflow: hidden;
  }}
  .x-card::before {{
    content: ""; position: absolute; inset: -40% -20% auto auto; width: 420px; height: 420px;
    background: radial-gradient(circle, {p['glow']} 0%, transparent 70%); opacity: .55; pointer-events: none;
  }}
  .x-head {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 26px; position: relative; }}
  .x-tag {{
    align-self: flex-start; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 800;
    letter-spacing: .16em; text-transform: uppercase; color: {p['accent']};
    background: {p['pill_bg']}; border: 1px solid {p['border']}; padding: 5px 14px; border-radius: 999px;
  }}
  .x-title {{ font-family: 'Outfit', sans-serif; font-size: 40px; font-weight: 800; line-height: 1.12;
             letter-spacing: -.02em; color: {p['text']}; }}
  .x-foot {{ margin-top: 24px; padding-top: 16px; font-family: 'JetBrains Mono', monospace; font-size: 13px;
            letter-spacing: .08em; color: {p['text_sub']}; border-top: 1px solid color-mix(in srgb, {p['text']} 12%, transparent); }}
  .x-track {{ background: color-mix(in srgb, {p['text']} 10%, transparent); border-radius: 999px; overflow: hidden; }}
  .x-fill {{ height: 100%; border-radius: 999px; background: {p['accent_gradient']}; box-shadow: 0 0 14px {p['glow']}; }}
  .x-mono {{ font-family: 'JetBrains Mono', monospace; }}
  {extra_css}
</style></head>
<body><div class="x-card">
  <div class="x-head">{tag_html}{title_html}</div>
  {inner}
  {foot_html}
</div></body></html>"""

    # --------------------------------------------------------------- ranking
    def build_ranking_bars_html(self, title: str = "TOP 5 HERRAMIENTAS IA", tag: str = "RANKING 2026",
                                items: Optional[List[Dict[str, Any]]] = None,
                                footer: str = "", variant: str = "orange_noir") -> str:
        p = self.get_palette(variant)
        items = items or [
            {"label": "Claude Code", "value": 96, "display": "96%"},
            {"label": "Cursor", "value": 88, "display": "88%"},
            {"label": "Copilot", "value": 74, "display": "74%"},
            {"label": "Windsurf", "value": 61, "display": "61%"},
            {"label": "Aider", "value": 47, "display": "47%"},
        ]
        mx = max([_num(i.get("value")) for i in items] + [1])
        rows = ""
        for idx, it in enumerate(items[:7], 1):
            pct = max(4, min(100, _num(it.get("value")) / mx * 100))
            disp = it.get("display") or it.get("value")
            lead = " lead" if idx == 1 else ""
            rows += f"""<div class="rk-row{lead}"><div class="rk-pos">{idx:02d}</div>
              <div class="rk-body"><div class="rk-top"><span class="rk-label">{_e(it.get('label'))}</span>
              <span class="rk-val x-mono">{_e(disp)}</span></div>
              <div class="x-track" style="height:14px"><div class="x-fill" style="width:{pct:.1f}%"></div></div></div></div>"""
        css = f"""
          .rk-row {{ display:flex; align-items:center; gap:18px; margin-bottom:16px; opacity:.88; }}
          .rk-row.lead {{ opacity:1; }}
          .rk-pos {{ font-family:'Outfit',sans-serif; font-size:30px; font-weight:900; width:54px; color:{p['text_sub']}; }}
          .rk-row.lead .rk-pos {{ background:{p['accent_gradient']}; -webkit-background-clip:text; color:transparent; }}
          .rk-body {{ flex:1; }} .rk-top {{ display:flex; justify-content:space-between; margin-bottom:8px; }}
          .rk-label {{ font-size:22px; font-weight:700; }} .rk-val {{ font-size:20px; font-weight:800; color:{p['accent']}; }}
        """
        return self._x_page(p, tag, title, rows, footer, css)

    # ----------------------------------------------------------- bar / line
    def build_chart_bars_html(self, title: str = "CRECIMIENTO MENSUAL", tag: str = "GRÁFICO",
                              series: Optional[List[Dict[str, Any]]] = None, chart_type: str = "bar",
                              highlight_index: int = -1, footer: str = "",
                              variant: str = "orange_noir") -> str:
        p = self.get_palette(variant)
        series = series or [{"label": "Ene", "value": 18}, {"label": "Feb", "value": 31},
                            {"label": "Mar", "value": 27}, {"label": "Abr", "value": 52},
                            {"label": "May", "value": 74}, {"label": "Jun", "value": 96}]
        n = len(series)
        mx = max([_num(s.get("value")) for s in series] + [1])
        hi = highlight_index if 0 <= highlight_index < n else n - 1
        W, H = 820, 300
        if (chart_type or "bar").lower() == "line":
            step = W / max(n - 1, 1)
            pts = [(i * step, H - (_num(s.get("value")) / mx) * (H - 30) - 10) for i, s in enumerate(series)]
            line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            area = f"0,{H} {line} {W},{H}"
            dots = "".join(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{9 if i == hi else 5}" fill="{p["accent"]}" '
                f'stroke="{p["card_bg"]}" stroke-width="3"/>'
                f'<text x="{x:.1f}" y="{y - 18:.1f}" text-anchor="middle" fill="{p["text"]}" '
                f'font-family="JetBrains Mono" font-size="16" font-weight="800">{_e(series[i].get("value"))}</text>'
                for i, (x, y) in enumerate(pts))
            labels = "".join(f'<span>{_e(s.get("label"))}</span>' for s in series)
            chart = f"""<svg viewBox="0 -30 {W} {H + 40}" width="{W}" height="{H + 40}" style="overflow:visible">
              <defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="{p['accent']}" stop-opacity=".45"/><stop offset="1" stop-color="{p['accent']}" stop-opacity="0"/></linearGradient></defs>
              <polygon points="{area}" fill="url(#ar)"/>
              <polyline points="{line}" fill="none" stroke="{p['accent']}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>
              {dots}</svg><div class="ch-labels">{labels}</div>"""
        else:
            cols = ""
            for i, s in enumerate(series):
                h = max(6, _num(s.get("value")) / mx * 100)
                cls = " hi" if i == hi else ""
                cols += f"""<div class="ch-col"><span class="ch-val x-mono">{_e(s.get('value'))}</span>
                  <div class="ch-bar{cls}" style="height:{h:.1f}%"></div><span class="ch-lab">{_e(s.get('label'))}</span></div>"""
            chart = f'<div class="ch-bars">{cols}</div>'
        css = f"""
          .ch-bars {{ display:flex; align-items:flex-end; gap:16px; height:340px; }}
          .ch-col {{ flex:1; height:100%; display:flex; flex-direction:column; justify-content:flex-end; align-items:center; gap:8px; }}
          .ch-bar {{ width:100%; border-radius:12px 12px 4px 4px; background:color-mix(in srgb, {p['accent']} 35%, transparent); }}
          .ch-bar.hi {{ background:{p['accent_gradient']}; box-shadow:0 0 24px {p['glow']}; }}
          .ch-val {{ font-size:17px; font-weight:800; color:{p['text']}; }}
          .ch-lab {{ font-size:15px; font-weight:600; color:{p['text_sub']}; }}
          .ch-labels {{ display:flex; justify-content:space-between; margin-top:12px; font-size:15px; font-weight:600; color:{p['text_sub']}; }}
        """
        return self._x_page(p, tag, title, chart, footer, css)

    # ---------------------------------------------------------------- perfil
    def build_profile_card_html(self, name: str = "Andrej Karpathy", role: str = "Ex-director de IA en Tesla",
                                handle: str = "@karpathy", bio: str = "Cofundador de OpenAI. Divulgador referente de redes neuronales.",
                                stats: Optional[List[Dict[str, Any]]] = None, tag: str = "PERFIL",
                                avatar_url: str = "", variant: str = "orange_noir") -> str:
        p = self.get_palette(variant)
        stats = stats or [{"value": "1.2M", "label": "Seguidores"}, {"value": "340", "label": "Papers"}, {"value": "15 años", "label": "Experiencia"}]
        initials = "".join(w[0] for w in (name or "?").split()[:2]).upper()
        avatar = (f'<img src="{_e(avatar_url)}" class="pf-av" />' if avatar_url
                  else f'<div class="pf-av pf-ini">{_e(initials)}</div>')
        st = "".join(f'<div class="pf-st"><b class="x-mono">{_e(s.get("value"))}</b><span>{_e(s.get("label"))}</span></div>' for s in stats[:4])
        inner = f"""<div class="pf-main">{avatar}<div class="pf-id">
          <div class="pf-name">{_e(name)}</div><div class="pf-role">{_e(role)}</div>
          <div class="pf-handle x-mono">{_e(handle)}</div></div></div>
          <p class="pf-bio">{_e(bio)}</p><div class="pf-stats">{st}</div>"""
        css = f"""
          .pf-main {{ display:flex; align-items:center; gap:26px; margin-bottom:20px; }}
          .pf-av {{ width:120px; height:120px; border-radius:50%; object-fit:cover; border:3px solid {p['accent']};
                   box-shadow:0 0 28px {p['glow']}; flex-shrink:0; }}
          .pf-ini {{ display:flex; align-items:center; justify-content:center; background:{p['accent_gradient']};
                    font-family:'Outfit'; font-size:46px; font-weight:900; color:#fff; }}
          .pf-name {{ font-family:'Outfit'; font-size:38px; font-weight:800; letter-spacing:-.02em; }}
          .pf-role {{ font-size:20px; color:{p['text_sub']}; margin-top:4px; font-weight:500; }}
          .pf-handle {{ font-size:16px; color:{p['accent']}; margin-top:8px; font-weight:700; }}
          .pf-bio {{ font-size:21px; line-height:1.45; color:{p['text_sub']}; margin-bottom:22px; }}
          .pf-stats {{ display:flex; gap:14px; }}
          .pf-st {{ flex:1; padding:14px 18px; border-radius:16px; background:{p['pill_bg']}; border:1px solid {p['border']}; display:flex; flex-direction:column; gap:4px; }}
          .pf-st b {{ font-size:26px; color:{p['text']}; }} .pf-st span {{ font-size:14px; color:{p['text_sub']}; font-weight:600; letter-spacing:.06em; text-transform:uppercase; }}
        """
        return self._x_page(p, tag, "", inner, "", css, width=860)

    # ------------------------------------------------------------ pros/cons
    def build_pros_cons_html(self, title: str = "¿VALE LA PENA?", tag: str = "VEREDICTO",
                             pros: Optional[List[str]] = None, cons: Optional[List[str]] = None,
                             footer: str = "", variant: str = "orange_noir") -> str:
        p = self.get_palette(variant)
        pros = pros or ["Ahorra horas de edición", "100% local y privado", "Resultados consistentes"]
        cons = cons or ["Requiere GPU decente", "Curva de aprendizaje inicial"]

        def col(items, ok):
            icon, color = ("✓", "#10b981") if ok else ("✕", "#ef4444")
            lis = "".join(f'<li><i style="color:{color};border-color:{color}">{icon}</i><span>{_e(t)}</span></li>' for t in items[:5])
            head = "A FAVOR" if ok else "EN CONTRA"
            return f'<div class="pc-col"><div class="pc-h" style="color:{color}">{head}</div><ul>{lis}</ul></div>'

        inner = f'<div class="pc-grid">{col(pros, True)}{col(cons, False)}</div>'
        css = f"""
          .pc-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
          .pc-col {{ padding:22px; border-radius:20px; background:color-mix(in srgb, {p['text']} 5%, transparent); border:1px solid color-mix(in srgb, {p['text']} 12%, transparent); }}
          .pc-h {{ font-family:'JetBrains Mono'; font-size:15px; font-weight:800; letter-spacing:.18em; margin-bottom:16px; }}
          ul {{ list-style:none; display:flex; flex-direction:column; gap:14px; }}
          li {{ display:flex; gap:12px; align-items:flex-start; font-size:21px; font-weight:600; line-height:1.3; }}
          li i {{ font-style:normal; width:28px; height:28px; border:2px solid; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:15px; font-weight:900; flex-shrink:0; margin-top:1px; }}
        """
        return self._x_page(p, tag, title, inner, footer, css, width=980)

    # ------------------------------------------------------------- cuenta atrás
    def build_countdown_html(self, title: str = "LANZAMIENTO OFICIAL", tag: str = "CUENTA ATRÁS",
                             days: Any = "03", hours: Any = "14", minutes: Any = "27", seconds: Any = "09",
                             date_label: str = "15 · NOV · 2026", footer: str = "",
                             variant: str = "orange_noir") -> str:
        p = self.get_palette(variant)
        units = [(days, "DÍAS"), (hours, "HORAS"), (minutes, "MIN"), (seconds, "SEG")]
        boxes = "".join(
            f'<div class="cd-box"><b class="x-mono">{_e(str(v).zfill(2))}</b><span>{lab}</span></div>'
            for v, lab in units)
        inner = f'<div class="cd-row">{boxes}</div><div class="cd-date x-mono">{_e(date_label)}</div>'
        css = f"""
          .cd-row {{ display:flex; gap:16px; }}
          .cd-box {{ flex:1; padding:26px 8px 18px; border-radius:22px; text-align:center;
                    background:linear-gradient(180deg, {p['pill_bg']}, transparent); border:1px solid {p['border']}; }}
          .cd-box b {{ display:block; font-size:84px; font-weight:800; line-height:1; background:{p['accent_gradient']};
                      -webkit-background-clip:text; color:transparent; }}
          .cd-box span {{ display:block; margin-top:10px; font-size:14px; font-weight:800; letter-spacing:.2em; color:{p['text_sub']}; }}
          .cd-date {{ margin-top:22px; text-align:center; font-size:22px; font-weight:800; letter-spacing:.22em; color:{p['text']}; }}
        """
        return self._x_page(p, tag, title, inner, footer, css, width=860)

    # -------------------------------------------------------------- dashboard
    def build_metrics_dashboard_html(self, title: str = "PANEL DE RENDIMIENTO", tag: str = "DASHBOARD",
                                     metrics: Optional[List[Dict[str, Any]]] = None,
                                     heat: Optional[List[float]] = None, heat_label: str = "Actividad semanal",
                                     footer: str = "", variant: str = "orange_noir") -> str:
        p = self.get_palette(variant)
        metrics = metrics or [
            {"label": "Vistas", "value": "1.8M", "delta": "+24%"},
            {"label": "Retención", "value": "84%", "delta": "+9%"},
            {"label": "CTR", "value": "11.2%", "delta": "+3.1%"},
            {"label": "Suscriptores", "value": "+12K", "delta": "+18%"},
        ]
        heat = heat or [.1, .3, .5, .8, .4, .2, .6, .9, 1, .7, .3, .5, .8, .6,
                        .2, .4, .7, .9, .5, .3, .6, .8, 1, .7, .4, .2, .5, .9]
        tiles = ""
        for m in metrics[:6]:
            d = str(m.get("delta", ""))
            neg = d.strip().startswith("-")
            col = "#ef4444" if neg else "#10b981"
            dh = f'<em style="color:{col}">{"▼" if neg else "▲"} {_e(d.lstrip("+-"))}</em>' if d else ""
            tiles += f'<div class="db-t"><span>{_e(m.get("label"))}</span><b class="x-mono">{_e(m.get("value"))}</b>{dh}</div>'
        cells = "".join(
            f'<i style="background:color-mix(in srgb, {p["accent"]} {max(8, min(100, _num(h) * 100)):.0f}%, transparent)"></i>'
            for h in heat[:42])
        inner = f"""<div class="db-grid">{tiles}</div>
          <div class="db-hl">{_e(heat_label)}</div><div class="db-heat">{cells}</div>"""
        css = f"""
          .db-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; margin-bottom:24px; }}
          .db-t {{ padding:18px 22px; border-radius:18px; background:{p['pill_bg']}; border:1px solid {p['border']}; display:flex; flex-direction:column; gap:6px; }}
          .db-t span {{ font-size:14px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:{p['text_sub']}; }}
          .db-t b {{ font-size:40px; font-weight:800; color:{p['text']}; }}
          .db-t em {{ font-style:normal; font-family:'JetBrains Mono'; font-size:16px; font-weight:800; }}
          .db-hl {{ font-family:'JetBrains Mono'; font-size:13px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; color:{p['text_sub']}; margin-bottom:12px; }}
          .db-heat {{ display:grid; grid-template-columns:repeat(14,1fr); gap:7px; }}
          .db-heat i {{ aspect-ratio:1; border-radius:6px; display:block; }}
        """
        return self._x_page(p, tag, title, inner, footer, css, width=900)

    # ------------------------------------------------------------- dispatcher
    EXTRA_TEMPLATE_ALIASES = {
        "ranking_bars": ("ranking_bars", "ranking", "top_list", "top5", "top_5"),
        "chart_bars": ("chart_bars", "chart", "bar_chart", "line_chart", "grafico"),
        "profile_card": ("profile_card", "profile", "perfil", "persona", "person_card"),
        "pros_cons": ("pros_cons", "pros_contras", "checklist_pc", "veredicto_pc"),
        "countdown": ("countdown", "cuenta_atras", "timer", "launch_date"),
        "metrics_dashboard": ("metrics_dashboard", "dashboard", "heatmap", "panel_metricas"),
    }

    def build_extra_template_html(self, tmpl: str, params: Dict[str, Any], variant: str) -> Optional[str]:
        """Devuelve HTML si `tmpl` pertenece al pack extra; si no, None."""
        key = next((k for k, al in self.EXTRA_TEMPLATE_ALIASES.items() if tmpl in al), None)
        if not key:
            return None
        g = params.get
        tag, title, foot = g("tag"), g("title") or g("headline"), g("footer") or g("footer_note") or ""
        if key == "ranking_bars":
            return self.build_ranking_bars_html(title or "TOP 5 HERRAMIENTAS IA", tag or "RANKING 2026", g("items"), foot, variant)
        if key == "chart_bars":
            return self.build_chart_bars_html(title or "CRECIMIENTO MENSUAL", tag or "GRÁFICO", g("series"),
                                              g("chart_type") or ("line" if tmpl == "line_chart" else "bar"),
                                              int(g("highlight_index", -1)), foot, variant)
        if key == "profile_card":
            return self.build_profile_card_html(
                g("name") or title or "Andrej Karpathy", g("role") or g("subtitle") or "Ex-director de IA en Tesla",
                g("handle") or "@karpathy", g("bio") or g("body") or "Cofundador de OpenAI. Divulgador referente de redes neuronales.",
                g("stats"), tag or "PERFIL", g("avatar_url") or "", variant)
        if key == "pros_cons":
            return self.build_pros_cons_html(title or "¿VALE LA PENA?", tag or "VEREDICTO", g("pros"), g("cons"), foot, variant)
        if key == "countdown":
            return self.build_countdown_html(title or "LANZAMIENTO OFICIAL", tag or "CUENTA ATRÁS",
                                             g("days", "03"), g("hours", "14"), g("minutes", "27"), g("seconds", "09"),
                                             g("date_label") or "15 · NOV · 2026", foot, variant)
        return self.build_metrics_dashboard_html(title or "PANEL DE RENDIMIENTO", tag or "DASHBOARD", g("metrics"),
                                                 g("heat"), g("heat_label") or "Actividad semanal", foot, variant)

    @staticmethod
    def get_extra_catalog() -> List[Dict[str, Any]]:
        return [
            {"id": "ranking_bars", "name": "Ranking Top N con Barras", "description": "Lista ordenada con barras proporcionales; el #1 destacado en gradiente.",
             "sfx": "whoosh", "animation": "stagger_bars", "default_variant": "orange_noir",
             "sample_params": {"title": "TOP 5 HERRAMIENTAS IA", "items": [{"label": "Claude Code", "value": 96, "display": "96%"}, {"label": "Cursor", "value": 88, "display": "88%"}]}},
            {"id": "chart_bars", "name": "Gráfico de Barras / Línea", "description": "Serie temporal en barras o línea con área; punto final resaltado. chart_type: bar|line.",
             "sfx": "chime", "animation": "grow_up", "default_variant": "orange_noir",
             "sample_params": {"title": "CRECIMIENTO MENSUAL", "chart_type": "line", "series": [{"label": "Ene", "value": 18}, {"label": "Feb", "value": 52}]}},
            {"id": "profile_card", "name": "Tarjeta de Perfil / Persona", "description": "Avatar (o iniciales), cargo, handle, bio y hasta 4 estadísticas.",
             "sfx": "pop", "animation": "spring_bounce", "default_variant": "orange_noir",
             "sample_params": {"name": "Andrej Karpathy", "role": "Ex-director de IA en Tesla", "handle": "@karpathy"}},
            {"id": "pros_cons", "name": "Pros y Contras", "description": "Dos columnas a favor / en contra con iconos de verificación.",
             "sfx": "impact", "animation": "convergence_pop", "default_variant": "orange_noir",
             "sample_params": {"title": "¿VALE LA PENA?", "pros": ["Ahorra tiempo"], "cons": ["Requiere GPU"]}},
            {"id": "countdown", "name": "Cuenta Atrás / Fecha", "description": "Cuatro bloques días/horas/min/seg con fecha clave.",
             "sfx": "alert", "animation": "elastic_scale_pop", "default_variant": "orange_noir",
             "sample_params": {"title": "LANZAMIENTO OFICIAL", "days": "03", "hours": "14", "date_label": "15 · NOV · 2026"}},
            {"id": "metrics_dashboard", "name": "Dashboard de Métricas + Mapa de Calor", "description": "Hasta 6 KPIs con delta y mapa de calor de actividad.",
             "sfx": "whoosh", "animation": "smooth_rise", "default_variant": "orange_noir",
             "sample_params": {"title": "PANEL DE RENDIMIENTO", "metrics": [{"label": "Vistas", "value": "1.8M", "delta": "+24%"}]}},
        ]
