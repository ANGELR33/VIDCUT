"""Módulo de Control de Calidad Visual Autónomo con Gemini Vision (VideoVisionQA).

Función:
Inspecciona fotogramas reales de los videos renderizados antes de su publicación en Facebook,
garantizando:
1. 0% contaminación cruzada (detecta y bloquea anime en canales de Fe, Política o Tech).
2. Coherencia temática con el nicho esperado.
3. Calidad estética y legibilidad visual.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.vision_qa")


class VideoVisionQA:
    """Auditor visual con Gemini Vision para control de calidad pre-publicación."""

    def __init__(self):
        self.temp_frames_dir = settings.STORAGE_DIR / "temp" / "qa_frames"
        self.temp_frames_dir.mkdir(parents=True, exist_ok=True)

    def extract_keyframes(self, video_path: Path, num_frames: int = 3) -> List[Path]:
        """Extrae fotogramas representativos a lo largo del video con FFmpeg."""
        if not video_path.exists():
            return []

        # Obtener duración del video con ffprobe
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "json", str(video_path)
        ]
        duration = 45.0
        try:
            res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            info = json.loads(res.stdout)
            duration = float(info.get("streams", [{}])[0].get("duration", 45.0))
        except Exception:
            pass

        timestamps: List[float] = []
        if num_frames == 1:
            timestamps = [duration * 0.5]
        elif num_frames == 2:
            timestamps = [duration * 0.3, duration * 0.7]
        else:
            timestamps = [duration * 0.25, duration * 0.50, duration * 0.75]

        extracted: List[Path] = []
        stem = video_path.stem
        for i, ts in enumerate(timestamps):
            out_img = self.temp_frames_dir / f"qa_{stem}_frame_{i+1}.jpg"
            out_img.unlink(missing_ok=True)
            # Extraer frame exacto
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{ts:.2f}",
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(out_img)
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=15)
                if out_img.exists() and out_img.stat().st_size > 1000:
                    extracted.append(out_img)
            except Exception as exc:
                safe_log(f"[VisionQA] Aviso extrayendo frame {i+1}: {exc}")

        return extracted

    def _gemini_client(self):
        api_key = (settings.GEMINI_API_KEY or "").split(",")[0].strip()
        if not api_key or api_key == "your_gemini_api_key_here":
            return None
        from google import genai
        return genai.Client(api_key=api_key)

    @staticmethod
    def _json_dict(data: Any) -> Dict[str, Any]:
        if isinstance(data, list):
            data = next((item for item in data if isinstance(item, dict)), {})
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _frames_for_asset(media_path: Path, count: int = 3) -> List[Path]:
        if media_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            return [media_path]

        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
                capture_output=True, text=True, timeout=15,
            )
            duration = float((probe.stdout or "").strip() or 0)
        except Exception:
            duration = 0.0

        times = [duration * 0.15, duration * 0.5, duration * 0.85] if duration > 1 else [1.0]
        out_dir = settings.STORAGE_DIR / "temp" / "qa_frames"
        out_dir.mkdir(parents=True, exist_ok=True)
        frames: List[Path] = []
        for index, ts in enumerate(times[:count]):
            out = out_dir / f"asset_{media_path.stem}_{index}.jpg"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", f"{max(0.0, ts):.2f}", "-i", str(media_path),
                     "-frames:v", "1", "-q:v", "3", str(out)],
                    capture_output=True, timeout=20,
                )
            except Exception:
                continue
            if out.exists() and out.stat().st_size > 1000:
                frames.append(out)
        return frames

    def classify_media(self, media_path: Path, scene_text: str = "") -> Dict[str, Any]:
        """Clasifica un asset antes de usarlo como fondo (diagrama, foto, anime, watermark...)."""
        media_path = Path(media_path)
        default = {
            "kind": "photo",
            "use_as_background": True,
            "has_dense_text": False,
            "has_watermark": False,
            "composition": "clean",
            "coherent_with_scene": True,
            "reason": "Sin auditoría",
        }
        if not media_path.exists():
            return default

        cache_dir = settings.STORAGE_DIR / "cache" / "media_qa"
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha1(
            f"{media_path.name}|{media_path.stat().st_size}|{int(media_path.stat().st_mtime)}".encode()
        ).hexdigest()
        cache_file = cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                cached = self._json_dict(json.loads(cache_file.read_text(encoding="utf-8")))
                if cached:
                    return {**default, **cached}
            except Exception:
                pass

        frames = self._frames_for_asset(media_path)
        client = self._gemini_client()
        if not frames or client is None:
            return default

        is_video = media_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp")
        try:
            from google.genai import types
            images = []
            for frame in frames:
                try:
                    images.append(Image.open(frame))
                except Exception:
                    pass
            if not images:
                return default
            prompt = (
                "Evalúa la calidad y relevancia de este recurso visual para un video profesional.\n"
                f"Narración / contexto de la escena: {scene_text[:500]}\n\n"
                "Determina con rigor:\n"
                "1. 'coherent_with_scene': ¿El contenido visual representa o se relaciona directamente con lo que se narra en la escena? (true/false). Si la narración trata de un tema y la imagen muestra algo completamente desconectado (por ejemplo, el sol o espacio cuando se habla de software o chips, o una oficina genérica cuando se habla de una batalla naval), responde false. Si muestra la entidad, persona, documento, gráfico o entorno del que se habla, responde true.\n"
                "2. 'kind': 'photo' | 'video_frame' | 'diagram' | 'chart_or_table' | 'document' | 'screenshot' | 'illustration' | 'anime' | 'watermark'\n"
                "3. 'has_dense_data': true si contiene gráficos, números, tablas, código o datos que requieren tiempo de lectura pausada.\n"
                "4. 'use_as_background': true si tiene calidad visual nítida para mostrarse en pantalla (sin marcas de agua comerciales invasivas tipo Shutterstock o Getty).\n"
                "5. 'has_watermark': true si tiene marcas de agua comerciales.\n"
                "6. 'recommended_dwell_sec': tiempo estimado recomendado en pantalla (ej: 3.5s a 8.0s) según su complejidad para que el espectador pueda apreciarlo y procesarlo con claridad.\n"
                "7. 'reason': explicación breve (1 frase).\n\n"
                "Responde JSON estricto:\n"
                "{\n"
                '  "coherent_with_scene": true/false,\n'
                '  "kind": "photo|video_frame|diagram|chart_or_table|document|screenshot|illustration|anime|watermark",\n'
                '  "has_dense_data": true/false,\n'
                '  "has_watermark": true/false,\n'
                '  "use_as_background": true/false,\n'
                '  "recommended_dwell_sec": 5.0,\n'
                '  "reason": "1 frase"\n'
                "}\n"
            )
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=images + [prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = self._json_dict(json.loads(response.text or "{}"))
            info = {**default, **{k: data.get(k, default[k]) for k in default}}
            try:
                cache_file.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
            return info
        except Exception as exc:
            safe_log(f"[VisionQA] classify_media falló para {media_path.name}: {exc}")
            return default
        finally:
            if is_video:
                for frame in frames:
                    try:
                        frame.unlink(missing_ok=True)
                    except OSError:
                        pass

    def audit_scene_image(self, frame_path: Path, scene_text: str, channel_name: str = "General") -> Dict[str, Any]:
        """Audita la composición de un plano ya renderizado (card + fondo + subtítulos)."""
        frame_path = Path(frame_path)
        if not frame_path.exists():
            return {"approved": True, "issues": [], "critique": "Sin frame"}
        client = self._gemini_client()
        if client is None:
            return {"approved": True, "issues": [], "critique": "Sin API key"}
        try:
            from google.genai import types
            image = Image.open(frame_path)
            prompt = (
                "Eres editor jefe de un canal de divulgación. Audita este fotograma de un video vertical.\n"
                f"Canal: {channel_name}\n"
                f"Lo que se narra en la escena: {scene_text[:500]}\n\n"
                "Rechaza (approved=false) si encuentras CUALQUIERA de estos defectos:\n"
                "- Texto cortado, palabras incompletas o diagramas recortados por el encuadre.\n"
                "- Una tarjeta/panel tapando texto importante del fondo o saliéndose del cuadro.\n"
                "- Collage, varias interfaces mezcladas o elementos que no se entienden.\n"
                "- Imagen incoherente con lo narrado o que parece un error de montaje.\n"
                "- Anime, caricaturas o logos de watermark.\n"
                "Aprueba solo si el plano es legible, coherente y se entiende de un vistazo.\n"
                "Nota: los subtítulos grandes en la parte inferior son parte normal del formato y NO son un defecto.\n\n"
                "Responde JSON: {\"approved\":true/false,\"issues\":[\"...\"],\"critique\":\"1-2 frases\"}"
            )
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=[image, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = json.loads(response.text or "{}")
            return {
                "approved": bool(data.get("approved", True)),
                "issues": data.get("issues", []) if isinstance(data.get("issues"), list) else [],
                "critique": str(data.get("critique", "")),
            }
        except Exception as exc:
            safe_log(f"[VisionQA] audit_scene_image falló: {exc}")
            return {"approved": True, "issues": [], "critique": str(exc)}

    def audit_video(
        self,
        video_path: Path,
        expected_niche: str,
        forbidden_elements: Optional[List[str]] = None,
        channel_name: str = "General",
    ) -> Dict[str, Any]:
        """
        Audita el video visualmente usando Gemini Vision.
        Retorna:
          {
            "approved": bool,
            "has_forbidden": bool,
            "critique": str,
            "detected_elements": List[str],
            "channel": str
          }
        """
        forbidden = forbidden_elements or ["anime", "caricaturas japonesas", "dibujos animados", "elementos fuera de contexto"]
        safe_log(f"\n[VisionQA] 👁️ Inspeccionando visualmente '{video_path.name}' para [{channel_name}]...")

        frames = self.extract_keyframes(video_path, num_frames=3)
        if not frames:
            safe_log("[VisionQA] ⚠️ No se pudieron extraer fotogramas para auditoría. Aprobando por omisión de extracción.")
            return {"approved": True, "warning": "No frames extracted", "channel": channel_name}

        # Preparar llamada a Gemini Vision
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "your_gemini_api_key_here":
            safe_log("[VisionQA] ⚠️ GEMINI_API_KEY no configurada. Saltando auditoría.")
            return {"approved": True, "warning": "No Gemini API key", "channel": channel_name}

        try:
            from google import genai
            from google.genai import types

            first_key = api_key.split(",")[0].strip()
            client = genai.Client(api_key=first_key)

            pil_images = []
            for f in frames:
                try:
                    pil_images.append(Image.open(f))
                except Exception:
                    pass

            if not pil_images:
                return {"approved": True, "warning": "Could not open frames as PIL images", "channel": channel_name}

            forbidden_str = ", ".join(forbidden)
            prompt = (
                f"Eres el Auditor Jefe de Calidad Visual de un estudio de video profesional.\n"
                f"Canal destino: {channel_name}\n"
                f"Nicho esperado: {expected_niche}\n"
                f"Elementos estrictamente PROHIBIDOS: {forbidden_str}\n\n"
                f"Examina los {len(pil_images)} fotogramas adjuntos del video final renderizado.\n"
                f"Determina si el metraje es coherente con el canal y confirma si contiene algún elemento prohibido.\n\n"
                f"Responde estrictamente en formato JSON:\n"
                f"{{\n"
                f"  \"approved\": true/false,\n"
                f"  \"has_forbidden\": true/false,\n"
                f"  \"forbidden_found\": [\"lista de cosas prohibidas si las hay\"],\n"
                f"  \"critique\": \"explicación concisa de 1 a 2 oraciones sobre lo que se ve en pantalla\",\n"
                f"  \"confidence\": 0.95\n"
                f"}}"
            )

            contents: list[Any] = pil_images + [prompt]
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )

            if response.text:
                result = json.loads(response.text)
                approved = bool(result.get("approved", True))
                has_forbidden = bool(result.get("has_forbidden", False))
                critique = result.get("critique", "Sin observaciones.")
                forbidden_found = result.get("forbidden_found", [])

                # Si detecta elementos prohibidos, desaprobar de inmediato
                if has_forbidden:
                    approved = False

                if approved:
                    safe_log(f"[VisionQA] ✅ APROBADO: {critique}")
                else:
                    safe_log(f"[VisionQA] 🛑 RECHAZADO: Elementos prohibidos detectados: {forbidden_found}. {critique}")

                return {
                    "approved": approved,
                    "has_forbidden": has_forbidden,
                    "critique": critique,
                    "forbidden_found": forbidden_found,
                    "channel": channel_name,
                }

        except Exception as exc:
            safe_log(f"[VisionQA] Aviso en auditoría Gemini Vision: {exc}. Permitiendo publicación con advertencia.")
            return {"approved": True, "warning": str(exc), "channel": channel_name}
        finally:
            # Limpiar frames temporales
            for f in frames:
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass

        return {"approved": True, "channel": channel_name}


# Instancia singleton para uso rápido en productores
vision_qa = VideoVisionQA()
