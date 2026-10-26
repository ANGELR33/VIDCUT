import os
import shutil
import subprocess
import json
from pathlib import Path
from threading import Event
from typing import Dict, Any, Optional
from config.settings import settings
from process_runner import run_process

class FileManager:
    """Administrador del ciclo de vida de archivos, metadatos y limpieza de almacenamiento."""

    @staticmethod
    def get_media_metadata(file_path: Path, cancel_event: Optional[Event] = None) -> Dict[str, Any]:
        """Obtiene duración, resolución y framerate usando ffprobe."""
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo {file_path} no existe.")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_type",
            "-of", "json",
            str(file_path)
        ]
        
        try:
            result = run_process(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 check=True, timeout=60, cancel_event=cancel_event)
            data = json.loads(result.stdout)
            
            duration = float(data.get("format", {}).get("duration", 0.0))
            video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
            
            width = int(video_stream.get("width", 0)) if video_stream else 0
            height = int(video_stream.get("height", 0)) if video_stream else 0
            
            fps = 30.0
            if video_stream and "r_frame_rate" in video_stream:
                num, denom = video_stream["r_frame_rate"].split("/")
                fps = float(num) / float(denom) if float(denom) > 0 else 30.0
                
            return {
                "duration": duration,
                "width": width,
                "height": height,
                "fps": round(fps, 2)
            }
        except Exception as e:
            return {"duration": 0.0, "width": 0, "height": 0, "fps": 30.0, "error": str(e)}

    @staticmethod
    def get_system_font_path() -> Optional[str]:
        """Devuelve la ruta normalizada para drawtext de FFmpeg compatible con Windows y Linux."""
        candidates = [
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        ]
        for c in candidates:
            if c.exists():
                return str(c.resolve()).replace("\\", "/").replace(":", "\\:")
        return None

    @staticmethod
    def create_analysis_proxy(source: Path, destination: Path,
                              cancel_event: Optional[Event] = None) -> Path:
        """Crea una copia liviana únicamente para el análisis remoto.

        El render final siempre parte del archivo original. Reducir el proxy a
        854 px y 12 fps conserva planos, texto visible y cambios de escena, y
        evita subir gigabytes a Gemini para decidir cortes y recursos.
        """
        if not source.exists():
            raise FileNotFoundError(f"El archivo de video no existe: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-i", str(source),
            # H.264 exige dimensiones pares. La expresión fija 854 cuando se
            # reduce y conserva la anchura original par para videos pequeños.
            # `-2` calcula la altura par preservando el aspecto.
            "-vf", "scale=w='if(gte(iw,854),854,trunc(iw/2)*2)':h=-2,fps=12",
            "-c:v", "libx264", "-preset", "veryfast", "-b:v", "520k", "-maxrate", "700k", "-bufsize", "1400k",
            "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(destination),
        ]
        run_process(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    encoding="utf-8", errors="replace", check=True, timeout=1800,
                    cancel_event=cancel_event)
        if not destination.exists() or destination.stat().st_size == 0:
            raise RuntimeError("FFmpeg no generó la copia de análisis.")
        return destination

    @staticmethod
    def reusable_analysis_proxy(source: Path, destination: Path) -> Optional[Path]:
        """Devuelve el proxy previo si corresponde exactamente al video actual.

        Reanudar una edición no debe volver a comprimir cientos de MB. Se exige
        que el proxy sea posterior al original y tenga un stream de video real.
        """
        try:
            if not destination.exists() or destination.stat().st_size < 32_000:
                return None
            if destination.stat().st_mtime < source.stat().st_mtime:
                return None
            metadata = FileManager.get_media_metadata(destination)
            if metadata.get("duration", 0) <= 0 or metadata.get("width", 0) <= 0:
                return None
            return destination
        except OSError:
            return None

    @staticmethod
    def clean_temp_directory() -> int:
        """Elimina todos los archivos del directorio temporal y devuelve la cantidad eliminada."""
        count = 0
        if not settings.TEMP_DIR.exists():
            return count

        for item in settings.TEMP_DIR.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink()
                    count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    count += 1
            except Exception as e:
                print(f"[FileManager] Advertencia al eliminar {item}: {e}")
        return count

    @staticmethod
    def cleanup_storage(keep_completed_outputs: bool = True) -> Dict[str, Any]:
        """Limpia archivos temporales, duplicados huérfanos y libera espacio en disco."""
        freed_bytes = 0
        deleted_count = 0

        # 1. Limpiar directorio temporal
        if settings.TEMP_DIR.exists():
            for item in settings.TEMP_DIR.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        size = item.stat().st_size
                        item.unlink()
                        freed_bytes += size
                        deleted_count += 1
                    elif item.is_dir():
                        for f in item.rglob("*"):
                            if f.is_file():
                                freed_bytes += f.stat().st_size
                                deleted_count += 1
                        shutil.rmtree(item, ignore_errors=True)
                except Exception as exc:
                    print(f"[FileManager] Error limpiando temp {item}: {exc}")

        # 2. Identificar qué inputs están activamente vinculados a proyectos con plan o resultado
        active_sources = set()
        for manifest in settings.PROJECTS_DIR.glob("*/project.json"):
            try:
                doc = json.loads(manifest.read_text(encoding="utf-8"))
                status = doc.get("status")
                # Si el proyecto terminó con éxito o tiene plan guardado, conservamos su source
                if status in ("done", "ready_for_export") or doc.get("plan"):
                    src = doc.get("source_file")
                    if src:
                        active_sources.add(Path(src).resolve())
            except Exception:
                pass

        # 3. Limpiar inputs huérfanos o duplicados
        # Agrupar por nombre original y tamaño para conservar solo el más reciente de cada archivo idéntico
        seen_duplicates: Dict[tuple, list] = {}
        if settings.INPUTS_DIR.exists():
            for src in settings.INPUTS_DIR.iterdir():
                if not src.is_file():
                    continue
                size = src.stat().st_size
                # Obtener nombre original sin el prefijo del task_id
                stem = src.name.split("_", 1)[-1] if "_" in src.name else src.name
                seen_duplicates.setdefault((stem, size), []).append(src)

            for (stem, size), files in seen_duplicates.items():
                # Ordenar por fecha de modificación (el más reciente primero)
                files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                # Mantener el más reciente si está activo o como única copia
                keep_first = files[0]
                for redundant in files[1:]:
                    # Si no está explícitamente protegido por un proyecto finalizado, borrar
                    if redundant.resolve() not in active_sources:
                        try:
                            f_size = redundant.stat().st_size
                            redundant.unlink(missing_ok=True)
                            freed_bytes += f_size
                            deleted_count += 1
                            # También limpiar carpeta del proyecto si era un proyecto vacío
                            proj_id = redundant.name.split("_", 1)[0]
                            proj_dir = settings.PROJECTS_DIR / proj_id
                            if proj_dir.exists():
                                shutil.rmtree(proj_dir, ignore_errors=True)
                        except Exception as exc:
                            print(f"[FileManager] Error eliminando input duplicado {redundant}: {exc}")

        return {
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "freed_gb": round(freed_bytes / (1024 * 1024 * 1024), 2),
            "deleted_files": deleted_count,
        }
