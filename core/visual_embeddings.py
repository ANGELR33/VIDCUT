"""Embeddings visuales opcionales (CLIP) para búsqueda semántica y para evitar imágenes repetidas.

Con ``SEMANTIC_LIBRARY=1`` la biblioteca propia (``assets/broll``) se busca por significado y no por las
palabras del nombre del archivo. Con ``VISUAL_DEDUPE=1`` se evita repetir imágenes casi idénticas en un
mismo video. Requiere ``pip install sentence-transformers`` (modelo ``clip-ViT-B-32``) y es opcional:

  - Apagado por defecto. Si la librería o el modelo no están, ``get_encoder()`` devuelve ``None`` y todo
    el sistema sigue con su comportamiento anterior (sin errores).
  - Los vectores se guardan en caché por archivo (ruta, tamaño y fecha) para no recalcular.
  - Los umbrales de similitud dependen del modelo; ``SEMANTIC_MIN_SCORE`` y ``DEDUPE_THRESHOLD`` son
    ajustables y sus valores por defecto son orientativos: calíbralos con tu propia biblioteca.

La lógica de decisión (similitud, ranking, duplicados, caché) usa Python puro y se prueba con un
codificador simulado, sin descargar modelos.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

MEDIA_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm", ".mkv", ".m4v")
Vector = List[float]


class Encoder(Protocol):
    def encode_text(self, text: str) -> Vector: ...
    def encode_image(self, path: Path) -> Optional[Vector]: ...


def _flag(name: str) -> bool:
    return os.getenv(name, "0").strip().lower() in ("1", "true", "yes", "on")


def semantic_library_enabled() -> bool:
    return _flag("SEMANTIC_LIBRARY")


def dedupe_enabled() -> bool:
    return _flag("VISUAL_DEDUPE")


def semantic_min_score() -> float:
    return float(os.getenv("SEMANTIC_MIN_SCORE", "0.22"))


def dedupe_threshold() -> float:
    return float(os.getenv("DEDUPE_THRESHOLD", "0.93"))


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def is_duplicate(vec: Sequence[float], used: Sequence[Sequence[float]], threshold: Optional[float] = None) -> Tuple[bool, float]:
    """(es_duplicado, mayor_similitud) frente a las imágenes ya usadas."""
    limit = dedupe_threshold() if threshold is None else threshold
    best = max((cosine(vec, u) for u in used), default=0.0)
    return best >= limit, best


class ClipEncoder:
    """Codificador real basado en sentence-transformers (carga perezosa)."""

    def __init__(self, model_name: str = "clip-ViT-B-32"):
        from sentence_transformers import SentenceTransformer  # dependencia opcional
        self.model = SentenceTransformer(model_name)

    def encode_text(self, text: str) -> Vector:
        return [float(x) for x in self.model.encode(text, normalize_embeddings=True)]

    def encode_image(self, path: Path) -> Optional[Vector]:
        from core.relevance_gate import _image_bytes
        import io
        from PIL import Image
        data = _image_bytes(Path(path))
        if not data:
            return None
        with Image.open(io.BytesIO(data)) as im:
            return [float(x) for x in self.model.encode(im.convert("RGB"), normalize_embeddings=True)]


_encoder_state: Dict[str, Any] = {"tried": False, "encoder": None}


def get_encoder() -> Optional[Encoder]:
    """Codificador global o None si está apagado o no disponible (se intenta una sola vez)."""
    if not (semantic_library_enabled() or dedupe_enabled()):
        return None
    if not _encoder_state["tried"]:
        _encoder_state["tried"] = True
        try:
            _encoder_state["encoder"] = ClipEncoder()
        except Exception as exc:
            from core.llm import safe_log
            safe_log(f"[Embeddings] CLIP no disponible ({type(exc).__name__}); se usa el comportamiento anterior.")
    return _encoder_state["encoder"]


class LibraryIndex:
    """Índice semántico de una carpeta de medios con caché en disco."""

    def __init__(self, root: Path, encoder: Encoder, cache_path: Optional[Path] = None):
        self.root = Path(root)
        self.encoder = encoder
        self.cache_path = Path(cache_path) if cache_path else self.root / ".embeddings_cache.json"
        self.vectors: Dict[str, Vector] = {}
        self.stats = {"encoded": 0, "cached": 0, "failed": 0}

    def _load_cache(self) -> Dict[str, Any]:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def build(self) -> None:
        cache = self._load_cache()
        fresh: Dict[str, Any] = {}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
                continue
            rel = str(path.relative_to(self.root))
            stat = path.stat()
            key = {"size": stat.st_size, "mtime": int(stat.st_mtime)}
            hit = cache.get(rel)
            if hit and hit.get("size") == key["size"] and hit.get("mtime") == key["mtime"] and hit.get("vec"):
                vec = hit["vec"]
                self.stats["cached"] += 1
            else:
                try:
                    vec = self.encoder.encode_image(path)
                except Exception:
                    vec = None
                if not vec:
                    self.stats["failed"] += 1
                    continue
                self.stats["encoded"] += 1
            self.vectors[rel] = vec
            fresh[rel] = {**key, "vec": vec}
        try:
            self.cache_path.write_text(json.dumps(fresh), encoding="utf-8")
        except OSError:
            pass

    def search(self, text: str, top_k: int = 3, min_score: Optional[float] = None) -> List[Tuple[Path, float]]:
        if not self.vectors or not (text or "").strip():
            return []
        floor = semantic_min_score() if min_score is None else min_score
        query = self.encoder.encode_text(text)
        ranked = sorted(((cosine(query, v), rel) for rel, v in self.vectors.items()), reverse=True)
        return [(self.root / rel, round(score, 4)) for score, rel in ranked[:top_k] if score >= floor]
