"""Filtro de relevancia visual para B-Roll.

Antes de aceptar un recurso descargado, un modelo con visión puntúa (0-10) si la
imagen o el fotograma realmente ilustra lo que dice el hablante. Si el puntaje
queda por debajo del umbral, el recurso se descarta y el orquestador prueba el
siguiente proveedor; si ninguno pasa, no se pone nada (mejor sin B-Roll que con
uno equivocado).

Diseño "fail-open": si ningún modelo de visión está disponible o falla, el
recurso se acepta tal cual (comportamiento anterior), nunca se bloquea el render.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

from core.llm import safe_log
from core.run_log import log_llm
import time

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}

DEFAULT_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "6"))
NVIDIA_VISION_MODEL = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-11b-vision-instruct")

JUDGE_PROMPT = """Eres un editor de video que decide si una imagen sirve como apoyo visual (B-Roll).

TEMA GENERAL DEL VIDEO: {topic}
FRASE QUE DICE EL HABLANTE: {phrase}
CONCEPTO A ILUSTRAR: {concept}

Mira la imagen y puntúa de 0 a 10 qué tan bien ilustra el concepto en el contexto del tema:
- 9-10: muestra exactamente la entidad, lugar, objeto o idea mencionada.
- 6-8: claramente relacionada y no induce a error.
- 3-5: genérica, de otro contexto, época o lugar, o solo tangencialmente relacionada.
- 0-2: sin relación, engañosa, con marca de agua visible, captura de pantalla irrelevante o texto ilegible.
Ante la duda, puntúa bajo. Es preferible no mostrar nada a mostrar algo equivocado.

Responde SOLO con JSON: {{"score": <número 0-10>, "reason": "<máximo 15 palabras>"}}"""


def parse_score(raw: str) -> Tuple[Optional[float], str]:
    """Extrae (score, reason) de la respuesta del modelo. (None, '') si no se puede."""
    if not raw:
        return None, ""
    text = raw.strip()
    data: Any = None
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None
    if isinstance(data, dict) and "score" in data:
        try:
            score = float(data["score"])
        except (TypeError, ValueError):
            return None, ""
        return max(0.0, min(10.0, score)), str(data.get("reason", ""))[:160]
    match = re.search(r"score\D{0,6}(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return max(0.0, min(10.0, float(match.group(1)))), ""
    return None, ""


def is_relevant(score: Optional[float], threshold: float = DEFAULT_THRESHOLD) -> bool:
    """Fail-open: sin puntaje (modelo no disponible) se acepta."""
    return True if score is None else score >= threshold


def _image_bytes(media_path: Path, max_side: int = 768) -> Optional[bytes]:
    """JPEG reducido de una imagen, o del fotograma central de un video."""
    from PIL import Image

    source = media_path
    tmp_frame: Optional[Path] = None
    try:
        if media_path.suffix.lower() in VIDEO_SUFFIXES:
            fd, tmp_name = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            tmp_frame = Path(tmp_name)
            duration = 0.0
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nw=1:nk=1", str(media_path)],
                    capture_output=True, text=True, timeout=20,
                )
                duration = float((probe.stdout or "0").strip() or 0)
            except Exception:
                duration = 0.0
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{max(0.0, duration / 2):.2f}", "-i", str(media_path),
                 "-frames:v", "1", "-q:v", "3", str(tmp_frame)],
                capture_output=True, timeout=30,
            )
            if not tmp_frame.exists() or tmp_frame.stat().st_size == 0:
                return None
            source = tmp_frame
        with Image.open(source) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=82)
            return buf.getvalue()
    except Exception as exc:
        safe_log(f"[Relevance] No se pudo preparar la imagen de {media_path.name}: {exc}")
        return None
    finally:
        if tmp_frame is not None:
            tmp_frame.unlink(missing_ok=True)


class RelevanceJudge:
    """Puntúa si un recurso visual ilustra lo que dice el hablante."""

    def __init__(self, llm: Any = None, threshold: float = DEFAULT_THRESHOLD,
                 concurrency: int = 3, enabled: bool = True):
        self.llm = llm
        self.threshold = threshold
        self.enabled = enabled
        self._sem = asyncio.Semaphore(concurrency)

    # ---- backends (síncronos; se ejecutan en hilo) ----
    def _score_nvidia(self, jpeg: bytes, prompt: str) -> Optional[str]:
        from config.settings import settings
        api_key = getattr(settings, "NVIDIA_API_KEY", "")
        if not api_key:
            return None
        from openai import OpenAI
        client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key, timeout=40.0)
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        started = time.monotonic()
        response = client.chat.completions.create(
            model=NVIDIA_VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}],
            temperature=0.0,
            max_tokens=120,
        )
        usage = getattr(response, "usage", None)
        log_llm("nvidia", NVIDIA_VISION_MODEL, "relevancia_visual",
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                latency_sec=time.monotonic() - started)
        return (response.choices[0].message.content or "").strip()

    def _score_gemini(self, jpeg: bytes, prompt: str) -> Optional[str]:
        if self.llm is None:
            return None
        from google.genai import types
        keys = self.llm.ordered_api_keys()
        if not keys:
            return None
        client = self.llm.client_for_key(keys[0])
        started = time.monotonic()
        response = client.models.generate_content(
            model=self.llm.models[0],
            contents=[types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), prompt],
            config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"),
        )
        usage = getattr(response, "usage_metadata", None)
        log_llm("gemini", self.llm.models[0], "relevancia_visual",
                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
                latency_sec=time.monotonic() - started)
        return (getattr(response, "text", "") or "").strip()

    def _score_sync(self, media_path: Path, prompt: str) -> Tuple[Optional[float], str]:
        jpeg = _image_bytes(media_path)
        if not jpeg:
            return None, "No se pudo leer el recurso para evaluarlo."
        for name, backend in (("NVIDIA", self._score_nvidia), ("Gemini", self._score_gemini)):
            try:
                raw = backend(jpeg, prompt)
            except Exception as exc:
                safe_log(f"[Relevance] {name} no pudo evaluar {media_path.name}: {exc}")
                continue
            if not raw:
                continue
            score, reason = parse_score(raw)
            if score is not None:
                return score, reason
        return None, "Ningún modelo de visión disponible."

    async def score(self, media_path: Path, concept: str, phrase: str = "",
                    topic: str = "") -> Tuple[Optional[float], str]:
        if not self.enabled:
            return None, "Filtro desactivado."
        prompt = JUDGE_PROMPT.format(
            topic=topic or "(no indicado)",
            phrase=phrase or "(no disponible)",
            concept=concept or "(no indicado)",
        )
        async with self._sem:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._score_sync, media_path, prompt), timeout=75
                )
            except Exception as exc:
                safe_log(f"[Relevance] Evaluación fallida para {media_path.name}: {exc}")
                return None, f"Error evaluando: {str(exc)[:80]}"
