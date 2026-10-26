"""Investigación web con hechos verificables y hoja de datos (fact sheet).

Reemplaza el bloque de "snippets sueltos" que se enviaba al director por:

1. Varias consultas (noticias + web) en español.
2. Descarga del texto completo de las fuentes más fiables (no solo el snippet).
3. Extracción de frases con cifras/fechas/citas y atribución real.
4. Corroboración entre dominios independientes.
5. Un fact sheet compacto + gancho recomendado para la Escena 1.
6. Auditoría de cifras del guion para detectar números inventados.

Todo es tolerante a fallos: si la red o una fuente falla, devuelve lo que tenga.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

from config.settings import settings
from core.llm import safe_log

CACHE_DIR = settings.STORAGE_DIR / "cache" / "research"
CACHE_TTL_SEC = 4 * 3600
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

TIER3_DOMAINS = (
    ".gov", ".gob", ".gob.", ".edu", ".int", "who.int", "un.org", "un.org", "nasa.gov",
    "worldbank.org", "imf.org", "oecd.org", "iea.org", "nature.com", "science.org",
    "sciencedirect.com", "thelancet.com", "nejm.org", "reuters.com", "apnews.com",
    "efeverde.com", "efe.com", "bbc.com", "bbc.co.uk", "statista.com", "ourworldindata.org",
)
TIER2_DOMAINS = (
    "elpais.com", "elmundo.es", "elconfidencial.com", "bbc.com", "cnn.com", "dw.com",
    "ft.com", "wsj.com", "bloomberg.com", "forbes.com", "economist.com", "wired.com",
    "technologyreview.com", "nationalgeographic.com", "eluniversal.com", "clarin.com",
    "lanacion.com.ar", "eltiempo.com", "elpais.com.co", "animalpolitico.com",
)
BLOCK_DOMAINS = (
    "facebook.com", "instagram.com", "tiktok.com", "pinterest.", "quora.com",
    "taringa.net", "blogspot.", "wordpress.com", "medium.com", "linktr.ee",
)

STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a", "en",
    "y", "o", "u", "que", "por", "para", "con", "sin", "sobre", "entre", "hasta", "desde",
    "es", "son", "fue", "fueron", "ser", "esta", "este", "estos", "estas", "su", "sus",
    "se", "lo", "le", "les", "no", "más", "mas", "pero", "como", "cuando", "donde", "ya",
    "the", "of", "and", "to", "in", "for", "on", "with", "is", "are", "was", "were",
    "a", "an", "by", "at", "from", "as", "that", "this", "it", "be", "has", "have",
}
TECH_ANCHORS = {
    "inteligencia", "artificial", "ia", "modelo", "modelos", "algoritmo", "algoritmos",
    "chip", "chips", "tecnologia", "software", "hardware", "openai", "anthropic",
    "google", "nvidia", "microsoft", "datos", "digital", "robot", "robots",
    "computacion", "servidores", "datacenter", "machine", "learning", "llm",
}

CONTRAST_WORDS = (
    "pero", "sin embargo", "a pesar", "récord", "record", "peor", "mejor", "duplicar",
    "triplicar", "caída", "caida", "aumento", "creció", "crecio", "desplomó", "desplomo",
    "prohibido", "oculto", "secreto", "primera vez", "nunca antes", "más alto", "mas alto",
)
GENERIC_TAGS = {
    "dato clave", "punto clave", "concepto técnico", "concepto tecnico", "mapa táctico",
    "mapa tactico", "métrica clave", "metrica clave", "dato verificado", "análisis",
    "analisis", "información", "informacion", "resumen",
}

NUM_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"\s*(%|por ciento|millones?|mil|billones?|trillones?|billion|million|trillion|"
    r"USD|EUR|dólares?|dolares?|euros?|pesos?|hectáreas?|hectareas?|toneladas?|km|kilómetros?|kilometros?)?",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "aside", "form", "svg", "noscript", "iframe"}
    CONTENT = {"p", "h1", "h2", "h3", "h4", "li", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.title = ""
        self._skip = 0
        self._content = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.CONTENT:
            self._content += 1
            if not self._skip:
                self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.CONTENT:
            self._content = max(0, self._content - 1)
            if not self._skip:
                self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()
        if not self._skip and self._content > 0 and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self) -> str:
        raw = "".join(self.parts)
        # Algunas páginas devuelven HTML escapado dentro del texto (&lt;p ...&gt;).
        raw = re.sub(r"<[^>]{0,500}>", " ", raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw)
        return raw.strip()


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(str(text or "")).lower()).strip()


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9áéíóúüñ]+", _norm(text)) if len(t) > 2 and t not in STOPWORDS}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return ""


def _tier(domain: str) -> int:
    if any(domain.endswith(d) or d in domain for d in TIER3_DOMAINS):
        return 3
    if any(d in domain for d in TIER2_DOMAINS):
        return 2
    return 1


def _tier_from_label(label: str) -> int:
    label = _norm(label)
    if any(name in label for name in ("reuters", "ap news", "associated press", "efe", "afp", "nasa", "onu", "unicef", "oms", "who", "banco mundial", "fmi", "imf", "ocde", "oecd", "nature", "science", "lancet", "statista")):
        return 3
    if any(name in label for name in ("bbc", "cnn", "dw", "el pais", "elpais", "el mundo", "bloomberg", "financial times", "forbes", "economist", "wired", "national geographic", "el tiempo", "clarin", "la nacion")):
        return 2
    return 1


def _is_blocked(domain: str) -> bool:
    return any(b in domain for b in BLOCK_DOMAINS)


def _title_key(title: str) -> str:
    return _norm(re.sub(r"[^a-z0-9áéíóúüñ ]+", " ", _strip_accents(title).lower()))[:80]


def _source_label(item: Dict[str, Any]) -> str:
    name = (item.get("source") or _domain(item.get("url", "")) or "Fuente").strip()
    name = re.sub(r"\s+on\s+MSN$", "", name, flags=re.IGNORECASE)
    date = (item.get("date") or "")[:10]
    return f"{name}, {date}" if date else name


def _extract_numbers(text: str) -> List[str]:
    values: List[str] = []
    for match in NUM_RE.finditer(text):
        raw, unit = match.group(1), (match.group(2) or "").lower()
        if not raw:
            continue
        clean = raw.replace(".", "").replace(",", ".") if re.search(r"\d[.,]\d{3}", raw) else raw.replace(",", ".")
        try:
            num = float(clean)
        except ValueError:
            continue
        if num < 1 and not unit:
            continue
        if num.is_integer():
            value = str(int(num))
        else:
            value = f"{num:.4g}".replace(",", ".")
        values.append(f"{value}{unit}".replace(" ", ""))
    return values


def _sentence_split(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡0-9\"“])", text)
    return [p.strip() for p in parts if p.strip()]


def _fetch_page(url: str, timeout: float = 6.0) -> str:
    import requests

    if _is_blocked(_domain(url)):
        return ""
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=True) as resp:
            if resp.status_code >= 400:
                return ""
            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type and "text" not in content_type:
                return ""
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=32768):
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if total >= 500_000:
                    break
            raw = b"".join(chunks)
            encoding = resp.encoding or "utf-8"
            try:
                html = raw.decode(encoding, errors="replace")
            except (LookupError, TypeError):
                html = raw.decode("utf-8", errors="replace")
    except Exception:
        return ""

    if not html:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return ""
    return parser.text()[:12000]


def _simplify_topic(topic: str) -> str:
    """Reduce la pregunta a sus términos buscables (chips, 2 nanómetros, TSMC...)."""
    stop = {
        "como", "cómo", "porque", "por", "que", "qué", "cual", "cuál", "cuando", "cuándo",
        "donde", "dónde", "funciona", "funcionan", "define", "definen", "explica", "explican",
        "entiende", "entienden", "sirve", "sirven", "hace", "hacen", "es", "son", "era",
        "los", "las", "una", "unos", "unas", "del", "para", "con", "sin", "sobre", "entre",
        "este", "esta", "estos", "estas", "video", "videos", "tema",
    }
    tokens = [t for t in re.findall(r"[a-z0-9áéíóúñ]{3,}", _norm(topic)) if t not in stop]
    # Priorizar términos técnicos/entidades sobre genéricos.
    priority = [t for t in tokens if any(k in t for k in ("chip", "nan", "tsmc", "samsung", "intel", "ia", "silicio", "semiconductor", "procesador"))]
    ordered = priority + [t for t in tokens if t not in priority]
    return " ".join(dict.fromkeys(ordered))[:90]


def _wikipedia_item(topic: str) -> Optional[Dict[str, Any]]:
    """Fuente de contexto de respaldo cuando las búsquedas no devuelven nada."""
    simple = _simplify_topic(topic)
    if not simple:
        return None
    headers = {"User-Agent": "AetherCut/1.0 (research; contact: local)"}
    try:
        import requests
        search = requests.get(
            "https://es.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": simple, "format": "json", "srlimit": 1},
            headers=headers,
            timeout=(4, 8),
        ).json()
        hits = (search.get("query") or {}).get("search") or []
        if not hits:
            return None
        title = hits[0].get("title") or ""
        if not title:
            return None
        summary = requests.get(
            f"https://es.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
            headers=headers,
            timeout=(4, 8),
        ).json()
        extract = str(summary.get("extract") or "").strip()
        if len(extract) < 60:
            return None
        return {
            "title": title,
            "url": (summary.get("content_urls") or {}).get("desktop", {}).get("page", ""),
            "snippet": extract[:1400],
            "source": "Wikipedia",
            "domain": "es.wikipedia.org",
            "tier": 3,
            "date": "",
        }
    except Exception as exc:
        safe_log(f"[Research] Wikipedia no disponible: {exc}")
        return None


def _search(topic: str) -> List[Dict[str, Any]]:
    from ddgs import DDGS

    results: List[Dict[str, Any]] = []
    seen: set = set()
    year = datetime.now().year
    queries = [
        ("news", topic, None),
        ("text", topic, "w"),
        ("text", f"{topic} cifras oficiales informe datos", None),
        ("text", f"{topic} data report statistics", None),
    ]

    with DDGS(timeout=6) as ddgs:
        for kind, query, timelimit in queries:
            try:
                if kind == "news":
                    batch = list(ddgs.news(query, region="es-es", max_results=6))
                else:
                    kwargs = {"region": "es-es", "max_results": 6}
                    if timelimit:
                        kwargs["timelimit"] = timelimit
                    batch = list(ddgs.text(query, **kwargs))
            except Exception as exc:
                safe_log(f"[Research] Consulta '{query}' falló: {exc}")
                continue

            for item in batch:
                title = (item.get("title") or "").strip()
                url = (item.get("url") or item.get("href") or "").strip()
                body = (item.get("body") or "").strip()
                domain = _domain(url)
                if not title or not url or _is_blocked(domain):
                    continue
                key = _title_key(title)
                if key in seen:
                    continue
                seen.add(key)
                source_label = item.get("source") or domain
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": body,
                    "date": (item.get("date") or "")[:10],
                    "source": source_label,
                    "domain": domain,
                    "tier": max(_tier(domain), _tier_from_label(source_label)),
                })

    # Si la pregunta completa no devuelve nada, buscar por términos clave.
    if len(results) < 2:
        simple = _simplify_topic(topic)
        if simple and _norm(simple) != _norm(topic):
            safe_log(f"[Research] Pocos resultados; reintentando con: '{simple}'")
            try:
                with DDGS(timeout=6) as ddgs:
                    for kind in ("text", "news"):
                        try:
                            batch = (
                                list(ddgs.text(simple, region="es-es", max_results=8))
                                if kind == "text"
                                else list(ddgs.news(simple, region="es-es", max_results=6))
                            )
                        except Exception:
                            continue
                        for item in batch:
                            title = (item.get("title") or "").strip()
                            url = (item.get("url") or item.get("href") or "").strip()
                            body = (item.get("body") or "").strip()
                            domain = _domain(url)
                            if not title or not url or _is_blocked(domain):
                                continue
                            key = _title_key(title)
                            if key in seen:
                                continue
                            seen.add(key)
                            source_label = item.get("source") or domain
                            results.append({
                                "title": title,
                                "url": url,
                                "snippet": body,
                                "date": (item.get("date") or "")[:10],
                                "source": source_label,
                                "domain": domain,
                                "tier": max(_tier(domain), _tier_from_label(source_label)),
                            })
                        if len(results) >= 4:
                            break
            except Exception as exc:
                safe_log(f"[Research] Reintento simplificado falló: {exc}")

    results.sort(key=lambda r: (r["tier"], bool(r["date"]), len(r["snippet"])), reverse=True)
    return results


def _clean_claim(text: str) -> str:
    """Quita restos de navegación/fechas de portada, sin tocar el contenido."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = re.sub(r"^\s*(?:\d+\s+(?:days?|hours?|minutes?)|hace\s+\d+\s+(?:días?|dias?|horas?|minutos?))\s+ago\s*[·•\-–—]*\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:Published|Updated|Actualizado|Publicado)\s*:?\s*", "", text, flags=re.IGNORECASE)
    # "Chile 26/02/2026 El Ministerio..." o "Santiago, 21 oct (Reuters) -"
    text = re.sub(r"^[A-ZÁÉÍÓÚÑ][\w\s\.\-]{0,45}\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+", "", text)
    text = re.sub(r"^[A-ZÁÉÍÓÚÑ][\w\s\.\-]{0,45}\b\d{1,2}\s+(?:de\s+)?[a-záéíóúñ]+\s+(?:de\s+)?\d{4}\s*[-–—]?\s*", "", text)
    text = re.sub(r"^(?:LONDRES|MADRID|SANTIAGO|BOGOTÁ|BOGOTA|MÉXICO|MEXICO|NUEVA YORK|BUENOS AIRES|LIMA)[,\s\-–—]+", "", text)
    text = re.sub(r"\s*\|\s*", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text.strip(" -–—·•")


def _truncate_claim(text: str, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    idx = max(cut.rfind(". "), cut.rfind("; "))
    if idx >= int(limit * 0.55):
        return cut[: idx + 1].strip()
    return cut.rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def _is_sentence_like(claim: str, numbers: List[str]) -> bool:
    """Descarta filas de tablas, menús y títulos concatenados."""
    words = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9]+", claim)
    if len(words) < 6:
        return False
    stop_ratio = sum(1 for w in words if _strip_accents(w.lower()) in STOPWORDS) / len(words)
    if stop_ratio < 0.12:
        return False
    if len(numbers) >= 4 and len(words) <= 22:
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    if len(words) < 25 and caps / len(words) > 0.45:
        return False
    if len(YEAR_RE.findall(claim)) >= 3 and len(words) < 32:
        return False
    if re.search(r"\d\s*/\s*[+\-]?\d", claim) and len(numbers) >= 2:
        return False
    if "<" in claim and ">" in claim:
        return False
    if claim.count("«") != claim.count("»"):
        return False
    if claim.count('"') % 2 != 0:
        return False
    if any(ch in claim for ch in ("▲", "▼", "→", "■", "●", "°")):
        return False
    low = _norm(claim)
    if any(x in low for x in (
        "fuente:", "capitulo ", "dashboard", "archivo excel", "archivo adjunto",
        "direccion de estudios", "division de informacion", "cifras exactas",
        "informe sobre el mercado", "descarga", " pdf", "excel", "hoja ",
    )):
        return False
    bad_endings = {
        "vs", "tras", "de", "del", "y", "o", "u", "con", "para", "por", "en", "a", "al",
        "que", "segun", "como", "entre", "desde", "hasta", "sobre", "ante", "bajo",
        "contra", "mientras", "durante", "sin", "su", "sus", "la", "el", "los", "las",
    }
    if _strip_accents(words[-1].lower()) in bad_endings:
        return False
    # Solo hechos: se descartan opiniones y notas de prensa autopromocionales.
    if any(x in low for x in (
        "podria", "expone a", "vulnerabilidad", "representa un riesgo", "no acepta",
        "significa que", "propias estimaciones", "la empresa informo", "segun la empresa",
        "estima que", "la compania informo",
    )):
        return False
    return True


def _fact_score(claim: str, item: Dict[str, Any], topic_terms: set, numbers: List[str]) -> float:
    low = _norm(claim)
    score = 1.0
    score += 1.4 if item["tier"] == 3 else (0.7 if item["tier"] == 2 else 0.0)
    score += 0.6 if any(u in claim for u in ("%", "$", "€", "millones", "mil ", "billones", "toneladas", "dólares", "euros")) else 0.0
    overlap = len(_tokens(claim) & topic_terms)
    score += min(1.2, overlap * 0.35)
    score += 0.4 if any(_strip_accents(w) in low for w in CONTRAST_WORDS) else 0.0
    score += 0.3 if any(w in low for w in ("informe", "estudio", "según", "segun", "datos", "registro", "balance")) else 0.0
    if any(w in low for w in ("propias estimaciones", "la empresa informo", "segun la empresa", "estima que", "la compania informo")):
        score -= 1.0
    if item.get("date"):
        try:
            age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(item["date"]).replace(tzinfo=timezone.utc)).days
            if age_days <= 21:
                score += 0.5
        except Exception:
            pass
    if len(claim) > 240:
        score -= 0.4
    if len(numbers) >= 2:
        score += 0.3
    return round(score, 2)


