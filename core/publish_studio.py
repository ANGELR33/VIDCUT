"""Estudio de Publicación.

Prepara exactamente lo que se va a publicar: video master, metadatos SEO
generados con IA (título, descripción, etiquetas) y una miniatura 1280x720
creada con modelos de imagen de Gemini (Nano Banana), con opción de basarse
en un fotograma real del video y respaldo tipográfico local con Pillow.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image
from google import genai
from google.genai import types

from config.settings import settings
from core.llm import LLMClient, safe_log

THUMB_W, THUMB_H = 1280, 720

# Modelos de imagen a intentar en orden (Nano Banana primero).
IMAGE_MODEL_CANDIDATES = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
]

THUMB_STYLES: Dict[str, Dict[str, str]] = {
    "cinematic": {
        "label": "🎬 Cinemático",
        "prompt": (
            "miniatura de YouTube cinematográfica estilo documental premium: "
            "iluminación dramática azul y naranja, profundidad de campo, atmósfera de cine de alto presupuesto"
        ),
    },
    "neon": {
        "label": "⚡ Neón Tech",
        "prompt": (
            "miniatura de YouTube estilo tecnología futurista: fondo oscuro con luces de neón cian y magenta, "
            "interfaz holográfica, alta energía visual tipo canal de gadgets y IA"
        ),
    },
    "alerta": {
        "label": "🚨 Breaking News",
        "prompt": (
            "miniatura de YouTube estilo noticiario de última hora: tensión máxima, luz roja de alerta, "
            "contraste agresivo, sensación de urgencia periodística"
        ),
    },
    "viral": {
        "label": "🔥 Viral Clickbait",
        "prompt": (
            "miniatura de YouTube ultra clickeable estilo creador viral: colores saturados, expresiones extremas, "
            "flechas y círculos de atención, máximo contraste y CTR"
        ),
    },
    "educativo": {
        "label": "🎓 Educativo Limpio",
        "prompt": (
            "miniatura de YouTube educativa y limpia: fondo de estudio moderno ordenado, luz suave, "
            "estilo divulgación profesional"
        ),
    },
}


class PublishStudio:
    """Prepara video + metadatos + miniatura listos para publicar en YouTube."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.store_root = settings.PROJECTS_DIR / project_id

    # ------------------------------------------------------------------ utils
    def read_document(self) -> Dict[str, Any]:
        manifest = self.store_root / "project.json"
        return json.loads(manifest.read_text(encoding="utf-8"))

    def resolve_master_video(self, document: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """Localiza el archivo de video final que se va a publicar."""
        document = document or self.read_document()
        result = document.get("result") or {}
        candidates: List[Path] = [
            Path(result.get("output_file") or ""),
            settings.OUTPUTS_DIR / f"{self.project_id}_master.mp4",
            settings.OUTPUTS_DIR / f"{self.project_id}_edited.mp4",
        ]
        for url_key in ("master_video_url", "media_url"):
            url = str(result.get(url_key) or "")
            if url.startswith("/media/"):
                candidates.append(settings.OUTPUTS_DIR / url[len("/media/"):])
        for path in candidates:
            try:
                if path and path.is_file() and path.stat().st_size > 0:
                    return path
            except OSError:
                continue
        # Último recurso: el propio archivo fuente.
        source = Path(document.get("source_file") or "")
        if source.is_file():
            return source
        return None

    def _probe_duration(self, video: Path) -> float:
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
                capture_output=True, text=True, timeout=30, check=True,
            )
            return float(out.stdout.strip() or 0)
        except Exception:
            return 0.0

    def _extract_frame(self, video: Path, at_seconds: float) -> Optional[Path]:
        """Extrae un fotograma del video para usarlo como base de la miniatura."""
        frame_path = self.store_root / "work" / f"pub_frame_{int(time.time())}.jpg"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{max(0.0, at_seconds):.2f}", "-i", str(video),
                 "-frames:v", "1", "-q:v", "2", str(frame_path)],
                capture_output=True, timeout=60, check=True,
            )
            return frame_path if frame_path.exists() else None
        except Exception as exc:
            safe_log(f"[PublishStudio] No se pudo extraer fotograma: {exc}")
            return None

    def _thumbnail_path(self) -> Path:
        return settings.OUTPUTS_DIR / f"{self.project_id}_thumbnail.jpg"

    def current_thumbnail_url(self) -> Optional[str]:
        path = self._thumbnail_path()
        return f"/media/{path.name}" if path.exists() else None

    # ------------------------------------------------------------- preparación
    def prepare(self) -> Dict[str, Any]:
        """Resumen de exactamente lo que se va a publicar."""
        document = self.read_document()
        video = self.resolve_master_video(document)
        result = document.get("result") or {}
        topic = result.get("topic") or (document.get("options") or {}).get("topic") or ""
        title = result.get("title") or document.get("title") or document.get("original_name") or topic or "Producción KAI"
        duration = result.get("duration") or (self._probe_duration(video) if video else 0.0)
        channel_classification = None
        all_channels = []
        try:
            from core.channel_manager import ChannelManager
            channel_classification = ChannelManager.classify_content(topic=topic or title)
            all_channels = ChannelManager.list_channels()
        except Exception:
            pass

        return {
            "project_id": self.project_id,
            "video_found": bool(video),
            "video_path": str(video) if video else None,
            "video_size_mb": round(video.stat().st_size / 1024 / 1024, 1) if video else 0,
            "title": title,
            "topic": topic,
            "duration": duration,
            "thumbnail_url": self.current_thumbnail_url(),
            "channel_classification": channel_classification,
            "channels": all_channels,
        }

    # ------------------------------------------------------- metadatos con IA
    def generate_metadata(self, instructions: str = "") -> Dict[str, Any]:
        """Título, descripción y etiquetas SEO optimizados para CTR."""
        document = self.read_document()
        result = document.get("result") or {}
        topic = result.get("topic") or (document.get("options") or {}).get("topic") or ""
        base_title = result.get("title") or document.get("title") or document.get("original_name") or topic or "Producción KAI"
        duration = result.get("duration") or 0.0

        speech_hint = ""
        plan_path = self.store_root / "work" / "broadcast_plan.json"
        if plan_path.exists():
            try:
                raw = json.loads(plan_path.read_text(encoding="utf-8"))
                speech_lines = [sc.get("speech", "") for sc in raw.get("scenes", [])[:4] if sc.get("speech")]
                if speech_lines:
                    speech_hint = "Extracto del guion:\n" + "\n".join(speech_lines)[:900]
            except (OSError, json.JSONDecodeError):
                pass

        prompt = f"""Eres un experto en SEO y CTR de YouTube para un canal de divulgación/news en español.
Redacta los metadatos de publicación para este video.

Tema: {topic or base_title}
Título base: {base_title}
Duración: {int(duration // 60)} min {int(duration % 60)} s
{speech_hint}
{("Indicaciones del creador: " + instructions) if instructions else ""}

Responde SOLO con un JSON válido con estas claves:
- "title": título irresistible, máximo 95 caracteres, sin comillas, en español.
- "description": descripción de 3 párrafos: gancho con las primeras 2 líneas (aparecen antes de "mostrar más"), resumen del contenido y cierre con llamada a la acción de suscripción. Termina con 3 hashtags relevantes.
- "tags": lista de 12 a 18 etiquetas de búsqueda (sin #), cortas y específicas.
- "thumbnail_text": frase corta de máximo 4 palabras para poner gigante en la miniatura (todo mayúsculas, sin puntos)."""

        from utils.json_validator import JSONValidator
        client = LLMClient()
        raw = client.generate(prompt, json_mode=True, deadline_sec=60)
        data = JSONValidator.extract_and_parse(raw)
        tags = [t.strip().lstrip("#") for t in data.get("tags", []) if isinstance(t, str) and t.strip()]
        return {
            "title": str(data.get("title", base_title))[:100],
            "description": str(data.get("description", ""))[:5000],
            "tags": tags[:20],
            "thumbnail_text": str(data.get("thumbnail_text", ""))[:40],
        }

    # ----------------------------------------------------- miniatura con IA
    def _image_keys(self) -> List[str]:
        """Key dedicada primero; el pool general de Gemini como respaldo."""
        raw = settings.GEMINI_IMAGE_API_KEY
        keys = [k.strip() for k in raw.split(",") if k.strip() and k.strip() != "your_gemini_image_api_key_here"]
        for pool_key in (settings.GEMINI_API_KEY or "").split(","):
            pool_key = pool_key.strip()
            if pool_key and pool_key not in keys and pool_key != "your_gemini_api_key_here":
                keys.append(pool_key)
        return keys

    def _build_thumb_prompt(self, title: str, topic: str, style: str, thumbnail_text: str, has_base: bool) -> str:
        style_prompt = THUMB_STYLES.get(style, THUMB_STYLES["cinematic"])["prompt"]
        overlay = (thumbnail_text or title).strip().upper()[:38]
        base_instr = (
            "Transforma esta imagen en una miniatura de YouTube profesional manteniendo su contenido reconocible"
            if has_base else
            "Genera una imagen original como miniatura de YouTube profesional"
        )
        return (
            f"{base_instr} de 1280x720 (16:9), {style_prompt}. "
            f"Composición para alto CTR: sujeto principal grande a la derecha, y a la izquierda el texto "
            f"«{overlay}» en tipografía bold impactante de 4 a 6 palabras máximo por línea, blanco con borde "
            f"y sombra negra gruesa, perfectamente legible y sin errores ortográficos. "
            f"Contexto del video: {topic or title}. "
            "Sin marcas de agua, sin logos, sin bordes negros. Calidad ultra detallada."
        )

    def generate_ai_thumbnail(
        self,
        title: str,
        topic: str = "",
        style: str = "cinematic",
        thumbnail_text: str = "",
        use_frame: bool = False,
        frame_at: Optional[float] = None,
        custom_prompt: str = "",
    ) -> Dict[str, Any]:
        """Miniatura 1280x720 con el modelo de imagen de Gemini.

        Si use_frame=True toma un fotograma real del video como base para que
        el modelo lo mejore. Si Gemini no está disponible cae al motor PIL local.
        """
        keys = self._image_keys()
        base_path: Optional[Path] = None
        if use_frame:
            video = self.resolve_master_video()
            if video:
                if frame_at is None:
                    duration = self._probe_duration(video)
                    frame_at = duration * 0.25 if duration > 4 else 1.0
                base_path = self._extract_frame(video, frame_at)
            if not base_path:
                safe_log("[PublishStudio] No se pudo obtener fotograma; generando miniatura sin base.")

        prompt = custom_prompt.strip() if custom_prompt.strip() else self._build_thumb_prompt(
            title, topic, style, thumbnail_text, base_path is not None
        )

        models = list(dict.fromkeys([settings.GEMINI_IMAGE_MODEL] + IMAGE_MODEL_CANDIDATES))
        last_error: Optional[Exception] = None
        quota_exhausted = False
        api_disabled = False
        dead_models: set = set()  # 404: el modelo no existe para estas keys
        for key in keys:
            client = genai.Client(api_key=key)
            for model in [m for m in models if m not in dead_models]:
                try:
                    safe_log(f"[PublishStudio] Generando miniatura con {model}...")
                    contents: List[Any] = [prompt]
                    if base_path:
                        contents.append(types.Part.from_bytes(data=base_path.read_bytes(), mime_type="image/jpeg"))
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(aspect_ratio="16:9"),
                        ),
                    )
                    image_bytes = self._extract_image_bytes(response)
                    if not image_bytes:
                        raise ValueError("el modelo no devolvió ninguna imagen")
                    out = self._save_thumbnail(image_bytes)
                    safe_log(f"[PublishStudio] Miniatura IA generada con {model}: {out.name}")
                    return {"url": f"/media/{out.name}", "model": model, "engine": "gemini"}
                except Exception as exc:
                    last_error = exc
                    text = str(exc)
                    if "NOT_FOUND" in text or " 404" in text:
                        dead_models.add(model)
                    if "RESOURCE_EXHAUSTED" in text or " 429" in text:
                        quota_exhausted = True
                    if "PERMISSION_DENIED" in text or "has not been used in project" in text:
                        api_disabled = True
                    safe_log(f"[PublishStudio] {model} falló: {text[:120]}")

        # Respaldo: motor tipográfico local (Pillow).
        if api_disabled:
            note = ("La API de Gemini no está habilitada en el proyecto de Google Cloud de esta key. "
                    "Actívala en console.developers.google.com/apis/library/generativelanguage.googleapis.com y vuelve a generar.")
        elif quota_exhausted:
            note = ("Cuota de imagen de Gemini agotada ahora mismo; se usó el motor local. "
                    "Inténtalo de nuevo en unos minutos.")
        else:
            note = "Gemini no disponible; miniatura generada con el motor local."
        return self._pillow_fallback(title=title, topic=topic, thumbnail_text=thumbnail_text,
                                     note=note, error=str(last_error or "")[:200])

    def generate_studio_thumbnail_fast(self, title: str, topic: str = "", style: str = "cinematic") -> Dict[str, Any]:
        """Miniatura profesional de estudio 1280x720 con el motor local (Pillow).

        Ruta rápida y determinista para dejar cada video producido listo para
        publicar sin depender de la cuota de los modelos de imagen.
        """
        return self._pillow_fallback(title=title, topic=topic, thumbnail_text="",
                                      note="Miniatura profesional de estudio generada.", error="")

    def _pillow_fallback(self, title: str, topic: str, thumbnail_text: str,
                         note: str, error: str) -> Dict[str, Any]:
        """Motor tipográfico local: badge broadcast + titular gigante + acentos neón."""
        from core.thumbnail_maker import YouTubeThumbnailMaker
        maker = YouTubeThumbnailMaker()
        res = maker.generate(
            title=thumbnail_text or title,
            badge_text="🔴 ESTRENO KAI",
            subtitle=topic or title,
            project_id=self.project_id,
        )
        # Normalizar al nombre canónico {pid}_thumbnail.jpg que la biblioteca detecta.
        canonical = self._thumbnail_path()
        try:
            source = Path(res.get("path") or "")
            if source.is_file() and source != canonical:
                canonical.write_bytes(source.read_bytes())
                res["url"] = f"/media/{canonical.name}"
        except OSError:
            pass
        return {"url": res["url"], "model": "pillow-local", "engine": "pillow",
                "note": note, "error": error}

    @staticmethod
    def _extract_image_bytes(response) -> Optional[bytes]:
        try:
            for candidate in response.candidates or []:
                for part in (candidate.content.parts if candidate.content else []) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and inline.data:
                        return inline.data
        except Exception:
            pass
        return None

    def _save_thumbnail(self, image_bytes: bytes) -> Path:
        """Normaliza la imagen a 1280x720 JPEG <2MB (límite de YouTube)."""
        import io
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if img.size != (THUMB_W, THUMB_H):
            ratio = max(THUMB_W / img.width, THUMB_H / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            x0 = (new_size[0] - THUMB_W) // 2
            y0 = (new_size[1] - THUMB_H) // 2
            img = img.crop((x0, y0, x0 + THUMB_W, y0 + THUMB_H))
        out = self._thumbnail_path()
        quality = 92
        while quality >= 60:
            img.save(out, "JPEG", quality=quality)
            if out.stat().st_size < 2 * 1024 * 1024:
                return out
            quality -= 10
        return out
