"""Puente opcional con Remotion para animaciones de representación avanzadas.

Remotion (React + Chromium) permite animaciones más ricas que el dibujo con Pillow. Es opcional y
está APAGADO por defecto (``REMOTION=1`` para activarlo): requiere Node.js 18+, ``npm install`` dentro
de ``remotion/`` y un navegador Chromium. Licencia de Remotion: gratis para individuos y equipos de
hasta 3 personas; con 4 o más hay que adquirir la licencia de empresa
(https://www.remotion.dev/docs/license/faq).

Si algo falta o falla (Node, dependencias, navegador, tiempo agotado) devuelve None y el orquestador
usa el renderizador interno, así que activar Remotion nunca puede dejar un apoyo visual sin generar.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from core.motion_cards import palette_for

REMOTION_DIR = Path(__file__).resolve().parent.parent / "remotion"
COMPOSITIONS = ("counter", "compare", "steps")


def enabled() -> bool:
    return os.getenv("REMOTION", "0").strip().lower() in ("1", "true", "yes", "on")


def available() -> bool:
    return bool(shutil.which("node")) and (REMOTION_DIR / "node_modules" / "@remotion" / "renderer").is_dir()


def _hex(color: str) -> str:
    return "#" + color[2:] if color.startswith("0x") else color


def build_props(spec: Dict[str, Any], duration: float) -> Optional[Dict[str, Any]]:
    kind = spec.get("kind")
    if kind not in COMPOSITIONS:
        return None
    c1, c2, accent = palette_for(spec.get("title", "") or kind)
    props: Dict[str, Any] = {"title": spec.get("title", ""), "durationSec": float(duration),
                             "palette": {"c1": _hex(c1), "c2": _hex(c2), "accent": _hex(accent)}}
    if kind == "counter":
        props.update(value=spec["value"], prefix=spec.get("prefix", ""), suffix=spec.get("suffix", ""),
                     decimals=spec.get("decimals", 0))
    else:
        props["items"] = spec["items"]
    return {"composition": kind, "props": props}


def render(spec: Dict[str, Any], out: Path, duration: float = 4.0, timeout: int = 300) -> Optional[Path]:
    if not (enabled() and available()):
        return None
    payload = build_props(spec, duration)
    if payload is None:
        return None
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
            tmp = fh.name
        res = subprocess.run(["node", "render.mjs", "--spec", tmp, "--out", str(out.resolve())],
                             cwd=str(REMOTION_DIR), capture_output=True, text=True, timeout=timeout)
        return out if res.returncode == 0 and out.is_file() and out.stat().st_size > 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
