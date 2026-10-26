"""Tipografía cinética de títulos y años flotantes (sin cards).

Resuelve dos problemas del sistema anterior:
1. Las palabras se apilaban muy separadas: cada una era un PNG recortado con su
   halo de sombra, así que el recorte dejaba aire enorme entre filas.
   Ahora TODAS las capas son del tamaño del lienzo y las palabras se maquetan
   juntas en un mismo bloque HTML (interlineado compacto, auto-ajuste al ancho);
   cada capa solo muestra UNA palabra, así ffmpeg las revela una a una en su
   posición exacta sin calcular offsets.
2. Una sola tipografía. Ahora hay 6 estilos de título y 3 de año.

Todo es transparente y flotante: cero cajas, cero tarjetas.
"""

from __future__ import annotations

import html as _html
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Anton'
    '&family=Archivo+Black&family=Oswald:wght@500;700'
    '&family=Playfair+Display:ital,wght@1,700;1,900'
    '&family=Space+Grotesk:wght@300;500;700&display=block" rel="stylesheet">'
)

TITLE_STYLES = (
    "condensed_glow",   # Anton condensada con degradado y brillo (ref. SOCIAL MEDIA)
    "fill_outline",     # palabras rellenas alternadas con palabras solo contorno
    "mirror",           # blanca enorme con reflejo (ref. OVERLAPPING SHADOW)
    "ghost_trail",      # blanca con estela de movimiento (ref. CURIOUS)
    "editorial_mix",    # fina y espaciada + serif itálica de énfasis (ref. Toss The Bouquet)
    "stack_hero",       # palabras previas pequeñas + palabra héroe gigante con barra
)

YEAR_STYLES = ("stack_gold", "wide_outline", "split_tone")

KEYWORD_STYLES = ("badge_glow", "contrast_split", "editorial_punch")

KEYWORD_DUOTONES = (
    ("#ff9436", "#ff5500"),  # naranja vibrante fuego
    ("#38bdf8", "#0284c7"),  # azul elÃ©ctrico neÃ³n
    ("#a855f7", "#ec4899"),  # pÃºrpura / magenta moderno
    ("#10b981", "#059669"),  # esmeralda tecno
    ("#f59e0b", "#d97706"),  # Ã¡mbar oro
    ("#3b82f6", "#1d4ed8"),  # cobalto intenso
)

# Palabras que, justo después de un número de 4 cifras, indican que NO es un año.
_NOT_YEAR_NEXT = {
    "personas", "millones", "mil", "usuarios", "dolares", "dólares", "euros",
    "pesos", "horas", "minutos", "segundos", "veces", "casos", "muertes", "años",
    "km", "kg", "metros", "habitantes", "dispositivos", "empleados", "estudiantes",
    "niños", "jóvenes", "adolescentes", "por", "calorías", "pasos", "mensajes",
}


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        r, g, b = 255, 183, 3
    return f"rgba({r},{g},{b},{alpha})"


def _split_lines(words: List[str]) -> List[List[int]]:
    """Agrupa índices de palabras en 1 o 2 líneas equilibradas (nunca más)."""
    n = len(words)
    if n <= 1:
        return [list(range(n))]
    total = len(" ".join(words))
    if total <= 16:
        return [list(range(n))]
    best, best_cost = 1, 10 ** 9
    for k in range(1, n):
        l1 = len(" ".join(words[:k]))
        l2 = len(" ".join(words[k:]))
        cost = max(l1, l2)
        if cost < best_cost:
            best, best_cost = k, cost
    return [list(range(best)), list(range(best, n))]