@dataclass
class Fact:
    claim: str
    numbers: List[str] = field(default_factory=list)
    source: str = ""
    url: str = ""
    domain: str = ""
    date: str = ""
    tier: int = 1
    score: float = 0.0
    corroborations: int = 0
    also_in: List[str] = field(default_factory=list)


def _has_tech_anchor(text: str) -> bool:
    if _tokens(text) & TECH_ANCHORS:
        return True
    return bool(re.search(r"\b(ia|ai)\b", _norm(text)))


def _build_facts(items: List[Dict[str, Any]], topic: str) -> List[Fact]:
    topic_terms = _tokens(topic) | _tokens(" ".join(i["title"] for i in items))
    focus_terms = _tokens(topic)
    tech_topic = any(k in _norm(topic) for k in (
        "inteligencia artificial", "tecnolog", "software", "hardware", "chip",
        "robot", "computacion", "datos", "digital", "openai", "nvidia",
    ))
    by_key: Dict[str, Fact] = {}

    for item in items:
        text = item.get("full_text") or item.get("snippet") or ""
        if not text:
            continue
        item_focus = bool(_tokens(item.get("title", "") + " " + item.get("snippet", "")) & focus_terms) if focus_terms else True
        item_tech = bool(_tokens(item.get("title", "") + " " + item.get("snippet", "")) & TECH_ANCHORS) if tech_topic else True
        if tech_topic and not item_tech:
            continue
        segments: List[str] = []
        for line in re.split(r"\n+", text):
            line = line.strip()
            if len(line) < 40:
                continue
            segments.extend(_sentence_split(line))
        for sentence in segments:
            if not (40 <= len(sentence) <= 300):
                continue
            low = _norm(sentence)
            if any(bad in low for bad in ("cookie", "suscribete", "suscríbete", "politica de privacidad", "iniciar sesion", "publicidad")):
                continue
            numbers = _extract_numbers(sentence)
            years = YEAR_RE.findall(sentence)
            strong_numbers = [n for n in numbers if not re.fullmatch(r"(19|20)\d{2}", n)]
            if not strong_numbers:
                continue
            if not _tokens(sentence):
                continue

            claim = _clean_claim(sentence.replace("\n", " "))
            if len(claim) < 40 or not _is_sentence_like(claim, numbers):
                continue
            if claim.count('"') % 2 != 0:
                continue
            if claim.startswith('"') and not any(w in _norm(claim) for w in ("segun", "dijo", "dicen", "afirmo", "senalo", "explico", "declaro")):
                continue
            if not claim[:1].isupper() and not claim[:1].isdigit():
                continue
            if tech_topic and not _has_tech_anchor(claim):
                continue
            if focus_terms and not (_tokens(claim) & focus_terms) and not item_focus and not tech_topic:
                continue
            claim = _truncate_claim(claim)
            num_sig = "|".join(sorted(set(numbers))) if numbers else "|".join(sorted(set(years)))
            key = num_sig + "|" + item.get("domain", "")
            score = _fact_score(claim, item, topic_terms, numbers)
            fact = Fact(
                claim=claim,
                numbers=numbers[:4],
                source=_source_label(item),
                url=item.get("url", ""),
                domain=item.get("domain", ""),
                date=item.get("date", ""),
                tier=item["tier"],
                score=score,
            )
            existing = by_key.get(key)
            if existing is None or fact.score > existing.score:
                by_key[key] = fact

    facts = sorted(by_key.values(), key=lambda f: f.score, reverse=True)[:28]

    # Corroboración entre dominios independientes
    for i, fact in enumerate(facts):
        fact_terms = _tokens(fact.claim)
        for j, other in enumerate(facts):
            if i == j or not other.domain or other.domain == fact.domain:
                continue
            same_number = bool(set(fact.numbers) & set(other.numbers))
            union = fact_terms | _tokens(other.claim)
            jaccard = len(fact_terms & _tokens(other.claim)) / max(1, len(union))
            if same_number and jaccard >= 0.3 or jaccard >= 0.55:
                fact.corroborations += 1
                if other.domain not in fact.also_in:
                    fact.also_in.append(other.domain)
        fact.score = round(fact.score + min(1.05, fact.corroborations * 0.35), 2)

    # Colapsar paráfrasis del mismo dato entre medios distintos.
    collapsed: List[Fact] = []
    for fact in sorted(facts, key=lambda f: f.score, reverse=True):
        terms = _tokens(fact.claim)
        duplicate = False
        for kept in collapsed:
            kept_terms = _tokens(kept.claim)
            union = terms | kept_terms
            jaccard = len(terms & kept_terms) / max(1, len(union))
            fact_nums, kept_nums = set(fact.numbers), set(kept.numbers)
            subset = bool(fact_nums and kept_nums) and (fact_nums <= kept_nums or kept_nums <= fact_nums)
            if (fact_nums & kept_nums) and (jaccard >= 0.5 or (subset and (fact.domain == kept.domain or jaccard >= 0.3))):
                duplicate = True
                break
        if not duplicate:
            collapsed.append(fact)

    collapsed.sort(key=lambda f: f.score, reverse=True)
    return collapsed[:12]


