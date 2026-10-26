"""Módulo Especializado de Clips Virales de Podcasts & Entrevistas en Español (Palabras con Peso).

Mecánica Exclusiva:
1. RASTREO EXCLUSIVO EN ESPAÑOL: The Wild Project (Jordi Wild), Date un Vlog (Javier Santaolalla),
   Roberto Martínez (Creativo), Gusgri, Filosofía de la Calle, debates de ciencia, psicología y filosofía.
2. 100% AUDIO Y VOZ ORIGINAL DEL INVITADO: Cero narración artificial ni voces sintéticas que tapen
   la conversación. "Solo poner a hablar" al protagonista real en su momento cumbre (30 a 55 segundos).
3. EDICIÓN VERTICAL 9:16 CINEMÁTICA:
   - Fondo difuminado estético + ventana nítida centrada en el ponente.
   - Titular gancho superior en caja de alto contraste (ej. '¿TIENE RAZÓN SOBRE ESTO?').
   - Subtítulos dinámicos palabra por palabra sincronizados con lo que dice.
   - Cierre de debate en los últimos 3-4 segundos para disparar los comentarios en Facebook.
"""

from __future__ import annotations

import json
import logging
import random
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yt_dlp

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.podcast_clipper")

USED_CLIPS_FILE = settings.STORAGE_DIR / "used_podcast_clips.json"

PODCAST_SEARCH_QUERIES = [
    {"query": "The Wild Project mejor momento debate reflexion", "channel": "The Wild Project", "topic": "Debate y Vida"},
    {"query": "Date un Vlog Javier Santaolalla explicacion ciencia universo", "channel": "Date un Vlog", "topic": "Ciencia y Cosmos"},
    {"query": "Roberto Martinez Creativo podcast mejor momento reflexion", "channel": "Creativo", "topic": "Mentalidad y Criterio"},
    {"query": "Gusgri podcast momento polemico revelacion entrevista", "channel": "Gusgri Podcast", "topic": "Verdades Incómodas"},
    {"query": "filosofia de la calle debate dilema moral psicologia", "channel": "Filosofía", "topic": "Dilema Humano"},
    {"query": "Jordi Wild entrevista cientifico reflexion verdad", "channel": "The Wild Project", "topic": "Ciencia y Realidad"},
    {"query": "Ernesto Castro filosofia debate verdad espanol", "channel": "Filosofía en Español", "topic": "Filosofía y Mente"},
    {"query": "entrevista psicologia oscura manipulacion comportamiento humano podcast", "channel": "Psicología", "topic": "Mente Humana"},
]


