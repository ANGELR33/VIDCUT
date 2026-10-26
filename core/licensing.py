"""Política de licencias para material visual.

Regla del proyecto: NO se usa stock genérico. Solo material original del canal,
archivo oficial/enciclopédico con licencia y, como último recurso, material
editorial/periodístico que debe revisarse antes de monetizar.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

ORIGINAL_SAFE_DOMAINS = (
    "wikimedia.org", "wikipedia.org", "archive.org", "nasa.gov", "esa.int",
    "noaa.gov", "loc.gov", "si.edu", "europa.eu", "gob.es", "gob.mx",
    "gob.cl", "gob.ar", "gob.co", "gob.pe", "gov.uk", "europa.eu",
)
OFFICIAL_COMPANY_DOMAINS = (
    "nvidia.com", "tsmc.com", "asml.com", "openai.com", "anthropic.com",
    "blog.google", "google.com", "microsoft.com", "apple.com", "intel.com",
    "samsung.com", "meta.com", "ibm.com", "qualcomm.com",
)

STOCK_DOMAINS = (
    "pexels.com", "pixabay.com", "unsplash.com", "shutterstock.com",
    "istockphoto.com", "gettyimages.com", "adobe.com", "stock.adobe.com",
    "dreamstime.com", "alamy.com", "depositphotos.com", "freepik.com",
    "vecteezy.com", "envato.com", "storyblocks.com",
)
EDITORIAL_DOMAINS = (
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "elpais.com",
    "elmundo.es", "elconfidencial.com", "cnn.com", "dw.com", "rtve.es",
    "efe.com", "afp.com", "bloomberg.com", "ft.com", "wsj.com",
)
TECH_AND_BENCHMARK_DOMAINS = (
    "huggingface.co", "arxiv.org", "paperswithcode.com", "lmsys.org",
    "artificialanalysis.ai", "github.com", "moonshot.cn", "kimi.ai", "kimi-k2.org",
    "deepseek.com", "openai.com", "anthropic.com", "mistral.ai", "cohere.com",
    "techcrunch.com", "theverge.com", "tomshardware.com", "anandtech.com",
    "arstechnica.com", "venturebeat.com", "semianalysis.com", "wccftech.com",
    "videocardz.com", "gsmarena.com", "medium.com", "towardsdatascience.com",
    "ecosistemastartup.com", "techmeme.com", "siliconangle.com", "x.com", "twitter.com",
)
UNKNOWN_SAFE_HINTS = (".gov", ".gob", ".edu", ".int")


def _result(domain: str, cls: str, allowed: bool, monetization_safe: bool, note: str) -> dict:
    return {
        "domain": domain,
        "class": cls,
        "allowed": allowed,
        "monetization_safe": monetization_safe,
        "original_or_archival": cls in ("local_original", "licensed_or_public", "official_source", "technical_press_benchmark"),
        "note": note,
    }


def classify_license(url: str) -> dict:
    text = str(url or "").strip()
    domain = ""
    try:
        domain = urlparse(text).netloc.replace("www.", "").lower()
    except Exception:
        pass

    if not domain and text:
        try:
            if Path(text).exists():
                return _result(
                    "local", "local_original", True, True,
                    "Material original del canal (biblioteca propia).",
                )
        except OSError:
            pass

    if any(d in domain for d in OFFICIAL_COMPANY_DOMAINS):
        return _result(
            domain, "official_source", True, False,
            "Sala de prensa/oficial de empresa: revisar permiso de uso de la imagen.",
        )
    if any(d in domain for d in STOCK_DOMAINS):
        return _result(
            domain, "stock", False, False,
            "Stock genérico: prohibido por la política editorial del canal.",
        )
    if any(d in domain for d in ORIGINAL_SAFE_DOMAINS) or any(domain.endswith(h) or h in domain for h in UNKNOWN_SAFE_HINTS):
        return _result(
            domain, "licensed_or_public", True, True,
            "Archivo oficial/enciclopédico con licencia o dominio público; citar fuente.",
        )
    if any(d in domain for d in TECH_AND_BENCHMARK_DOMAINS):
        return _result(
            domain, "technical_press_benchmark", True, False,
            "Publicación técnica, benchmark o reporte de investigación (citar fuente en pantalla).",
        )
    if any(d in domain for d in EDITORIAL_DOMAINS):
        return _result(
            domain, "editorial_use", True, False,
            "Uso editorial/periodístico: revisar derechos antes de monetizar.",
        )
    return _result(
        domain or "unknown", "unknown", False, False,
        "Origen sin licencia clara: no usar como material principal.",
    )
