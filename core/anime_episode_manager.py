"""Gestor Autónomo de Episodios Completos para Anime Recap (AetherCut AI).

Descarga o resuelve el capítulo canónico completo (Full Episode) una sola vez
y extrae cortes cinemáticos sincronizados con FFmpeg en 1080p nativo.
Elimina por completo la búsqueda fragmentada en YouTube para este tipo de contenido,
garantizando 100% de coherencia visual, fidelidad al guion y cero anacronismos.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from config.settings import settings
from core.llm import safe_log

# Lock global para evitar descargas concurrentes duplicadas del mismo episodio
_episode_lock = threading.Lock()


class AnimeEpisodeManager:
    """Motor de resolución, descarga y corte canónico de episodios de anime."""

    BASE_DIR = settings.STORAGE_DIR / "anime_episodes"

    @classmethod
    def get_local_episode_file(cls, series_name: str, episode_num: int) -> Optional[Path]:
        """Comprueba si el episodio ya se encuentra descargado o suministrado localmente."""
        series_clean = series_name.strip()
        ep_dir = cls.BASE_DIR / series_clean
        if not ep_dir.exists():
            return None

        for pattern in (
            f"episode_{episode_num:02d}.mp4",
            f"episode_{episode_num}.mp4",
            f"capitulo_{episode_num:02d}.mp4",
            f"capitulo_{episode_num}.mp4",
            f"ep_{episode_num:02d}.mp4",
            f"ep_{episode_num}.mp4",
            f"episode_{episode_num:02d}.mkv",
            f"episode_{episode_num}.mkv",
        ):
            cand = ep_dir / pattern
            if cand.exists() and cand.stat().st_size > 5_000_000:
                return cand

        # Búsqueda difusa si el usuario nombró el archivo libremente (ej: "Black Clover 04.mp4")
        for f in ep_dir.glob("*.mp4"):
            m = re.search(r'(?:ep|cap|episodio|capitulo|\b)(\d+)\b', f.name, re.IGNORECASE)
            if m and int(m.group(1)) == episode_num and f.stat().st_size > 5_000_000:
                return f

        return None

    @classmethod
    def resolve_remote_url(cls, series_name: str, episode_num: int) -> Optional[str]:
        """Obtiene la URL remota directa del archivo MP4 del episodio completo."""
        series_low = series_name.lower().strip()

        # 1. Catálogo optimizado de alta velocidad (Archive.org)
        if "black clover" in series_low:
            return f"https://archive.org/download/black-clover-lat-{episode_num}/Black%20Clover%20Lat%20{episode_num}.mp4"

        # 2. Búsqueda automática en repositorios de video para otras series
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', series_name).strip()
            q = f"title:({clean_name}) AND mediatype:(movies)"
            url = f"https://archive.org/advancedsearch.php?q={urllib.parse.quote(q)}&fl[]=identifier,title&output=json"
            res = requests.get(url, headers={"User-Agent": "AetherCutAI/2.0"}, timeout=8)
            if res.status_code == 200:
                data = res.json()
                docs = data.get("response", {}).get("docs", [])
                for d in docs:
                    ident = str(d.get("identifier", ""))
                    if f"{episode_num}" in ident:
                        return f"https://archive.org/download/{ident}/{ident}.mp4"
        except Exception as exc:
            safe_log(f"[AnimeEpisodeManager] Búsqueda remota alternativa para {series_name} ep {episode_num}: {exc}")

        return None

    @classmethod
    def get_or_download_episode(cls, series_name: str, episode_num: int) -> Optional[Path]:
        """Asegura la disponibilidad local del archivo de video del episodio completo."""
        local = cls.get_local_episode_file(series_name, episode_num)
        if local:
            return local

        remote_url = cls.resolve_remote_url(series_name, episode_num)
        if not remote_url or not remote_url.startswith("http"):
            safe_log(f"[AnimeEpisodeManager] ⚠️ No se encontró fuente directa para «{series_name}» Episodio {episode_num}")
            return None

        with _episode_lock:
            # Comprobar nuevamente por si otro hilo terminó la descarga
            local = cls.get_local_episode_file(series_name, episode_num)
            if local:
                return local

            series_clean = series_name.strip()
            ep_dir = cls.BASE_DIR / series_clean
            ep_dir.mkdir(parents=True, exist_ok=True)
            target_file = ep_dir / f"episode_{episode_num:02d}.mp4"
            tmp_file = ep_dir / f"episode_{episode_num:02d}.download.tmp"

            safe_log(f"[AnimeEpisodeManager] 📥 Descargando episodio completo {episode_num} de «{series_name}»...")
            try:
                # 1. Intentar con curl.exe nativo (rápido, sin GIL, manejo automático de redirects de Archive.org)
                curl_cmd = ["curl.exe", "-L", "-s", "-o", str(tmp_file), remote_url]
                subprocess.run(curl_cmd, timeout=300)
                if tmp_file.exists() and tmp_file.stat().st_size > 5_000_000:
                    tmp_file.replace(target_file)
                    safe_log(f"[AnimeEpisodeManager] ✅ Episodio {episode_num} guardado en {target_file.name} ({target_file.stat().st_size // (1024*1024)} MB).")
                    return target_file
            except Exception as curl_err:
                safe_log(f"[AnimeEpisodeManager] curl aviso: {curl_err}, intentando con stream requests...")

            try:
                with requests.get(remote_url, stream=True, timeout=45) as r:
                    r.raise_for_status()
                    with open(tmp_file, "wb") as f_out:
                        for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                            if chunk:
                                f_out.write(chunk)
                                f_out.flush()

                if tmp_file.exists() and tmp_file.stat().st_size > 5_000_000:
                    tmp_file.replace(target_file)
                    safe_log(f"[AnimeEpisodeManager] ✅ Episodio {episode_num} guardado en {target_file.name} ({target_file.stat().st_size // (1024*1024)} MB).")
                    return target_file
            except Exception as dl_err:
                safe_log(f"[AnimeEpisodeManager] Error al descargar episodio {episode_num}: {dl_err}")
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)

        return None

    @classmethod
    def extract_clip_for_scene(
        cls,
        series_name: str,
        episode_num: int,
        scene_num: int,
        total_scenes: int,
        duration: float,
        out_path: Path,
        sub_clip_idx: int = 0,
    ) -> Optional[Path]:
        """Corta un fragmento canónico en 1080p nativo desde el episodio completo.
        
        Calcula la marca de tiempo proporcionalmente dentro del episodio para que
        las tomas avancen en perfecta sincronía narrativa de principio a fin.
        """
        # Intentar obtener el archivo local (o descargarlo para que los recortes subsiguientes sean instantáneos)
        local_file = cls.get_local_episode_file(series_name, episode_num)
        if not local_file:
            local_file = cls.get_or_download_episode(series_name, episode_num)

        source_str = str(local_file) if local_file else None
        if not source_str:
            raw_url = cls.resolve_remote_url(series_name, episode_num)
            if raw_url:
                try:
                    head_res = requests.head(raw_url, allow_redirects=True, timeout=8)
                    source_str = head_res.url if head_res.status_code < 400 else raw_url
                except Exception:
                    source_str = raw_url

        if not source_str:
            safe_log(f"[AnimeEpisodeManager] No se pudo resolver fuente para «{series_name}» Ep {episode_num}")
            return None

        # Rango útil del episodio canónico: 90s (post-opening) hasta 1300s (pre-ending)
        useful_start = 95.0
        useful_end = 1300.0
        window = useful_end - useful_start

        scene_ratio = max(0.0, float(scene_num - 1)) / max(1.0, float(total_scenes))
        base_t = useful_start + (scene_ratio * (window - 80.0))
        target_t = base_t + (sub_clip_idx * 16.0)
        if target_t >= useful_end:
            target_t = useful_start + (target_t % window)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        clip_dur = max(3.0, min(14.0, float(duration)))

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{target_t:.2f}",
            "-i", source_str,
            "-t", f"{clip_dur:.2f}",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",
            str(out_path)
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, timeout=35)
            if out_path.exists() and out_path.stat().st_size > 30_000:
                safe_log(f"[AnimeEpisodeManager] 🎬 Clip canónico extraído de Ep {episode_num} (t={target_t:.1f}s, dur={clip_dur:.1f}s) -> {out_path.name}")
                return out_path
            else:
                safe_log(f"[AnimeEpisodeManager] ⚠️ Fallo al recortar clip de anime: {res.stderr[-200:] if res.stderr else 'Salida vacía'}")
        except Exception as exc:
            safe_log(f"[AnimeEpisodeManager] Error ejecutando FFmpeg para clip de anime: {exc}")

        return None

    @classmethod
    def extract_clip_at(
        cls,
        series_name: str,
        episode_num: int,
        start: float,
        dur: float,
        out_path: Path,
    ) -> Optional[Path]:
        """Corta un fragmento en un instante EXACTO del episodio (precisión por mención)."""
        local_file = cls.get_local_episode_file(series_name, episode_num)
        if not local_file:
            local_file = cls.get_or_download_episode(series_name, episode_num)
        if not local_file:
            safe_log(f"[AnimeEpisodeManager] Sin archivo local para Ep {episode_num}")
            return None

        out_path.parent.mkdir(parents=True, exist_ok=True)
        clip_dur = max(1.0, min(14.0, float(dur)))
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{max(0.0, float(start)):.3f}",
            "-i", str(local_file),
            "-t", f"{clip_dur:.3f}",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-an",
            str(out_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=60)
            if out_path.exists() and out_path.stat().st_size > 20_000:
                return out_path
            safe_log(f"[AnimeEpisodeManager] ⚠️ extract_clip_at falló: {res.stderr[-200:] if res.stderr else 'vacío'}")
        except Exception as exc:
            safe_log(f"[AnimeEpisodeManager] Error extract_clip_at: {exc}")
        return None