def _read_used_clips() -> set[str]:
    if USED_CLIPS_FILE.exists():
        try:
            return set(json.loads(USED_CLIPS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def _save_used_clip(clip_id: str):
    used = _read_used_clips()
    used.add(clip_id)
    USED_CLIPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_CLIPS_FILE.write_text(json.dumps(list(used), indent=2), encoding="utf-8")


class SpanishPodcastClipper:
    """Extractor y editor autónomo de clips de podcasts en español para Palabras con Peso."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.OUTPUTS_DIR
        self.temp_dir = settings.STORAGE_DIR / "temp" / "podcast_clips"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def search_best_clip_candidate(self) -> Optional[Dict[str, Any]]:
        """Busca en YouTube un video o clip relevante en español de 25s a 120s."""
        used_ids = _read_used_clips()

        # 1. Intentar primero con el Radar de Tendencias en Tiempo Real (YouTube Data API v3)
        try:
            from core.realtime_trend_radar import realtime_trend_radar
            trending_candidates = realtime_trend_radar.get_trending_podcast_candidates(used_ids)
            for cand in trending_candidates:
                safe_log(f"[PodcastClipper] 🚀 Candidato Viral encontrado por TrendRadar: «{cand['title']}» ({cand.get('views', 0):,} views) [ID: {cand['id']}]")
                return cand
        except Exception as exc:
            safe_log(f"[PodcastClipper] Aviso consultando TrendRadar: {exc}")

        # 2. Respaldo por búsqueda heurística yt-dlp
        shuffled_queries = list(PODCAST_SEARCH_QUERIES)
        random.shuffle(shuffled_queries)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "socket_timeout": 15,
        }

        # Revisar cookies si existen
        for c_cand in [settings.STORAGE_DIR / "cookies.txt", settings.BASE_DIR / "cookies.txt"]:
            if c_cand.is_file() and c_cand.stat().st_size > 10:
                ydl_opts["cookiefile"] = str(c_cand.resolve())
                break

        for item in shuffled_queries:
            query = item["query"]
            safe_log(f"[PodcastClipper] 🔍 Buscando clips en español para: «{query}»...")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    res = ydl.extract_info(f"ytsearch10:{query}", download=False)
                    entries = res.get("entries", [])
                    for e in entries:
                        if not e:
                            continue
                        vid_id = e.get("id")
                        dur = e.get("duration") or 0
                        title = e.get("title", "")
                        if vid_id in used_ids:
                            continue
                        # Preferir clips cortos o extractos manejables (25s a 180s)
                        if 25 <= dur <= 240 or (dur == 0 and ("clip" in title.lower() or "short" in title.lower())):
                            safe_log(f"[PodcastClipper] ✓ Candidato óptimo: «{title}» ({dur}s) [ID: {vid_id}]")
                            return {
                                "id": vid_id,
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                                "title": title,
                                "duration": dur,
                                "channel": item["channel"],
                                "topic": item["topic"],
                            }
            except Exception as exc:
                safe_log(f"[PodcastClipper] Aviso buscando «{query}»: {exc}")

        return None

    def download_and_slice(self, candidate: Dict[str, Any], max_duration: float = 55.0) -> Optional[Path]:
        """Descarga el metraje original del podcast con audio limpio en español."""
        vid_id = candidate["id"]
        raw_out = self.temp_dir / f"raw_{vid_id}.mp4"
        raw_out.unlink(missing_ok=True)

        dur = candidate.get("duration", 0)
        start_sec = 0.0
        # Si el video dura más de 65s, tomar el tramo central más potente
        if dur > 65:
            start_sec = min(15.0, (dur - max_duration) / 2)
        end_sec = start_sec + min(dur if dur > 0 else max_duration, max_duration)

        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": str(raw_out.with_suffix("")) + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 20,
            "download_ranges": yt_dlp.utils.download_range_func(None, [(start_sec, end_sec)]),
            "force_keyframes_at_cuts": False,
            "postprocessors": [{
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4"
            }],
        }

        for c_cand in [settings.STORAGE_DIR / "cookies.txt", settings.BASE_DIR / "cookies.txt"]:
            if c_cand.is_file() and c_cand.stat().st_size > 10:
                ydl_opts["cookiefile"] = str(c_cand.resolve())
                break

        try:
            safe_log(f"[PodcastClipper] 📥 Descargando fragmento original de «{candidate['title']}» ({start_sec}s - {end_sec}s)...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([candidate["url"]])

            if raw_out.exists() and raw_out.stat().st_size > 500_000:
                return raw_out
            # Buscar cualquier extensión descargada
            cands = list(self.temp_dir.glob(f"raw_{vid_id}.*"))
            if cands:
                return cands[0]
        except Exception as exc:
            safe_log(f"[PodcastClipper] Error descargando video: {exc}")

        return None

    def generate_subtitles(self, video_path: Path) -> Optional[Path]:
        """Transcribe la locución real del invitado con Whisper para generar subtítulos sincronizados."""
        try:
            from core.transcriber import WhisperTranscriber
            from core.subtitle_generator import SubtitleGenerator

            safe_log("[PodcastClipper] 🎙️ Transcribiendo discurso original del entrevistado con Whisper...")
            transcriber = WhisperTranscriber(language="es", max_words=5, max_dur=2.2)
            captions = transcriber.transcribe(video_path)

            if not captions:
                safe_log("[PodcastClipper] No se detectaron palabras en la transcripción.")
                return None

            ass_path = video_path.with_suffix(".ass")
            SubtitleGenerator.generate_ass(captions, ass_path, width=1080, height=1920)
            if ass_path.exists():
                safe_log(f"[PodcastClipper] ✓ Subtítulos generados con éxito: {len(captions)} frases.")
                return ass_path
        except Exception as exc:
            safe_log(f"[PodcastClipper] Aviso en transcripción: {exc}")

        return None

    def detect_speaker_focus(self, raw_video: Path, duration: float, in_w: int, in_h: int) -> Dict[str, Any]:
        """Detecta la posición del ponente principal para encuadre inteligente automático 9:16."""
        default_result = {
            "has_person": True,
            "speaker_x_center_percent": 50.0,
            "layout_type": "blurred_stack",
            "person_count": 1,
            "crop_x": max(0, int((in_w - int(in_h * 9 / 16)) / 2)),
            "crop_w": int(in_h * (9 / 16))
        }

        sample_time = min(max(3.0, duration * 0.35), max(1.0, duration - 2.0))
        sample_path = self.temp_dir / f"face_sample_{uuid.uuid4().hex[:6]}.jpg"

        try:
            cmd = [
                "ffmpeg", "-y", "-ss", str(sample_time),
                "-i", str(raw_video),
                "-frames:v", "1",
                "-update", "1",
                "-q:v", "2",
                str(sample_path)
            ]
            subprocess.run(cmd, capture_output=True, timeout=15, check=True)

            if not sample_path.exists() or sample_path.stat().st_size == 0:
                return default_result

            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = """Analiza este fotograma de podcast o entrevista.
Identifica la posición de la persona que habla o el sujeto principal.
Devuelve ÚNICAMENTE un JSON válido con este esquema:
{
  "has_person": true,
  "speaker_x_center_percent": 50.0,
  "person_count": 1,
  "layout_type": "single_speaker_centered"
}
Donde:
- speaker_x_center_percent: float de 0.0 (extremo izquierdo) a 100.0 (extremo derecho) indicando el centro horizontal de la persona o rostro principal.
- layout_type: debe ser "single_speaker_centered", "single_speaker_off_center", "two_shot_split" o "wide_shot".
"""
            resp = client.models.generate_content(
                model=getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest"),
                contents=[prompt, genai.types.Part.from_bytes(data=sample_path.read_bytes(), mime_type="image/jpeg")]
            )
            raw_text = resp.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else {}

            speaker_pct = float(parsed.get("speaker_x_center_percent", 50.0))
            layout = str(parsed.get("layout_type", "single_speaker_centered"))
            person_count = int(parsed.get("person_count", 1))

            crop_w = int(in_h * (9 / 16))
            center_x = (speaker_pct / 100.0) * in_w
            calculated_crop_x = int(center_x - crop_w / 2)
            clamped_crop_x = max(0, min(in_w - crop_w, calculated_crop_x))

            sample_path.unlink(missing_ok=True)
            return {
                "has_person": bool(parsed.get("has_person", True)),
                "speaker_x_center_percent": speaker_pct,
                "layout_type": layout,
                "person_count": person_count,
                "crop_x": clamped_crop_x,
                "crop_w": crop_w
            }
        except Exception as exc:
            safe_log(f"[PodcastClipper] Aviso en Auto-Face Tracking (usando encuadre seguro): {exc}")
            sample_path.unlink(missing_ok=True)
            return default_result

    def render_vertical_reel(
        self,
        raw_video: Path,
        ass_subs: Optional[Path],
        hook_title: str,
        output_path: Path,
        debate_text: Optional[str] = None,
    ) -> bool:
        """Ensambla el Reel vertical 9:16 (1080x1920) con encuadre inteligente y audio original."""
        output_path.unlink(missing_ok=True)
        safe_log(f"[PodcastClipper] 🎬 Masterizando Reel vertical 9:16 para Palabras con Peso...")

        # Detectar dimensiones reales del clip
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "json", str(raw_video)
        ]
        try:
            p_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            info = json.loads(p_res.stdout)
            st = info.get("streams", [{}])[0]
            in_w = int(st.get("width", 1920))
            in_h = int(st.get("height", 1080))
            duration = float(st.get("duration", 45.0))
        except Exception:
            in_w, in_h, duration = 1920, 1080, 45.0

        is_vertical = (in_h > in_w)
        
        # Formatear el titular gancho en 2 líneas equilibradas (máx 28 caracteres por línea) en la Safe Zone
        import textwrap
        raw_words = hook_title.replace(":", " -").replace("'", "").replace('"', '').strip()
        wrapped = textwrap.wrap(raw_words, width=28)
        if len(wrapped) >= 2:
            esc_hook_line1 = wrapped[0].replace("'", "").replace(":", "\\:")
            esc_hook_line2 = wrapped[1].replace("'", "").replace(":", "\\:")
            title_filter = (
                f"drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':text='{esc_hook_line1}':"
                f"fontcolor=white:fontsize=36:x=(w-tw)/2:y=240:box=1:boxcolor=black@0.85:boxborderw=14,"
                f"drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':text='{esc_hook_line2}':"
                f"fontcolor=white:fontsize=36:x=(w-tw)/2:y=298:box=1:boxcolor=black@0.85:boxborderw=14"
            )
        else:
            esc_hook = (wrapped[0] if wrapped else "REFLEXIÓN IMPERDIBLE").replace("'", "").replace(":", "\\:")
            title_filter = (
                f"drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':text='{esc_hook}':"
                f"fontcolor=white:fontsize=38:x=(w-tw)/2:y=260:box=1:boxcolor=black@0.85:boxborderw=16"
            )

        # Marca de agua sutil y elegante en la esquina superior derecha (Safe Zone de Reels)
        wm_text = "Palabras con Peso"
        wm_filter = (
            f"drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':text='{wm_text}':"
            f"fontcolor=white@0.65:fontsize=22:x=w-tw-48:y=90:box=1:boxcolor=black@0.45:boxborderw=8"
        )

        # Filtro de video con Auto-Face Tracking y Smart Re-Framing
        if is_vertical:
            vf = (
                f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v_base];"
                f"[v_base]{title_filter},{wm_filter}[v_titled]"
            )
        else:
            # Análisis de Encuadre Inteligente (Smart Re-Framing / Face Tracking)
            focus = self.detect_speaker_focus(raw_video, duration, in_w, in_h)
            layout_type = focus.get("layout_type", "blurred_stack")
            crop_x = focus.get("crop_x", max(0, int((in_w - int(in_h * 9 / 16)) / 2)))
            crop_w = focus.get("crop_w", int(in_h * (9 / 16)))
            speaker_pct = focus.get("speaker_x_center_percent", 50.0)

            # Si es un ponente individual, recortamos centrado dinámicamente en el ponente a pantalla completa vertical 9:16
            if layout_type in ["single_speaker_centered", "single_speaker_off_center"] and focus.get("person_count", 1) <= 1:
                safe_log(f"[PodcastClipper] 🎯 Auto-Face Tracking: Encuadre centrado en ponente a {speaker_pct:.1f}% (crop_x={crop_x})")
                vf = (
                    f"[0:v]crop={crop_w}:{in_h}:{crop_x}:0,scale=1080:1920:flags=lanczos[v_base];"
                    f"[v_base]{title_filter},{wm_filter}[v_titled]"
                )
            else:
                # Si hay varios ponentes (two_shot_split / wide_shot), usamos la composición con fondo difuminado para no cortar a nadie
                safe_log(f"[PodcastClipper] 👥 Toma múltiple ({layout_type}): Composición cinemática con fondo difuminado y ventana central")
                vf = (
                    f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
                    f"[0:v]scale=1080:-1[fg];"
                    f"[bg][fg]overlay=0:(1920-h)/2[v_base];"
                    f"[v_base]{title_filter},{wm_filter}[v_titled]"
                )

        # Pregunta de debate en los últimos 4 segundos en la zona inferior segura
        debate_st = max(0.0, duration - 4.5)
        raw_debate = (debate_text or "¿Tiene razón o exageró? 👇 Déjalo en comentarios").strip()
        esc_debate = raw_debate.replace(":", "\\:").replace("'", "\\'")
        vf += (
            f";[v_titled]drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':text='{esc_debate}':"
            f"fontcolor=#FFE500:fontsize=32:x=(w-tw)/2:y=h-th-280:box=1:boxcolor=black@0.85:boxborderw=14:"
            f"enable='gte(t,{debate_st})'[v_debated]"
        )

        last_v = "[v_debated]"
        if ass_subs and ass_subs.exists():
            ass_p_str = str(ass_subs.resolve()).replace("\\", "/").replace(":", "\\:")
            vf += f";{last_v}ass='{ass_p_str}'[v_final]"
            last_v = "[v_final]"

        # Sound Design profesional: Whoosh al inicio para el gancho + Impact al cierre para el debate
        whoosh_sfx = settings.BASE_DIR / "assets" / "audio" / "whoosh.wav"
        impact_sfx = settings.BASE_DIR / "assets" / "audio" / "impact.wav"
        has_sfx = whoosh_sfx.is_file() and impact_sfx.is_file()

        inputs = ["-i", str(raw_video)]
        if has_sfx:
            inputs.extend(["-i", str(whoosh_sfx), "-i", str(impact_sfx)])
            debate_delay_ms = int(debate_st * 1000)
            af = (
                f"[1:a]adelay=300|300,volume=0.30[sfx_whoosh];"
                f"[2:a]adelay={debate_delay_ms}|{debate_delay_ms},volume=0.25[sfx_impact];"
                f"[0:a][sfx_whoosh][sfx_impact]amix=inputs=3:duration=first:dropout_transition=2[a_mixed];"
                f"[a_mixed]loudnorm=I=-16:TP=-1.5:LRA=11[a_final]"
            )
            full_filter_complex = f"{vf};{af}"
            map_audio = "[a_final]"
            audio_extra_args: list[str] = []
        else:
            full_filter_complex = vf
            map_audio = "0:a?"
            audio_extra_args = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", full_filter_complex,
            "-map", last_v,
            "-map", map_audio,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "16",
            "-b:v", "8500k",
            "-maxrate", "12000k",
            "-bufsize", "16000k",
            "-pix_fmt", "yuv420p",
            "-color_range", "tv",
            "-colorspace", "bt709",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", "48000",
            "-ac", "2",
            *audio_extra_args,
            "-t", str(duration),
            "-movflags", "+faststart",
            str(output_path),
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1_000_000:
                safe_log(f"[PodcastClipper] ✓ Reel vertical masterizado exitosamente: {output_path.name} ({output_path.stat().st_size // 1024} KB)")
                return True
            else:
                safe_log(f"[PodcastClipper] Error FFmpeg (código {res.returncode}): {res.stderr[-300:]}")
        except Exception as exc:
            safe_log(f"[PodcastClipper] Excepción masterizando Reel: {exc}")

        return False

    def generate_ai_hook(self, candidate: Dict[str, Any]) -> Tuple[str, str]:
        """Usa Gemini o heurísticas para generar un hook superior viral y una pregunta de debate para Facebook Reels."""
        clean_cand_title = candidate["title"].replace('"', '').replace("'", "")
        clean_cand_title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', clean_cand_title).strip()
        default_hook = f"¿TIENE RAZÓN? | {clean_cand_title[:35].upper()}"
        default_debate = "¿Tiene razón o exageró? 👇 Déjalo en comentarios"

        try:
            from google import genai
            from google.genai import types
            api_key = settings.GEMINI_API_KEY
            if api_key and api_key != "your_gemini_api_key_here":
                first_key = api_key.split(",")[0].strip()
                client = genai.Client(api_key=first_key)
                prompt = (
                    f"Para el clip de podcast en español '{candidate['title']}' "
                    f"del canal '{candidate.get('channel', 'Podcast')}' sobre '{candidate.get('topic', 'Debate')}', "
                    f"genera en JSON exacto: "
                    f"1. hook_title: titular gancho ultra viral de maximo 6 palabras en MAYUSCULAS (sin emojis) que detenga el scroll. "
                    f"2. debate_question: pregunta corta y directa para los comentarios del Reel (maximo 12 palabras, incluye un emoji 👇)."
                )
                r = client.models.generate_content(
                    model="gemini-flash-lite-latest",
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                if r.text:
                    data = json.loads(r.text)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    hook = data.get("hook_title", "").strip().upper()
                    debate = data.get("debate_question", "").strip()
                    if hook and len(hook) <= 45:
                        default_hook = hook
                    if debate:
                        default_debate = debate
                    safe_log(f"[PodcastClipper] 💡 Hook IA Generado: «{default_hook}» | Debate: «{default_debate}»")
        except Exception as exc:
            safe_log(f"[PodcastClipper] Aviso generando Hook con IA (usando default): {exc}")

        return default_hook, default_debate

    def produce_podcast_clip(self) -> Optional[Dict[str, Any]]:
        """Ciclo completo: Buscar candidato ➔ Descargar ➔ Transcribir ➔ Masterizar Reel 9:16."""
        candidate = self.search_best_clip_candidate()
        if not candidate:
            safe_log("[PodcastClipper] No se encontró candidato disponible.")
            return None

        raw_vid = self.download_and_slice(candidate, max_duration=55.0)
        if not raw_vid or not raw_vid.exists():
            safe_log("[PodcastClipper] No se pudo descargar el video.")
            return None

        _save_used_clip(candidate["id"])

        # Generar subtítulos automáticos
        ass_subs = self.generate_subtitles(raw_vid)

        # Generar titular superior gancho y pregunta de debate con IA
        hook_title, debate_question = self.generate_ai_hook(candidate)

        project_id = uuid.uuid4().hex[:8]
        master_file = self.output_dir / f"palabras_{project_id}_master.mp4"
        thumb_file = self.output_dir / f"palabras_{project_id}_thumbnail.jpg"

        success = self.render_vertical_reel(
            raw_video=raw_vid,
            ass_subs=ass_subs,
            hook_title=hook_title,
            output_path=master_file,
            debate_text=debate_question,
        )

        if not success:
            return None

        # Miniatura rápida del segundo 2
        try:
            subprocess.run([
                "ffmpeg", "-y", "-ss", "00:00:02", "-i", str(master_file),
                "-vframes", "1", "-q:v", "2", str(thumb_file)
            ], capture_output=True, timeout=15)
        except Exception:
            pass

        clean_cand_title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', candidate.get("title", "")).replace('"', '').replace("'", "").strip()
        title = f"{hook_title} | {clean_cand_title[:50]}"
        desc = (
            f"{title}\n\n"
            f"Momento clave en {candidate['channel']} sobre {candidate['topic']}.\n\n"
            f"¿Estás de acuerdo o crees que exageró? Déjame tu opinión en los comentarios. 👇\n\n"
            f"#Debate #Podcast #TheWildProject #Reflexión #Mente #Criterio #Verdades"
        )

        return {
            "project_id": project_id,
            "master_file": master_file,
            "thumbnail_file": thumb_file,
            "title": title,
            "description": desc,
            "source_title": candidate["title"],
            "channel": candidate["channel"],
        }