def _pick_hook(facts: List[Fact]) -> Optional[Fact]:
    def impact(fact: Fact) -> float:
        value = fact.score
        low = _norm(fact.claim)
        if any("%" in n for n in fact.numbers):
            value += 0.4
        for number in fact.numbers:
            digits = re.match(r"(\d+)", number)
            if digits:
                try:
                    value += min(1.0, math.log10(int(digits.group(1)) + 1) * 0.25)
                except ValueError:
                    pass
        if any(_strip_accents(w) in low for w in CONTRAST_WORDS):
            value += 0.3
        if fact.corroborations >= 2:
            value += 0.5
        if 50 <= len(fact.claim) <= 180:
            value += 0.4
        if any(w in low for w in ("propias estimaciones", "la empresa informo", "segun la empresa", "estima que")):
            value -= 1.2
        if any(w in low for w in ("informe", "estudio", "oficial", "ministerio", "onu", "ocde", "banco mundial", "universidad")):
            value += 0.4
        if any(w in low for w in ("podria", "podría", "expone", "vulnerabilidad", "representa un riesgo", "significa que", "demuestra que", "no acepta")):
            value -= 0.6
        if "…" in fact.claim:
            value -= 1.5
        if "–" in fact.claim or "—" in fact.claim:
            value -= 0.3
        if len(YEAR_RE.findall(fact.claim)) >= 3:
            value -= 1.0
        if fact.claim.endswith("."):
            value += 0.2
        if any(w in low for w in ("aumento", "aumento", "alcanzo", "alcanzó", "registro", "registró", "cayo", "cayó", "crecio", "creció", "supero", "superó")):
            value += 0.25
        return value

    clean = [
        f for f in facts
        if f.numbers
        and "…" not in f.claim
        and f.claim.endswith((".", "?", "!"))
        and f.claim.count('"') % 2 == 0
        and 50 <= len(f.claim) <= 220
    ]
    candidates = clean or [f for f in facts if f.numbers] or facts
    return max(candidates, key=impact) if candidates else None


