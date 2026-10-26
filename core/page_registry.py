"""Registro único de páginas, canales y temas.

Evita que un video de tecnología termine en la página de historia (o al revés).
Es la fuente de verdad para auditar el ruteo; los productores pueden seguir
usando sus IDs, pero aquí queda documentado a qué tema pertenece cada página.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from config.settings import settings
from core.llm import safe_log

REGISTRY_FILE = settings.STORAGE_DIR / "page_registry.json"


def load_registry() -> Dict[str, Any]:
    if not REGISTRY_FILE.exists():
        return {"version": 1, "pages": []}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"version": 1, "pages": []}
    except Exception as exc:
        safe_log(f"[PageRegistry] No se pudo leer {REGISTRY_FILE.name}: {exc}")
        return {"version": 1, "pages": []}


def pages() -> List[Dict[str, Any]]:
    data = load_registry()
    return [p for p in (data.get("pages") or []) if isinstance(p, dict)]


def page_for_channel(channel_id: str) -> Optional[Dict[str, Any]]:
    for page in pages():
        if page.get("youtube_channel_id") and page.get("youtube_channel_id") == channel_id:
            return page
    return None


def theme_for_page(page_id: str) -> Optional[Dict[str, Any]]:
    for page in pages():
        if str(page.get("page_id")) == str(page_id):
            return page
    return None


def validate_channel_page(channel_id: str, page_id: str) -> Dict[str, Any]:
    page = theme_for_page(page_id)
    if not page:
        return {"mapped": False, "warnings": ["La página no está en page_registry.json"]}
    expected_channel = page.get("youtube_channel_id")
    warnings: List[str] = []
    if expected_channel and expected_channel != channel_id:
        warnings.append(
            f"El canal {channel_id} no es el canal asignado a '{page.get('page_name')}' "
            f"({expected_channel})"
        )
    return {
        "mapped": True,
        "page_name": page.get("page_name"),
        "theme": page.get("theme"),
        "producer": page.get("producer"),
        "warnings": warnings,
    }
