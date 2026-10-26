#!/usr/bin/env python3
"""Diagnóstico previo ("preflight"): comprueba que el entorno puede ejecutar VIDCUT.

    python scripts/doctor.py

Revisa Python, FFmpeg/FFprobe, dependencias, claves configuradas (solo dice si existen, nunca las muestra),
escritura en la carpeta de almacenamiento y tarifas de costos. Sale con código 1 si falta algo crítico.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
Check = Tuple[str, str, str]  # (nombre, estado: ok|warn|fail, detalle)

REQUIRED_MODULES = ["pydantic", "dotenv", "aiohttp", "aiofiles", "PIL", "fastapi", "uvicorn", "google.genai", "openai", "ddgs"]
OPTIONAL_MODULES = ["faster_whisper", "cv2", "scenedetect", "edge_tts", "yt_dlp"]
KEYS = {
    "GEMINI_API_KEY": "fail",       # sin Gemini no hay plan de edición
    "NVIDIA_API_KEY": "warn",       # respaldo y filtro de relevancia visual
    "DEEPSEEK_API_KEY": "warn",
    "PEXELS_API_KEY": "warn",
    "PIXABAY_API_KEY": "warn",
}


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def run_checks() -> List[Check]:
    _load_env()
    checks: List[Check] = []

    ok = sys.version_info >= (3, 10)
    checks.append(("Python >= 3.10", "ok" if ok else "fail", sys.version.split()[0]))

    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        checks.append((tool, "ok" if path else "fail", path or "no está en PATH"))

    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
            checks.append((f"módulo {name}", "ok", ""))
        except Exception as exc:
            checks.append((f"módulo {name}", "fail", f"{type(exc).__name__}: instala requirements.txt"))
    for name in OPTIONAL_MODULES:
        try:
            importlib.import_module(name)
            checks.append((f"módulo {name}", "ok", ""))
        except Exception:
            checks.append((f"módulo {name}", "warn", "opcional: algunas funciones no estarán disponibles"))

    for key, level in KEYS.items():
        present = bool(os.getenv(key, "").strip())
        checks.append((key, "ok" if present else level, "configurada" if present else "vacía o ausente"))

    storage = Path(os.getenv("AETHERCUT_STORAGE_DIR") or (ROOT / "storage"))
    try:
        storage.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=storage, delete=True):
            pass
        checks.append(("almacenamiento escribible", "ok", str(storage)))
    except OSError as exc:
        checks.append(("almacenamiento escribible", "fail", f"{storage}: {exc}"))

    pricing = ROOT / "config" / "pricing.json"
    try:
        data = json.loads(pricing.read_text(encoding="utf-8"))
        rates = (data.get("llm_per_million_tokens") or {}).items()
        missing = [name for name, r in rates if not name.startswith("_") and (r or {}).get("input") is None]
        checks.append(("tarifas de costos", "warn" if missing else "ok",
                       f"{len(missing)} modelo(s) sin tarifa en config/pricing.json" if missing else "completas"))
    except Exception as exc:
        checks.append(("tarifas de costos", "warn", f"no se pudo leer config/pricing.json: {exc}"))

    if not (ROOT / ".env").exists():
        checks.append((".env", "warn", "no existe: copia .env.example a .env y completa las claves"))
    return checks


def main() -> int:
    icons = {"ok": "OK  ", "warn": "AVISO", "fail": "FALLA"}
    checks = run_checks()
    for name, status, detail in checks:
        print(f"[{icons[status]}] {name}" + (f" - {detail}" if detail else ""))
    fails = sum(1 for _, s, _ in checks if s == "fail")
    warns = sum(1 for _, s, _ in checks if s == "warn")
    print(f"\nResultado: {fails} falla(s) crítica(s), {warns} aviso(s).")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