def _short_hook(text: str, limit: int = 170) -> str:
    text = _clean_claim(text)
    parts = _sentence_split(text)
    if not parts:
        return text[:limit]
    out = ""
    for part in parts:
        if out and len(out) + len(part) + 1 > limit:
            break
        if not out and len(part) > limit:
            cut = part[:limit]
            idx = max(cut.rfind(","), cut.rfind(";"))
            out = cut[:idx] if idx >= 60 else cut.rsplit(" ", 1)[0]
            break
        out = (out + " " + part).strip()
    out = out.strip().rstrip(".,;:")
    return out if out.endswith(("?", "!")) else out + "."


def _build_brief(topic: str, facts: List[Fact], hook: Optional[Fact], context: Optional[List[Dict[str, Any]]] = None) -> str:
    context = context or []
    if not facts:
        lines = [
            "CONTEXTO VERIFICADO (fuentes reales; NO inventes cifras que no aparezcan aquí):",
        ]
        for item in context[:5]:
            lines.append(f"- {item.get('title', '')}: {item.get('snippet', '')} [Fuente: {item.get('source', '')}]")
        lines += [
            "",
            "REGLAS DE FIDELIDAD:",
            "- Si no hay una cifra respaldada, explica la idea sin números.",
            "- Cita las fuentes por su nombre cuando uses su información.",
            "- No inventes estudios, fechas ni estadísticas.",
        ]
        return "\n".join(lines)

    lines = [
        "INVESTIGACIÓN VERIFICADA (cada dato incluye su fuente real; trátala como la única verdad disponible).",
    ]
    if hook:
        lines.append(f'GANCHO RECOMENDADO PARA LA ESCENA 1: "{hook.claim}" - Fuente: {hook.source}')
    lines.append("")
    lines.append("DATOS (usa SOLO estas cifras y atribuciones; no inventes números ni estudios):")
    for idx, fact in enumerate(facts, start=1):
        corroborated = f"; corroborado por {', '.join(fact.also_in[:3])}" if fact.also_in else ""
        lines.append(f"{idx}. {fact.claim} [Fuente: {fact.source}{corroborated}]")
    if context:
        lines += ["", "CONTEXTO DE FUENTES (para explicar sin inventar):"]
        for item in context[:3]:
            lines.append(f"- {item.get('title', '')}: {item.get('snippet', '')[:280]} [Fuente: {item.get('source', '')}]")
    lines += [
        "",
        "REGLAS DE FIDELIDAD:",
        "- Toda cifra, fecha o estadística de la narración debe salir de la lista anterior.",
        "- Cita al menos dos fuentes por su nombre en el guion (ej.: «según Reuters», «el informe de la ONU»).",
        "- Si un dato no está en la lista, no lo inventes: explícalo sin cifras.",
        "- Toda card que use un dato debe mostrar su fuente en el pie.",
    ]
    return "\n".join(lines)


