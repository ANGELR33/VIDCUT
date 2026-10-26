"""
Remotion Engine — capa de composición profesional de AetherCut.

Renderiza con Remotion (React + Chromium headless) elementos animados con canal
alpha (MOV ProRes 4444) que FFmpeg superpone sobre la escena. Hoy:

  * Subtítulos palabra-por-palabra estilo divulgador, con la palabra hablada
    resaltada y las palabras clave (cifras, nombres propios, siglas, conceptos
    fuertes) en color de énfasis.

Diseño defensivo: si Node, las dependencias de ``remotion_studio`` o el render
fallan, devuelve ``None`` y SceneEngine cae a los subtítulos libass de siempre.
Nunca debe romper la producción de un video.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config.settings import settings

logger = logging.getLogger("aethercut.remotion")

# Palabras que merecen énfasis visual aunque no sean cifras ni nombres propios.
_EMPHASIS_WORDS = {
    "nunca", "jamás", "jamas", "millones", "miles", "secreto", "secretos",
    "increíble", "increible", "descubrimiento", "peligro", "peligroso",
    "urgente", "primera", "primer", "único", "unico", "única", "unica",
    "imposible", "verdad", "mentira", "falso", "falsa", "científicos",
    "cientificos", "misterio", "anomalía", "anomalia", "récord", "record",
    "histórico", "historico", "revolución", "revolucion", "peor", "mejor",
    "nadie", "todos", "todo", "cero", "gratis", "prohibido", "oculto",
}

_ACRONYM = re.compile(r"^[A-ZÁÉÍÓÚÑ]{2,}[.,;:!?…]*$")
_HAS_NUMBER = re.compile(r"[\d%$€£]")
_STRIP_PUNCT = re.compile(r"[.,;:!?…¿¡\"'()\[\]«»]")


def split_words_with_timing(
    boundaries: Optional[Sequence[Tuple[float, float, str]]],
    speech: str,
    duration: float,
) -> List[Dict[str, Any]]:
    """Reparte el tiempo de cada frase del TTS entre sus palabras (por caracteres).

    Edge-TTS entrega límites por frase; dentro de cada una el reparto
    proporcional a la longitud (más una pequeña ponderación por sílaba larga)
    es indistinguible a simple vista y no requiere una segunda síntesis.
    """
    words: List[Dict[str, Any]] = []

    def spread(start: float, end: float, text: str) -> None:
        tokens = [t for t in text.replace("\n", " ").split(" ") if t.strip()]
        if not tokens:
            return
        span = max(0.2, end - start)
        weights = [max(1.0, len(_STRIP_PUNCT.sub("", t))) ** 0.9 + (0.6 if re.search(r"[,;:]$", t) else 0.0)
                   for t in tokens]
        total = sum(weights) or 1.0
        cursor = start
        for tok, wgt in zip(tokens, weights):
            w_dur = span * (wgt / total)
            words.append({"text": tok, "start": round(cursor, 3), "end": round(cursor + w_dur, 3)})
            cursor += w_dur

    if boundaries:
        for st, en, text in boundaries:
            spread(float(st), float(en), str(text))
    else:
        lead = 0.12
        active = max(2.0, duration - 0.45)
        spread(lead, lead + active, speech)

    mark_emphasis(words)
    return words


def mark_emphasis(words: List[Dict[str, Any]], max_ratio: float = 0.28) -> None:
    """Marca palabras clave sin saturar: como mucho ~28 % del texto y nunca
    dos seguidas (si todo es énfasis, nada lo es)."""
    candidates: List[Tuple[int, float]] = []
    sentence_start = True
    for i, w in enumerate(words):
        raw = w["text"]
        bare = _STRIP_PUNCT.sub("", raw)
        low = bare.lower()
        score = 0.0
        if _HAS_NUMBER.search(raw):
            score = 3.0
        elif _ACRONYM.match(raw) and len(bare) >= 2:
            score = 2.8
        elif bare[:1].isupper() and not sentence_start and len(bare) >= 4:
            score = 2.2  # nombre propio a mitad de frase
        elif low in _EMPHASIS_WORDS:
            score = 1.8
        elif len(bare) >= 12:
            score = 1.0
        if score > 0:
            candidates.append((i, score))
        sentence_start = bool(re.search(r"[.!?…]$", raw))

    budget = max(1, int(len(words) * max_ratio))
    chosen: List[int] = []
    for idx, _score in sorted(candidates, key=lambda c: -c[1]):
        if len(chosen) >= budget:
            break
        if any(abs(idx - c) <= 1 for c in chosen):
            continue
        chosen.append(idx)
    for i in chosen:
        words[i]["emphasis"] = True


class RemotionEngine:
    """Puente Python → Remotion (proceso Node) con degradación elegante."""

    STUDIO_DIR = settings.BASE_DIR / "remotion_studio"

    def __init__(self) -> None:
        self._available: Optional[bool] = None

    # ------------------------------------------------------------ disponibilidad
    def available(self) -> bool:
        if self._available is not None:
            return self._available
        ok = (
            shutil.which("node") is not None
            and (self.STUDIO_DIR / "render.mjs").exists()
            and (self.STUDIO_DIR / "node_modules" / "remotion").exists()
            and (self.STUDIO_DIR / "node_modules" / "@remotion" / "renderer").exists()
        )
        self._available = ok
        if not ok:
            logger.info("[Remotion] No disponible (¿npm install en remotion_studio?). Se usarán subtítulos libass.")
        return ok

    # ------------------------------------------------------------------ captions
    @staticmethod
    def caption_geometry(width: int, height: int, vertical: bool) -> Tuple[int, int, int, int]:
        """(strip_w, strip_h, x, y) de la franja de subtítulos dentro del frame."""
        if vertical:
            strip_h = int(height * 0.30)
            return width, strip_h, 0, int(height * 0.60)
        strip_h = int(height * 0.28)
        return width, strip_h, 0, height - strip_h

    async def render_captions(
        self,
        words: List[Dict[str, Any]],
        duration: float,
        out_dir: Path,
        width: int,
        height: int,
        vertical: bool,
        fps: int = 30,
        cancel_event: Optional[Any] = None,
        timeout: float = 420.0,
    ) -> Optional[Tuple[Path, int, int]]:
        """Renderiza los subtítulos animados. Devuelve (mov, x, y) o ``None``."""
        if not words or not self.available():
            return None

        strip_w, strip_h, x, y = self.caption_geometry(width, height, vertical)
        props = {
            "words": words,
            "durationSec": round(float(duration), 3),
            "width": strip_w,
            "height": strip_h,
            "fps": fps,
            "vertical": vertical,
            "activeColor": "#FFE14D",
            "emphasisColor": "#38BDF8",
        }
        digest = hashlib.md5(json.dumps(props, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_mov = out_dir / f"pro_captions_{digest}.mov"
        if out_mov.exists() and out_mov.stat().st_size > 20_000:
            return out_mov, x, y

        props_path = out_dir / f"pro_captions_{digest}.json"
        props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

        cmd = ["node", "render.mjs", str(props_path.resolve()), str(out_mov.resolve()), "KaiCaptions"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.STUDIO_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._kill(proc)
                raise
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            logger.warning("[Remotion] Render de subtítulos agotó el tiempo (%ss).", timeout)
            out_mov.unlink(missing_ok=True)
            return None
        except Exception as exc:
            logger.warning("[Remotion] No se pudo lanzar el render: %s", exc)
            return None

        if proc.returncode != 0 or not out_mov.exists() or out_mov.stat().st_size < 20_000:
            tail = ((err or b"") + (out or b"")).decode(errors="replace")[-400:]
            logger.warning("[Remotion] Render falló (rc=%s): %s", proc.returncode, tail)
            out_mov.unlink(missing_ok=True)
            return None
        return out_mov, x, y

    async def render_overlay(
        self,
        composition_id: str,
        props: Dict[str, Any],
        out_dir: Path,
        timeout: float = 120.0,
    ) -> Optional[Path]:
        """Renderiza cualquier composición React de Remotion con canal alpha a MOV ProRes 4444."""
        if not self.available():
            return None

        digest = hashlib.md5(
            json.dumps({"id": composition_id, "props": props}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:10]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_mov = out_dir / f"remotion_{composition_id}_{digest}.mov"
        if out_mov.exists() and out_mov.stat().st_size > 20_000:
            return out_mov

        props_path = out_dir / f"remotion_{composition_id}_{digest}.json"
        props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

        cmd = ["node", "render.mjs", str(props_path.resolve()), str(out_mov.resolve()), composition_id]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.STUDIO_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except Exception as exc:
            logger.warning("[Remotion] Error en render_overlay (%s): %s", composition_id, exc)
            return None

        if proc.returncode != 0 or not out_mov.exists() or out_mov.stat().st_size < 20_000:
            tail = ((err or b"") + (out or b"")).decode(errors="replace")[-300:]
            logger.warning("[Remotion] Falló render de %s: %s", composition_id, tail)
            out_mov.unlink(missing_ok=True)
            return None
        return out_mov

    @staticmethod
    def _kill(proc: "asyncio.subprocess.Process") -> None:
        try:
            proc.kill()
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            except Exception:
                pass