class KineticTitleRenderer:
    """Renderiza capas de título por palabra y llamadas de año flotantes."""

    def __init__(self, web_renderer):
        self.web = web_renderer
        self.browser_bin = web_renderer.browser_bin

    # ------------------------------------------------------------------ util
    def _screenshot(self, html_text: str, out_png: Path, w: int, h: int, budget_ms: int = 4500) -> None:
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        html_file = out_png.with_suffix(".html")
        html_file.write_text(html_text, encoding="utf-8")
        args = [
            self.browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--virtual-time-budget={budget_ms}",
            f"--screenshot={out_png.resolve()}",
            f"--window-size={w},{h}",
            html_file.resolve().as_uri(),
        ]
        subprocess.run(args, capture_output=True, check=True, timeout=45)

    @staticmethod
    def _normalize_canvas(png: Path, w: int, h: int) -> None:
        """Garantiza PNG exactamente w×h anclado arriba-izquierda (capas alineadas)."""
        from PIL import Image
        im = Image.open(png).convert("RGBA")
        if im.size != (w, h):
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            canvas.paste(im.crop((0, 0, min(w, im.width), min(h, im.height))), (0, 0))
            im = canvas
        im.save(png)

    @staticmethod
    def _tight_crop(png: Path, pad: int = 24, alpha_min: int = 6) -> None:
        from PIL import Image
        im = Image.open(png).convert("RGBA")
        mask = im.getchannel("A").point(lambda a: 255 if a > alpha_min else 0)
        bbox = mask.getbbox()
        if bbox:
            b = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                 min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad))
            im.crop(b).save(png)

    # ------------------------------------------------------------- títulos
    def _build_title_html(
        self, words: List[str], active: int, style: str, duo: Tuple[str, str],
        eyebrow: str, w: int, h: int,
    ) -> str:
        A, B = duo
        esc = lambda s: _html.escape(str(s), quote=True)
        n = len(words)
        last = n - 1

        # ---- composición de líneas y rol de cada palabra según el estilo ----
        if style == "editorial_mix":
            display = []
            for i, wd in enumerate(words):
                display.append(wd.capitalize() if i == last else wd)
            lines = [[0]] if n == 1 else [list(range(n - 1)), [last]]
        elif style == "stack_hero":
            display = list(words)
            lines = [[0]] if n == 1 else [list(range(n - 1)), [last]]
        else:
            display = list(words)
            lines = _split_lines(words)

        def role(i: int) -> str:
            if style == "condensed_glow":
                return "g"
            if style == "fill_outline":
                return "f" if i % 2 == 0 else "o"
            if style == "mirror":
                return "m"
            if style == "ghost_trail":
                return "gh"
            if style == "editorial_mix":
                if i == last:
                    return "k"
                return "s" if len(words[i]) <= 3 else "l"
            if style == "stack_hero":
                return "hero" if i == last else "sm"
            return "g"

        lines_html = []
        for ln in lines:
            spans = []
            for i in ln:
                off = "" if i == active else " off"
                spans.append(
                    f'<span class="w {role(i)}{off}" data-t="{esc(display[i])}">{esc(display[i])}</span>'
                )
            lines_html.append(f'<div class="ln">{"".join(spans)}</div>')
        bar_html = ""
        if style == "stack_hero":
            off = "" if active == last else " off"
            bar_html = f'<div class="bar{off}"></div>'
        eb = ""
        if eyebrow:
            off = "" if active == 0 else " off"
            eb = f'<div class="eb{off}">{esc(eyebrow)}</div>'

        base_px, max_w, max_h = 300, 0.84, 0.50
        css = ""
        if style == "condensed_glow":
            css = f"""
            #blk{{font-family:'Anton',sans-serif;text-transform:uppercase;letter-spacing:.012em;line-height:.98}}
            .g{{background:linear-gradient(180deg,#fff 0%,{A} 42%,{B} 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
            .ln{{filter:drop-shadow(0 .05em 0 rgba(0,0,0,.55)) drop-shadow(0 .09em .12em rgba(0,0,0,.85)) drop-shadow(0 0 .22em {_rgba(A, .45)})}}
            """
        elif style == "fill_outline":
            css = f"""
            #blk{{font-family:'Anton',sans-serif;text-transform:uppercase;letter-spacing:.015em;line-height:.96}}
            .f{{background:linear-gradient(180deg,{A},{B});-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
            .o{{-webkit-text-fill-color:transparent;-webkit-text-stroke:.026em #fff}}
            .ln{{filter:drop-shadow(0 .06em .12em rgba(0,0,0,.8))}}
            """
        elif style == "mirror":
            max_h = 0.36
            css = """
            #blk{font-family:'Anton',sans-serif;text-transform:uppercase;letter-spacing:.01em;line-height:.95}
            .m{background:linear-gradient(180deg,#fff 45%,#c6ccd8 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
            .ln{filter:drop-shadow(0 .03em .05em rgba(0,0,0,.6))}
            #lines{-webkit-box-reflect:below -.02em linear-gradient(transparent 56%, rgba(255,255,255,.34))}
            """
        elif style == "ghost_trail":
            base_px = 240
            css = """
            #blk{font-family:'Archivo Black',sans-serif;text-transform:uppercase;letter-spacing:-.01em;line-height:1}
            .gh{color:#fff;text-shadow:-.025em 0 .03em rgba(255,255,255,.6),-.06em 0 .06em rgba(255,255,255,.38),-.11em 0 .10em rgba(255,255,255,.2),-.17em 0 .16em rgba(255,255,255,.1),0 .07em .18em rgba(0,0,0,.85)}
            """
        elif style == "editorial_mix":
            base_px, max_h = 250, 0.55
            css = f"""
            #blk{{line-height:1.05}}
            .ln{{align-items:baseline;filter:drop-shadow(0 .04em .08em rgba(0,0,0,.85))}}
            .s{{font-family:'Space Grotesk',sans-serif;font-weight:300;font-size:.34em;letter-spacing:.42em;text-transform:uppercase;color:#e9edf5;margin:0 .15em}}
            .l{{font-family:'Space Grotesk',sans-serif;font-weight:300;font-size:.5em;letter-spacing:.34em;text-transform:uppercase;color:#fff}}
            .k{{font-family:'Playfair Display',serif;font-style:italic;font-weight:900;font-size:1.25em;letter-spacing:-.01em;line-height:1.05;background:linear-gradient(180deg,#fff 0%,{A} 55%,{B} 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;padding:0 .06em}}
            """
        elif style == "stack_hero":
            css = f"""
            #blk{{line-height:1}}
            .ln{{filter:drop-shadow(0 .05em .1em rgba(0,0,0,.85))}}
            .sm{{font-family:'Oswald',sans-serif;font-weight:700;font-size:.34em;letter-spacing:.34em;text-transform:uppercase;color:rgba(255,255,255,.94);margin:0 .12em}}
            .hero{{font-family:'Anton',sans-serif;text-transform:uppercase;font-size:1.25em;letter-spacing:.01em;line-height:1;background:linear-gradient(180deg,#fff 0%,{A} 45%,{B} 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
            .bar{{width:46%;height:.05em;margin-top:.04em;border-radius:99px;background:linear-gradient(90deg,transparent,{A},{B},transparent);box-shadow:0 0 .25em {_rgba(A, .7)}}}
            """

        lines_wrapper = f'<div id="lines">{"".join(lines_html)}</div>'
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{FONTS_LINK}
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{w}px;height:{h}px;background:transparent;overflow:hidden}}
#stage{{width:{w}px;height:{h}px;display:flex;align-items:center;justify-content:center}}
#blk{{display:inline-flex;flex-direction:column;align-items:center;font-size:{base_px}px;text-align:center}}
#lines{{display:flex;flex-direction:column;align-items:center}}
.ln{{display:flex;justify-content:center;align-items:baseline;gap:.2em;white-space:nowrap}}
.w{{display:inline-block;position:relative}}
.off{{visibility:hidden}}
.eb{{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:.105em;letter-spacing:.55em;margin-bottom:.35em;color:rgba(255,255,255,.85);text-transform:uppercase;text-shadow:0 2px 10px rgba(0,0,0,.85);padding-left:.55em}}
{css}
</style></head><body>
<div id="stage"><div id="blk">{eb}{lines_wrapper}{bar_html}</div></div>
<script>
(function(){{
  var BASE={base_px},MAXW={w}*{max_w},MAXH={h}*{max_h};
  function fit(){{
    var b=document.getElementById('blk');var fs=BASE;b.style.fontSize=fs+'px';
    for(var k=0;k<5;k++){{
      var r=b.getBoundingClientRect();
      var s=Math.min(MAXW/r.width,MAXH/r.height);
      if(Math.abs(s-1)<0.012)break;
      fs=Math.min(fs*s,BASE);b.style.fontSize=fs+'px';
    }}
  }}
  if(document.fonts&&document.fonts.ready){{document.fonts.ready.then(function(){{requestAnimationFrame(fit);}});}}else{{fit();}}
}})();
</script></body></html>"""

    def render_title_layers(
        self,
        title: str,
        out_dir: Path,
        style: str = "condensed_glow",
        duo: Optional[Tuple[str, str]] = None,
        eyebrow: str = "",
        canvas: Tuple[int, int] = (1920, 1080),
        max_words: int = 4,
    ) -> List[Path]:
        """Una capa PNG (tamaño de lienzo) por palabra. Lista vacía si algo falla."""
        try:
            words = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñüÜ0-9']+", str(title or ""))[:max_words]
            if not words:
                return []
            if style not in TITLE_STYLES:
                style = TITLE_STYLES[0]
            w, h = canvas
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            duo = duo or ("#FFB703", "#FB8500")
            eyebrow = (eyebrow or "").strip()[:30]
            paths: List[Path] = []
            for i in range(len(words)):
                png = out_dir / f"title_layer_{i}.png"
                page = self._build_title_html(words, i, style, duo, eyebrow, w, h)
                self._screenshot(page, png, w, h)
                self._normalize_canvas(png, w, h)
                paths.append(png)
            return paths
        except Exception:
            return []

    # --------------------------------------------------------------- años
    @staticmethod
    def find_years(speech: str) -> List[Tuple[str, float]]:
        """Devuelve [(año, fracción_0-1_de_posición_en_el_discurso)] sin duplicados."""
        out: List[Tuple[str, float]] = []
        seen = set()
        text = speech or ""
        total = max(1, len(text))
        for m in re.finditer(r"(?<![\d.,])(1[5-9]\d{2}|20[0-4]\d)(?![\d.,]*\d)", text):
            year = m.group(1)
            if year in seen:
                continue
            tail = re.match(r"\s*([A-Za-zÁÉÍÓÚÑáéíóúñ%]+)", text[m.end():])
            if tail and tail.group(1).lower() in _NOT_YEAR_NEXT:
                continue
            seen.add(year)
            out.append((year, m.start() / total))
        return out

    def _year_html(self, year: str, style: str) -> str:
        first, second = year[:2], year[2:]
        base = f"""<!DOCTYPE html><html><head><meta charset="utf-8">{FONTS_LINK}
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:transparent;}}
body{{width:1500px;height:1000px;display:flex;align-items:center;justify-content:center}}
"""
        if style == "stack_gold":
            return base + f"""
