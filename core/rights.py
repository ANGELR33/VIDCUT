"""Control de derechos del material visual (B-Roll) antes de publicar.

Cada recurso recibe un estado de derechos, calculado con el proveedor que lo entregó y la
procedencia que dejó guardada (``<cue>_provenance.json``):

  cleared               material propio, dominio público o fuente con licencia que no exige crédito
  attribution_required  archivo con licencia que exige citar la fuente (p. ej. Wikimedia CC BY-SA)
  review                uso editorial, de prensa o de empresa: revisar permiso antes de monetizar
  risky                 sin licencia clara o extraído de plataformas (clips de YouTube): riesgo de reclamo

La política ``LICENSE_POLICY`` decide qué se rechaza:
  permissive (por defecto)  no rechaza nada; solo registra y avisa (no cambia flujos existentes)
  balanced                  rechaza ``risky``
  strict                    rechaza ``review`` y ``risky``

Esto es una ayuda para el criterio humano, no asesoría legal: ninguna clasificación automática
garantiza que un uso esté permitido.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List

from core.licensing import classify_license

STATUSES = ("cleared", "attribution_required", "review", "risky")
_RANK = {s: i for i, s in enumerate(STATUSES)}

# Piso por proveedor: el estado nunca puede ser mejor que este.
PROVIDER_FLOOR = {
    "LocalOriginalAssetProvider": "cleared",
    "OriginalSourceAssetProvider": "cleared",
    "OpenStockAssetProvider": "attribution_required",
    "WebPhotoAssetProvider": "review",
    "PexelsAssetProvider": "attribution_required",
    "PixabayAssetProvider": "attribution_required",
    "YouTubeReactionAssetProvider": "risky",
}
_PUBLIC_DOMAIN = re.compile(r"public domain|dominio p[uú]blico|cc0|cc-0|pd-", re.IGNORECASE)


def _worse(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


def policy() -> str:
    value = os.getenv("LICENSE_POLICY", "permissive").strip().lower()
    return value if value in ("permissive", "balanced", "strict") else "permissive"


def policy_allows(status: str, mode: str = "") -> bool:
    mode = mode or policy()
    if mode == "strict":
        return status in ("cleared", "attribution_required")
    if mode == "balanced":
        return status != "risky"
    return True


def classify_rights(provider: str, provenance: Dict[str, Any] | None) -> Dict[str, str]:
    """{status, note, attribution} para un recurso entregado por ``provider``."""
    prov = provenance or {}
    floor = PROVIDER_FLOOR.get(provider, "review")
    source_url = str(prov.get("source_url", "") or "")
    license_text = str(prov.get("license", "") or "")

    if str(prov.get("source_name", "")).startswith("Biblioteca original") or provider == "LocalOriginalAssetProvider":
        return {"status": "cleared", "note": "Material propio del canal.", "attribution": ""}

    status, note = floor, ""
    if source_url:
        info = classify_license(source_url)
        cls = info["class"]
        if cls == "local_original":
            by_domain, note = "cleared", "Archivo local propio."
        elif cls == "licensed_or_public":
            by_domain = "attribution_required"
            note = "Archivo con licencia o dominio público: cita la fuente."
        elif cls in ("official_source", "technical_press_benchmark", "editorial_use"):
            by_domain, note = "review", info["note"]
        elif cls == "stock":
            by_domain, note = "review", "Banco de imágenes: verifica la licencia concreta."
        else:
            by_domain, note = "risky", info["note"]
        # El dominio solo puede empeorar el piso del proveedor, salvo licencias libres explícitas.
        status = _worse(floor, by_domain)
    else:
        note = "Sin registro de procedencia: no se puede verificar la licencia."
        status = _worse(floor, "review")

    if _PUBLIC_DOMAIN.search(license_text) and status == "attribution_required" and provider != "WebPhotoAssetProvider":
        status, note = "cleared", "Dominio público (CC0 o equivalente)."

    if provider == "YouTubeReactionAssetProvider":
        status, note = "risky", "Clip tomado de YouTube: puede generar reclamo de derechos de autor."

    attribution = ""
    if status == "attribution_required":
        who = prov.get("artist") or prov.get("source_name") or "Autor desconocido"
        title = prov.get("context_note") or ""
        attribution = f"{title + ' — ' if title else ''}{who} ({source_url or 'sin URL'})" + (
            f" [{license_text}]" if license_text else "")
    return {"status": status, "note": note, "attribution": attribution}


def summarize(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for item in items:
        counts[item.get("status", "review")] = counts.get(item.get("status", "review"), 0) + 1
    return counts


def render_markdown(items: List[Dict[str, Any]], mode: str) -> str:
    counts = summarize(items)
    lines = [
        "# Reporte de derechos del material visual", "",
        f"- Política activa: **{mode}**",
        f"- Liberado: {counts['cleared']}  ·  Requiere crédito: {counts['attribution_required']}  ·  "
        f"Revisar: {counts['review']}  ·  Riesgoso: {counts['risky']}", "",
        "Es una ayuda para tu revisión, no asesoría legal.", "",
    ]
    pending = [i for i in items if i["status"] in ("review", "risky")]
    if pending:
        lines += ["## Revisar antes de publicar", "", "| Estado | Concepto | Proveedor | Fuente | Nota |", "|---|---|---|---|---|"]
        lines += [f"| {i['status']} | {i['concept']} | {i['provider']} | {i['source_url'] or '-'} | {i['note']} |"
                  for i in pending]
        lines.append("")
    credits = [i["attribution"] for i in items if i["attribution"]]
    if credits:
        lines += ["## Créditos para la descripción", ""] + [f"- {c}" for c in dict.fromkeys(credits)] + [""]
    return "\n".join(lines)
