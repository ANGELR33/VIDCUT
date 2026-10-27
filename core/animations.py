"""Elige qué animación de representación corresponde a lo que dice el hablante.

Analiza la frase (o el concepto) y devuelve una especificación con el tipo y sus datos:

  counter   una cifra que cuenta hacia arriba ("la inflación subió 300%", "10 millones de usuarios")
  compare   dos cosas frente a frente con barras ("Ferrari vs Toyota", "40% contra 25%")
  steps     una lista o secuencia ("primero A, segundo B, tercero C")
  concept   tarjeta con el concepto (por defecto, cuando no hay datos que animar)

Solo extrae datos que están en el texto: nunca inventa cifras. Función pura, español e inglés básico.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_UNIT = r"%|por ciento|percent|millones|millón|million|billones|mil millones|billion|mil|k|m|x|veces|times|años|years|días|days|dólares|dollars|usd|\$|€|euros"
_VALUE = re.compile(rf"(?P<pre>[$€])?\s*(?P<num>{_NUM})\s*(?P<unit>{_UNIT})?", re.IGNORECASE)
_VS = re.compile(r"\b(?:vs\.?|versus|contra|frente a|comparado con|compared to|compared with|against)\b", re.IGNORECASE)
_ORDINALS = re.compile(r"\b(primero|segundo|tercero|cuarto|quinto|first|second|third|fourth|fifth|paso\s*\d+|step\s*\d+)\b[:,]?\s*", re.IGNORECASE)


def parse_number(raw: str) -> Optional[float]:
    """'1.200.000' -> 1200000, '3,5' -> 3.5, '2.5' -> 2.5. None si no es un número claro."""
    s = raw.strip()
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
        return float(re.sub(r"[.,]", "", s))
    if re.fullmatch(r"\d+[.,]\d+", s):
        return float(s.replace(",", "."))
    if s.isdigit():
        return float(s)
    return None


def _unit_scale(unit: str) -> float:
    u = (unit or "").lower()
    if u in ("mil millones", "billones", "billion"):
        return 1e9
    if u in ("millones", "millón", "million", "m"):
        return 1e6
    if u in ("mil", "k"):
        return 1e3
    return 1.0


def _values(text: str) -> List[Dict[str, Any]]:
    out = []
    for m in _VALUE.finditer(text or ""):
        num = parse_number(m.group("num"))
        if num is None:
            continue
        unit = (m.group("unit") or "").strip()
        prefix = (m.group("pre") or "").strip()
        out.append({"value": num, "unit": unit, "prefix": prefix, "span": m.span(),
                    "text": m.group(0).strip()})
    return out


def _clean_label(text: str) -> str:
    t = re.sub(r"\s+", " ", re.sub(_VALUE, " ", text or "")).strip(" ,.;:-—¿?¡!\"'")
    words = t.split()
    return " ".join(words[-4:]) if len(words) > 4 else t


def display_unit(v: Dict[str, Any]) -> str:
    u = v["unit"].lower()
    if u in ("%", "por ciento", "percent"):
        return "%"
    if u in ("x", "veces", "times"):
        return "x"
    if v["prefix"] in ("$", "€"):
        return ""
    return {"millones": " M", "millón": " M", "million": " M", "m": " M", "mil": " K", "k": " K",
            "mil millones": " MM", "billones": " MM", "billion": " MM"}.get(u, f" {v['unit']}" if v["unit"] else "")


def split_steps(text: str) -> List[str]:
    parts = [p.strip(" ,.;:") for p in _ORDINALS.split(text or "")]
    parts = [p for p in parts if p and not _ORDINALS.fullmatch(p + " ")]
    return parts


def choose_animation(phrase: str, concept: str = "") -> Dict[str, Any]:
    """{kind, ...datos}. Si no hay nada que animar, kind='concept' con el concepto como texto."""
    text = " ".join(x for x in (phrase, concept) if x).strip()
    label = (concept or phrase or "").strip()
    values = _values(phrase or text)

    if phrase and _VS.search(phrase):
        left, right = _VS.split(phrase, maxsplit=1)
        a, b = _values(left), _values(right)
        if a and b and a[-1]["unit"].lower() == b[0]["unit"].lower():
            return {"kind": "compare", "title": label,
                    "items": [{"label": _clean_label(left) or "A", "value": a[-1]["value"] * _unit_scale(a[-1]["unit"]),
                               "display": a[-1]["text"]},
                              {"label": _clean_label(right) or "B", "value": b[0]["value"] * _unit_scale(b[0]["unit"]),
                               "display": b[0]["text"]}]}

    steps = split_steps(phrase or "")
    if phrase and len(_ORDINALS.findall(phrase)) >= 2 and len(steps) >= 2:
        return {"kind": "steps", "title": label, "items": [s for s in steps[:5]]}

    if values:
        best = max(values, key=lambda v: v["value"] * _unit_scale(v["unit"]))
        is_year = 1900 <= best["value"] <= 2100 and not best["unit"] and not best["prefix"]
        if not is_year:
            return {"kind": "counter", "title": label, "value": best["value"], "prefix": best["prefix"],
                    "suffix": display_unit(best), "decimals": 1 if best["value"] != int(best["value"]) else 0}
    return {"kind": "concept", "title": label}
