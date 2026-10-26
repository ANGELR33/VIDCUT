#!/usr/bin/env python3
"""Escáner de claves y secretos en archivos versionados. Solo usa la biblioteca estándar.

Uso:
    python scripts/check_secrets.py            # escanea el repo (git ls-files)
    python scripts/check_secrets.py RUTA       # escanea una carpeta

Sale con código 1 si encuentra algo. Los valores de ejemplo que contienen FAKE o EXAMPLE se ignoran.
Nunca imprime el secreto completo, solo un fragmento enmascarado.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

PATTERNS = {
    "NVIDIA API key": re.compile(r"nvapi-[A-Za-z0-9_\-]{20,}"),
    "OpenAI/DeepSeek style key": re.compile(r"\bsk-[A-Za-z0-9]{24,}"),
    "Speechify style key": re.compile(r"\bsk_[A-Za-z0-9]{30,}"),
    "Google API key": re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    "Gemini key (AQ.)": re.compile(r"\bAQ\.[A-Za-z0-9_\-]{30,}"),
    "Google OAuth client secret": re.compile(r"GOCSPX-[A-Za-z0-9_\-]{10,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "AetherCut live key": re.compile(r"aethercut_live_[A-Za-z0-9]{6,}"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "storage", "build", "out"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mp3", ".wav", ".zip",
                 ".ttf", ".otf", ".woff", ".woff2", ".pdf", ".ico", ".webm", ".mkv", ".pyc", ".ipynb_checkpoints"}
MAX_BYTES = 2_000_000


@dataclass
class Finding:
    path: str
    line: int
    kind: str
    preview: str


def _mask(value: str) -> str:
    return value[:6] + "***" + f"({len(value)} car.)"


def _is_placeholder(value: str) -> bool:
    upper = value.upper()
    return "FAKE" in upper or "EXAMPLE" in upper or "XXXX" in upper


def _candidate_files(root: Path) -> List[Path]:
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True)
        files = [root / p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]
        if files:
            return files
    except Exception:
        pass
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found.extend(Path(base) / n for n in names)
    return found


def scan(root: Path) -> List[Finding]:
    root = Path(root)
    findings: List[Finding] = []
    for path in _candidate_files(root):
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    if not _is_placeholder(match.group(0)):
                        findings.append(Finding(str(path.relative_to(root)), number, kind, _mask(match.group(0))))
    return findings


def main(argv: List[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    findings = scan(root)
    if not findings:
        print("OK: no se encontraron claves ni secretos en los archivos versionados.")
        return 0
    print(f"ERROR: {len(findings)} posible(s) secreto(s) encontrado(s):")
    for f in findings:
        print(f"  {f.path}:{f.line}  [{f.kind}]  {f.preview}")
    print("Quita el valor del código, muévelo a .env y ROTA la clave: si ya estuvo en el historial, está expuesta.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