def research_topic(topic: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Devuelve {"facts","hook","brief","sources"} con datos reales y corroborados."""
    topic = (topic or "").strip()
    if not topic:
        return {"facts": [], "hook": None, "brief": "", "sources": []}

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{hashlib.sha1(_norm(topic).encode('utf-8')).hexdigest()}.json"
    if not force_refresh and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if time.time() - float(cached.get("created_ts", 0)) < CACHE_TTL_SEC:
                return cached["sheet"]
        except Exception:
            pass

    started = time.time()
    items = _search(topic)
    if len(items) < 2:
        wiki = _wikipedia_item(topic)
        if wiki:
            items.append(wiki)
    if not items:
        sheet = {"facts": [], "hook": None, "brief": "", "sources": [], "context": []}
        return sheet

    # Descargar las fuentes más fiables en paralelo, con diversidad de dominio
    # (máximo 2 páginas por dominio para que la corroboración sea real).
    to_fetch: List[Dict[str, Any]] = []
    per_domain: Dict[str, int] = {}
    for item in items:
        domain = item.get("domain", "")
        if per_domain.get(domain, 0) >= 2:
            continue
        per_domain[domain] = per_domain.get(domain, 0) + 1
        to_fetch.append(item)
        if len(to_fetch) >= 6:
            break
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch_page, item["url"]): item for item in to_fetch}
        for future in as_completed(futures, timeout=14):
            item = futures[future]
            try:
                item["full_text"] = future.result() or ""
            except Exception:
                item["full_text"] = ""

    facts = _build_facts(items, topic)
    hook = _pick_hook(facts)
    if hook:
        hook = Fact(**{**asdict(hook), "claim": _short_hook(hook.claim)})
    context = [
        {
            "title": i.get("title", ""),
            "source": i.get("source") or i.get("domain", ""),
            "snippet": (i.get("snippet") or "")[:520],
        }
        for i in items
        if (i.get("snippet") or "").strip()
    ][:6]
    brief = _build_brief(topic, facts, hook, context)

    sheet = {
        "facts": [asdict(f) for f in facts],
        "hook": asdict(hook) if hook else None,
        "brief": brief,
        "context": context,
        "sources": [
            {"name": i.get("source"), "url": i.get("url"), "domain": i.get("domain"), "date": i.get("date")}
            for i in items[:8]
        ],
    }
    try:
        cache_path.write_text(
            json.dumps({"created_ts": time.time(), "sheet": sheet}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    except OSError:
        pass

    safe_log(
        f"[Research] {len(facts)} datos verificados de {len(items)} fuentes en {time.time() - started:.1f}s "
        f"(hook: {'sí' if hook else 'no'})"
    )
    return sheet


# ---------------------------------------------------------------------------
# Integración con el plan del director
# ---------------------------------------------------------------------------

def _match_fact(text: str, facts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    text_nums = set(_extract_numbers(text))
    text_terms = _tokens(text)
    best = None
    best_score = 0.0
    for fact in facts:
        fact_terms = _tokens(fact.get("claim", ""))
        shared = len(text_terms & fact_terms)
        union = text_terms | fact_terms
        jaccard = shared / max(1, len(union))
        number_hit = bool(text_nums & set(fact.get("numbers") or []))
        score = (2.0 if number_hit else 0.0) + jaccard
        if not number_hit and not (shared >= 3 and jaccard >= 0.45):
            continue
        if score > best_score:
            best_score, best = score, fact
    return best


def attach_sources_to_plan(plan: Any, sheet: Dict[str, Any]) -> int:
    """Añade la fuente real a las cards que usan un dato del fact sheet."""
    facts = sheet.get("facts") or []
    if not facts:
        return 0
    attached = 0
    for scene in getattr(plan, "scenes", []) or []:
        card = getattr(scene, "card", None)
        if not card:
            continue
        headline = str(getattr(card, "headline", "") or "")
        body = str(getattr(card, "body", "") or "")
        stat = str(getattr(card, "stat", "") or "")
        match = _match_fact(" ".join((headline, body, stat)), facts)
        if not match:
            continue
        params = getattr(card, "params", None)
        if not isinstance(params, dict):
            params = {}
            try:
                card.params = params
            except Exception:
                continue
        params.setdefault("source", match.get("source", ""))
        params.setdefault("source_url", match.get("url", ""))
        badge = str(getattr(card, "badge", "") or "").strip().lower()
        if badge in GENERIC_TAGS or not badge:
            try:
                card.badge = "DATO VERIFICADO"
            except Exception:
                pass
        attached += 1
    return attached


def _known_numbers(sheet: Dict[str, Any]) -> Tuple[set, set]:
    facts = sheet.get("facts") or []
    known: set = set()
    years: set = set()
    for fact in facts:
        known.update(str(n) for n in (fact.get("numbers") or []))
        years.update(YEAR_RE.findall(fact.get("claim", "")))
    return known, years


def _unsupported_in_text(speech: str, known: set, known_years: set) -> List[str]:
    out: List[str] = []
    for number in _extract_numbers(speech):
        digits = re.match(r"(\d+)", number)
        if not digits:
            continue
        value = int(digits.group(1))
        if value <= 12 and not re.search(r"%|€|\$", number):
            continue
        if number in known or str(value) in known or str(value) in known_years:
            continue
        out.append(number)
    return out


def generate_hook_variants(topic: str, sheet: Dict[str, Any], llm: Any = None, deadline_sec: float = 18.0) -> List[Dict[str, Any]]:
    """Propone 3 ganchos cortos basados SOLO en datos del fact sheet.

    Si el LLM no está disponible o devuelve cifras no respaldadas, se usan los
    propios hechos verificados como ganchos (sin inventar nada).
    """
    facts = sheet.get("facts") or []
    if not facts:
        return []
    known, known_years = _known_numbers(sheet)

    variants: List[Dict[str, Any]] = []
    if llm is not None:
        allowed = "\n".join(f"{i}. {f['claim']} [Fuente: {f['source']}]" for i, f in enumerate(facts[:8], start=1))
        prompt = f"""Eres guionista de ganchos para YouTube/Shorts en español.
Tema: "{topic}".

DATOS VERIFICADOS (no puedes usar otras cifras):
{allowed}

Escribe 3 ganchos de apertura distintos, cada uno de máximo 80 caracteres:
- Deben despertar curiosidad sin mentir ni exagerar.
- Sin emojis, sin mayúsculas gritadas, sin "¿Sabías que...?" repetido.
- Cada gancho debe apoyarse en uno de los datos (indica el número).
- Español neutro, directo, concreto.

Devuelve SOLO JSON: {{"hooks":[{{"text":"...","fact":1,"score":95,"best":true,"reason":"..."}}]}}"""
        try:
            if llm is None:
                from core.llm import LLMClient
                llm = LLMClient()
            raw = llm.generate(prompt, json_mode=True, deadline_sec=deadline_sec)
            from utils.json_validator import JSONValidator
            data = JSONValidator.extract_and_parse(raw)
            for item in (data.get("hooks") or [])[:5]:
                if not isinstance(item, dict):
                    continue
                text = _clean_hook_text(item.get("text", ""))
                if not text or len(text) > 90:
                    continue
                if _unsupported_in_text(text, known, known_years):
                    continue
                try:
                    idx = int(item.get("fact", 0)) - 1
                except (TypeError, ValueError):
                    idx = -1
                source = facts[idx]["source"] if 0 <= idx < len(facts) else facts[0]["source"]
                try:
                    score = int(float(item.get("score", 0)))
                except (TypeError, ValueError):
                    score = 0
                variants.append({
                    "text": text,
                    "source": source,
                    "reason": _clean_hook_text(item.get("reason", ""), 140),
                    "score": max(0, min(100, score)),
                    "best": bool(item.get("best", False)),
                })
        except Exception as exc:
            safe_log(f"[Research] No se generaron ganchos con IA: {exc}")

    if not variants:
        picked: List[Dict[str, Any]] = []
        best_fact = sheet.get("hook")
        if isinstance(best_fact, dict) and best_fact.get("claim"):
            picked.append(best_fact)
        for idx in (0, 2, 4):
            if idx < len(facts):
                picked.append({"claim": facts[idx]["claim"], "source": facts[idx]["source"]})
        used: set = set()
        for pos, fact in enumerate(picked):
            text = _clean_hook_text(_strip_reporting(fact.get("claim", "")), 140)
            key = _norm(text)[:60]
            if not text or key in used:
                continue
            used.add(key)
            variants.append({
                "text": text,
                "source": fact.get("source", ""),
                "reason": "Dato verificado del fact sheet.",
                "score": max(50, 100 - pos * 10),
                "best": pos == 0,
            })

    # Deduplicar conservando orden.
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for item in variants:
        key = _norm(item["text"])[:70]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    # La IA elige: mejor puntuación primero (con "best" como desempate).
    unique.sort(key=lambda h: (bool(h.get("best")), int(h.get("score", 0))), reverse=True)
    for position, item in enumerate(unique[:3]):
        item["recommended"] = position == 0
    return unique[:3]


def _clean_hook_text(text: str, limit: int = 90) -> str:
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]", "", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip().strip('"“”')
    if text:
        text = text[0].upper() + text[1:]
    if limit and len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = (cut or text[:limit]).rstrip(".,;:") + "…"
    return text


def _strip_reporting(text: str) -> str:
    """Quita conectores y marcos periodísticos para que el gancho empiece por el hecho."""
    clean = _clean_hook_text(text, 0).strip(" ,;:")
    clean = re.sub(
        r"^(sin embargo|no obstante|ademas|en ese escenario|en cuanto a [^,]+,|"
        r"el informe muestra que|el mismo organismo senalo que|el informe senala que|"
        r"segun [^,]+,|de acuerdo con [^,]+,|los datos muestran que)\s*",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = clean.strip(" ,;:–—-")
    if clean:
        clean = clean[0].upper() + clean[1:]
    return clean or _clean_hook_text(text, 120)


def audit_plan_numbers(plan: Any, sheet: Dict[str, Any]) -> Dict[str, Any]:
    """Detecta cifras del guion que no aparecen en la investigación."""
    known, known_years = _known_numbers(sheet)
    unsupported: List[Dict[str, Any]] = []
    checked = 0
    for scene in getattr(plan, "scenes", []) or []:
        speech = str(getattr(scene, "speech", "") or "")
        checked += len(_extract_numbers(speech))
        for number in _unsupported_in_text(speech, known, known_years):
            unsupported.append({
                "scene": getattr(scene, "scene_id", None),
                "number": number,
                "context": speech[:140],
            })
    return {"checked": checked, "unsupported": unsupported[:20], "count": len(unsupported)}


def repair_unsupported_numbers(plan: Any, sheet: Dict[str, Any], llm: Any = None, deadline_sec: float = 25.0) -> int:
    """Reescribe las locuciones con cifras sin respaldo usando SOLO el fact sheet.

    Es una corrección acotada: si la nueva versión conserva cifras inventadas o
    cambia demasiado la longitud, se descarta y se mantiene la original.
    """
    facts = sheet.get("facts") or []
    if not facts:
        return 0
    audit = audit_plan_numbers(plan, sheet)
    if not audit.get("unsupported"):
        return 0

    scenes = {getattr(s, "scene_id", None): s for s in getattr(plan, "scenes", []) or []}
    targets = []
    for item in audit["unsupported"]:
        scene = scenes.get(item["scene"])
        if scene is not None and scene not in targets:
            targets.append(scene)
    if not targets:
        return 0

    allowed = "\n".join(f"- {f['claim']} [Fuente: {f['source']}]" for f in facts[:8])
    payload = [{"scene_id": getattr(s, "scene_id", None), "speech": str(getattr(s, "speech", ""))} for s in targets]
    prompt = f"""Eres editor de guion para un canal documental en español.
Estas locuciones contienen cifras que NO están respaldadas por la investigación.

DATOS VERIFICADOS (únicas cifras permitidas):
{allowed}

LOCUCIONES A CORREGIR:
{json.dumps(payload, ensure_ascii=False, indent=1)}

Reescribe cada locución cumpliendo:
- Elimina o sustituye cualquier cifra que no esté en los DATOS VERIFICADOS.
- Si no hay un dato equivalente, explica la idea SIN cifras (no inventes).
- Conserva el significado, el tono y una longitud similar (±20%).
- No agregues nuevas cifras que no aparezcan en la lista.

Devuelve SOLO JSON: {{"scenes":[{{"scene_id":1,"speech":"..."}}]}}"""

    try:
        if llm is None:
            from core.llm import LLMClient
            llm = LLMClient()
        raw = llm.generate(prompt, json_mode=True, deadline_sec=deadline_sec)
        from utils.json_validator import JSONValidator
        data = JSONValidator.extract_and_parse(raw)
        rewritten = data.get("scenes") if isinstance(data, dict) else None
    except Exception as exc:
        safe_log(f"[Research] No se pudieron reparar cifras sin respaldo: {exc}")
        return 0

    known, known_years = _known_numbers(sheet)
    applied = 0
    for item in rewritten or []:
        if not isinstance(item, dict):
            continue
        try:
            scene_id = int(item.get("scene_id"))
        except (TypeError, ValueError):
            continue
        scene = scenes.get(scene_id)
        new_speech = str(item.get("speech", "") or "").strip()
        if scene is None or not new_speech:
            continue
        old_words = len(str(getattr(scene, "speech", "")).split())
        new_words = len(new_speech.split())
        if old_words and not (old_words * 0.6 <= new_words <= old_words * 1.4):
            continue
        if _unsupported_in_text(new_speech, known, known_years):
            continue
        scene.speech = new_speech
        applied += 1

    if applied:
        safe_log(f"[Research] {applied} locuciones corregidas para eliminar cifras sin respaldo.")
    return applied
