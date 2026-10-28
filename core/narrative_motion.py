"""Bridge from semantic edit plans to Remotion's narrative motion-graphics composition.

The Remotion path is preferred when its local Node dependencies are installed; the existing
Pillow/FFmpeg renderer remains the fail-open fallback. No external API is required.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

STUDIO_DIR = Path(__file__).resolve().parent.parent / "remotion_studio"


def available() -> bool:
    return (
        shutil.which("node") is not None
        and (STUDIO_DIR / "render.mjs").is_file()
        and (STUDIO_DIR / "node_modules" / "@remotion" / "renderer").is_dir()
        and (STUDIO_DIR / "node_modules" / "remotion").is_dir()
    )


def enabled() -> bool:
    # Enabled by default for installations that already have Remotion Studio.
    return os.getenv("NARRATIVE_MOTION", "1").strip().lower() not in {"0", "false", "no", "off"}


def render_scene(
    spec: Dict[str, Any],
    out: Path,
    width: int,
    height: int,
    fps: int = 30,
    timeout: int = 240,
) -> Optional[Path]:
    """Render one semantic scene as a transparent ProRes MOV, or return None safely."""
    if not enabled():
        print("[NarrativeMotion] Motor Remotion desactivado por NARRATIVE_MOTION; se usará el motor de respaldo.")
        return None
    if not available():
        print("[NarrativeMotion] Remotion no está disponible (Node, render.mjs o dependencias ausentes); se usará el motor de respaldo.")
        return None
    try:
        duration = float(spec.get("duration", 0))
        if not 1.0 <= duration <= 15.0 or width < 320 or height < 240 or fps < 12 or fps > 60:
            return None
        props = {
            "kind": str(spec.get("kind", "concept"))[:32],
            "title": str(spec.get("title", ""))[:100],
            "labelA": str(spec.get("label_a", ""))[:48],
            "labelB": str(spec.get("label_b", ""))[:48],
            "spokenPhrase": str(spec.get("spoken_phrase", ""))[:400],
            "words": [
                {"word": str(w.get("word", ""))[:40], "start": max(0.0, float(w.get("start", 0.0))), "end": max(0.0, float(w.get("end", 0.0)))}
                for w in (spec.get("words", []) or [])
                if isinstance(w, dict) and str(w.get("word", "")).strip()
            ][:240],
            "durationSec": round(duration, 3),
            "width": int(width),
            "height": int(height),
            "fps": int(fps),
            "vertical": height > width,
            "theme": {"primary": "#70C8F2", "accent": "#F46B45", "bg": "#0B1017", "textColor": "#F4F2EC"},
        }
        digest = hashlib.sha256(json.dumps(props, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        final = out.with_name(f"{out.stem}_{digest}.mov")
        if final.is_file() and final.stat().st_size > 20_000:
            return final
        props_path = final.with_suffix(".json")
        tmp = final.with_name(final.stem + ".partial.mov")
        props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        try:
            proc = subprocess.run(
                ["node", "render.mjs", str(props_path.resolve()), str(tmp.resolve()), "NarrativeScene"],
                cwd=str(STUDIO_DIR), capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 20_000:
                detail = (proc.stderr or proc.stdout or "salida ausente o demasiado pequeña").strip()[-1200:]
                print(f"[NarrativeMotion] Render Remotion falló (código {proc.returncode}): {detail}")
                return None
            tmp.replace(final)
            return final
        finally:
            tmp.unlink(missing_ok=True)
            props_path.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"[NarrativeMotion] Error en puente Remotion: {exc}")
        return None