#yr{{position:relative;display:inline-flex;flex-direction:column;align-items:center;font-family:'Anton',sans-serif;font-size:270px;line-height:.84;letter-spacing:.02em;filter:drop-shadow(0 .05em .08em rgba(0,0,0,.7)) drop-shadow(0 0 .12em rgba(255,200,80,.25))}}
.d{{background:linear-gradient(180deg,#ffffff 0%,#fff1c2 38%,#e9b84a 78%,#b87a1a 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;-webkit-text-stroke:.012em #f3c969}}
.sw{{position:absolute;left:-14%;width:128%;top:33%;height:36%;pointer-events:none;overflow:visible}}
</style></head><body>
<div id="yr"><div class="d">{first}</div><div class="d">{second}</div>
<svg class="sw" viewBox="0 0 360 200" preserveAspectRatio="none">
<defs><linearGradient id="g" x1="0" y1="1" x2="1" y2="0">
<stop offset="0" stop-color="#b9791c"/><stop offset=".45" stop-color="#f6c453"/><stop offset=".8" stop-color="#fff6cf"/><stop offset="1" stop-color="#ffffff"/></linearGradient></defs>
<path d="M0 152 C140 142 250 112 352 18 C238 92 120 150 0 188 Z" fill="url(#g)"/>
<path d="M6 150 C142 138 250 108 340 30" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="1.6"/>
</svg></div></body></html>"""
        if style == "wide_outline":
            return base + f"""
#yr{{position:relative;display:inline-block;font-family:'Anton',sans-serif;font-size:330px;line-height:1;letter-spacing:.02em;filter:drop-shadow(0 .04em .08em rgba(0,0,0,.75))}}
.o{{-webkit-text-fill-color:transparent;-webkit-text-stroke:3px #fff}}
.fl{{position:absolute;left:0;top:0;background:linear-gradient(180deg,#ffe08a,#ff9f1c);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;-webkit-mask-image:linear-gradient(180deg,transparent 50%,#000 50%)}}
.rule{{height:7px;margin-top:6px;border-radius:99px;background:linear-gradient(90deg,#ffb703,#fb8500,transparent)}}
</style></head><body>
<div><div id="yr"><div class="o">{year}</div><div class="fl">{year}</div></div><div class="rule"></div></div></body></html>"""
        # split_tone
        return base + f"""
#yr{{display:inline-flex;font-family:'Archivo Black',sans-serif;font-size:190px;line-height:1;letter-spacing:-.03em;filter:drop-shadow(0 .04em .07em rgba(0,0,0,.8))}}
.a{{color:#fff}}
.b{{background:linear-gradient(180deg,#ffd166,#fb8500);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.rule{{height:8px;margin-top:4px;border-radius:99px;background:linear-gradient(90deg,#fff,#ffb703,transparent)}}
</style></head><body>
<div><div id="yr"><span class="a">{first}</span><span class="b">{second}</span></div><div class="rule"></div></div></body></html>"""

    def render_year_callout(self, year: str, out_png: Path, style_idx: int = 0) -> Optional[Tuple[Path, str]]:
        """PNG transparente recortado del año. Devuelve (ruta, estilo) o None."""
        try:
            style = YEAR_STYLES[style_idx % len(YEAR_STYLES)]
            out_png = Path(out_png)
            self._screenshot(self._year_html(year, style), out_png, 1500, 1000, budget_ms=4000)
            self._tight_crop(out_png, pad=24, alpha_min=6)
            return out_png, style
        except Exception:
            return None

    @staticmethod
    def find_keywords(speech: str, scene_name: str = "", card_headline: str = "") -> List[Dict[str, Any]]:
        """
        Extrae palabras clave de alto impacto o datos cuantitativos para rÃ³tulos flotantes de Ã©nfasis.
        Devuelve lista de dicts ordenados por posiciÃ³n:
          [{"text": "40% MENOS", "tag": "DATO CLAVE", "frac": 0.35, "kind": "stat", "style": "badge_glow"}, ...]
        """
        res: List[Dict[str, Any]] = []
        seen = set()
        text = speech or ""
        total_len = max(1, len(text))
        ignore_set = set(re.findall(r"\w+", (scene_name + " " + card_headline).lower()))

        # 1. Datos cuantitativos y mÃ©tricas de impacto
        stat_patterns = [
            r"\b\d+(?:[.,]\d+)?%\s*(?:menos|mas|mÃ¡s|de aumento|de caÃ­da|de caida)?\b",
            r"\b\d+(?:[.,]\d+)?\s*(?:veces|x|horas|minutos|segundos|millones|miles)\b",
        ]
        for pat in stat_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                raw = m.group(0).strip()
                if raw.lower() not in seen:
                    seen.add(raw.lower())
                    res.append({
                        "text": raw.upper(),
                        "tag": "DATO CLAVE",
                        "frac": m.start() / total_len,
                        "kind": "stat",
                        "style": "badge_glow"
                    })

        # 2. Conceptos clave de alto impacto psicolÃ³gico / tecnolÃ³gico / hÃ¡bitos
        high_impact_concepts = [
            ("dopamina", "NEUROCIENCIA", "badge_glow"),
            ("cortisol", "NEUROCIENCIA", "badge_glow"),
            ("neurociencia", "NEUROCIENCIA", "contrast_split"),
            ("algoritmo", "SISTEMA", "contrast_split"),
            ("atencion secuestrada", "ALERTA", "editorial_punch"),
            ("atenciÃ³n secuestrada", "ALERTA", "editorial_punch"),
            ("sobreestimulacion", "ALERTA", "editorial_punch"),
            ("sobreestimulaciÃ³n", "ALERTA", "editorial_punch"),
            ("multitarea", "ERROR", "contrast_split"),
            ("disciplina", "MÃ‰TODO", "editorial_punch"),
            ("habito atomico", "MÃ‰TODO", "editorial_punch"),
            ("hÃ¡bito atÃ³mico", "MÃ‰TODO", "editorial_punch"),
            ("productividad", "CLAVE", "contrast_split"),
            ("enfoque profundo", "CLAVE", "editorial_punch"),
            ("enfoque", "ENFOQUE", "badge_glow"),
            ("distraccion", "ALERTA", "contrast_split"),
            ("distracciÃ³n", "ALERTA", "contrast_split"),
            ("error critico", "ERROR CRÃTICO", "contrast_split"),
            ("error crÃ­tico", "ERROR CRÃTICO", "contrast_split"),
            ("regla de oro", "REGLA DE ORO", "editorial_punch"),
            ("secreto", "SECRETO", "editorial_punch"),
            ("exito", "CLAVE", "badge_glow"),
            ("éxito", "CLAVE", "badge_glow"),
            ("resultados oficiales", "IMPACTO", "contrast_split"),
        ]
        for term, tag, st in high_impact_concepts:
            for m in re.finditer(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE):
                raw = m.group(0).strip()
                if raw.lower() not in seen and raw.lower() not in ignore_set:
                    seen.add(raw.lower())
                    res.append({
                        "text": raw.upper(),
                        "tag": tag,
                        "frac": m.start() / total_len,
                        "kind": "concept",
                        "style": st
                    })

        # 3. Palabras completas en MAYÃšSCULAS sostenidas (3-16 caracteres) en el texto
        for m in re.finditer(r"\b[A-ZÃÃ‰ÃÃ“ÃšÃ‘]{3,16}\b", text):
            raw = m.group(0).strip()
            if raw.lower() not in seen and raw.lower() not in _NOT_YEAR_NEXT and raw.lower() not in ignore_set:
                if len(raw) >= 4 and not raw.isdigit():
                    seen.add(raw.lower())
                    res.append({
                        "text": raw,
                        "tag": "CLAVE",
                        "frac": m.start() / total_len,
                        "kind": "caps",
                        "style": "contrast_split"
                    })

        res.sort(key=lambda x: x["frac"])
        return res

    def _keyword_html(self, text: str, style: str, tag: str, duo: Tuple[str, str]) -> str:
        c1, c2 = duo
        base_head = f"""<!DOCTYPE html><html><head><meta charset="utf-8">{FONTS_LINK}
        <style>
          * {{ margin:0; padding:0; box-sizing:border-box; }}
          body {{ background: transparent; padding: 40px; display: inline-block; }}
          .wrap {{ display: inline-flex; flex-direction: column; align-items: flex-start; }}
        """
        if style == "badge_glow":
            return base_head + f"""
          .tag {{
            display: inline-flex; align-items: center; gap: 6px;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;
            color: {c1}; margin-bottom: 8px;
            background: {_rgba(c1, 0.12)}; border: 1px solid {_rgba(c1, 0.35)};
            padding: 4px 14px; border-radius: 999px;
            box-shadow: 0 0 16px {_rgba(c1, 0.25)};
          }}
          .tag-dot {{ width: 6px; height: 6px; border-radius: 50%; background: {c1}; box-shadow: 0 0 8px {c1}; }}
          .word {{
            font-family: 'Anton', sans-serif;
            font-size: 84px;
            line-height: 0.95;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            background: linear-gradient(175deg, #ffffff 15%, {c1} 65%, {c2} 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 12px 28px rgba(0,0,0,0.9)) drop-shadow(0 0 35px {_rgba(c1, 0.45)});
          }}
        </style></head><body>
          <div class="wrap">
            <div class="tag"><span class="tag-dot"></span>{tag}</div>
            <div class="word">{text}</div>
          </div>
        </body></html>"""
        elif style == "contrast_split":
            return base_head + f"""
          .tag {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 12px; font-weight: 700; letter-spacing: 0.24em; text-transform: uppercase;
            color: rgba(255,255,255,0.7); margin-bottom: 6px;
          }}
          .word {{
            font-family: 'Archivo Black', sans-serif;
            font-size: 78px;
            line-height: 0.95;
            letter-spacing: -0.01em;
            text-transform: uppercase;
            color: #ffffff;
            -webkit-text-stroke: 2px {c1};
            filter: drop-shadow(0 14px 30px rgba(0,0,0,0.95)) drop-shadow(0 0 25px {_rgba(c1, 0.5)});
          }}
          .bar {{
            width: 100%; height: 4px; border-radius: 999px; margin-top: 10px;
            background: linear-gradient(90deg, {c1}, {c2}, transparent);
            box-shadow: 0 0 12px {c1};
          }}
        </style></head><body>
          <div class="wrap">
            <div class="tag">// {tag}</div>
            <div class="word">{text}</div>
            <div class="bar"></div>
          </div>
        </body></html>"""
        else:  # editorial_punch
            return base_head + f"""
          .tag {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px; font-weight: 700; letter-spacing: 0.20em; text-transform: uppercase;
            color: {c1}; margin-bottom: 8px;
          }}
          .word {{
            font-family: 'Playfair Display', serif;
            font-style: italic;
            font-weight: 900;
            font-size: 82px;
            line-height: 1.0;
            background: linear-gradient(135deg, #ffffff 20%, {c1} 70%, {c2} 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 14px 28px rgba(0,0,0,0.9)) drop-shadow(0 0 30px {_rgba(c1, 0.4)});
          }}
        </style></head><body>
          <div class="wrap">
            <div class="tag"># {tag}</div>
            <div class="word">{text}</div>
          </div>
        </body></html>"""

    def render_keyword_callout(
        self,
        text: str,
        out_png: Path,
        style: str = "badge_glow",
        tag: str = "DATO CLAVE",
        duo: Tuple[str, str] = ("#ff9436", "#ff5500")
    ) -> Optional[Path]:
        """Renderiza un rÃ³tulo flotante recortado de palabra clave con estilo premium."""
        try:
            if style not in KEYWORD_STYLES:
                style = KEYWORD_STYLES[0]
            out_png = Path(out_png)
            html = self._keyword_html(text, style, tag, duo)
            self._screenshot(html, out_png, 1200, 420, budget_ms=4500)
            self._tight_crop(out_png, pad=20, alpha_min=6)
            return out_png if out_png.exists() else None
        except Exception:
            return None
