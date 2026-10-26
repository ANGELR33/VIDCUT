"""Confianza de fuentes para las tarjetas verificadas.

Un dato en pantalla con una fuente débil daña la credibilidad del video. Las reglas:

- Las redes sociales, foros y agregadores no cuentan como evidencia.
- Tarjeta de DATO (cifra, fecha, hecho) o de CORRECCIÓN: exige 1 fuente de nivel alto
  (gobierno, universidad, organismo internacional, agencia de noticias o revista científica)
  o 2 dominios distintos de nivel medio o superior.
- Tarjeta de ENTIDAD o definición (persona, lugar, término): basta 1 fuente de nivel medio
  o superior (p. ej. una enciclopedia).

Con ``SOURCE_TRUST_STRICT=0`` el chequeo se desactiva. Función pura y sin red.
"""

from __future__ import annotations

import os
import re
from typing import Iterable, List, Tuple

HIGH_EXACT = {
    "who.int", "un.org", "worldbank.org", "imf.org", "oecd.org", "europa.eu", "nasa.gov", "esa.int",
    "cern.ch", "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nature.com", "science.org",
    "thelancet.com", "nih.gov", "cepal.org", "iea.org", "bis.org", "ecb.europa.eu",
}
HIGH_SUFFIX = (".gov", ".edu", ".mil", ".int")
HIGH_PATTERN = re.compile(r"(^|\.)(gob|gov|gouv|edu|ac)\.[a-z]{2,3}$")
MEDIUM_EXACT = {
    "wikipedia.org", "britannica.com", "nytimes.com", "elpais.com", "bloomberg.com", "ft.com", "wsj.com",
    "theguardian.com", "washingtonpost.com", "dw.com", "france24.com", "cnn.com", "aljazeera.com",
    "economist.com", "lanacion.com.ar", "clarin.com", "infobae.com", "eltiempo.com", "elmundo.es",
    "expansion.com", "statista.com", "ourworldindata.org", "scientificamerican.com", "wired.com",
    "arstechnica.com", "techcrunch.com", "theverge.com", "xataka.com",
}
EXCLUDED = {
    "facebook.com", "instagram.com", "x.com", "twitter.com", "tiktok.com", "reddit.com", "quora.com",
    "pinterest.com", "medium.com", "blogspot.com", "wordpress.com", "tumblr.com", "youtube.com",
    "youtu.be", "linkedin.com", "answers.com", "yahoo.com", "brainly.lat", "brainly.com",
}
DATA_KINDS = {"cifra", "fecha", "dato", "estadistica", "estadística", "complemento", "refuerzo", "ley", "normativa"}


def normalize_domain(domain: str) -> str:
    d = (domain or "").lower().strip()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    return d[4:] if d.startswith("www.") else d


def _matches(domain: str, names: Iterable[str]) -> bool:
    return any(domain == n or domain.endswith("." + n) for n in names)


def tier(domain: str) -> str:
    """'excluded' | 'high' | 'medium' | 'low' para un dominio."""
    d = normalize_domain(domain)
    if not d:
        return "excluded"
    if _matches(d, EXCLUDED):
        return "excluded"
    if _matches(d, HIGH_EXACT) or d.endswith(HIGH_SUFFIX) or HIGH_PATTERN.search(d):
        return "high"
    if _matches(d, MEDIUM_EXACT):
        return "medium"
    return "low"


def _registrable(domain: str) -> str:
    parts = normalize_domain(domain).split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "co", "gob", "gov", "edu", "org", "ac"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else ".".join(parts)


def assess_sources(kind: str, verdict: str, domains: List[str]) -> Tuple[bool, str]:
    """(aceptable, motivo). Solo evalúa tarjetas 'supported' o 'contradicted'."""
    if os.getenv("SOURCE_TRUST_STRICT", "1").strip().lower() in ("0", "false", "no", "off"):
        return True, "chequeo desactivado"
    if verdict not in ("supported", "contradicted"):
        return True, "no aplica"

    usable = [d for d in (normalize_domain(x) for x in domains) if tier(d) != "excluded"]
    tiers = {d: tier(d) for d in usable}
    highs = [d for d, t in tiers.items() if t == "high"]
    mediums = [d for d, t in tiers.items() if t == "medium"]
    distinct_good = {_registrable(d) for d in highs + mediums}

    if not usable:
        return False, "las fuentes son redes sociales, foros o no tienen dominio"

    is_data = verdict == "contradicted" or (kind or "").lower() in DATA_KINDS
    if is_data:
        if highs or len(distinct_good) >= 2:
            return True, "fuente de nivel alto o dos fuentes independientes"
        return False, "un dato o corrección necesita una fuente oficial/científica o dos fuentes independientes"
    if highs or mediums:
        return True, "fuente de referencia reconocida"
    return False, "la entidad solo se apoya en fuentes de baja confianza"
