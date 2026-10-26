"""
video-use Adapter
Integra capacidades de video-use (CLI y servidor MCP) para extracción de keyframes,
análisis de ritmo visual e inspección de video para agentes de IA y la composición.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aethercut.video_use")


class VideoUseAdapter:
    def __init__(self):
        self.has_npx = True

    def extract_keyframes(
        self,
        video_path: Path,
        out_dir: Path,
        interval_sec: float = 3.0,
        max_frames: int = 8,
    ) -> List[Path]:
        """
        Extrae keyframes del video para que los agentes de IA (GLM-5.3 / Gemini)
        puedan inspeccionar el contenido visual, composición y ritmo de cortes.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        video_path = Path(video_path)

        if not video_path.exists():
            return []

        extracted: List[Path] = []
        try:
            # Intento de uso de video-use CLI si está en el entorno
            cmd_cli = [
                "npx", "--yes", "video-use", "frames",
                "-i", str(video_path),
                "-o", str(out_dir),
                "-n", str(max_frames),
            ]
            res = subprocess.run(cmd_cli, capture_output=True, timeout=12)
            if res.returncode == 0:
                extracted = sorted(list(out_dir.glob("*.jpg")) + list(out_dir.glob("*.png")))
                if extracted:
                    return extracted
        except Exception as _e:
            logger.debug(f"[VideoUse] CLI video-use fallback a ffmpeg: {_e}")

        # Fallback determinista ultrarrápido con FFmpeg local
        try:
            pattern = str(out_dir / "keyframe_%03d.jpg")
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", f"fps=1/{interval_sec},scale=640:-1",
                "-vframes", str(max_frames),
                "-q:v", "3",
                pattern,
            ]
            subprocess.run(cmd, capture_output=True, timeout=15)
            extracted = sorted(list(out_dir.glob("keyframe_*.jpg")))
        except Exception as exc:
            logger.warning(f"[VideoUse] Error extrayendo fotogramas: {exc}")

        return extracted

    def get_video_motion_summary(self, video_path: Path) -> Dict[str, Any]:
        """Devuelve metadatos básicos de duración, fps y dimensiones para sincronización."""
        video_path = Path(video_path)
        if not video_path.exists():
            return {"exists": False}

        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration",
                "-of", "json",
                str(video_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                streams = data.get("streams", [])
                if streams:
                    s = streams[0]
                    return {
                        "exists": True,
                        "width": int(s.get("width", 1920)),
                        "height": int(s.get("height", 1080)),
                        "fps": eval(s.get("r_frame_rate", "25/1")),
                        "duration": float(s.get("duration", 0.0) or 0.0),
                    }
        except Exception as exc:
            logger.debug(f"[VideoUse] Error en ffprobe summary: {exc}")

        return {"exists": True, "width": 1920, "height": 1080, "fps": 25.0}
