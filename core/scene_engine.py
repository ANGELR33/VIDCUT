"""Motor de Escenas (Scene Engine) para KAI Streamer.

Renderiza cada escena diseñada por el AI Director de forma modular:
- Modulación emocional de voz y entonación por escena (excited, surprised, serious, skeptical).
- Layouts de cámara reactivos:
    * "avatar_cam": Plano principal de KAI hablando al espectador.
    * "video_reaction": Video / B-Roll 100% en pantalla con KAI en PIP en esquina reaccionando en vivo.
    * "card_focus": Tarjeta Bento destacada con datos clave verificados y KAI en PIP.
    * "chat_debate": Pantalla de debate con overlay de chat y preguntas de la comunidad.
- Ensamble y concatenación instantánea y estable sin desbordamiento de memoria de FFmpeg.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.settings import settings
from core.avatar_narrator import AvatarNarrator, DEFAULT_VOICE
from core.avatar_renderer import AvatarRenderer
from core.card_renderer import InfoCardRenderer
from core.chat_renderer import LiveChatRenderer
from core.director import DirectorBroadcastPlan, DirectorScene, SceneCard
from core.models import InfoCard
from core.orchestrator import AssetOrchestrator
from core.llm import safe_log
from core.youtube_audio import get_youtube_bgm_track, get_youtube_sfx_path
from utils.file_manager import FileManager


# Presets de subtítulos (ASS force_style). 'classic' = estilo original de la app.
SUBTITLE_STYLES: Dict[str, str] = {
    "classic": "FontName=Segoe UI,Bold=1,PrimaryColour=&H00FFFFFF,BorderStyle=3,OutlineColour=&HB2000000",
    "outline": "FontName=Segoe UI,Bold=1,PrimaryColour=&H00FFFFFF,BorderStyle=1,Outline=3,Shadow=0,OutlineColour=&H00000000",
    "viral": "FontName=Segoe UI Black,Bold=1,PrimaryColour=&H0000F5D4,BorderStyle=1,Outline=4,Shadow=1,OutlineColour=&H00000000",
    "hormozi": "FontName=Segoe UI Black,Bold=1,PrimaryColour=&H0000FFFF,BorderStyle=1,Outline=4,Shadow=2,OutlineColour=&H00000000",
    "mrbeast": "FontName=Segoe UI Black,Bold=1,PrimaryColour=&H0000FFFF,SecondaryColour=&H0038BDF8,BorderStyle=1,Outline=5,Shadow=2,OutlineColour=&H00000000",
    "cyber_glow": "FontName=Segoe UI,Bold=1,PrimaryColour=&H00F8BD38,BorderStyle=1,Outline=3,Shadow=2,OutlineColour=&H80000000",
    "neon": "FontName=Segoe UI,Bold=1,PrimaryColour=&H00FFE600,BorderStyle=1,Outline=2,Shadow=2,OutlineColour=&H00551A00",
    "minimal": "FontName=Segoe UI,Bold=0,PrimaryColour=&H00FFFFFF,BorderStyle=1,Outline=1,Shadow=0,OutlineColour=&H80000000",
    "cinema": "FontName=Georgia,Italic=1,Bold=0,PrimaryColour=&H00F2F2F2,BorderStyle=1,Outline=2,Shadow=1,OutlineColour=&H00000000",
}


ASS_STYLE_SPECS: Dict[str, Dict[str, Any]] = {
    "hormozi": {
        "font": "Segoe UI Black",
        "primary": "&H0000FFFF",  # Amarillo brillante (#FFFF00 en BGR)
        "secondary": "&H00FFFFFF",
        "outline_c": "&H00000000",
        "back_c": "&H80000000",
        "bold": -1,
        "outline": 5,
        "shadow": 2,
        "uppercase": True,
    },
    "viral": {
        "font": "Segoe UI Black",
        "primary": "&H00D4F500",  # Lima/Cyan viral
        "secondary": "&H00FFFFFF",
        "outline_c": "&H00000000",
        "back_c": "&H80000000",
        "bold": -1,
        "outline": 5,
        "shadow": 2,
        "uppercase": True,
    },
    "mrbeast": {
        "font": "Segoe UI Black",
        "primary": "&H0000FFFF",
        "secondary": "&H0038BDF8",
        "outline_c": "&H00000000",
        "back_c": "&H80000000",
        "bold": -1,
        "outline": 6,
        "shadow": 3,
        "uppercase": True,
    },
    "classic": {
        "font": "Segoe UI",
        "primary": "&H00FFFFFF",
        "secondary": "&H0000FFFF",
        "outline_c": "&H00000000",
        "back_c": "&H60000000",
        "bold": -1,
        "outline": 4,
        "shadow": 2,
        "uppercase": False,
    },
}

def srt_time_to_ass(t_str: str) -> str:
    """Convierte timestamp de SRT ('00:00:01,461') a formato ASS ('0:00:01.46')."""
    t_str = t_str.strip().replace(",", ".")
    parts = t_str.split(":")
    if len(parts) == 3:
        h = int(parts[0])
        m = parts[1]
        s_parts = parts[2].split(".")
        s = s_parts[0]
        cs = (s_parts[1] + "00")[:2] if len(s_parts) > 1 else "00"
        return f"{h}:{m}:{s}.{cs}"
    return "0:00:00.00"


def generate_ass_from_srt(
    srt_path: Path,
    ass_path: Path,
    width: int,
    height: int,
    sub_style: str = "hormozi",
    font_size: int = 52,
    margin_v: int = 380,
) -> Path:
    """Genera archivo ASS nativo con PlayResX y PlayResY calibrados para renderizado de subtítulos sin cortes ni desbordes."""
    style_specs = ASS_STYLE_SPECS
    spec = style_specs.get((sub_style or "").strip().lower(), style_specs["hormozi"])
    is_upper = spec.get("uppercase", False)

    header = f"""[Script Info]
Title: Dynamic Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{spec['font']},{font_size},{spec['primary']},{spec['secondary']},{spec['outline_c']},{spec['back_c']},{spec['bold']},0,0,0,100,100,0,0,1,{spec['outline']},{spec['shadow']},2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogues = []
    if srt_path.exists():
        raw_content = srt_path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
        blocks = [b.strip() for b in raw_content.split("\n\n") if b.strip()]
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            time_idx = -1
            for idx, line in enumerate(lines):
                if "-->" in line:
                    time_idx = idx
                    break
            if time_idx != -1 and len(lines) > time_idx + 1:
                start_raw, end_raw = lines[time_idx].split("-->")
                start_ass = srt_time_to_ass(start_raw)
                end_ass = srt_time_to_ass(end_raw)
                text = r"\N".join(lines[time_idx + 1 :])
                if is_upper:
                    text = text.upper()
                dialogues.append(
                    f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}"
                )

    ass_path.write_text(header + "\n".join(dialogues) + "\n", encoding="utf-8")
    return ass_path


def _sec_to_ass(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs = 0
    if s >= 60:
        m += 1
        s = 0
    if m >= 60:
        h += 1
        m = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_karaoke_ass(
    word_times: List[Dict[str, Any]],
    ass_path: Path,
    width: int,
    height: int,
    sub_style: str = "hormozi",
    font_size: int = 52,
    margin_v: int = 380,
    chunk_size: int = 3,
) -> Path:
    """Genera subtítulos karaoke: cada palabra se ilumina al pronunciarse."""
    spec = ASS_STYLE_SPECS.get((sub_style or "").strip().lower(), ASS_STYLE_SPECS["hormozi"])
    is_upper = spec.get("uppercase", False)
    header = f"""[Script Info]
Title: Dynamic Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{spec['font']},{font_size},{spec['primary']},{spec['secondary']},{spec['outline_c']},{spec['back_c']},{spec['bold']},0,0,0,100,100,0,0,1,{spec['outline']},{spec['shadow']},2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    chunks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for word in word_times or []:
        if not isinstance(word, dict) or not str(word.get("word", "")).strip():
            continue
        current.append(word)
        if len(current) >= chunk_size:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)

    dialogues: List[str] = []
    for chunk in chunks:
        try:
            start = float(chunk[0].get("start", 0.0))
            end = float(chunk[-1].get("end", start))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        durations = []
        for word in chunk:
            try:
                durations.append(max(0.05, float(word.get("end", 0)) - float(word.get("start", 0))))
            except (TypeError, ValueError):
                durations.append(0.1)
        total = sum(durations) or 1.0
        span = max(0.15, end - start)
        parts = []
        for word, duration in zip(chunk, durations):
            cs = max(1, int(round((duration / total) * span * 100)))
            text = str(word.get("word", "")).strip()
            if not text:
                continue
            if is_upper:
                text = text.upper()
            parts.append(f"{{\\kf{cs}}}{text}")
        if not parts:
            continue
        dialogues.append(
            f"Dialogue: 0,{_sec_to_ass(start)},{_sec_to_ass(end + 0.08)},Default,,0,0,0,,{' '.join(parts)}"
        )

    ass_path.write_text(header + "\n".join(dialogues) + "\n", encoding="utf-8")
    return ass_path


def subtitle_force_style(sub_style: str, font_size: int, margin_v: int) -> str:
    """Devuelve el force_style de libass para el preset pedido (fallback: classic) con alineación centrada y márgenes seguros."""
    base = SUBTITLE_STYLES.get((sub_style or "classic").strip().lower(), SUBTITLE_STYLES["classic"])
    if (sub_style or "").strip().lower() == "viral":
        font_size = int(font_size * 1.15)
    return f"{base},FontSize={font_size},MarginV={margin_v},Alignment=2,MarginL=40,MarginR=40"


# Modulación de voz emocional real (rate=velocidad, pitch=tono)
# Estos valores cambian la prosodia del TTS para dar vida real a las escenas con respiración humana
EMOTION_VOICE_MODULATION: Dict[str, Tuple[str, str]] = {
    "excited":   ("+1%",  "+1Hz"),    # Dinámico y entusiasta con dicción nítida (sin correr)
    "surprised": ("+0%",  "+2Hz"),    # Asombro natural y pausa clara
    "serious":   ("-5%",  "-2Hz"),    # Más pausado y grave — peso y autoridad
    "skeptical": ("-4%",  "-1Hz"),    # Ligeramente más lento — tono reflexivo
    "confident": ("-1%",  "+0Hz"),    # Ritmo seguro y natural de locución
    "humor":     ("+1%",  "+1Hz"),    # Ágil y ligero, espontáneo
    "dramatic":  ("-8%",  "-3Hz"),    # Pausado y de suspenso cinematográfico
    "podcast":   ("-3%",  "+0Hz"),    # Ritmo relajado, conversacional con pausas humanas
    "breaking":  ("+2%",  "+1Hz"),    # Noticioso ágil pero articulado y respirable (nunca acelerado)
}

# Cadena profesional de voz para TTS de estudio: quita retumbe, da presencia,
# suaviza sibilancia y nivela la dinamica antes del loudnorm final.
VOICE_PRO_CHAIN = (
    "highpass=f=85,"
    "equalizer=f=250:t=q:w=1:g=-2,"
    "equalizer=f=3800:t=q:w=1:g=2.5,"
    "deesser=i=0.3:m=0.5:f=0.5,"
    "acompressor=threshold=-20dB:ratio=3:attack=15:release=180:makeup=1.5"
)

# Presets de color grading cinematico para FFmpeg eq+curves
# IMPORTANTE: todos los valores de curvas deben estar en el rango [0.0, 1.0]
COLOR_GRADE_FILTERS: Dict[str, str] = {
    "raw":             "",  # Sin filtro — salida nativa del encoder
    "cinema":          "eq=contrast=1.05:saturation=0.92:brightness=-0.01,curves=r='0/0 0.5/0.47 1/0.95':g='0/0 0.5/0.49 1/0.97':b='0/0.02 0.5/0.52 1/0.99'",
    "cinema_vignette": "eq=contrast=1.06:saturation=0.95:brightness=-0.01,vignette=PI/5",
    "documentary":     "eq=contrast=1.08:saturation=1.02:brightness=-0.01,unsharp=lx=3:ly=3:la=0.3,vignette=PI/5.5",
    "broadcast":       "eq=contrast=1.08:saturation=1.1:brightness=0.02,unsharp=lx=3:ly=3:la=0.4",
    "neon":            "eq=contrast=1.15:saturation=1.4:brightness=-0.02,curves=r='0/0 0.5/0.44 1/0.90':b='0/0.03 0.5/0.55 1/0.99'",
    "warm":            "eq=contrast=1.04:saturation=1.08,curves=r='0/0.04 0.5/0.54 1/0.98':g='0/0 0.5/0.49 1/0.96':b='0/0 0.5/0.44 1/0.88'",
    "cool":            "eq=contrast=1.03:saturation=0.88,curves=r='0/0 0.5/0.44 1/0.88':b='0/0.04 0.5/0.55 1/0.99'",
}


class SceneEngine:
    """Motor de composición y renderizado escena por escena."""

    def __init__(
        self,
        workdir: Path,
        aspect_ratio: str = "16:9",
        voice: str = DEFAULT_VOICE,
        card_theme: str = "dark",
        cancel_event: Optional[Any] = None,
        sub_style: str = "classic",
        subs_enabled: bool = True,
        burn_subtitles: bool = False,
        fps: int = 30,
        crf: int = 18,
        audio_normalize: bool = True,
        color_grade: str = "cinema",
        bgm_volume: float = 0.12,
        bgm_track: str = "default",
        style_spec: Optional[Dict[str, Any]] = None,
        topic: str = "",
        origin: str = "",
        extra_notes: str = "",
        is_anime: Optional[bool] = None,
        enable_avatar: bool = True,
    ):
        self.topic = topic or ""
        self.origin = origin or ""
        self.extra_notes = extra_notes or ""
        self.enable_avatar = enable_avatar
        self.style_spec = style_spec
        if style_spec:
            if not card_theme or card_theme in ("dark", "auto"):
                card_theme = style_spec.get("card_theme", card_theme)
            if not sub_style or sub_style in ("classic", "auto"):
                sub_style = style_spec.get("sub_style", sub_style)
        self.sub_style = sub_style
        self.subs_enabled = subs_enabled
        self.burn_subtitles = burn_subtitles
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.aspect_ratio = aspect_ratio
        self.is_vertical = aspect_ratio == "9:16"
        self.W, self.H = (1080, 1920) if self.is_vertical else (1920, 1080)
        self.voice = voice
        self.card_theme = card_theme
        self.cancel_event = cancel_event
        self.fps = fps
        self.crf = crf
        self.audio_normalize = audio_normalize
        self.color_grade = color_grade
        self.bgm_volume = bgm_volume
        self.bgm_track = bgm_track

        # Si topic u origin no vinieron explícitos, intentar leer project.json del workdir
        if not self.topic:
            for p_file in [self.workdir / "project.json", self.workdir.parent / "project.json"]:
                if p_file.exists():
                    try:
                        p_data = json.loads(p_file.read_text(encoding="utf-8"))
                        self.topic = self.topic or p_data.get("topic") or p_data.get("original_name") or ""
                        opts = p_data.get("options") or {}
                        self.origin = self.origin or opts.get("origin") or ""
                        self.extra_notes = self.extra_notes or opts.get("extra_notes") or ""
                    except Exception:
                        pass

        # Desactivación total y permanente de anime para blindar los canales contra contaminación visual
        combined_text = f"{self.topic} {self.origin} {self.extra_notes}".lower()
        self.is_anime = False
        self.anime_series_name = ""

        # Asignación de Marca de Agua de Canal Unificada
        if self.is_anime:
            self.brand_watermark = f"{self.anime_series_name} T 4"
        elif any(k in combined_text for k in ("huellas", "cristiano", "fe", "biblico", "dios")):
            self.brand_watermark = "Huellas Sagradas"
        elif any(k in combined_text for k in ("nucleo", "deep dife", "geopolitica")):
            self.brand_watermark = "Núcleo Ideológico"
        elif any(k in combined_text for k in ("contrapunto", "pixelgrama", "debate")):
            self.brand_watermark = "Contrapunto"
        elif any(k in combined_text for k in ("palabras", "podcast", "entrevista")):
            self.brand_watermark = "Palabras con Peso"
        else:
            self.brand_watermark = "AetherCut"

        self._total_scenes = 8
        self._anime_used_src: List[Tuple[int, float]] = []
        self.narrator = AvatarNarrator(voice=voice)
        self.card_renderer = InfoCardRenderer(self.W, self.H, theme=card_theme)
        from core.web_card_renderer import WebCardRenderer
        self.web_renderer = WebCardRenderer()
        from core.kinetic_titles import KineticTitleRenderer
        self.title_renderer = KineticTitleRenderer(self.web_renderer)
        self.chat_renderer = LiveChatRenderer(width=340 if not self.is_vertical else 300)
        self.orchestrator = AssetOrchestrator(target_dir=self.workdir / "assets")
        if self.is_anime:
            from core.asset_providers import YouTubeReactionAssetProvider
            self.orchestrator.providers = [YouTubeReactionAssetProvider()]
        try:
            from core.deepseek_motion_director import deepseek_motion_director
            self.deepseek_motion_director = deepseek_motion_director
        except Exception:
            self.deepseek_motion_director = None
        self.glm_motion_director = None
        try:
            from core.motion_graphics_engine import MotionGraphicsEngine
            self.motion_engine = MotionGraphicsEngine(self.web_renderer, is_vertical=self.is_vertical)
        except Exception:
            self.motion_engine = None
        try:
            from core.ai_remotion_generator import AIRemotionGenerator
            self.ai_remotion = AIRemotionGenerator()
        except Exception:
            self.ai_remotion = None
        self.used_visual_paths: set = set()
        self.used_clip_names: set = set()
        try:
            from core.asset_providers import YouTubeReactionAssetProvider
            YouTubeReactionAssetProvider.reset_used_assets()
        except Exception:
            pass


    @staticmethod
    def _is_valid_media_clip(clip_p: Path) -> bool:
        """Comprueba si un archivo multimedia existe y tiene frames decodificables."""
        if not clip_p.exists() or clip_p.stat().st_size < 1000:
            return False
        if clip_p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            return True
        try:
            res = subprocess.run(
                ["ffmpeg", "-i", str(clip_p), "-t", "0.5", "-f", "null", "-"],
                capture_output=True, text=True, timeout=5
            )
            if "Output file is empty" in res.stderr:
                return False
            return True
        except Exception:
            return False

    async def render_scene(
        self,
        scene: DirectorScene,
        avatar_clip: Optional[Path] = None,
        avatar_webm: Optional[Path] = None,
        bgm_path: Optional[Path] = None,
        chat_overlay_path: Optional[Path] = None,
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> Path:
        """Renderiza una escena individual en su propio archivo MP4."""
        scene_dir = self.workdir / f"scene_{scene.scene_id}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        scene_out = scene_dir / f"scene_{scene.scene_id}.mp4"
        # Escritura atómica con UUID único para evitar bloqueos de Windows [WinError 32]
        scene_tmp = scene_dir / f"scene_{scene.scene_id}_{uuid.uuid4().hex[:6]}.tmp.mp4"
        for old_tmp in scene_dir.glob(f"scene_{scene.scene_id}*.tmp.mp4"):
            try:
                old_tmp.unlink(missing_ok=True)
            except OSError:
                pass

        # 0. Cache inteligente de escenas (Reanudar sin rehacer lo que ya está listo).
        # Se valida tamaño Y la firma de settings + guion: una escena hecha con otro
        # formato (9:16 ↔ 16:9), otra voz u otro texto NO se reutiliza nunca.
        thumb_path = scene_dir / "scene_thumb.jpg"
        meta_path = scene_dir / "render_meta.json"
        if scene_out.exists() and scene_out.stat().st_size > 50000 and self._cache_meta_valid(meta_path, scene):
            for old_tmp in scene_dir.glob(f"scene_{scene.scene_id}*.tmp.mp4"):
                try:
                    old_tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            if not thumb_path.exists():
                try:
                    import subprocess
                    await asyncio.to_thread(subprocess.run, [
                        "ffmpeg", "-y", "-ss", "0.5", "-i", str(scene_out),
                        "-vframes", "1", "-q:v", "3", str(thumb_path)
                    ], capture_output=True, timeout=5)
                except Exception:
                    pass
            safe_log(f"[SceneEngine] Reusando escena {scene.scene_id} ({scene.name}) ya renderizada.")
            if status_cb:
                status_cb(f"Escena {scene.scene_id} restaurada desde caché.")
            return scene_out

        if status_cb:
            status_cb(f"Dirigiendo Escena {scene.scene_id}: {scene.name} ({scene.type})")

        speech_text = scene.speech.strip()
        if not speech_text:
            speech_text = "Dato mata relato, analicemos este punto a fondo."

        if self.is_anime:
            self._current_scene_speech = speech_text
            self._current_scene_name = scene.name
            sc_id_m = re.search(r'\d+', str(scene.scene_id))
            self._current_scene_num = int(sc_id_m.group(0)) if sc_id_m else 1

        from utils.speech_normalizer import normalize_speech_for_tts
        tts_speech_text = normalize_speech_for_tts(speech_text)

        rate_mod, pitch_mod = EMOTION_VOICE_MODULATION.get(scene.emotion, ("-2%", "+0Hz"))
        audio_path = scene_dir / "voice.mp3"

        sentence_boundaries = []
        word_times: List[Dict[str, Any]] = []
        audio_generated = False
        document_assets: Set[str] = set()

        # 1. Síntesis neuronal de alta fidelidad con el narrador (Speechify / Gemini / Voz seleccionada por el usuario)
        try:
            safe_log(f"[SceneEngine] Sintetizando locución con la voz seleccionada ({self.voice}) para escena {scene.scene_id}...")
            _, tts_duration = await self.narrator.synthesize(
                tts_speech_text, audio_path, voice=self.voice, rate=rate_mod, pitch=pitch_mod
            )
            if audio_path.exists() and audio_path.stat().st_size > 500:
                audio_generated = True
                safe_log(f"[SceneEngine] Audio de escena {scene.scene_id} generado exitosamente con voz {self.voice} ({audio_path.stat().st_size} bytes)")
        except Exception as _narrator_err:
            safe_log(f"[SceneEngine] Error en síntesis neuronal con narrador: {_narrator_err}")

        # 2. Respaldo secundario con Edge-TTS (si la red lo permite)
        if not audio_generated:
            try:
                import edge_tts
                communicate = edge_tts.Communicate(tts_speech_text, self.voice, rate=rate_mod, pitch=pitch_mod)
                with open(audio_path, "wb") as f_audio:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            f_audio.write(chunk["data"])
                        elif chunk["type"] == "SentenceBoundary":
                            s_sec = chunk["offset"] / 10_000_000
                            d_sec = chunk["duration"] / 10_000_000
                            sentence_boundaries.append((s_sec, s_sec + d_sec, chunk["text"].strip()))
                if audio_path.exists() and audio_path.stat().st_size > 500:
                    audio_generated = True
            except Exception as _edge_err:
                safe_log(f"[SceneEngine] Edge-TTS no disponible ({_edge_err}). Pasando a gTTS regional...")

        # 3. Respaldo terciario infalible con gTTS regional
        if not audio_generated:
            try:
                from gtts import gTTS
                v_lower = (self.voice or "").lower()
                tld = "com.mx"
                if any(x in v_lower for x in ["es-es", "alvaro"]):
                    tld = "es"
                elif any(x in v_lower for x in ["es-co", "gonzalo", "clon"]):
                    tld = "com.co"
                elif any(x in v_lower for x in ["es-ar", "tomas", "elena"]):
                    tld = "com.ar"
                gtts_obj = gTTS(text=tts_speech_text, lang="es", tld=tld)
                gtts_obj.save(str(audio_path))
                audio_generated = True
            except Exception as _gtts_err:
                safe_log(f"[SceneEngine] Error crítico generando voz fallback: {_gtts_err}")
                raise

        # Medir duración exacta del audio real de la escena generado limpiamente por el TTS neural
        tts_duration = self._get_audio_duration(audio_path)

        # Alineación real a nivel palabra (Whisper) para que cada overlay caiga en la sílaba exacta.
        # Funciona con cualquier motor de voz (Speechify/Gemini/Edge/gTTS), que no exponen timestamps.
        try:
            from core.word_aligner import align_audio_to_script
            aligned_words, aligned_sentences = await asyncio.wait_for(
                asyncio.to_thread(
                    align_audio_to_script,
                    audio_path,
                    speech_text,
                    tts_duration,
                    scene_dir / "word_times.json",
                    "es",
                    self.cancel_event,
                ),
                timeout=180.0,
            )
            if aligned_words:
                word_times = aligned_words
            if aligned_sentences:
                sentence_boundaries = aligned_sentences
                safe_log(f"[SceneEngine] 🎯 {len(word_times)} palabras alineadas en escena {scene.scene_id} (sincronía exacta de overlays).")
        except Exception as _align_err:
            safe_log(f"[SceneEngine] Alineación de palabras omitida en escena {scene.scene_id}: {_align_err}")

        # Si sentence_boundaries no fue provisto por Edge-TTS, calcular boundaries de frases con la duración real del audio
        if not sentence_boundaries:
            raw_sentences = [s.strip() for s in re.split(r"([.!?…]+)", tts_speech_text) if s.strip()]
            full_sents = []
            cur_s = ""
            for part in raw_sentences:
                cur_s += (" " if cur_s else "") + part
                if re.search(r"[.!?…]$", part):
                    full_sents.append(cur_s.strip())
                    cur_s = ""
            if cur_s:
                full_sents.append(cur_s.strip())
            if not full_sents:
                full_sents = [tts_speech_text]

            cur_t = 0.0
            total_chars = max(1, sum(len(s) for s in full_sents))
            for s in full_sents:
                s_dur = (len(s) / total_chars) * tts_duration
                sentence_boundaries.append((round(cur_t, 2), round(cur_t + s_dur, 2), s))
                cur_t += s_dur

        # La escena se ajusta de forma milimétrica al audio hablado para evitar silencios y mantener sincronía exacta con los fotogramas
        duration = max(3.0, round(tts_duration + 0.15, 2))
        dur_str = f"{duration:.2f}"

        # 2. Curaduría Inteligente de Contenido y Apoyo Visual
        from core.smart_media_curator import SmartMediaCurator, VisualIntentType, VisualNature
        visual_intent = SmartMediaCurator.analyze_narration_intent(speech_text, scene.name)
        safe_log(f"[SmartMediaCurator] 🧠 Intención detectada para escena {scene.scene_id}: {visual_intent.intent_type.value} ('{visual_intent.entity_name}')")

        broll_img = None
        is_opening_scene = (int(getattr(scene, "scene_id", 1)) == 1)
        is_hook_scene = is_opening_scene

        # Solo usar el estudio streamer si explícitamente se pide avatar_cam en escenas intermedias y NO hay visual_query
        # En la apertura (escena 1), SIEMPRE se busca material visual/documental relevante del tema
        if (scene.type == "avatar_cam" or scene.camera == "hero_center") and not is_opening_scene and not scene.visual_query:
            studio_blur_path = Path("assets/streamer_studio_blur_9_16.jpg" if self.is_vertical else "assets/streamer_studio_blur_16_9.jpg")
            if studio_blur_path.exists():
                broll_img = studio_blur_path
            elif Path("assets/streamer_studio_room.jpg").exists():
                broll_img = Path("assets/streamer_studio_room.jpg")

        # PRECISIÓN QUIRÚRGICA (solo anime): cada mención de personaje/acción en la voz
        # dispara un corte al plano del episodio donde eso realmente aparece.
        anime_precise_clips: List[Tuple[Path, float]] = []
        if self.is_anime:
            try:
                anime_precise_clips = await self._plan_anime_precise_clips(
                    scene, scene_dir, speech_text, audio_path, sentence_boundaries, duration
                )
            except Exception as _pe:
                safe_log(f"[SceneEngine] Precisión anime no disponible, método base: {_pe}")
                anime_precise_clips = []
            if anime_precise_clips:
                broll_img = anime_precise_clips[0][0]

        if scene.type == "vector_motion" and not anime_precise_clips:
            # Sustituir monigotes/stickmen vectoriales por metraje periodístico o documental real en alta definición
            try:
                v_concept = scene.visual_query or f"{scene.name} documental reportaje 4k"
                safe_log(f"[SceneEngine] 🎬 Obteniendo material periodístico/documental HD para escena conceptual {scene.scene_id}: '{v_concept}'")
                broll_img = await self._get_scene_visual(v_concept, scene_dir, is_video_scene=True, intent=visual_intent)
                if not broll_img or not broll_img.exists():
                    fallback_concept = f"{scene.name} investigacion periodismo documentary 4k"
                    broll_img = await self._get_scene_visual(fallback_concept, scene_dir, is_video_scene=True, intent=visual_intent)
            except Exception as _ev:
                safe_log(f"[SceneEngine] Fallback en visual conceptual: {_ev}")

        # MODO ANÁLISIS DE CASO: si el director ancló esta escena a un fotograma
        # REAL del video fuente, ese fotograma ES el fondo — evidencia visual
        # del caso concreto, jamás stock genérico. (Imagen → Ken Burns.)
        case_frame_idx = getattr(scene, "case_frame", None)
        if case_frame_idx is not None:
            case_frame_path = self.workdir / "case_frames" / f"frame_{int(case_frame_idx):02d}.jpg"
            if case_frame_path.exists():
                broll_img = case_frame_path
                safe_log(f"[SceneEngine] 🎯 Escena {scene.scene_id}: fotograma REAL del caso (frame {int(case_frame_idx)}) como fondo.")

        if not broll_img or not broll_img.exists():
            # Priorizar video en movimiento para todas las escenas con B-Roll, reacción, noticias o contexto
            # En la apertura (escena 1), SIEMPRE es video documental de alto impacto
            is_video_reaction = is_opening_scene or (scene.type != "avatar_cam") or ("video" in (scene.visual_query or "").lower())
            broll_img = await self._get_scene_visual(scene.visual_query, scene_dir, is_video_scene=is_video_reaction, intent=visual_intent)

        # Garantizar que NUNCA quede un fondo negro vacío: si la descarga no encontró imagen externa,
        # usar el set de estudio iluminado cinemático con bokeh de KAI
        if not broll_img or not broll_img.exists():
            fallback_bg = Path("assets/streamer_studio_blur_9_16.jpg" if self.is_vertical else "assets/streamer_studio_blur_16_9.jpg")
            if not fallback_bg.exists():
                fallback_bg = Path("assets/streamer_studio_room.jpg")
            if fallback_bg.exists():
                broll_img = fallback_bg

        # Registro y Verificación de Procedencia del Material Visual
        media_prov = self._get_media_provenance(broll_img)
        if media_prov:
            try:
                from core.licensing import classify_license
                lic = classify_license(media_prov.get("source_url", ""))
                media_prov["license_class"] = lic["class"]
                media_prov["allowed"] = lic["allowed"]
                media_prov["monetization_safe"] = lic["monetization_safe"]
                if not lic["allowed"]:
                    safe_log(
                        f"[Licensing] AVISO escena {scene.scene_id}: material {lic['class']} "
                        f"({lic['domain']}) no permitido como principal. {lic['note']}"
                    )
                elif not lic["monetization_safe"]:
                    safe_log(
                        f"[Licensing] Aviso escena {scene.scene_id}: {lic['class']} "
                        f"({lic['domain']}). {lic['note']}"
                    )
            except Exception as _lic_err:
                safe_log(f"[Licensing] Aviso clasificando licencia: {_lic_err}")
        provenance_chip_path = None
        if media_prov and media_prov.get("attribution_badge"):
            b_text = str(media_prov.get("attribution_badge", "")).strip()
            s_name = str(media_prov.get("source_name", "Archivo Oficial")).strip()
            safe_log(f"[SmartMediaCurator] 🛡️ Proveniencia: {b_text} | Fuente: {s_name} | Licencia: {media_prov.get('license', 'Uso Libre')}")
            # Si es documental real, histórico, o reconstrucción, generar pastilla de transparencia en pantalla
            if any(k in b_text.upper() for k in ("HISTÓRICO", "HISTORICO", "DOCUMENTAL", "RECONSTRUCCIÓN", "RECONSTRUCCION", "SIMULACIÓN", "SIMULACION", "VERIFICADO")):
                try:
                    out_chip_p = scene_dir / f"provenance_chip_{scene.scene_id}.png"
                    provenance_chip_path = self.web_renderer.render_visual_template(
                        template_name="source_chip",
                        out_png=out_chip_p,
                        params={"source_name": s_name, "tag": b_text},
                        variant="orange_noir",
                    )
                except Exception as _p_err:
                    safe_log(f"[SmartMediaCurator] Fallback en source chip: {_p_err}")

        # Sin pastillas flotantes: la atribución va en el pie de la card editorial.
        provenance_chip_path = None

        # 2b. Descargar clips secuenciales de referencia (visual_beats) o segundo clip complementario
        bg_clips: List[Tuple[Path, float]] = []
        if anime_precise_clips:
            bg_clips = list(anime_precise_clips)
        if broll_img and broll_img.exists() and not anime_precise_clips:
            bg_clips.append((broll_img, 0.0))
            if hasattr(self, "used_clip_names"):
                self.used_clip_names.add(broll_img.name)
            if hasattr(self, "used_visual_paths"):
                b_str = str(broll_img.resolve()) if hasattr(broll_img, "resolve") else str(broll_img)
                self.used_visual_paths.add(b_str)

        def _is_distinct_clip(cand: Optional[Path], current_clips: List[Tuple[Path, float]]) -> bool:
            if not cand or not cand.exists():
                return False
            if self.is_anime and cand.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                return False
            cand_p = cand.resolve() if hasattr(cand, "resolve") else cand
            for p, _ in current_clips:
                if p == cand or p.name == cand.name:
                    return False
                try:
                    if p.resolve() == cand_p:
                        return False
                except Exception:
                    pass
            # Evitar repetición global entre distintas escenas del proyecto (solo para b-rolls externos)
            if not self.is_anime:
                used_paths = getattr(self, "used_visual_paths", set())
                if str(cand) in used_paths or str(cand_p) in used_paths:
                    return False
                used_names = getattr(self, "used_clip_names", set())
                if cand.name in used_names:
                    return False
            return True

        # Si el director aportó visual_beats con frases exactas, sincronizar cortes con esas frases
        beats = getattr(scene, "visual_beats", []) or []
        vq2 = getattr(scene, "visual_query2", "") or ""
        if anime_precise_clips:
            pass  # plan quirúrgico ya sincronizado con la voz
        elif beats and len(beats) > 1 and duration >= 5.0:
            # Calcular momentos de corte para cada beat
            segment_step = duration / len(beats)
            for b_idx, beat in enumerate(beats[1:], start=1):
                b_query = beat.get("query") if isinstance(beat, dict) else str(beat)
                if not b_query or not b_query.strip():
                    continue
                # Si beat tiene trigger literal, intentar ubicar el timestamp exacto en boundaries
                b_time = round(b_idx * segment_step, 2)
                b_trig = (beat.get("trigger") or "").lower().strip() if isinstance(beat, dict) else ""
                hit = None
                if b_trig and word_times:
                    trig_tokens = [w for w in re.findall(r"\w+", b_trig) if len(w) >= 4][:3]
                    for trig in trig_tokens:
                        for wt in word_times:
                            if trig in re.sub(r"\W+", "", str(wt.get("word", "")).lower()):
                                hit = float(wt.get("start", 0.0))
                                break
                        if hit is not None:
                            break
                    if hit is not None:
                        b_time = max(1.2, min(duration - 2.0, round(hit - 0.08, 2)))
                if hit is None and b_trig and sentence_boundaries:
                    for s_st, _s_en, s_txt in sentence_boundaries:
                        if b_trig in s_txt.lower() or any(w in s_txt.lower() for w in b_trig.split()[:3]):
                            b_time = max(1.5, min(duration - 2.0, round(s_st, 2)))
                            break
                try:
                    clip_path = await self._get_scene_visual(b_query, scene_dir, is_video_scene=True)
                    if clip_path and _is_distinct_clip(clip_path, bg_clips):
                        bg_clips.append((clip_path, b_time))
                        if hasattr(self, "used_clip_names"):
                            self.used_clip_names.add(clip_path.name)
                except Exception as _eb:
                    safe_log(f"[SceneEngine] Error obteniendo beat visual '{b_query}': {_eb}")
        elif vq2 and vq2.strip() and vq2.strip().lower() != (scene.visual_query or "").strip().lower():
            try:
                broll_img2 = await self._get_scene_visual(vq2, scene_dir, is_video_scene=True)
                if broll_img2 and _is_distinct_clip(broll_img2, bg_clips):
                    bg_clips.append((broll_img2, round(duration * 0.5, 2)))
                    if hasattr(self, "used_clip_names"):
                        self.used_clip_names.add(broll_img2.name)
            except Exception as _e:
                safe_log(f"[SceneEngine] Fallback en segundo clip: {_e}")

        # 2c. Afinidad Semántica y Visual Lock vs. Ritmo Dinámico
        # Distingue entre:
        # A) Evidencia Directa / Documento Clave / Cita Oficial / Cifras Críticas:
        #    -> Visual Anchor ACTIVO: El video "se posa" con calma, foco visual y estabilidad para leer y asimilar la prueba.
        # B) Fondos Decorativos o de Stock en Narración:
        #    -> Ritmo dinámico acelerado (cortes cada 2.4s a 3.2s sin repetir el mismo plano).
        card_obj = getattr(scene, "card", None)
        c_template_raw = str(getattr(card_obj, "template", "") if hasattr(card_obj, "template") else (card_obj.get("template", "") if isinstance(card_obj, dict) else "")).lower().strip()
        c_badge_raw = str(getattr(card_obj, "badge", "") if hasattr(card_obj, "badge") else (card_obj.get("badge", "") if isinstance(card_obj, dict) else "")).upper().strip()

        is_evidence_card = bool(card_obj) and (
            c_template_raw in (
                "document_evidence_split", "document_evidence", "split_evidence", "platzi_evidence", "informe_split",
                "quote_evidence", "quote", "citation",
                "newspaper_clipping", "newspaper", "press_clipping", "titular_prensa",
                "stat_counter", "stat_card",
                "versus_split", "versus", "vs",
                "map", "geointel_map",
                "timeline_milestone", "timeline", "cronologia",
                "spec_matrix", "benchmark_table",
                "workflow_diagram", "router_pattern",
                "social_post", "tweet"
            )
            or any(k in c_badge_raw for k in (
                "INFORME", "EVIDENCIA", "DOCUMENT", "ONU", "UNODC", "CITACIÓN", "OFICIAL",
                "NOTICIA", "PRENSA", "PERIODICO", "PERIÓDICO", "TITULAR",
                "VERSUS", "COMPARATIVA", "RÉCORD", "RECORD", "CIFRA", "ESTADÍSTICA",
                "MAPA", "GEO", "CRONOLOGIA", "TIMELINE", "BENCHMARK", "MATRIZ"
            ))
        )

        is_exact_evidence = (
            is_evidence_card
            or getattr(scene, "soundbite_clip", None) is not None
            or getattr(scene, "case_frame", None) is not None
            or getattr(scene, "is_evidence", False)
            or (visual_intent and visual_intent.intent_type in (
                VisualIntentType.HISTORICAL_EVENT,
                VisualIntentType.GEO_LOCATION,
                VisualIntentType.VERSUS_COMPARISON,
                VisualIntentType.STAT_NUMBER,
                VisualIntentType.COMPLEX_CONCEPT,
            ))
            or any(k in (scene.name or "").lower() for k in ("declaración", "soundbite", "evidencia", "prueba", "documento", "confesión", "informe", "balance", "cifra"))
        )

        # Reglas Editoriales de Ritmo, Prevención de Congelamiento y Protección de Copyright (YouTube Content ID):
        # 1. YouTube Content ID: El algoritmo automático de fingerprinting de YouTube analiza fragmentos continuos
        #    que exceden los 6 a 8 segundos. Mantener cada clip individual estrictamente entre 2.2s y 5.5s
        #    garantiza el estándar de Fair Use (Uso Legítimo) y bloquea reclamos automatizados de terceros.
        # 2. Sin congelamiento eterno: Si una escena dura 7 a 20 segundos, se distribuyen entre 3 a 4 clips según relevancia.
        #    - En escenas de evidencia: intervalo estable de 4.2s a 5.0s (tiempo para leer datos/documentos sin rebasar el umbral).
        #    - En escenas narrativas o de gancho: intervalo dinámico de 2.0s a 3.2s (máxima retención y variedad).
        should_anchor_evidence = is_exact_evidence and not is_hook_scene

        # Evaluación dinámica de densidad informativa del contenido:
        # Si la escena contiene datos, tablas, diagramas o documentos que requieren lectura:
        has_dense_content = (
            bool(document_assets)
            or is_exact_evidence
            or (getattr(scene, "card", None) is not None)
            or scene.type in ("card_focus", "versus_split", "evidence_document")
        )

        if self.is_anime:
            target_interval = 3.6
            max_allowed_gap = 4.2
            max_clips_limit = max(4, math.ceil(duration / 3.4))
            safe_log(f"[SceneEngine] 🎬 Pacing Dinámico (Escena {scene.scene_id}): Cortes estratégicos cada {target_interval}s.")
        elif has_dense_content:
            # Gráficas, tablas, documentos, tarjetas y métricas: permanencia amplia para lectura y comprensión
            target_interval = max(5.0, min(8.0, duration / 2.0)) if duration >= 10.0 else max(4.5, duration - 0.8)
            max_allowed_gap = max(6.5, target_interval + 1.5)
            max_clips_limit = max(2, math.ceil(duration / target_interval))
            safe_log(f"[SceneEngine] 📊 Contenido con datos densos (Escena {scene.scene_id}): Permanencia de lectura ({target_interval:.1f}s por plano).")
        else:
            # Planos escénicos, B-Roll y narración fluida: ritmo cinematográfico natural
            target_interval = 3.2 if is_hook_scene else 4.2
            max_allowed_gap = 4.0 if is_hook_scene else 5.2
            max_clips_limit = max(2, math.ceil(duration / (2.6 if is_hook_scene else 3.8)))

        if (not anime_precise_clips) and (scene.type != "avatar_cam" or is_hook_scene or should_anchor_evidence) and duration >= (3.6 if is_hook_scene else 4.6):
            existing_times = [t for _, t in bg_clips]
            all_pts = sorted(existing_times + [duration])
            max_gap = max((all_pts[i+1] - all_pts[i] for i in range(len(all_pts)-1)), default=duration)

            target_clips_min = max(3, math.ceil(duration / 3.8)) if self.is_anime else (2 if duration < 7.0 else (3 if duration < 13.0 else 4))
            force_cuts = (max_gap > max_allowed_gap) or (len(bg_clips) < target_clips_min)

            if force_cuts:
                target_cut = target_interval
                while target_cut <= duration - 1.2 and len(bg_clips) < max_clips_limit:
                    if not any(abs(t - target_cut) < 1.0 for t in existing_times):
                        sub_q = ""
                        # 1. Usar visual_queries secundarias diseñadas por el director si existen
                        if scene.visual_queries and len(bg_clips) < len(scene.visual_queries):
                            cand_q = scene.visual_queries[len(bg_clips)]
                            if cand_q and cand_q != scene.visual_query:
                                sub_q = f"{cand_q} 4k"

                        # 2. Revisar si hay un beat visual del director cercano a este tiempo
                        if not sub_q and getattr(scene, "visual_beats", None):
                            for vb in scene.visual_beats:
                                if isinstance(vb, dict) and vb.get("query"):
                                    sub_q = f"{vb['query']} 4k"
                                    break

                        # 3. Variación cinemática anclada al tema o persona
                        if not sub_q:
                            base_q = scene.visual_query or "documentary footage"
                            if self.is_anime:
                                anime_name = getattr(self, "anime_series_name", "Black Clover")
                                clean_base = base_q.replace("4k", "").replace("documentary", "").replace("footage", "").strip()
                                # Anclaje dinámico al episodio específico del arco
                                range_m = re.search(r'(?:episodios?|episodes?|ep\.?)\s*(\d+)\s*(?:-|a|to)\s*(\d+)', str(getattr(self, "topic", "")), re.IGNORECASE)
                                ep_m = re.search(r'(?:ep|episode|episodio)\s*(\d+)', (base_q + " " + getattr(scene, "name", "")).lower())
                                if ep_m:
                                    target_ep_str = ep_m.group(1)
                                elif range_m:
                                    min_ep = int(range_m.group(1))
                                    max_ep = int(range_m.group(2))
                                    sc_num = getattr(self, "_current_scene_num", 1)
                                    tot_sc = len(getattr(self, "scenes", [])) or 6
                                    calc_ep = min_ep + int(((sc_num - 1) / max(1, tot_sc)) * (max_ep - min_ep + 0.99))
                                    target_ep_str = str(min(max_ep, max(min_ep, calc_ep)))
                                else:
                                    target_ep_str = "1"

                                ep_anchor = f"episode {target_ep_str}"
                                variations = [
                                    "action clip",
                                    "sakuga clip",
                                    "fight clip",
                                    "scene clip"
                                ]
                                var_suffix = variations[(len(bg_clips) - 1) % len(variations)]
                                noise_sub = {"in", "on", "at", "to", "for", "from", "with", "by", "the", "a", "an", "and", "or", "of", "no", "not", "into", "en", "de", "la", "el", "los", "las", "un", "una", "y", "o", "del", "al", "anime", "video", "clip", "scene", "episode", "episodio", "ep"}
                                speech_words = [w for w in re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]+', speech_text) if len(w) >= 4 and w.lower() not in noise_sub and w.lower() not in anime_name.lower()]
                                sub_words = [w for w in re.findall(r'[a-zA-Z]+', clean_base) if w.lower() not in noise_sub and w.lower() not in anime_name.lower()]
                                salient = sub_words[:2] or speech_words[:2]
                                core_sub = " ".join(salient)
                                sub_q = f"{anime_name} {ep_anchor} {core_sub} {var_suffix}".strip()
                            else:
                                is_person_or_speech = any(k in base_q.lower() for k in (
                                    "speech", "interview", "press", "president", "presidente", "minister",
                                    "milei", "trump", "musk", "biden", "petro", "bukele", "sanchez", "altman", "news"
                                ))
                                if is_person_or_speech:
                                    variations = [
                                        "press conference angle",
                                        "speech statement closeup",
                                        "reaction audience media angle",
                                        "official press report footage",
                                        "alternate speech angle"
                                    ]
                                else:
                                    variations = [
                                        "close up detail 4k",
                                        "wide angle perspective 4k",
                                        "dynamic documentary angle",
                                        "archival footage hd",
                                        "cinematic motion angle 4k"
                                    ]
                                var_suffix = variations[(len(bg_clips) - 1) % len(variations)]
                                sub_q = f"{base_q} {var_suffix}"

                        try:
                            supp_clip = await self._get_scene_visual(sub_q, scene_dir, is_video_scene=True)
                            if supp_clip and _is_distinct_clip(supp_clip, bg_clips):
                                bg_clips.append((supp_clip, round(target_cut, 2)))
                                existing_times.append(round(target_cut, 2))
                                if hasattr(self, "used_clip_names"):
                                    self.used_clip_names.add(supp_clip.name)
                                safe_log(f"[SceneEngine] ⚡ Corte de ritmo dinámico (Micro-Pacing t={target_cut:.1f}s): '{sub_q}'")
                            elif self.is_anime and broll_img and broll_img.exists() and broll_img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                                # Reutilizar metraje auténtico oficial de la escena con offset dinámico sin arriesgar descargas espurias
                                bg_clips.append((broll_img, round(target_cut, 2)))
                                existing_times.append(round(target_cut, 2))
                                safe_log(f"[SceneEngine] 🎬 Reencuadre cinemático sobre metraje oficial de la escena (t={target_cut:.1f}s)")
                            elif self.is_anime:
                                # Reutilizar clips oficiales canónicos ya verificados y descargados en este proyecto
                                existing_assets = list((self.work_dir / "assets").glob("scene_cue_*_yt.mp4")) if hasattr(self, "work_dir") and (self.work_dir / "assets").exists() else []
                                valid_assets = [a for a in existing_assets if a.exists() and a.stat().st_size > 100000]
                                if valid_assets:
                                    borrowed = valid_assets[(len(bg_clips) * 3) % len(valid_assets)]
                                    bg_clips.append((borrowed, round(target_cut, 2)))
                                    existing_times.append(round(target_cut, 2))
                                    safe_log(f"[SceneEngine] 🎬 Reencuadre desde archivo oficial canónico existente: {borrowed.name} (t={target_cut:.1f}s)")
                            elif bg_clips:
                                # Sin metraje nuevo disponible: no duplicar artificialmente la misma imagen cada 2 segundos.
                                # Se sostiene la toma existente con movimiento continuo de cámara sin saltos espurios.
                                pass
                        except Exception as _esup:
                            safe_log(f"[SceneEngine] Fallback en B-Roll complementario: {_esup}")
                    target_cut += target_interval

        # Filtrar clips corruptos o sin frames decodificables
        valid_bg_clips = []
        for p, t in bg_clips:
            if self._is_valid_media_clip(p):
                valid_bg_clips.append((p, t))
            else:
                safe_log(f"[SceneEngine] ⚠️ Descartando clip corrupto o sin frames decodificables: {p.name}")
        bg_clips = valid_bg_clips

        # Auditoría de assets: clasificar cada imagen antes de usarla como fondo.
        # Descarta anime/collages y detecta diagramas para mostrarlos completos (sin recorte).
        document_assets.clear()
        try:
            from core.vision_qa import vision_qa
            audited: List[Tuple[Path, float]] = []
            _pairs = list(bg_clips)
            _infos = await asyncio.gather(*[
                asyncio.to_thread(vision_qa.classify_media, _p, speech_text) for _p, _ in _pairs
            ])
            for (_p, _t), _info in zip(_pairs, _infos):
                _suffix = _p.suffix.lower()
                _is_img = _suffix in (".jpg", ".jpeg", ".png", ".webp")
                _is_vid = _suffix in (".mp4", ".mov", ".webm", ".mkv", ".m4v")
                if _is_img or _is_vid:
                    _kind = str(_info.get("kind", "")).lower()
                    _dense = bool(_info.get("has_dense_text"))
                    _watermark = bool(_info.get("has_watermark"))
                    _doc_kind = _kind in ("diagram", "screenshot", "text_graphic")
                    if _kind in ("anime", "collage", "logo", "watermark") or _watermark or not _info.get("coherent_with_scene", True):
                        safe_log(f"[SceneEngine] 🚫 Asset descartado ({_kind or 'incoherente'}): {_p.name}")
                        continue
                    if _is_vid and (_doc_kind or _dense or not _info.get("use_as_background", True)):
                        safe_log(f"[SceneEngine] 🚫 Clip con texto/diagrama descartado ({_kind}): {_p.name}")
                        continue
                    if _is_img and (_doc_kind or _dense):
                        document_assets.add(str(_p))
                        safe_log(f"[SceneEngine] 📄 Documento detectado ({_kind}): {_p.name}. Se mostrará completo, sin zoom ni card encima.")
                audited.append((_p, _t))
            bg_clips = audited
            if document_assets and not self.is_anime:
                target_interval = max(5.0, min(8.0, duration / 2.0)) if duration >= 10.0 else max(4.5, duration - 0.8)
                max_allowed_gap = max(6.5, target_interval + 1.5)
        except Exception as _qa_err:
            safe_log(f"[SceneEngine] Aviso clasificando assets: {_qa_err}")

        # Si no se pudo obtener ningún B-Roll o falló la descarga, usar estudio ambiental
        if not bg_clips:
            studio_blur_path = Path("assets/streamer_studio_blur_9_16.jpg" if self.is_vertical else "assets/streamer_studio_blur_16_9.jpg")
            fallback_bg = studio_blur_path if studio_blur_path.exists() else Path("assets/streamer_studio_room.jpg")
            if fallback_bg.exists():
                bg_clips.append((fallback_bg, 0.0))

        # Garantía Universal Anti-Congelamiento y Variación Continua (Fotos y Videos):
        # En canales normales/periodismo: subdivide en tomas de 2.6s a 3.4s con punch-ins.
        # EN ANIME RECAP: Cada clip de animación fluye naturalmente (7s a 10s).
        # PROHIBIDO cortar cada 2 segundos y PROHIBIDO repetir el mismo clip 20 veces.
        bg_clips.sort(key=lambda x: x[1])
        if anime_precise_clips:
            pass  # cortes ya anclados a cada mención; no tocar
        elif self.is_anime:
            distinct_anime_clips: List[Tuple[Path, float]] = []
            last_t = -999.0
            for clip_p, t_start in bg_clips:
                if not distinct_anime_clips:
                    distinct_anime_clips.append((clip_p, 0.0))
                    last_t = 0.0
                elif (t_start - last_t) >= 2.2:
                    distinct_anime_clips.append((clip_p, round(t_start, 2)))
                    last_t = t_start

            # Garantía Absoluta: Si hay menos de 3 planos y la escena dura >= 5s,
            # subdividir en cortes estratégicos cada 3.5s para alternancia y movimiento continuo
            if len(distinct_anime_clips) < max(2, math.ceil(duration / 4.0)) and duration >= 5.0:
                base_clip, _ = distinct_anime_clips[0]
                dense_anime: List[Tuple[Path, float]] = [(base_clip, 0.0)]
                t_step = 3.5
                cur_t = t_step
                cut_idx = 1
                while cur_t <= duration - 1.2:
                    dense_anime.append((base_clip, round(cur_t, 2)))
                    cur_t += t_step
                    cut_idx += 1
                distinct_anime_clips = dense_anime

            bg_clips = distinct_anime_clips
        else:
            all_collected_media = [p for p, _ in bg_clips if p and p.exists()]
            dense_clips: List[Tuple[Path, float]] = []
            for idx_c, (clip_p, t_start) in enumerate(bg_clips):
                t_next = bg_clips[idx_c + 1][1] if (idx_c + 1 < len(bg_clips)) else duration
                seg_len = round(t_next - t_start, 2)
                dense_clips.append((clip_p, t_start))

                if seg_len > max_allowed_gap and seg_len >= 4.0:
                    is_img_seg = clip_p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                    if len(all_collected_media) <= 1:
                        # Una sola imagen de fondo: dejar que fluya en Ken Burns suave continuo sin cortes artificiales sobre sí misma
                        pass
                    else:
                        sub_step = 3.0 if is_hook_scene else (3.8 if is_img_seg else 4.6)
                        t_sub = round(t_start + sub_step, 2)
                        alt_idx = 0
                        while t_sub <= t_next - 1.2:
                            if len(all_collected_media) > 1 and is_img_seg:
                                next_media = all_collected_media[(idx_c + alt_idx + 1) % len(all_collected_media)]
                            else:
                                next_media = clip_p
                            dense_clips.append((next_media, t_sub))
                            alt_idx += 1
                            t_sub = round(t_sub + sub_step, 2)

            dense_clips.sort(key=lambda x: x[1])
            bg_clips = dense_clips

        # Detección inteligente de cortes de declaración / Soundbite del protagonista
        # REGLA ESTRICTA DE ANIME: Si es anime/manga/ficción, NUNCA se activa soundbite de personas reales
        # ni se pausa la locución. El narrador habla continuo al 100% y los visuales son clips puros de anime.
        if self.is_anime:
            is_soundbite_scene = False
        else:
            speech_low = (scene.speech or "").lower()
            name_low = (scene.name or "").lower()
            quote_keywords = [
                "dijo", "afirmó", "afirmo", "declaró", "declaro", "aseguró", "aseguro",
                "expresó", "expreso", "manifestó", "manifiesto", "palabras", "discurso",
                "conferencia", "entrevista", "declaraciones", "cita", "testimonio",
                "rueda de prensa", "escuchen", "miren lo que dijo", "atención a lo que",
                "esto afirmó", "declaró ante", "en sus propias palabras", "escuchémoslo", "escuchenlo"
            ]
            is_quote_context = any(k in speech_low or k in name_low for k in quote_keywords)
            is_soundbite_scene = (
                scene.type == "video_reaction"
                or getattr(scene, "soundbite", False)
                or is_quote_context
                or getattr(self, "enable_clip_audio", False)
            )

        clip_audio_candidate = None
        soundbite_offset = 0.0
        soundbite_window = 0.0

        if not self.is_anime:
            # 1. Si el director asignó un clip de soundbite real del video fuente:
            sb_clip_name = getattr(scene, "soundbite_clip", None)
            if sb_clip_name:
                for cand_p in [
                    self.workdir / "case_soundbites" / sb_clip_name,
                    self.workdir / sb_clip_name,
                    Path(sb_clip_name),
                ]:
                    if cand_p.exists() and cand_p.stat().st_size > 10000:
                        clip_audio_candidate = cand_p
                        soundbite_offset = getattr(scene, "soundbite_offset", 0.0) or 0.0
                        soundbite_window = getattr(scene, "soundbite_dur", None) or 3.8
                        safe_log(f"[SceneEngine] 🎯 Soundbite directo del director vinculado: {cand_p.name} (dur={soundbite_window:.2f}s)")
                        break

            # 2. Si no hay soundbite predefinido pero es escena de soundbite/reacción:
            if not clip_audio_candidate:
                clip_audio_candidate = self._get_clip_with_audio(bg_clips)
                if is_soundbite_scene and clip_audio_candidate:
                    # Análisis semántico y de voz para encontrar el punto estratégico y lógico donde habla la persona
                    try:
                        from core.soundbite_analyzer import StrategicSoundbiteAnalyzer
                        sb_analyzer = StrategicSoundbiteAnalyzer()
                        target_kw = getattr(scene, "chips", []) + [w for w in (scene.name or "").split() if len(w) > 3]
                        sb_info = await asyncio.to_thread(
                            sb_analyzer.find_best_soundbite_in_clip,
                            clip_audio_candidate,
                            scene.speech,
                            target_kw,
                        )
                        if sb_info:
                            soundbite_offset = sb_info.start_sec
                            soundbite_window = max(2.6, min(5.8, sb_info.duration + 0.35))
                            safe_log(f"[SceneEngine] 🎙️ Soundbite estratégico detectado (t={soundbite_offset:.2f}s, dur={soundbite_window:.2f}s): «{sb_info.quote}»")
                        else:
                            soundbite_offset = 0.0
                            soundbite_window = 3.6
                    except Exception as _sbe:
                        safe_log(f"[SceneEngine] Aviso detectando offset de soundbite: {_sbe}")
                        soundbite_offset = 0.0
                        soundbite_window = 3.6

        # Pausas estratégicas para cortes de declaración / clips del protagonista:
        # - sb_pause_before: Pausa de suspense / respiración (0.40s) tras terminar KAI y antes de que hable la persona.
        # - sb_pause_after: Pausa de reflexión (0.55s) tras terminar la declaración para absorber su impacto antes de la siguiente escena.
        sb_pause_before = 0.0 if self.is_anime else 0.40
        sb_pause_after = 0.0 if self.is_anime else 0.55

        if is_soundbite_scene and clip_audio_candidate and not self.is_anime:
            soundbite_start_t = round(tts_duration + sb_pause_before, 2)
            duration = max(duration, round(soundbite_start_t + soundbite_window + sb_pause_after, 2))
            dur_str = f"{duration:.2f}"
            # Asegurar que el fondo corte al clip del protagonista al iniciar el soundbite (con micro-anticipo visual cinemático)
            clip_switch_t = max(0.0, round(soundbite_start_t - 0.20, 2))
            has_clip_at_sb = any(p == clip_audio_candidate and abs(t - clip_switch_t) < 0.35 for p, t in bg_clips)
            if not has_clip_at_sb and clip_switch_t < duration:
                bg_clips.append((clip_audio_candidate, clip_switch_t))
                bg_clips.sort(key=lambda x: x[1])
            safe_log(f"[SceneEngine] 🎙️ Soundbite activo: reservando {soundbite_window:.2f}s para voz real del protagonista ({clip_audio_candidate.name}) con pausas estratégicas (pre={sb_pause_before}s, post={sb_pause_after}s). Duración escena: {duration:.2f}s")

        # Decisión del Director sobre la presencia del presentador en la escena:
        # Se activa si la escena fue diseñada con cámara de presentador (pip o avatar_cam),
        # y se desactiva si el Director asignó voice_over para dar prioridad absoluta al material visual en pantalla completa.
        cam_type = str(getattr(scene, "camera", "voice_over") or "voice_over").lower().strip()
        sc_type = str(getattr(scene, "type", "voice_over") or "voice_over").lower().strip()
        is_voice_over_only = (
            cam_type in ("voice_over", "none", "hidden")
            or sc_type in ("voice_over", "document_evidence", "evidence_document")
            or not getattr(self, "enable_avatar", True)
        )
        is_scene_documentary = is_voice_over_only
        scene_avatar_clip = None if is_scene_documentary else (scene_dir / "kai_avatar_synced.mov")
        if not is_scene_documentary:
            try:
                from core.avatar_renderer import AvatarRenderer
                rnd = AvatarRenderer()
                await asyncio.to_thread(
                    rnd.render_reaction_clip,
                    duration_sec=duration,
                    out_path=scene_avatar_clip,
                    audio_path=audio_path,
                    fps=24
                )
                if not scene_avatar_clip.exists() or scene_avatar_clip.stat().st_size < 10000:
                    safe_log(f"[SceneEngine] Avatar sincronizado inválido o vacío para escena {scene.scene_id}: fallback a base.")
                    scene_avatar_clip = None
            except Exception as exc:
                safe_log(f"[SceneEngine] Fallback a avatar clip base: {exc}")
                scene_avatar_clip = None
        else:
            safe_log(f"[SceneEngine] 🎬 Escena {scene.scene_id}: Avatar sincronizado omitido para estilo documental puro.")

        # 2d. Microelementos visuales cinéticos y badges dinámicos diseñados por DeepSeek Flash
        # 2d. Microelementos visuales cinéticos y badges dinámicos diseñados por DeepSeek Flash
        motion_overlay_path = None
        motion_badges = []
        motion_stat = None
        if getattr(self, "motion_engine", None):
            motion_dir = getattr(self, "deepseek_motion_director", None)
            if motion_dir:
                try:
                    acc_col = getattr(scene, "accent_color", "#ff9436") or "#ff9436"
                    motion_spec = motion_dir.design_motion_spec(
                        scene_name=scene.name,
                        speech_text=speech_text,
                        duration=duration,
                        accent_color=acc_col,
                        scene_type=getattr(scene, "type", "broll_narration"),
                    )
                    motion_assets = await self.motion_engine.render_scene_motion_assets(
                        motion_spec=motion_spec,
                        duration=duration,
                        scene_dir=scene_dir,
                        scene_id=scene.scene_id,
                        accent_color=acc_col,
                    )
                    motion_overlay_path = motion_assets.get("bg_overlay")
                    motion_badges = motion_assets.get("badges", [])
                    motion_stat = motion_assets.get("stat")
                    # Sin insignias/píldoras flotantes: solo texto y cards editoriales.
                    motion_badges = []
                    motion_stat = None
                    if motion_overlay_path and motion_overlay_path.exists():
                        safe_log(f"[SceneEngine] ✓ Capa de motion graphics DeepSeek Flash lista para escena {scene.scene_id} ({len(motion_badges)} insignias escalonadas)")
                except Exception as _me:
                    safe_log(f"[SceneEngine] Fallback en motion graphics: {_me}")
                    motion_overlay_path = None
                    motion_badges = []
                    motion_stat = None

        # 3. Preparar tarjeta Bento moderna o alternativa visual honesta
        card_img_path = None
        animated_card_path = None
        card_visual_type = "bento"
        card_start_time = 0.5
        smart_card_dur = None

        # Si el director no asignó tarjeta pero la locución menciona una cifra, lugar, comparación,
        # frase impactante, acontecimiento o concepto difícil, generar la alternativa visual honesta adecuada:
        if not scene.card and visual_intent and visual_intent.intent_type != VisualIntentType.GENERAL_BROLL:
            from core.director import SceneCard
            if visual_intent.intent_type == VisualIntentType.STAT_NUMBER and visual_intent.stat_value:
                # Las cifras y porcentajes se animan con Motion Graphics cinéticos flotantes (DeepSeek Flash)
                # sin crear tarjetas toscas estáticas que oscurezcan el video.
                safe_log(f"[SmartMediaCurator] 📊 Cifra en locución ({visual_intent.stat_value}) -> Animación cinética flotante DeepSeek sin card tosco.")
            elif visual_intent.intent_type == VisualIntentType.GEO_LOCATION:
                scene.card = SceneCard(
                    headline=visual_intent.entity_name,
                    stat=visual_intent.location or "ZONA TÁCTICA",
                    body=f"Ubicación geográfica clave: {visual_intent.entity_name} ({visual_intent.location})",
                    badge="MAPA TÁCTICO",
                    template="map",
                )
                safe_log(f"[SmartMediaCurator] 🗺️ Lugar en locución -> Generando Mapa GeoIntel: {visual_intent.entity_name}")
            elif visual_intent.intent_type == VisualIntentType.VERSUS_COMPARISON:
                scene.card = SceneCard(
                    headline=visual_intent.entity_name,
                    body=visual_intent.secondary_entity,
                    badge="COMPARATIVA",
                    template="versus_split",
                )
                safe_log(f"[SmartMediaCurator] ⚔️ Comparación en locución -> Generando Versus Split: {visual_intent.entity_name} vs {visual_intent.secondary_entity}")
            elif visual_intent.intent_type == VisualIntentType.IMPACT_PHRASE:
                scene.card = SceneCard(
                    headline=visual_intent.entity_name,
                    body=visual_intent.raw_sentence[:90],
                    badge="PUNTO CLAVE",
                    template="alert_banner",
                )
                safe_log(f"[SmartMediaCurator] ⚡ Frase impactante en locución -> Generando Alert Banner: {visual_intent.entity_name}")
            elif visual_intent.intent_type == VisualIntentType.COMPLEX_CONCEPT:
                scene.card = SceneCard(
                    headline=visual_intent.entity_name,
                    body=visual_intent.raw_sentence[:95],
                    badge="CONCEPTO TÉCNICO",
                    template="tech_card",
                )
                safe_log(f"[SmartMediaCurator] 💡 Concepto difícil en locución -> Generando Tech Card: {visual_intent.entity_name}")
            elif visual_intent.intent_type == VisualIntentType.HISTORICAL_EVENT and visual_intent.year:
                scene.card = SceneCard(
                    headline=visual_intent.entity_name,
                    body=visual_intent.raw_sentence[:110],
                    stat=str(visual_intent.year),
                    badge=f"ARCHIVO · {visual_intent.year}",
                    template="quote_evidence",
                )
                safe_log(f"[SmartMediaCurator] 📜 Acontecimiento con fecha -> Generando Registro Histórico: {visual_intent.year}")

        # Calcular temporización sincronizada para que aparezca cuando aporte contexto y se retire cuando deje de ser relevante
        if visual_intent:
            card_start_time, smart_card_dur = SmartMediaCurator.calculate_smart_timing(
                visual_intent, sentence_boundaries, duration, word_times=word_times
            )

        # 3b. Remotion AI: Evaluación prioritaria para animaciones React (MetricCounter / VersusComparison)
        ai_remotion_mov: Optional[Path] = None
        if getattr(self, "ai_remotion", None) and self.ai_remotion.remotion.available() and duration >= 3.0:
            c_templ_cand = str(getattr(scene.card, "template", "") if hasattr(scene.card, "template") else (scene.card.get("template", "") if isinstance(scene.card, dict) else "")).lower() if scene.card else ""
            c_stat_cand = str(getattr(scene.card, "stat", "") if hasattr(scene.card, "stat") else (scene.card.get("stat", "") if isinstance(scene.card, dict) else "")) if scene.card else ""
            is_stat_candidate = (
                c_templ_cand in ("stat_counter", "stat_card")
                or (visual_intent and visual_intent.intent_type == VisualIntentType.STAT_NUMBER)
                or ("%" in c_stat_cand or (c_stat_cand and any(ch.isdigit() for ch in c_stat_cand) and len(c_stat_cand) < 14))
            )
            is_versus_candidate = (
                c_templ_cand in ("versus_split", "versus", "vs")
                or (visual_intent and visual_intent.intent_type == VisualIntentType.VERSUS_COMPARISON)
                or (scene.card and " vs " in (getattr(scene.card, "headline", "") or "").lower())
            )
            if is_stat_candidate or is_versus_candidate:
                try:
                    ai_remotion_mov = await self.ai_remotion.render_ai_overlay(
                        scene_name=scene.name,
                        speech_text=speech_text,
                        duration=duration,
                        out_dir=scene_dir,
                        vertical=self.is_vertical,
                        theme_spec=getattr(self, "style_spec", None),
                        card=scene.card,
                        intent=visual_intent,
                    )
                    if ai_remotion_mov and ai_remotion_mov.exists() and ai_remotion_mov.stat().st_size > 20000:
                        safe_log(f"[SceneEngine] ⚛️ Remotion React overlay animado generado para escena {scene.scene_id}: {ai_remotion_mov.name}")
                        scene.card = None  # Remotion toma el protagonismo; evitamos tarjeta estática redundante
                except Exception as _re_err:
                    safe_log(f"[SceneEngine] Remotion React overlay omitido, fallback a estático: {_re_err}")
                    ai_remotion_mov = None

        if scene.card:
            card_img_path = scene_dir / f"card_{scene.scene_id}.png"
            c_badge = str(scene.card.get("badge") if isinstance(scene.card, dict) else getattr(scene.card, "badge", "") or "").upper()
            c_headline = str(scene.card.get("headline") if isinstance(scene.card, dict) else getattr(scene.card, "headline", "") or "")
            c_body = str(scene.card.get("body") if isinstance(scene.card, dict) else getattr(scene.card, "body", "") or c_headline)
            c_stat = str(scene.card.get("stat") if isinstance(scene.card, dict) else getattr(scene.card, "stat", "") or "")
            c_style = str(getattr(scene.card, "style", "auto") if hasattr(scene.card, "style") else (scene.card.get("style", "auto") if isinstance(scene.card, dict) else "auto")).lower().strip()
            c_icon = str(getattr(scene.card, "icon", "✓") if hasattr(scene.card, "icon") else (scene.card.get("icon", "✓") if isinstance(scene.card, dict) else "✓")).strip()
            c_sub = str(getattr(scene.card, "subtitle", "") if hasattr(scene.card, "subtitle") else (scene.card.get("subtitle", "") if isinstance(scene.card, dict) else "")).strip()

            # Sincronización temporal con la locución si se mencionan palabras clave del titular
            if sentence_boundaries and c_headline and not smart_card_dur:
                c_words = [w.lower() for w in re.findall(r'\w+', c_headline) if len(w) > 3]
                for s_st, _s_en, s_txt in sentence_boundaries:
                    low_txt = s_txt.lower()
                    if any(w in low_txt for w in c_words):
                        card_start_time = max(0.4, min(duration - 2.5, round(s_st, 2)))
                        break

            c_template = str(getattr(scene.card, "template", "auto") if hasattr(scene.card, "template") else (scene.card.get("template", "auto") if isinstance(scene.card, dict) else "auto")).lower().strip()
            c_variant = str(getattr(scene.card, "variant", "orange_noir") if hasattr(scene.card, "variant") else (scene.card.get("variant", "orange_noir") if isinstance(scene.card, dict) else "orange_noir")).lower().strip()
            c_params = dict(getattr(scene.card, "params", {}) if hasattr(scene.card, "params") else (scene.card.get("params", {}) if isinstance(scene.card, dict) else {}))

            try:
                # 0. Plantillas dedicadas del VisualTemplatesLibrary
                # 0a. Distintivo Viral Inclinado (Reels: '✓ ganó Opus', '100% Real', 'Confirmado')
                if c_template == "verdict_badge" or c_style == "verdict_badge" or any(k in c_badge for k in ("VEREDICTO", "GANADOR", "GANÓ", "GANO", "SELLO", "BADGE", "STAMP")) or any(k in c_headline.lower() for k in ("ganó", "gano", "ganador", "100% real", "veredicto")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="verdict_badge",
                        out_png=card_img_path,
                        params={"headline": c_headline, "icon": c_icon or "✓", "subtitle": c_sub or c_body, **c_params},
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "verdict_badge"
                        safe_log(f"[SceneEngine] 🏷️ Distintivo Viral (Verdict Badge) generado para escena {scene.scene_id}: {c_headline}")

                # 0b. Tarjeta Técnica Flotante Superior (Reels: 'find-skills por Vercel')
                elif c_template in ("tech_card", "tech_header") or c_style == "tech_card" or any(k in c_badge for k in ("TECH", "HERRAMIENTA", "SKILL", "TOOL", "DEV", "GITHUB", "CÓDIGO", "CODIGO")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="tech_card",
                        out_png=card_img_path,
                        params={"title": c_headline, "subtitle": c_sub or c_body or c_stat, **c_params},
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "tech_card"
                        safe_log(f"[SceneEngine] 💻 Tarjeta Técnica Flotante (Tech Card) generada para escena {scene.scene_id}: {c_headline}")

                # 0c. Cifra Récord / Métrica Clave con medidor en gradiente (solo si no es otra plantilla explícita)
                elif c_template in ("stat_counter", "stat_card") or ((c_template in ("auto", "default", "") or not c_template) and (any(k in c_badge for k in ("RÉCORD", "RECORD", "CIFRA", "MÉTRICA", "METRICA")) or ("%" in c_stat or (c_stat and any(ch.isdigit() for ch in c_stat) and len(c_stat) < 12 and not any(k in c_badge for k in ("MAPA", "GEO", "INFORME", "EVIDENCIA", "DOCUMENTO")))))):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="stat_counter",
                        out_png=card_img_path,
                        params={"stat_value": c_stat or "100%", "stat_label": c_body or c_headline, "headline": c_headline, "tag": c_badge or "MÉTRICA CLAVE", **c_params},
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "stat_counter"
                        safe_log(f"[SceneEngine] 📊 Métrica Clave (Stat Counter) generada para escena {scene.scene_id}: {c_stat}")

                # 0d. Comparativa Versus Dual (Lado A vs Lado B con divisor circular central)
                elif c_template in ("versus_split", "versus", "vs") or any(k in c_badge for k in ("VERSUS", "COMPARATIVA", "DUAL", "VS")) or (" vs " in c_headline.lower() or " vs " in c_body.lower() or " vs " in c_stat.lower()):
                    s_a = c_headline
                    s_b = c_body or "IA"
                    st_a, st_b = "", ""
                    if " vs " in c_headline.lower():
                        parts = c_headline.split(" vs ", 1)
                        s_a, s_b = parts[0].strip(), parts[1].strip()
                    if " vs " in c_stat.lower():
                        st_parts = c_stat.split(" vs ", 1)
                        st_a, st_b = st_parts[0].strip(), st_parts[1].strip()
                    card_res = self.web_renderer.render_visual_template(
                        template_name="versus_split",
                        out_png=card_img_path,
                        params={"side_a": s_a, "side_b": s_b, "stat_a": st_a, "stat_b": st_b, "tag": c_badge or "COMPARATIVA DIRECTA", **c_params},
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "versus_split"
                        safe_log(f"[SceneEngine] ⚔️ Comparativa Versus Dual generada para escena {scene.scene_id}: {s_a} vs {s_b}")

                # 0e. Insignia de Hito, Fase o Paso (Step Badge)
                elif c_template in ("step_badge", "step", "phase") or any(k in c_badge for k in ("PASO", "FASE", "HITO", "REGLA")) or (c_headline.lower().startswith("paso ") or c_headline.lower().startswith("fase ")):
                    step_num = c_stat or "01"
                    m_num = re.search(r'\d+', c_headline)
                    if m_num and not c_stat:
                        step_num = m_num.group(0)
                    card_res = self.web_renderer.render_visual_template(
                        template_name="step_badge",
                        out_png=card_img_path,
                        params={"step_number": step_num, "step_title": c_headline, "subtitle": c_body or c_sub, **c_params},
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "step_badge"
                        safe_log(f"[SceneEngine] 🔢 Insignia de Fase (Step Badge) generada para escena {scene.scene_id}: {c_headline}")

                # 0f. Banner de Alerta Crítica HUD
                elif c_template in ("alert_banner", "alert", "warning") or any(k in c_badge for k in ("ALERTA", "PELIGRO", "WARNING", "CRÍTICO", "CRITICO")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="alert_banner",
                        out_png=card_img_path,
                        params={"headline": c_headline, "body": c_body, "tag": c_badge or "ADVERTENCIA CRÍTICA", **c_params},
                        variant="crimson_hazard" if c_variant == "orange_noir" else c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "alert_banner"
                        safe_log(f"[SceneEngine] ⚠️ Banner de Alerta Táctica generado para escena {scene.scene_id}: {c_headline}")

                # 0g. Pastilla de Fuente Verificada (Source Chip)
                elif c_template in ("source_chip", "chip", "source") or any(k in c_badge for k in ("FUENTE", "ATRIBUCIÓN", "ATRIBUCION", "ORIGEN")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="source_chip",
                        out_png=card_img_path,
                        params={"source_name": c_headline, "tag": c_badge or "FUENTE OFICIAL", **c_params},
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "source_chip"
                        safe_log(f"[SceneEngine] 🛡️ Pastilla de Fuente (Source Chip) generada para escena {scene.scene_id}: {c_headline}")

                # 0h. Citas / Evidencias documentales -> Cita Vox Style de alta fidelidad
                elif c_template in ("quote_evidence", "quote", "citation") or any(k in c_badge for k in ("DOCUMENTAL", "EVIDENCIA", "INFORME", "CITA")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="quote_evidence",
                        out_png=card_img_path,
                        params={"quote_text": c_body or c_headline, "source": c_stat or "Registro Oficial 2026", **c_params},
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "quote_evidence"
                        safe_log(f"[SceneEngine] 📜 Cita/Evidencia Vox Style generada para escena {scene.scene_id}")

                # 0i. Recorte de Periódico / Prensa con Subrayador Neón (Estilo Adrià Solà Pastor / Vox)
                elif c_template in ("newspaper_clipping", "newspaper", "press_clipping", "titular_prensa") or any(k in c_badge for k in ("NOTICIA", "PRENSA", "PERIODICO", "PERIÓDICO", "TITULAR", "FINANCIAL", "BLOOMBERG", "WSJ", "REUTERS")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="newspaper_clipping",
                        out_png=card_img_path,
                        params={
                            "headline": c_headline,
                            "newspaper": c_stat or "FINANCIAL TIMES",
                            "body_lead": c_body if c_body != c_headline else "",
                            "tag": c_badge or "EVIDENCIA EDITORIAL",
                            **c_params
                        },
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "newspaper_clipping"
                        safe_log(f"[SceneEngine] 📰 Recorte de Prensa con Subrayador Neón generado para escena {scene.scene_id}: {c_headline}")

                # 0j. Publicación Verificada en Redes (X / Twitter Card)
                elif c_template in ("social_post", "tweet", "x_post", "comunicado_social") or any(k in c_badge for k in ("TWEET", "TWITTER", "POST", "DECLARACION", "DECLARACIÓN", "X")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="social_post",
                        out_png=card_img_path,
                        params={
                            "author_name": c_headline,
                            "handle": c_stat if c_stat.startswith("@") else f"@{c_headline.lower().replace(' ', '')}",
                            "post_text": c_body or c_headline,
                            **c_params
                        },
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "social_post"
                        safe_log(f"[SceneEngine] 🐦 Publicación Social Verificada generada para escena {scene.scene_id}: {c_headline}")

                # 0k. Cronología Documental / Línea de Tiempo
                elif c_template in ("timeline_milestone", "timeline", "cronologia", "hitos") or any(k in c_badge for k in ("CRONOLOGIA", "CRONOLOGÍA", "TIMELINE", "EVOLUCIÓN", "EVOLUCION")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="timeline_milestone",
                        out_png=card_img_path,
                        params={
                            "title": c_headline,
                            **c_params
                        },
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "timeline_milestone"
                        safe_log(f"[SceneEngine] ⏳ Línea de Tiempo Documental generada para escena {scene.scene_id}: {c_headline}")

                # 0l. Diagrama de Arquitectura / Patrón de Enrutamiento Agéntico (Estilo Santa IA - Router Pattern)
                elif c_template in ("workflow_diagram", "workflow", "router_pattern", "agent_graph", "nodos_agente", "diagrama_flujo") or any(k in c_badge for k in ("ROUTER", "ARQUITECTURA", "PATRON", "PATRÓN", "FLUJO", "AGENTES", "AGENTE")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="workflow_diagram",
                        out_png=card_img_path,
                        params={
                            "title": c_headline,
                            "note": c_body or "Aislamiento de contexto: solo el agente seleccionado consume tokens.",
                            **c_params
                        },
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "workflow_diagram"
                        safe_log(f"[SceneEngine] 🔀 Diagrama de Arquitectura / Router Agéntico generado para escena {scene.scene_id}: {c_headline}")

                # 0m. Consola Terminal HUD / Claude Code CLI (Estilo Dev / Santa IA)
                elif c_template in ("terminal_hud", "terminal", "cli_console", "code_terminal", "consola_codigo") or any(k in c_badge for k in ("TERMINAL", "CLI", "CODIGO", "CÓDIGO", "CLAUDE CODE", "COMMAND")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="terminal_hud",
                        out_png=card_img_path,
                        params={
                            "command": c_headline,
                            "body": c_body,
                            **c_params
                        },
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "terminal_hud"
                        safe_log(f"[SceneEngine] 💻 Consola Terminal HUD generada para escena {scene.scene_id}: {c_headline}")

                # 0n. Matriz de Especificaciones / Benchmark Comparativo (Estilo Santa IA)
                elif c_template in ("spec_matrix", "benchmark_table", "matrix_table", "comparativa_metricas", "benchmark") or any(k in c_badge for k in ("BENCHMARK", "MATRIZ", "COMPARATIVA", "METRICAS", "MÉTRICAS")):
                    card_res = self.web_renderer.render_visual_template(
                        template_name="spec_matrix",
                        out_png=card_img_path,
                        params={
                            "title": c_headline,
                            "subtitle": c_body,
                            "tag": c_badge or "BENCHMARK DE ARQUITECTURA",
                            **c_params
                        },
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "spec_matrix"
                        safe_log(f"[SceneEngine] 📊 Matriz de Especificaciones / Benchmark generada para escena {scene.scene_id}: {c_headline}")

                # 0o. Pantalla Dividida Documental (Estilo Platzi + Agustín Laje)
                elif c_template in ("document_evidence_split", "document_evidence", "split_evidence", "platzi_evidence", "informe_split") or any(k in c_badge for k in ("INFORME OFICIAL", "EVIDENCIA DOCUMENTAL", "ONU", "UNODC", "CITACIÓN FORMAL", "DOCUMENTO")):
                    doc_img = str(broll_img) if broll_img and Path(broll_img).exists() else c_params.get("image_path")
                    card_res = self.web_renderer.render_visual_template(
                        template_name="document_evidence_split",
                        out_png=card_img_path,
                        params={
                            "headline": c_headline,
                            "excerpt": c_body or c_headline,
                            "institution": c_params.get("institution") or (c_badge if c_badge != "DATO CLAVE" else "ORGANISMO OFICIAL"),
                            "date_str": c_params.get("date_str") or "INFORME OFICIAL",
                            "highlight_phrase": c_params.get("highlight_phrase") or c_stat or "",
                            "image_path": doc_img,
                            "stat_value": c_stat or c_params.get("stat_value") or "",
                            "stat_label": c_params.get("stat_label") or "Métrica Clave",
                            "stat_value2": c_params.get("stat_value2") or "",
                            "stat_label2": c_params.get("stat_label2") or "",
                            "tag": c_badge or "EVIDENCIA DOCUMENTAL",
                            "presenter_name": c_params.get("presenter_name", "ANÁLISIS DOCUMENTAL"),
                            "layout_mode": "split" if not self.is_vertical else "card_only",
                            **c_params,
                        },
                        variant=c_variant,
                    )
                    if card_res and card_res.exists():
                        card_visual_type = "document_evidence_split"
                        safe_log(f"[SceneEngine] 📜 Pantalla Dividida Documental Platzi/Laje generada para escena {scene.scene_id}: {c_headline}")

                # 1. Mapa Geopolítico / Satelital Táctico GeoIntel (si aplica específicamente)
                elif c_template in ("map", "geointel_map") or any(k in c_badge for k in ("MAPA", "GEO", "GEOPOLÍTICA", "UBICACIÓN", "UBICACION")) or "mapa" in c_headline.lower():
                    bg_has_map = any("map" in str(getattr(b, "query", "")).lower() or "satellite" in str(getattr(b, "query", "")).lower() for b in getattr(scene, "visual_beats", [])) or "map" in str(scene.visual_query).lower() or "satellite" in str(scene.visual_query).lower()
                    if bg_has_map and self.is_vertical:
                        safe_log(f"[SceneEngine] 🌍 Metraje de fondo es mapa satelital completo; omitiendo tarjeta superpuesta para apreciar el mapa en 100% de la pantalla.")
                        card_img_path = None
                    else:
                        map_result = self.web_renderer.render_geointel_map_to_image(
                            location_title=c_headline,
                            country_name=c_stat or "ZONA DE INVESTIGACIÓN",
                            out_png=card_img_path,
                            coordinates_str="COORDENADAS SATELITALES",
                            notes=c_body,
                            badge=c_badge or "RECONOCIMIENTO GEOGRÁFICO",
                        )
                        if map_result and map_result.exists():
                            card_visual_type = "map"
                            safe_log(f"[SceneEngine] 🗺️ Mapa Geopolítico GeoIntel generado para escena {scene.scene_id}")
                        else:
                            card_img_path = None

                # 2. Texto editorial (Fallback final, sin badges)
                else:
                    self.web_renderer.render_visual_template(
                        template_name="text_card",
                        out_png=card_img_path,
                        params={
                            "headline": c_headline,
                            "body": c_body,
                            "source": c_params.get("source", ""),
                        },
                        variant=c_variant,
                    )
                    card_visual_type = "text_card"
                    safe_log(f"[SceneEngine] 📝 Tarjeta editorial generada para escena {scene.scene_id}")
            except Exception as _we:
                safe_log(f"[SceneEngine] Fallback a tarjeta editorial simplificada: {_we}")
                try:
                    self.web_renderer.render_visual_template(
                        template_name="text_card",
                        out_png=card_img_path,
                        params={
                            "headline": c_headline,
                            "body": c_body,
                            "source": c_params.get("source", ""),
                        },
                        variant=c_variant,
                    )
                    card_visual_type = "text_card"
                except Exception as _fe:
                    safe_log(f"[SceneEngine] Fallback final a CardRenderer: {_fe}")
                    card_obj = InfoCard(
                        card_id=f"sc_card_{scene.scene_id}",
                        headline=c_headline,
                        claim=c_body or c_headline,
                        search_query=c_headline,
                        body=c_body,
                        start_sec=0.8,
                        end_sec=max(3.0, duration - 0.5),
                        stat_value=c_stat,
                        verdict="supported",
                        kind="cifra" if c_stat else "dato",
                    )
                    self.card_renderer.render(card_obj, card_img_path)

            # Todas las cards usan el sistema editorial: sin badges, iconos ni pills.
            try:
                from core.editorial_cards import TEMPLATE_ALIASES as _EDIT_ALIASES
                _edit_kind = _EDIT_ALIASES.get(c_template, "text_card")
                if card_img_path and card_img_path.exists():
                    card_visual_type = "stat_counter" if _edit_kind == "data_hero" else "text_card"
            except Exception:
                pass

            # 2b. Count-up animado de la cifra principal (solo valores numéricos claros)
            if card_visual_type == "stat_counter" and c_stat:
                try:
                    from core.animated_stat_card import create_animated_stat_card
                    anim_out = scene_dir / f"card_{scene.scene_id}_anim.mov"
                    c_source = str(c_params.get("source") or "")
                    anim_res = await asyncio.to_thread(
                        create_animated_stat_card,
                        c_stat,
                        anim_out,
                        c_headline,
                        c_body if c_body != c_headline else "",
                        c_source,
                        self.fps,
                        0.9,
                    )
                    if anim_res:
                        animated_card_path = anim_res[0]
                        safe_log(f"[SceneEngine] 🔢 Count-up animado listo para escena {scene.scene_id}: {c_stat}")
                except Exception as _anim_err:
                    safe_log(f"[SceneEngine] Count-up omitido en escena {scene.scene_id}: {_anim_err}")

        # 3b. Preparar chips / pastillas referenciales dinámicas sincronizadas con el momento en que se mencionan
        chips_img_path = None
        chip_start_time = 0.8
        if getattr(scene, "chips", None) and scene.chips:
            # Chips/pastillas desactivados: solo se permiten cards y texto editorial.
            chips_img_path = None

        # 3c. Preparar Pop-up reactivo sincronizado si la escena tiene popups definidos
        popup_img_path = None
        popup_start_time = 1.2
        popups_list = getattr(scene, "popups", []) or []
        # Pop-ups tipo pastilla desactivados: el texto relevante ya lo aportan
        # las cards editoriales, los títulos cinéticos y las fechas.
        popups_list = []
        if popups_list and not card_img_path:
            p_data = popups_list[0] if isinstance(popups_list[0], dict) else {"text": str(popups_list[0])}
            p_txt = p_data.get("text", "").strip()
            p_kind = p_data.get("kind", "fact")
            p_trig = (p_data.get("trigger") or "").lower().strip()
            if p_txt:
                out_pop_path = scene_dir / f"popup_{scene.scene_id}.png"
                try:
                    popup_img_path = self.web_renderer.render_popup_to_image(
                        text=p_txt,
                        out_png=out_pop_path,
                        tag_label="CLAVE" if p_kind == "fact" else p_kind.upper(),
                        kind=p_kind,
                    )
                    safe_log(f"[SceneEngine] 💡 Micro Pop-up WebCardRenderer generado para escena {scene.scene_id}")
                except Exception as _wpe:
                    safe_log(f"[SceneEngine] Fallback a InfoCardRenderer para popup: {_wpe}")
                    try:
                        popup_img_path = self.card_renderer.render_info_popup(text=p_txt, kind=p_kind, out_path=out_pop_path)
                    except Exception as _ep:
                        safe_log(f"[SceneEngine] Error renderizando popup: {_ep}")
                        popup_img_path = None

                if p_trig and sentence_boundaries:
                    for s_st, _s_en, s_txt in sentence_boundaries:
                        if p_trig in s_txt.lower():
                            popup_start_time = max(0.6, round(s_st, 2))
                            break

        # 3d. Preparar Rótulo Broadcast Lower Third si no hay tarjeta Bento ni popup para contexto visual
        lower_third_img_path = None
        if not card_img_path and not popup_img_path and scene.type in ("video_reaction", "breaking_news", "avatar_cam") and duration >= 4.0:
            lt_tag = "NOTICIA EN VIVO" if scene.type == "breaking_news" else ("REACCIÓN EN VIVO" if scene.type == "video_reaction" else "EN VIVO")
            lt_sub = (scene.speech[:75].rsplit(" ", 1)[0] + "…") if len(scene.speech) > 75 else scene.speech
            out_lt_path = scene_dir / f"lower_third_{scene.scene_id}.png"
            try:
                lower_third_img_path = self.web_renderer.render_visual_template(
                    template_name="lower_third",
                    out_png=out_lt_path,
                    params={"headline": scene.name, "body": lt_sub, "tag": lt_tag},
                    variant="orange_noir",
                )
                safe_log(f"[SceneEngine] 📺 Rótulo Broadcast WebCardRenderer generado para escena {scene.scene_id}")
            except Exception as _wlt:
                safe_log(f"[SceneEngine] Fallback a Pillow para lower third: {_wlt}")
                try:
                    lower_third_img_path = self.card_renderer.render_broadcast_lower_third(
                        headline=scene.name,
                        subtitle=lt_sub,
                        tag=lt_tag,
                        out_path=out_lt_path,
                    )
                except Exception as exc_lt:
                    safe_log(f"[SceneEngine] Fallback lower third: {exc_lt}")
                    lower_third_img_path = None

        # 3e. Preparar Texto Libre Cinemático Flotante (sin card) si la escena es un Top, ranking o enumeración
        free_title_img_path = None
        free_title_blur_bg = False
        kinetic_word_paths = []
        free_data = getattr(scene, "free_title", None)
        # Exclusión mutua Fase 2: si la escena ya cuenta con tarjeta renderizada, suprimir free_title
        if card_img_path and card_img_path.exists():
            free_data = None
        elif not free_data and not card_img_path:
            name_low = scene.name.lower()
            m_top = re.search(r"(?:puesto|número|numero|top|#|factor|punto|clave)\s*(\d+)", name_low)
            if m_top:
                num_val = int(m_top.group(1))
                num_str = f"{num_val:02d}"
                clean_title = re.sub(r"(?i)^(?:puesto|número|numero|top|#|factor|punto|clave)\s*\d+[\s:.-]*", "", scene.name).strip()
                free_data = {
                    "number": num_str if num_val < 100 else str(num_val),
                    "title": clean_title or scene.name,
                    "tag": f"PUESTO {num_str} · RANKING" if ("top" in name_low or "puesto" in name_low) else f"HITO #{num_str}",
                    "subtitle": (scene.speech[:65].rsplit(" ", 1)[0] + "…") if len(scene.speech) > 65 else scene.speech,
                    "blur_bg": True,
                }

        kinetic_layered = False
        if free_data:
            out_free_path = scene_dir / f"free_title_{scene.scene_id}.png"
            kinetic_word_paths = []
            kinetic_layered = False
            try:
                free_title_img_path = self.web_renderer.render_free_kinetic_text_to_image(
                    main_title=free_data.get("title") or scene.name,
                    out_png=out_free_path,
                    number=free_data.get("number", ""),
                    tag=free_data.get("tag", ""),
                    subtitle=free_data.get("subtitle", ""),
                    highlight=free_data.get("highlight", ""),
                    accent_color=free_data.get("accent_color", "#ff9436"),
                )
                free_title_blur_bg = bool(free_data.get("blur_bg", True))
                safe_log(f"[SceneEngine] 🎬 Texto Libre Cinemático Flotante generado para escena {scene.scene_id}")
            except Exception as _fe:
                safe_log(f"[SceneEngine] Error generando texto libre cinemático: {_fe}")
                free_title_img_path = None

            # Tipografía cinética VIRAL: cada palabra como PNG bicolor gigante que
            # estalla en pantalla una a una (pop + rise) al ritmo de la locución.
            # Solo si Chromium funciona y el título tiene 1-4 palabras; el PNG
            # completo queda como fallback si la serie falla.
            if free_title_img_path is not None or free_data.get("title"):
                try:
                    from core.web_card_renderer import KINETIC_DUOTONES
                    duo = KINETIC_DUOTONES[int(scene.scene_id) % len(KINETIC_DUOTONES)]
                    from core.kinetic_titles import TITLE_STYLES
                    _tstyle = free_data.get("style")
                    if _tstyle not in TITLE_STYLES:
                        _tstyle = TITLE_STYLES[int(scene.scene_id) % len(TITLE_STYLES)]
                    _eyebrow = " · ".join([x for x in (str(free_data.get("number", "") or ""), str(free_data.get("tag", "") or "")) if x])
                    try:
                        kinetic_word_paths = self.title_renderer.render_title_layers(
                            title=free_data.get("title") or scene.name,
                            out_dir=scene_dir / f"kt_{scene.scene_id}",
                            style=_tstyle,
                            duo=duo,
                            eyebrow=_eyebrow,
                            canvas=(self.W, self.H),
                            max_words=4,
                        )
                        kinetic_layered = bool(kinetic_word_paths)
                    except Exception:
                        kinetic_word_paths = []
                    if not kinetic_word_paths:
                        kinetic_word_paths = self.web_renderer.render_kinetic_word_series(
                            title=free_data.get("title") or scene.name,
                            out_dir=scene_dir / f"kinetic_{scene.scene_id}",
                            duo=duo,
                            max_words=4,
                        )
                    if kinetic_word_paths:
                        safe_log(f"[SceneEngine] ⚡ {len(kinetic_word_paths)} palabras cinéticas bicolor listas (escena {scene.scene_id})")
                except Exception as _ke:
                    kinetic_word_paths = []

        # 4. Generar subtítulos para la escena
                # 3f. Rotulos flotantes cinematicos de palabras clave y anos (enfasis sin cards)
        keyword_callout_overlays: List[Dict[str, Any]] = []
        try:
            from core.kinetic_titles import KEYWORD_DUOTONES
            kw_duo = KEYWORD_DUOTONES[int(scene.scene_id) % len(KEYWORD_DUOTONES)]

            found_years = self.title_renderer.find_years(speech_text)
            found_kws = self.title_renderer.find_keywords(
                speech=speech_text,
                scene_name=scene.name,
                card_headline=getattr(scene.card, "headline", "") or ""
            )

            candidates = []
            for y_val, y_frac in found_years[:1]:
                candidates.append({"type": "year", "text": y_val, "frac": y_frac, "tag": "ANO HISTORICO"})
            for kw_item in found_kws[:2]:
                candidates.append({
                    "type": "keyword",
                    "text": kw_item["text"],
                    "frac": kw_item["frac"],
                    "tag": kw_item["tag"],
                    "style": kw_item.get("style", "badge_glow")
                })

            candidates.sort(key=lambda c: c["frac"])
            candidates = candidates[:2]

            for idx_c, cand in enumerate(candidates):
                kw_png = scene_dir / f"kw_{scene.scene_id}_{idx_c}.png"
                rendered_path = None
                if cand["type"] == "year":
                    res_y = self.title_renderer.render_year_callout(cand["text"], kw_png, style_idx=int(scene.scene_id) + idx_c)
                    if res_y:
                        rendered_path = res_y[0]
                else:
                    rendered_path = self.title_renderer.render_keyword_callout(
                        text=cand["text"],
                        out_png=kw_png,
                        style=cand.get("style", "badge_glow"),
                        tag=cand.get("tag", "CLAVE"),
                        duo=kw_duo,
                    )
                if rendered_path and rendered_path.exists():
                    keyword_callout_overlays.append({
                        "path": rendered_path,
                        "frac": cand["frac"],
                        "text": cand["text"],
                    })
        except Exception as _kwe:
            safe_log(f"[SceneEngine] Fallback en palabras clave flotantes: {_kwe}")

        # Remotion AI: Si no se renderizó antes, evaluar si la escena se beneficia de uno
        if not ai_remotion_mov:
            has_primary_foreground = bool(
                (card_img_path and card_img_path.exists())
                or (free_title_img_path and free_title_img_path.exists())
            )
            if getattr(self, "ai_remotion", None) and duration >= 3.0 and not has_primary_foreground:
                try:
                    ai_remotion_mov = await self.ai_remotion.render_ai_overlay(
                        scene_name=scene.name,
                        speech_text=speech_text,
                        duration=duration,
                        out_dir=scene_dir,
                        vertical=self.is_vertical,
                        theme_spec=getattr(self, "style_spec", None),
                        card=scene.card,
                        intent=visual_intent,
                    )
                except Exception as _re_err:
                    safe_log(f"[SceneEngine] Remotion AI overlay omitido: {_re_err}")

        srt_path = self._generate_scene_subtitles(speech_text, duration, scene_dir, sentence_boundaries, word_times)

        # 4b. Detección inteligente de personas/protagonistas mencionados para Spotlight con foto
        person_spotlight_overlays: List[Dict[str, Any]] = []
        try:
            from core.smart_media_curator import SmartMediaCurator
            from core.web_media import WikiMediaClient
            mentions = SmartMediaCurator.detect_person_mentions(
                speech_text=speech_text or "",
                sentence_boundaries=sentence_boundaries,
                scene_duration=duration,
            )
            if mentions:
                portraits_dir = self.workdir / "portraits"
                portraits_dir.mkdir(parents=True, exist_ok=True)
                wiki_client = WikiMediaClient()

                for m_idx, m in enumerate(mentions):
                    p_slug = re.sub(r'[^a-z0-9]+', '_', m['name'].lower()).strip('_')
                    portrait_p = portraits_dir / f"{p_slug}.jpg"
                    if not portrait_p.exists() or portrait_p.stat().st_size < 500:
                        try:
                            w_res = await wiki_client.search(m.get("query_wiki") or m["name"])
                            if w_res and w_res.image_url:
                                await wiki_client.download_image(w_res.image_url, portrait_p)
                        except Exception as _we:
                            safe_log(f"[SceneEngine] Aviso buscando retrato wiki para {m['name']}: {_we}")

                    spotlight_png = scene_dir / f"person_spotlight_{scene.scene_id}_{m_idx}_{p_slug}.png"
                    tpl_params = {
                        "name": m["name"],
                        "role": m.get("role") or "Figura Pública",
                        "image_path": str(portrait_p) if (portrait_p.exists() and portrait_p.stat().st_size > 500) else None,
                        "tag": "PROTAGONISTA" if m_idx == 0 else "PERSONAJE",
                    }
                    rendered_p = self.web_renderer.render_visual_template(
                        template_name="person_spotlight",
                        out_png=spotlight_png,
                        params=tpl_params,
                        variant=getattr(scene, "theme_variant", "orange_noir") or "orange_noir",
                    )
                    if rendered_p and rendered_p.exists():
                        person_spotlight_overlays.append({
                            "png_path": rendered_p,
                            "start_time": m["start_time"],
                            "duration": m["duration"],
                            "name": m["name"],
                        })
                        safe_log(f"[SceneEngine] 👤 Spotlight con foto generado para '{m['name']}' (t={m['start_time']:.1f}s - {m['start_time'] + m['duration']:.1f}s)")
        except Exception as _pe:
            safe_log(f"[SceneEngine] Aviso en detección de personas: {_pe}")

        if document_assets and (card_img_path or animated_card_path):
            card_img_path = None
            animated_card_path = None
            safe_log(f"[SceneEngine] 📄 Escena {scene.scene_id}: card suprimida para no tapar el documento.")

        # 5. Montar filtergraph de FFmpeg específico para el layout de la escena
        inputs: List[str] = []
        filter_parts: List[str] = []
        num_in = 0

        # Montaje secuencial dinámico de todos los clips de fondo (bg_clips)
        if bg_clips:
            if len(bg_clips) == 1:
                first_bg_path, _ = bg_clips[0]
                first_is_image = first_bg_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                if first_is_image and str(first_bg_path) in document_assets:
                    # Documento/diagrama: se ve completo sobre un fondo desenfocado (nunca recortado).
                    inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(first_bg_path)])
                    filter_parts.append(
                        f"[0:v]split=2[dbg][dfg];"
                        f"[dbg]scale={self.W}:{self.H}:force_original_aspect_ratio=increase,crop={self.W}:{self.H},boxblur=28:2[dbg2];"
                        f"[dfg]scale={self.W}:{self.H}:force_original_aspect_ratio=decrease[dfg2];"
                        f"[dbg2][dfg2]overlay=x=(W-w)/2:y=(H-h)/2,setsar=1,format=yuv420p[v_bg0]"
                    )
                elif first_is_image:
                    inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(first_bg_path)])
                    kb_frames = max(1, int(float(dur_str) * self.fps))
                    z_step = max(0.0003, round(0.22 / kb_frames, 5))
                    pan_step = max(0.2, round(25.0 / kb_frames, 2))
                    kb_mode = int(scene.scene_id) % 4
                    if kb_mode == 0:
                        kb_filter = f"zoompan=z='min(zoom+{z_step},1.22)':x='iw/2-(iw/zoom/2)+{max(1, int(self.W*0.02))}*on/{kb_frames}':y='ih/2-(ih/zoom/2)':d={kb_frames}:s={self.W}x{self.H}:fps={self.fps}"
                    elif kb_mode == 1:
                        kb_filter = f"zoompan=z='if(lte(zoom,1.02),1.02,max(1.02,1.22-{z_step}*on))':x='iw/2-(iw/zoom/2)-{max(1, int(self.W*0.02))}*on/{kb_frames}':y='ih/2-(ih/zoom/2)':d={kb_frames}:s={self.W}x{self.H}:fps={self.fps}"
                    elif kb_mode == 2:
                        kb_filter = f"zoompan=z=1.08:x='min(x+{pan_step},iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={kb_frames}:s={self.W}x{self.H}:fps={self.fps}"
                    else:
                        kb_filter = f"zoompan=z=1.08:x='max(0,iw-iw/zoom-{pan_step}*on)':y='ih/2-(ih/zoom/2)':d={kb_frames}:s={self.W}x{self.H}:fps={self.fps}"
                    filter_parts.append(
                        f"[0:v]scale={int(self.W * 1.14)}:{int(self.H * 1.14)}:force_original_aspect_ratio=increase,"
                        f"crop={int(self.W * 1.14)}:{int(self.H * 1.14)},"
                        f"{kb_filter},"
                        f"setsar=1[v_bg0]"
                    )
                else:
                    inputs.extend(["-t", dur_str, "-r", str(self.fps), "-i", str(first_bg_path)])
                    cam_x = f"'(in_w-out_w)/2 + 35*(t/{dur_str})'"
                    cam_y = f"'(in_h-out_h)/2 + 18*(t/{dur_str})'"
                    filter_parts.append(
                        f"[0:v]scale={int(self.W * 1.08)}:{int(self.H * 1.08)}:force_original_aspect_ratio=increase,"
                        f"crop={self.W}:{self.H}:x={cam_x}:y={cam_y},setsar=1,"
                        f"tpad=stop_mode=clone:stop_duration={dur_str},trim=duration={dur_str},setpts=PTS-STARTPTS[v_bg0]"
                    )
                cur_v = "v_bg0"
                num_in += 1
            else:
                # Múltiples B-Rolls: Concat lineal sin frame buffering ni desincronización
                seg_cuts = [max(0.0, cut) for _, cut in bg_clips]
                seg_cuts[0] = 0.0
                seg_tags = []
                for i, (clip_p, _) in enumerate(bg_clips):
                    t_start = seg_cuts[i]
                    t_end = seg_cuts[i + 1] if (i + 1 < len(bg_clips)) else duration
                    seg_dur = max(0.5, round(t_end - t_start, 2))
                    seg_dur_str = f"{seg_dur:.2f}"
                    is_img = clip_p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                    clip_in_idx = num_in
                    num_in += 1
                    seg_tag = f"v_seg_{i}"
                    seg_tags.append(f"[{seg_tag}]")

                    if is_img:
                        inputs.extend(["-loop", "1", "-t", seg_dur_str, "-r", str(self.fps), "-i", str(clip_p)])
                        if str(clip_p) in document_assets:
                            filter_parts.append(
                                f"[{clip_in_idx}:v]split=2[dbg{i}][dfg{i}];"
                                f"[dbg{i}]scale={self.W}:{self.H}:force_original_aspect_ratio=increase,crop={self.W}:{self.H},boxblur=28:2[dbg2_{i}];"
                                f"[dfg{i}]scale={self.W}:{self.H}:force_original_aspect_ratio=decrease[dfg2_{i}];"
                                f"[dbg2_{i}][dfg2_{i}]overlay=x=(W-w)/2:y=(H-h)/2,setsar=1,format=yuv420p,"
                                f"trim=duration={seg_dur_str},setpts=PTS-STARTPTS[{seg_tag}]"
                            )
                        else:
                            kb_frames_sub = max(1, int(seg_dur * self.fps))
                            z_step_sub = max(0.0003, round(0.22 / kb_frames_sub, 5))
                            pan_step = max(0.2, round(25.0 / kb_frames_sub, 2))
                            kb_mode = (int(scene.scene_id) + i) % 4
                            if kb_mode == 0:
                                kb_filter = f"zoompan=z='min(zoom+{z_step_sub},1.22)':x='iw/2-(iw/zoom/2)+{max(1, int(self.W*0.02))}*on/{kb_frames_sub}':y='ih/2-(ih/zoom/2)':d={kb_frames_sub}:s={self.W}x{self.H}:fps={self.fps}"
                            elif kb_mode == 1:
                                kb_filter = f"zoompan=z='if(lte(zoom,1.02),1.02,max(1.02,1.22-{z_step_sub}*on))':x='iw/2-(iw/zoom/2)-{max(1, int(self.W*0.02))}*on/{kb_frames_sub}':y='ih/2-(ih/zoom/2)':d={kb_frames_sub}:s={self.W}x{self.H}:fps={self.fps}"
                            elif kb_mode == 2:
                                kb_filter = f"zoompan=z=1.08:x='min(x+{pan_step},iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={kb_frames_sub}:s={self.W}x{self.H}:fps={self.fps}"
                            else:
                                kb_filter = f"zoompan=z=1.08:x='max(0,iw-iw/zoom-{pan_step}*on)':y='ih/2-(ih/zoom/2)':d={kb_frames_sub}:s={self.W}x{self.H}:fps={self.fps}"

                            filter_parts.append(
                                f"[{clip_in_idx}:v]scale={int(self.W * 1.14)}:{int(self.H * 1.14)}:force_original_aspect_ratio=increase,"
                                f"crop={int(self.W * 1.14)}:{int(self.H * 1.14)},"
                                f"{kb_filter},"
                                f"setsar=1,trim=duration={seg_dur_str},setpts=PTS-STARTPTS[{seg_tag}]"
                            )
                    else:
                        is_soundbite_seg = (
                            is_soundbite_scene
                            and clip_audio_candidate
                            and clip_p == clip_audio_candidate
                            and abs(t_start - round(tts_duration, 2)) < 0.35
                            and soundbite_offset > 0.05
                        )
                        # Offset temporal dinámico y reencuadre punch-in para cortes sucesivos del mismo archivo
                        same_file_prev = (i > 0 and bg_clips[i - 1][0] == clip_p)
                        v_offset = (i * 4.5) if (same_file_prev and not is_soundbite_seg) else 0.0
                        if is_soundbite_seg:
                            inputs.extend(["-ss", f"{soundbite_offset:.3f}", "-t", seg_dur_str, "-r", str(self.fps), "-i", str(clip_p)])
                        elif v_offset > 0.1:
                            inputs.extend(["-ss", f"{v_offset:.2f}", "-t", seg_dur_str, "-r", str(self.fps), "-i", str(clip_p)])
                        else:
                            inputs.extend(["-t", seg_dur_str, "-r", str(self.fps), "-i", str(clip_p)])

                        # Movimiento cinemático continuo y alternancia de cámaras para cada plano:
                        cam_mode = i % 4
                        if cam_mode == 0:
                            scale_factor = 1.08
                            cam_x = f"'(in_w-out_w)/2 + 30*(t/{seg_dur_str})'"
                            cam_y = f"'(in_h-out_h)/2'"
                        elif cam_mode == 1:
                            scale_factor = 1.08
                            cam_x = f"'(in_w-out_w)/2 - 30*(t/{seg_dur_str})'"
                            cam_y = f"'(in_h-out_h)/2 + 15*(t/{seg_dur_str})'"
                        elif cam_mode == 2:
                            scale_factor = 1.15  # Plano cerrado / punch-in dramático
                            cam_x = f"'(in_w-out_w)/2'"
                            cam_y = f"'(in_h-out_h)/2 - 15*(t/{seg_dur_str})'"
                        else:
                            scale_factor = 1.10
                            cam_x = f"'(in_w-out_w)/2 + 15*(t/{seg_dur_str})'"
                            cam_y = f"'(in_h-out_h)/2 + 20*(t/{seg_dur_str})'"

                        # Corte seco profesional: el cambio de camara/encuadre ya da el golpe
                        # visual. Fundir a negro en cada corte apaga la energia del montaje.
                        trans_fade = ""
                        filter_parts.append(
                            f"[{clip_in_idx}:v]scale={int(self.W * scale_factor)}:{int(self.H * scale_factor)}:force_original_aspect_ratio=increase,"
                            f"crop={self.W}:{self.H}:x={cam_x}:y={cam_y},setsar=1{trans_fade},"
                            f"tpad=stop_mode=clone:stop_duration={seg_dur_str},trim=duration={seg_dur_str},setpts=PTS-STARTPTS[{seg_tag}]"
                        )
                all_segs = "".join(seg_tags)
                filter_parts.append(f"{all_segs}concat=n={len(bg_clips)}:v=1:a=0[v_bg_seq]")
                cur_v = "v_bg_seq"
        else:
            inputs.extend(["-f", "lavfi", "-i", f"color=c=0x0a0a0c:s={self.W}x{self.H}:d={dur_str}:r=25"])
            filter_parts.append("[0:v]format=yuva420p[v_bg0]")
            cur_v = "v_bg0"
            num_in += 1

        # Superposicion sutil de microelementos cineticos de fondo (particulas y acentos HUD)
        if motion_overlay_path and motion_overlay_path.exists():
            inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(motion_overlay_path)])
            m_idx = num_in
            num_in += 1
            filter_parts.append(
                f"[{m_idx}:v]format=rgba,fade=t=in:st=0.3:d=0.35:alpha=1,fade=t=out:st={duration-0.35:.2f}:d=0.35:alpha=1[motion_in];"
                f"[{cur_v}][motion_in]overlay=x='8*sin(t*0.9)':y='6*cos(t*0.7)':enable='between(t,0.3,{duration-0.2:.2f})'[v_bg_motion]"
            )
            cur_v = "v_bg_motion"

        # Desenfoque temporal dinámico: si hay tarjeta o texto libre cinemático, desenfocar durante su aparición
        # Duración de la tarjeta adaptada por importancia conceptual y tiempo de lectura:
        # - Elementos clave (mapas, comparativas versus, citas/pruebas forenses, prensa, cifras récord):
        #   Permanecen en pantalla de 5.5s a 8.5s (o proporcional en escenas largas) para que el espectador pueda asimilar y leer.
        # - Elementos ligeros (chips de autoría, sellos rápidos): 3.0s a 4.5s.
        if card_img_path and card_img_path.exists():
            c_hl = scene.card.get("headline") if isinstance(scene.card, dict) else getattr(scene.card, "headline", "")
            c_bd = scene.card.get("body") if isinstance(scene.card, dict) else getattr(scene.card, "body", "")
            c_bg = str(scene.card.get("badge") if isinstance(scene.card, dict) else getattr(scene.card, "badge", "") or "").upper()
            c_tmpl = str(scene.card.get("template") if isinstance(scene.card, dict) else getattr(scene.card, "template", "") or "").lower()
            card_words = len(f"{c_hl or ''} {c_bd or ''}".split())

            # Detectar si es un elemento visual de alta relevancia temática, documental o gráfica
            is_important_visual = (
                card_visual_type in ("document_evidence_split", "versus_split", "quote_evidence", "newspaper_clipping", "social_post", "stat_counter", "alert_banner")
                or c_tmpl in ("document_evidence_split", "split_evidence", "platzi_evidence", "map", "versus_split", "quote_evidence", "newspaper_clipping", "social_post", "stat_counter", "alert_banner", "timeline_milestone")
                or any(k in c_bg for k in ("MAPA", "GEO", "VERSUS", "COMPARATIVA", "EVIDENCIA", "PRUEBA", "OFICIAL", "DESCLASIFICADO", "ARCHIVO", "DOCUMENTO", "INFORME", "RÉCORD", "RECORD", "CIFRA", "CRÍTICO", "CRITICO", "ALERTA"))
                or (visual_intent and visual_intent.intent_type in (
                    VisualIntentType.GEO_LOCATION,
                    VisualIntentType.VERSUS_COMPARISON,
                    VisualIntentType.HISTORICAL_EVENT,
                    VisualIntentType.STAT_NUMBER,
                    VisualIntentType.COMPLEX_CONCEPT
                ))
                or getattr(scene, "case_frame", None) is not None
            )

            if is_important_visual:
                reading_calc = max(5.5, 0.32 * card_words + 2.5)
                ideal_calc = max(reading_calc, smart_card_dur or 6.5)
                max_card_cap = 8.5 if duration < 25.0 else min(10.5, duration * 0.40)
            else:
                reading_calc = max(3.0, 0.22 * card_words + 1.8)
                ideal_calc = min(reading_calc, smart_card_dur or 4.2)
                max_card_cap = 5.0

            # Garantizar que el elemento se retire limpiamente antes del corte de escena (al menos 0.7s de margen)
            max_allowed = max(2.2, duration - card_start_time - 0.7)
            card_duration = max(2.2, min(ideal_calc, min(max_card_cap, max_allowed)))
        else:
            card_duration = 0.0
        # Duración del texto libre: con serie cinética la ventana cubre el
        # estallido escalonado de las palabras (0.32s por palabra) + 1.6s de
        # lectura final. Sin serie, el comportamiento clásico.
        if free_title_blur_bg and (free_title_img_path or kinetic_word_paths):
            if kinetic_word_paths:
                free_title_dur = max(2.4, min(4.6, 0.32 * len(kinetic_word_paths) + 1.6))
            else:
                free_title_dur = min(3.5, max(2.2, duration - 0.8))
        else:
            free_title_dur = 0.0

        if is_scene_documentary or getattr(self, "pure_footage", False):
            # En documentales / geopolítica, metraje de archivo 4K a 100% brillo y claridad sin velos oscuros
            filter_parts.append(f"[{cur_v}]copy[v_dim]")
        elif card_duration > 0:
            if card_visual_type in ("verdict_badge", "tech_card"):
                # Badges y tech cards flotan limpiamente sobre el video nítido sin desenfoque pesado
                filter_parts.append(f"[{cur_v}]drawbox=x=0:y=0:w={self.W}:h={self.H}:color=black@0.10:t=fill[v_dim]")
            elif card_visual_type in ("document_evidence_split", "quote_evidence", "newspaper_clipping"):
                # Para documentos oficiales y prensa editorial: atenuación cinematográfica sutil
                filter_parts.append(
                    f"[{cur_v}]drawbox=x=0:y=0:w={self.W}:h={self.H}:color=black@0.35:t=fill:enable='between(t,{card_start_time:.2f},{card_start_time + card_duration:.2f})'[v_dim]"
                )
            else:
                # Bento Box / Cita / Mapa / Stat Counter
                filter_parts.append(
                    f"[{cur_v}]drawbox=x=0:y=0:w={self.W}:h={self.H}:color=black@0.25:t=fill:enable='between(t,{card_start_time:.2f},{card_start_time + card_duration:.2f})'[v_dim]"
                )
        elif free_title_dur > 0:
            filter_parts.append(f"[{cur_v}]drawbox=x=0:y=0:w={self.W}:h={self.H}:color=black@0.25:t=fill:enable='between(t,0.4,{0.4 + free_title_dur:.2f})'[v_dim]")
        else:
            filter_parts.append(f"[{cur_v}]copy[v_dim]")
        cur_v = "v_dim"

        # Avatar según layout de cámara
        av_file = scene_avatar_clip if (scene_avatar_clip and scene_avatar_clip.exists()) else (avatar_clip or avatar_webm)
        if av_file and Path(av_file).exists():
            # SIN '-r' de entrada: el clip de avatar nace a 24 fps y su envolvente de
            # lip-sync está construida a 24 fps. Re-tiempearlo a 25 (-r 25) adelantaba
            # la boca ~4% y hacía que el loop reiniciara en el 96% de cada escena.
            # A fps nativos, el clip dura exactamente lo que duró el audio y el loop
            # reinicia justo al terminar la escena.
            inputs.extend(["-t", dur_str, "-stream_loop", "-1", "-i", str(av_file)])
            av_idx = num_in
            num_in += 1

            # REGLA AUDIOVISUAL (FASES 4 Y 5): ROL DEL AVATAR Y APERTURA DINÁMICA
            # El avatar actúa como presentador/narrador visual secundario.
            # En la apertura (escena 1), el video comienza mostrando INFORMACIÓN VISUAL RELEVANTE desde t=0.
            # El avatar NUNCA monopoliza el centro de la pantalla al inicio; entra suave en PIP a los ~2.2s
            # o se mantiene en esquina PIP para no tapar el gancho documental ni la tipografía cinética.
            is_opening = (int(getattr(scene, "scene_id", 1)) == 1)
            cam = str(getattr(scene, "camera", "pip_corner") or "pip_corner").lower().strip()
            sc_type = str(getattr(scene, "type", "video_reaction") or "video_reaction").lower().strip()

            if self.is_anime:
                # Avatar discreto y pequeño en esquina inferior (sin estorbar el combate ni los personajes del anime)
                av_w_pip = int(self.W * (0.11 if not self.is_vertical else 0.16))
                av_x_pip = int(self.W - av_w_pip - 20)
                av_y_pip = int(self.H - av_w_pip - (25 if not self.is_vertical else 55))
            else:
                av_w_pip = int(self.W * (0.24 if not self.is_vertical else 0.36))
                av_x_pip = int(self.W - av_w_pip - (40 if not self.is_vertical else 26))
                av_y_pip = int(self.H - av_w_pip - (40 if not self.is_vertical else 96))

            cam_type = str(getattr(scene, "camera", "voice_over") or "voice_over").lower().strip()
            sc_type = str(getattr(scene, "type", "voice_over") or "voice_over").lower().strip()
            is_voice_over_scene = (
                cam_type in ("voice_over", "none", "hidden")
                or sc_type in ("voice_over", "document_evidence", "evidence_document")
                or not getattr(self, "enable_avatar", True)
            )

            if is_voice_over_scene:
                # Escena puramente visual: el avatar NO se superpone, pantalla completa limpia para el metraje/datos
                safe_log(f"[SceneEngine] 🎙️ Escena {scene.scene_id}: Foco visual completo ('{cam_type}'). Pantalla limpia sin avatar.")

            elif self.is_anime:
                # En anime: el avatar SIEMPRE sale pequeño abajo en esquina PIP discreta, jamás tapando el centro
                filter_parts.append(
                    f"[{av_idx}:v]scale={av_w_pip}:{av_w_pip},format=rgba[avatar];"
                    f"[{cur_v}][avatar]overlay={av_x_pip}:{av_y_pip}:eof_action=pass[v_av]"
                )
                cur_v = "v_av"
                safe_log(f"[SceneEngine] 🎬 Avatar Anime en PIP inferior discreto ({av_w_pip}x{av_w_pip}) en escena {scene.scene_id}.")

            elif is_opening or cam == "pip_delayed":
                # APERTURA DINÁMICA: Los primeros 2.0s a 2.5s están dedicados 100% al impacto visual
                # (video documental de fondo, kinetic typography o tarjeta). El avatar entra suavemente
                # en recuadro PIP en la esquina inferior derecha para apoyar la narración.
                delay_t = min(2.5, max(1.8, round(duration * 0.22, 2))) if duration >= 5.0 else 1.2
                filter_parts.append(
                    f"[{av_idx}:v]scale={av_w_pip}:{av_w_pip},format=rgba,"
                    f"fade=t=in:st={delay_t:.2f}:d=0.35:alpha=1[av_pip_delayed];"
                    f"[{cur_v}][av_pip_delayed]overlay={av_x_pip}:{av_y_pip}:enable='gte(t,{delay_t:.2f})':eof_action=pass[v_av]"
                )
                cur_v = "v_av"
                safe_log(f"[SceneEngine] 🎬 Apertura dinámica activa en escena {scene.scene_id}: Avatar entra en PIP a los {delay_t:.1f}s.")

            elif cam == "split_screen" or card_visual_type == "document_evidence_split":
                # MODO PANTALLA DIVIDIDA PLATZI / AGUSTÍN LAJE:
                # El presentador se ubica en el pod vertical izquierdo alineado con la plantilla
                if not self.is_vertical:
                    av_w_split = 510
                    av_h_split = 740
                    av_x_split = 65
                    av_y_split = 135
                    filter_parts.append(
                        f"[{av_idx}:v]scale={av_w_split}:{av_h_split}:force_original_aspect_ratio=increase,"
                        f"crop={av_w_split}:{av_h_split},format=rgba[avatar_split];"
                        f"[{cur_v}][avatar_split]overlay={av_x_split}:{av_y_split}:eof_action=pass[v_av]"
                    )
                    cur_v = "v_av"
                    safe_log(f"[SceneEngine] 🎬 Pantalla dividida activa en escena {scene.scene_id}: Avatar en Pod izquierdo (510x740).")
                else:
                    # En formato vertical, presentador centrado en tercio superior
                    av_w_split = int(self.W * 0.88)
                    av_h_split = int(self.H * 0.36)
                    av_x_split = int((self.W - av_w_split) / 2)
                    av_y_split = 80
                    filter_parts.append(
                        f"[{av_idx}:v]scale={av_w_split}:{av_h_split}:force_original_aspect_ratio=increase,"
                        f"crop={av_w_split}:{av_h_split},format=rgba[avatar_split];"
                        f"[{cur_v}][avatar_split]overlay={av_x_split}:{av_y_split}:eof_action=pass[v_av]"
                    )
                    cur_v = "v_av"

            elif cam == "hero_center" and not is_opening and not (card_img_path and card_img_path.exists()):
                # Solo permitido en escenas intermedias/finales sin tarjeta que bloquee el centro
                av_w_hero = int(self.W * (0.50 if not self.is_vertical else 0.65))
                av_x_hero = int((self.W - av_w_hero) / 2)
                av_y_hero = int(self.H - av_w_hero + 30)
                filter_parts.append(
                    f"[{av_idx}:v]scale={av_w_hero}:{av_w_hero},format=rgba[avatar];"
                    f"[{cur_v}][avatar]overlay={av_x_hero}:{av_y_hero}:eof_action=pass[v_av]"
                )
                cur_v = "v_av"

            else:
                # Comportamiento estándar ergonómico: Presentador en recuadro PIP en la esquina inferior derecha
                filter_parts.append(
                    f"[{av_idx}:v]scale={av_w_pip}:{av_w_pip},format=rgba[avatar];"
                    f"[{cur_v}][avatar]overlay={av_x_pip}:{av_y_pip}:eof_action=pass[v_av]"
                )
                cur_v = "v_av"

        # ── Ventana del overlay Remotion (cifra animada) ──
        # Regla de limpieza: solo UNA cifra/dato a la vez en pantalla. Mientras el overlay
        # Remotion está activo se suprimen popups, lower third, años flotantes y rótulos con números.
        remo_active = bool(ai_remotion_mov and ai_remotion_mov.exists() and not (card_img_path and card_img_path.exists()))
        remo_start, remo_end = 0.0, 0.0
        if remo_active:
            remo_len = min(duration, 3.8)
            remo_start = max(0.3, min(float(card_start_time or 0.5), max(0.3, duration - remo_len - 0.2)))
            remo_end = min(duration - 0.1, remo_start + remo_len)
            popup_img_path = None
            lower_third_img_path = None

        # Overlay adicional según tipo de escena: Texto Libre Cinemático o Tarjeta Bento
        if kinetic_word_paths and not (ai_remotion_mov and ai_remotion_mov.exists()):
            # ── TIPOGRAFÍA CINÉTICA VIRAL (palabra a palabra) ──
            # Cada palabra estalla en pantalla con fade + rise (ease-out cúbico)
            # escalonadas 0.32s, apiladas verticalmente como bloque central. La
            # serie completa respira junta y se funde a la vez al terminar.
            n_words = len(kinetic_word_paths)
            stagger = 0.32
            ft_start = 0.4
            ft_end = min(duration - 0.3, ft_start + (n_words - 1) * stagger + 1.7)
            for i_w, word_path in enumerate(kinetic_word_paths):
                inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(word_path)])
                w_idx = num_in
                num_in += 1
                st = ft_start + i_w * stagger
                # PNG a 2x: reducir al tamaño objetivo (palabra ~200px de alto en pantalla)
                _sc = "" if kinetic_layered else "scale=iw*0.5:ih*0.5,"
                filter_parts.append(
                    f"[{w_idx}:v]{_sc}format=rgba,"
                    f"fade=t=in:st={st:.2f}:d=0.20:alpha=1,"
                    f"fade=t=out:st={ft_end - 0.35:.2f}:d=0.35:alpha=1[kw{i_w}_a]"
                )
                # Pop con rise: entra subiendo 34px con easing cúbico y se apila
                # centrada como bloque (offset vertical por índice de palabra).
                pop_calc = f"min(max((t-{st:.2f})/0.30\\,0)\\,1)"
                row_off = (i_w - (n_words - 1) / 2.0)
                if kinetic_layered:
                    y_expr = f"34*(1-pow({pop_calc}\\,3))"
                    _kx = "0"
                else:
                    y_expr = f"(H-h)/2 + {row_off:.2f}*(h+14) + 34*(1-pow({pop_calc}\\,3))"
                    _kx = "(W-w)/2"
                filter_parts.append(
                    f"[{cur_v}][kw{i_w}_a]overlay=x='{_kx}':y='{y_expr}':"
                    f"enable='between(t,{st:.2f},{ft_end:.2f})'[v_kw{i_w}]"
                )
                cur_v = f"v_kw{i_w}"

        elif free_title_img_path and free_title_img_path.exists():
            inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(free_title_img_path)])
            ft_idx = num_in
            num_in += 1
            ft_end = 0.4 + free_title_dur
            ft_fo = max(0.4, ft_end - 0.35)
            # Entrada con fade in 0.25s + fade out suave 0.35s
            filter_parts.append(
                f"[{ft_idx}:v]format=rgba,fade=t=in:st=0.4:d=0.25:alpha=1,fade=t=out:st={ft_fo:.2f}:d=0.35:alpha=1[ft_animated]"
            )
            # Entrada con movimiento cinemático flotante (rise suave de 24px hacia el centro)
            ft_calc = f"min(max((t-0.4)/0.35\\,0)\\,1)"
            ft_y_expr = f"(H-h)/2 + 24*(1-pow({ft_calc}\\,3))"
            filter_parts.append(
                f"[{cur_v}][ft_animated]overlay=x='(W-w)/2':y='{ft_y_expr}':enable='between(t,0.4,{ft_end:.2f})'[v_ft]"
            )
            cur_v = "v_ft"

        elif (card_img_path and card_img_path.exists()) or animated_card_path:
            if animated_card_path:
                inputs.extend(["-i", str(animated_card_path)])
            else:
                inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(card_img_path)])
            c_idx = num_in
            num_in += 1
            card_end = card_start_time + card_duration
            fo_start = max(card_start_time, card_end - 0.35)

            if card_visual_type == "verdict_badge":
                # Distintivo viral inclinado: Spring Bounce elástico (overshoot) + respiración flotante viva
                # Escala 0.65 -> 1.03 -> 1.00 en 0.28s
                bounce_calc = f"min(max((t-{card_start_time:.2f})/0.28\\,0)\\,1)"
                scale_expr = f"iw*min(1.0\\, 0.65 + 0.38*sin({bounce_calc}*1.9))"
                filter_parts.append(
                    f"[{c_idx}:v]scale=eval=frame:w='{scale_expr}':h=-2,format=rgba,"
                    f"fade=t=in:st={card_start_time:.2f}:d=0.18:alpha=1,fade=t=out:st={fo_start:.2f}:d=0.35:alpha=1[card_animated]"
                )
                ease_y = f"((H-h)/2) - 40"
                filter_parts.append(f"[{cur_v}][card_animated]overlay=x='(W-w)/2':y='{ease_y}':enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                cur_v = "v_card"

            elif card_visual_type == "tech_card":
                # Tarjeta técnica moderna: Flotando en el tercio superior con deslizamiento suave y oscilación sutil
                top_y = int(self.H * 0.16) if self.is_vertical else int(self.H * 0.12)
                slide_dist = 28
                slide_calc = f"min(max((t-{card_start_time:.2f})/0.32\\,0)\\,1)"
                ease_y = f"{top_y} - {slide_dist}*(1-pow({slide_calc}\\,3))"
                filter_parts.append(
                    f"[{c_idx}:v]format=rgba,fade=t=in:st={card_start_time:.2f}:d=0.25:alpha=1,fade=t=out:st={fo_start:.2f}:d=0.35:alpha=1[card_animated]"
                )
                filter_parts.append(f"[{cur_v}][card_animated]overlay=x='(W-w)/2':y='{ease_y}':enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                cur_v = "v_card"

            elif card_visual_type in ("step_badge", "source_chip"):
                # Insignia de paso o fuente: Entrada lateral flotante con rebote sutil desde la izquierda
                slide_dist = 40
                slide_calc = f"min(max((t-{card_start_time:.2f})/0.30\\,0)\\,1)"
                ease_x = f"50 - {slide_dist}*(1-pow({slide_calc}\\,3))"
                chip_y = int(self.H * 0.68) if self.is_vertical else int(self.H * 0.72)
                filter_parts.append(
                    f"[{c_idx}:v]format=rgba,fade=t=in:st={card_start_time:.2f}:d=0.20:alpha=1,fade=t=out:st={fo_start:.2f}:d=0.30:alpha=1[card_animated]"
                )
                filter_parts.append(f"[{cur_v}][card_animated]overlay=x='{ease_x}':y='{chip_y}':enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                cur_v = "v_card"

            elif card_visual_type == "alert_banner":
                # Alerta táctica HUD: Caída rápida e impacto de advertencia en el tercio superior
                alert_y = int(self.H * 0.18) if self.is_vertical else int(self.H * 0.14)
                slide_dist = 35
                slide_calc = f"min(max((t-{card_start_time:.2f})/0.26\\,0)\\,1)"
                ease_y = f"{alert_y} - {slide_dist}*(1-pow({slide_calc}\\,3))"
                filter_parts.append(
                    f"[{c_idx}:v]format=rgba,fade=t=in:st={card_start_time:.2f}:d=0.15:alpha=1,fade=t=out:st={fo_start:.2f}:d=0.30:alpha=1[card_animated]"
                )
                filter_parts.append(f"[{cur_v}][card_animated]overlay=x='(W-w)/2':y='{ease_y}':enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                cur_v = "v_card"

            elif card_visual_type == "stat_counter":
                # En vertical la cifra se ancla arriba para dejar libre la zona de subtítulos.
                card_top = int(self.H * 0.14) if self.is_vertical else None
                card_y = f"{card_top}" if card_top is not None else "(H-h)/2"
                if animated_card_path:
                    hold = max(0.2, card_duration)
                    fade_out = max(0.1, hold - 0.30)
                    filter_parts.append(
                        f"[{c_idx}:v]format=rgba,"
                        f"tpad=stop_mode=clone:stop_duration={hold:.2f},"
                        f"trim=duration={hold:.2f},setpts=PTS-STARTPTS,"
                        f"fade=t=in:st=0:d=0.18:alpha=1,"
                        f"fade=t=out:st={fade_out:.2f}:d=0.30:alpha=1,"
                        f"setpts=PTS+{card_start_time:.2f}/TB[card_animated]"
                    )
                    filter_parts.append(
                        f"[{cur_v}][card_animated]overlay=x='(W-w)/2':y='{card_y}':eof_action=pass:"
                        f"enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]"
                    )
                else:
                    # Métrica gigante: entrada suave
                    slide_dist = 22
                    slide_calc = f"min(max((t-{card_start_time:.2f})/0.32\\,0)\\,1)"
                    ease_y = f"{card_y} + {slide_dist}*(1-pow({slide_calc}\\,3))"
                    filter_parts.append(
                        f"[{c_idx}:v]format=rgba,fade=t=in:st={card_start_time:.2f}:d=0.25:alpha=1,fade=t=out:st={fo_start:.2f}:d=0.35:alpha=1[card_animated]"
                    )
                    filter_parts.append(f"[{cur_v}][card_animated]overlay=x='(W-w)/2':y='{ease_y}':enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                cur_v = "v_card"

            elif card_visual_type == "document_evidence_split":
                # Pantalla dividida Platzi + Agustín Laje (1920x1080 o Vertical)
                filter_parts.append(
                    f"[{c_idx}:v]format=rgba,fade=t=in:st={card_start_time:.2f}:d=0.30:alpha=1,fade=t=out:st={fo_start:.2f}:d=0.35:alpha=1[card_animated]"
                )
                if self.is_vertical:
                    filter_parts.append(f"[{cur_v}][card_animated]overlay=x='(W-w)/2':y='(H-h)/2':enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                else:
                    filter_parts.append(f"[{cur_v}][card_animated]overlay=x=0:y=0:enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                cur_v = "v_card"

            else:
                # Bento Box / Versus Split / Quote / Mapa estándar
                slide_dist = 26
                slide_calc = f"min(max((t-{card_start_time:.2f})/0.35\\,0)\\,1)"
                card_base_x = "((W-w)/2)"
                top_y = int(self.H * 0.16) if self.is_vertical else None
                base_y = f"{top_y}" if top_y is not None else "((H-h)/2)"
                ease_y = f"{base_y}+{slide_dist}*(1-pow({slide_calc}\\,3))"
                filter_parts.append(
                    f"[{c_idx}:v]format=rgba,fade=t=in:st={card_start_time:.2f}:d=0.35:alpha=1,fade=t=out:st={fo_start:.2f}:d=0.35:alpha=1[card_animated]"
                )
                filter_parts.append(f"[{cur_v}][card_animated]overlay=x='{card_base_x}':y='{ease_y}':enable='between(t,{card_start_time:.2f},{card_end:.2f})'[v_card]")
                cur_v = "v_card"


        elif popup_img_path and popup_img_path.exists():
            # Pop-up informativo HUD animado con entrada suave y salida centrada
            inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(popup_img_path)])
            pop_idx = num_in
            num_in += 1
            pop_start = popup_start_time
            pop_dur = min(4.5, duration - pop_start - 0.4)
            pop_end = pop_start + max(2.5, pop_dur)
            pop_fo = max(pop_start + 0.3, pop_end - 0.35)
            filter_parts.append(
                f"[{pop_idx}:v]format=rgba,fade=t=in:st={pop_start:.2f}:d=0.30:alpha=1,fade=t=out:st={pop_fo:.2f}:d=0.35:alpha=1[pop_animated]"
            )
            pop_base_x = "((W-w)/2)" if not self.is_vertical else "30"
            pop_y = 150 if not self.is_vertical else int(self.H * 0.36)
            slide_dist = 22
            slide_calc = f"min(max((t-{pop_start:.2f})/0.35\\,0)\\,1)"
            ease_x = f"{pop_base_x}-{slide_dist}*(1-pow({slide_calc}\\,3))"
            filter_parts.append(f"[{cur_v}][pop_animated]overlay=x='{ease_x}':y={pop_y}:enable='between(t,{pop_start:.2f},{pop_end:.2f})'[v_pop]")
            cur_v = "v_pop"

        elif lower_third_img_path and lower_third_img_path.exists():
            # Rótulo Broadcast Lower Third con entrada en el segundo 0.8 hasta el 4.8
            inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(lower_third_img_path)])
            lt_idx = num_in
            num_in += 1
            lt_start = 0.8
            lt_end = min(duration - 0.4, 4.8)
            lt_fo = max(lt_start, lt_end - 0.4)
            filter_parts.append(
                f"[{lt_idx}:v]format=rgba,fade=t=in:st={lt_start}:d=0.35:alpha=1,fade=t=out:st={lt_fo:.2f}:d=0.35:alpha=1[lt_animated]"
            )
            lt_x = "((W-w)/2)" if not self.is_vertical else 30
            lt_y = int(self.H - 180) if not self.is_vertical else int(self.H * 0.70)
            slide_dist = 26
            slide_calc = f"min(max((t-{lt_start})/0.4\\,0)\\,1)"
            ease_y = f"{lt_y}+{slide_dist}*(1-pow({slide_calc}\\,3))"
            filter_parts.append(f"[{cur_v}][lt_animated]overlay=x='{lt_x}':y='{ease_y}':enable='between(t,{lt_start},{lt_end:.2f})'[v_lt]")
            cur_v = "v_lt"

        elif scene.type == "chat_debate" and chat_overlay_path and chat_overlay_path.exists():
            inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(chat_overlay_path)])
            ch_idx = num_in
            num_in += 1
            cx = 60 if not self.is_vertical else 30
            cy = int(self.H - 330) if not self.is_vertical else int(self.H * 0.72)
            filter_parts.append(f"[{cur_v}][{ch_idx}:v]overlay={cx}:{cy}:enable='between(t,0.5,{duration-0.3:.2f})'[v_chat]")
            cur_v = "v_chat"

        # ── AÑOS FLOTANTES: cuando la locución menciona un año, aparece suelto
        # (sin tarjeta) con estilo tipográfico rotativo. Nunca rompe la escena.
        try:
            if card_duration <= 0 and not remo_active:
                _yrs = self.title_renderer.find_years(speech_text or "")[:2]
                _busy_until = (0.4 + free_title_dur + 0.3) if free_title_dur > 0 else 0.0
                _last_end = 0.0
                for _yi, (_year, _frac) in enumerate(_yrs):
                    _t = _frac * duration
                    for (_s0, _s1, _stext) in (sentence_boundaries or []):
                        if _year in (_stext or ""):
                            _pos = (_stext.find(_year) / max(1, len(_stext)))
                            _t = float(_s0) + _pos * (float(_s1) - float(_s0))
                            break
                    _t = max(_t, _busy_until, _last_end + 0.2, 0.6)
                    _yd = 2.6
                    if _t + _yd > duration - 0.2:
                        _t = duration - 0.2 - _yd
                    if _t < _busy_until or _t < _last_end:
                        continue
                    _ypng = scene_dir / f"year_{scene.scene_id}_{_yi}.png"
                    _res = self.title_renderer.render_year_callout(_year, _ypng, style_idx=int(scene.scene_id) + _yi)
                    if not _res:
                        continue
                    _ypath = _res[0]
                    inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(_ypath)])
                    _y_idx = num_in
                    num_in += 1
                    _t_end = _t + _yd
                    _maxw = int(self.W * (0.30 if not self.is_vertical else 0.55))
                    filter_parts.append(
                        f"[{_y_idx}:v]scale=w=min(iw\\,{_maxw}):h=-2,format=rgba,"
                        f"fade=t=in:st={_t:.2f}:d=0.35:alpha=1,"
                        f"fade=t=out:st={_t_end - 0.4:.2f}:d=0.4:alpha=1[yr{_yi}_a]"
                    )
                    _ycalc = f"min(max((t-{_t:.2f})/0.5\\,0)\\,1)"
                    _yx = int(self.W * 0.06) if not self.is_vertical else int(self.W * 0.06)
                    _yy = f"(H-h)/2 + 30*(1-pow({_ycalc}\\,3))" if not self.is_vertical else f"{int(self.H * 0.14)} + 30*(1-pow({_ycalc}\\,3))"
                    filter_parts.append(
                        f"[{cur_v}][yr{_yi}_a]overlay=x={_yx}:y='{_yy}':"
                        f"enable='between(t,{_t:.2f},{_t_end:.2f})'[v_yr{_yi}]"
                    )
                    cur_v = f"v_yr{_yi}"
                    _last_end = _t_end
        except Exception as _ye:
            safe_log(f"[SceneEngine] Año flotante omitido: {_ye}")

        # Overlay de chips / pastillas referenciales dinámicas sincronizadas con la locución (popup de 3.5s a 4.5s)
        if chips_img_path and chips_img_path.exists():
            inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(chips_img_path)])
            chp_idx = num_in
            num_in += 1
            # Posición FIJA y predecible (regla broadcast): abajo-izquierda dentro
            # del área segura, sin importar el contenido. Antes flotaba al centro
            # o a 150px según la escena — el espectador nunca aprendía dónde mirar.
            # El PNG viene a 2x (device-scale-factor), se reduce al 78%: banderas
            # grandes (~70px) y texto nítido.
            chip_x = 64 if not self.is_vertical else 26
            chip_y = "main_h-overlay_h-88" if not self.is_vertical else "main_h-overlay_h-150"
            # Duración del pop-up: 3.5 segundos o hasta el final de la escena
            chip_dur = 3.5
            chip_end = min(duration - 0.25, round(chip_start_time + chip_dur, 2))
            ch_fo = max(chip_start_time + 0.3, chip_end - 0.35)
            filter_parts.append(
                f"[{chp_idx}:v]scale=iw*0.78:ih*0.78,format=rgba,fade=t=in:st={chip_start_time:.2f}:d=0.25:alpha=1,fade=t=out:st={ch_fo:.2f}:d=0.35:alpha=1[chips_animated]"
            )
            filter_parts.append(f"[{cur_v}][chips_animated]overlay=x={chip_x}:y='{chip_y}':enable='between(t,{chip_start_time:.2f},{chip_end:.2f})'[v_chips]")
            cur_v = "v_chips"

        # Overlay de Pastilla de Atribución y Proveniencia Verificada (Source / Transparency Chip)
        if provenance_chip_path and provenance_chip_path.exists():
            inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(provenance_chip_path)])
            prv_idx = num_in
            num_in += 1
            prv_start = 0.6
            prv_dur = 3.6
            prv_end = min(duration - 0.3, round(prv_start + prv_dur, 2))
            prv_fo = max(prv_start + 0.3, prv_end - 0.4)
            prv_x = "(W-w-40)" if not self.is_vertical else "(W-w-24)"
            prv_y = 40 if not self.is_vertical else 80
            filter_parts.append(
                f"[{prv_idx}:v]scale=iw*0.75:ih*0.75,format=rgba,fade=t=in:st={prv_start:.2f}:d=0.25:alpha=1,fade=t=out:st={prv_fo:.2f}:d=0.35:alpha=1[prv_animated]"
            )
            filter_parts.append(
                f"[{cur_v}][prv_animated]overlay=x='{prv_x}':y={prv_y}:enable='between(t,{prv_start:.2f},{prv_end:.2f})'[v_prv]"
            )
            cur_v = "v_prv"

        # Superposición de insignias secuenciales escalonadas (Países, fechas, empresas) diseñadas por DeepSeek Flash
        if motion_badges:
            total_b = len(motion_badges)
            rack_gap = 16
            total_rack_w = sum(b.get("width", 220) for b in motion_badges) + (total_b - 1) * rack_gap
            start_x = max(40, (self.W - total_rack_w) // 2)
            cur_badge_x = start_x
            rack_y = int(self.H * 0.18) if not self.is_vertical else int(self.H * 0.16)

            for bi, b_meta in enumerate(motion_badges):
                b_path = b_meta.get("path")
                if not b_path or not b_path.exists():
                    continue
                b_st = float(b_meta.get("delay_sec", 1.0 + bi * 1.2))
                b_end = min(duration - 0.3, max(b_st + 3.2, duration - 0.4))
                b_fo = max(b_st + 0.3, b_end - 0.35)
                inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(b_path)])
                b_idx = num_in
                num_in += 1
                b_w = b_meta.get("width", 220)

                pop_calc = f"min(max((t-{b_st:.2f})/0.25\\,0)\\,1)"
                b_y_expr = f"{rack_y} + 22*(1-pow({pop_calc}\\,3))"
                filter_parts.append(
                    f"[{b_idx}:v]format=rgba,fade=t=in:st={b_st:.2f}:d=0.20:alpha=1,fade=t=out:st={b_fo:.2f}:d=0.35:alpha=1[b_item_{bi}];"
                    f"[{cur_v}][b_item_{bi}]overlay=x='{cur_badge_x}':y='{b_y_expr}':enable='between(t,{b_st:.2f},{b_end:.2f})'[v_bdg_{bi}]"
                )
                cur_v = f"v_bdg_{bi}"
                cur_badge_x += b_w + rack_gap

        # Superposición de métrica cinética destacada (porcentaje o cifra animada) diseñada por DeepSeek Flash
        if motion_stat and not card_img_path:
            s_path = motion_stat.get("path")
            if s_path and s_path.exists():
                s_st = float(motion_stat.get("delay_sec", 1.4))
                s_end = min(duration - 0.3, max(s_st + 3.8, duration - 0.4))
                s_fo = max(s_st + 0.3, s_end - 0.35)
                inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(s_path)])
                s_idx = num_in
                num_in += 1
                stat_y = int(self.H * 0.32) if not self.is_vertical else int(self.H * 0.28)
                stat_pop = f"min(max((t-{s_st:.2f})/0.28\\,0)\\,1)"
                stat_y_expr = f"{stat_y} + 26*(1-pow({stat_pop}\\,3))"
                filter_parts.append(
                    f"[{s_idx}:v]format=rgba,fade=t=in:st={s_st:.2f}:d=0.22:alpha=1,fade=t=out:st={s_fo:.2f}:d=0.35:alpha=1[stat_anim];"
                    f"[{cur_v}][stat_anim]overlay=x='(W-w)/2':y='{stat_y_expr}':enable='between(t,{s_st:.2f},{s_end:.2f})'[v_mstat]"
                )
                cur_v = "v_mstat"

        # Superposicion de palabras clave / anos flotantes (rotulos de enfasis sin cards)
        if keyword_callout_overlays:
            kw_dur = 2.1
            for k_i, k_data in enumerate(keyword_callout_overlays):
                k_path = k_data["path"]
                k_frac = k_data["frac"]
                # Con overlay Remotion activo: no mostrar rótulos numéricos ni solapados con la cifra animada
                if remo_active:
                    _kt = str(k_data.get("text", ""))
                    _kt_start = max(0.8, min(duration - 2.5, k_frac * duration))
                    if any(ch.isdigit() for ch in _kt) or (_kt_start < remo_end + 0.3 and _kt_start + 2.1 > remo_start - 0.3):
                        safe_log(f"[SceneEngine] 🧹 Rótulo '{_kt}' omitido en escena {scene.scene_id}: cifra Remotion activa.")
                        continue
                # Determinar momento idoneo evitando colision con card o free_title
                ideal_t = max(0.8, min(duration - kw_dur - 0.4, k_frac * duration))
                if card_img_path and card_img_path.exists() and card_duration > 0:
                    c_start = card_start_time
                    c_exit = card_start_time + card_duration
                    # Si cabe antes de la tarjeta con margen suficiente
                    if c_start >= kw_dur + 0.8 and (ideal_t + kw_dur + 0.3) <= c_start:
                        kw_start = ideal_t
                    # O si cabe después de que finalice la tarjeta
                    elif duration >= c_exit + kw_dur + 0.5:
                        kw_start = max(c_exit + 0.5, ideal_t)
                    else:
                        safe_log(f"[SceneEngine] 🛡️ Keyword callout '{k_data.get('text')}' omitido en escena {scene.scene_id} por colisión con tarjeta [{c_start:.1f}s-{c_exit:.1f}s].")
                        continue
                elif free_title_img_path and free_title_img_path.exists() and free_title_dur > 0:
                    f_exit = 0.4 + free_title_dur
                    if duration >= f_exit + kw_dur + 0.6:
                        kw_start = max(f_exit + 0.6, ideal_t)
                    else:
                        safe_log(f"[SceneEngine] 🛡️ Keyword callout '{k_data.get('text')}' omitido en escena {scene.scene_id} por colisión con free_title.")
                        continue
                else:
                    kw_start = ideal_t

                kw_end = min(duration - 0.2, kw_start + kw_dur)
                if kw_end - kw_start >= 1.2:
                    inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(k_path)])
                    kw_in_idx = num_in
                    num_in += 1
                    fo_st = max(kw_start + 0.2, kw_end - 0.28)
                    filter_parts.append(
                        f"[{kw_in_idx}:v]format=rgba,fade=t=in:st={kw_start:.2f}:d=0.22:alpha=1,fade=t=out:st={fo_st:.2f}:d=0.28:alpha=1[kwo_{k_i}]"
                    )
                    kw_slide = f"min(max((t-{kw_start:.2f})/0.25\\,0)\\,1)"
                    if not self.is_vertical:
                        kw_y_base = int(self.H * 0.72)
                        kw_y_expr = f"{kw_y_base} + 16*(1-pow({kw_slide}\\,3))"
                    else:
                        kw_y_expr = f"((H-h)/2)+24*(1-pow({kw_slide}\\,3))"
                    filter_parts.append(
                        f"[{cur_v}][kwo_{k_i}]overlay=x='(W-w)/2':y='{kw_y_expr}':enable='between(t,{kw_start:.2f},{kw_end:.2f})'[v_kwo_{k_i}]"
                    )
                    cur_v = f"v_kwo_{k_i}"

        # Superposición de Overlay Cinemático Remotion (React + Alpha ProRes)
        # Exclusión mutua estricta: asegurar que nunca se superponga sobre una tarjeta existente
        if remo_active:
            inputs.extend(["-t", dur_str, "-r", str(self.fps), "-i", str(ai_remotion_mov)])
            remo_idx = num_in
            num_in += 1
            # setpts desplaza el overlay al instante inteligente; eof_action=pass + enable
            # garantizan que desaparece al terminar (antes quedaba el último fotograma congelado).
            filter_parts.append(
                f"[{remo_idx}:v]scale={self.W}:{self.H},format=rgba,setpts=PTS-STARTPTS+{remo_start:.2f}/TB[v_remo]"
            )
            filter_parts.append(
                f"[{cur_v}][v_remo]overlay=0:0:eof_action=pass:enable='between(t,{remo_start:.2f},{remo_end:.2f})'[v_with_remo]"
            )
            cur_v = "v_with_remo"

        # Superposición de tarjetas Spotlight con Foto sincronizadas con la mención de cada persona
        if person_spotlight_overlays:
            for ps_idx, ps in enumerate(person_spotlight_overlays):
                ps_png = ps["png_path"]
                if ps_png.exists():
                    inputs.extend(["-loop", "1", "-t", dur_str, "-r", str(self.fps), "-i", str(ps_png)])
                    ps_idx_in = num_in
                    num_in += 1
                    ps_st = ps["start_time"]
                    ps_end = min(duration - 0.15, ps_st + ps["duration"])
                    ps_fo = max(ps_st + 0.3, ps_end - 0.28)
                    filter_parts.append(
                        f"[{ps_idx_in}:v]format=rgba,fade=t=in:st={ps_st:.2f}:d=0.25:alpha=1,fade=t=out:st={ps_fo:.2f}:d=0.28:alpha=1[ps_{ps_idx}_anim]"
                    )
                    slide_dist = 22
                    ps_calc = f"min(max((t-{ps_st:.2f})/0.28\\,0)\\,1)"
                    if self.is_vertical:
                        ps_x = "((W-w)/2)"
                        ps_y_base = int(self.H * 0.72)
                    else:
                        ps_x = "60"
                        ps_y_base = int(self.H - 195)
                    ps_ease_y = f"{ps_y_base} + {slide_dist}*(1-pow({ps_calc}\\,3))"
                    filter_parts.append(
                        f"[{cur_v}][ps_{ps_idx}_anim]overlay=x='{ps_x}':y='{ps_ease_y}':enable='between(t,{ps_st:.2f},{ps_end:.2f})'[v_ps_{ps_idx}]"
                    )
                    cur_v = f"v_ps_{ps_idx}"

        # Subtítulos con libass (queman en pantalla si burn_subtitles está activo, en vertical o en modo anime)
        should_burn_subs = (
            getattr(self, "burn_subtitles", False)
            or self.is_anime
            or (self.is_vertical and getattr(self, "subs_enabled", True))
        )
        if srt_path and srt_path.exists() and should_burn_subs:
            ass_path = srt_path.with_suffix(".ass")
            sub_size = 32 if not self.is_vertical else 54
            margin_v = 64 if not self.is_vertical else 420
            st_style = self.sub_style
            if self.is_vertical and st_style in ("classic", "default", ""):
                st_style = "hormozi"
            if word_times:
                generate_karaoke_ass(
                    word_times,
                    ass_path,
                    width=self.W,
                    height=self.H,
                    sub_style=st_style,
                    font_size=sub_size,
                    margin_v=margin_v,
                    chunk_size=3 if self.is_vertical else 4,
                )
            else:
                generate_ass_from_srt(
                    srt_path,
                    ass_path,
                    width=self.W,
                    height=self.H,
                    sub_style=st_style,
                    font_size=sub_size,
                    margin_v=margin_v,
                )
            esc_ass = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")
            filter_parts.append(
                f"[{cur_v}]ass='{esc_ass}'[v_sub]"
            )
            cur_v = "v_sub"

        # Título superior / HUD y Marca de Agua:
        # En videos verticales 9:16 (Shorts/Reels) o documentales cinematográficos, CERO banners tipo debug
        # con nombres de escena internos ni marcas toscas. 100% metraje limpio.
        show_hud = (
            getattr(self, "show_hud_header", False)
            and not self.is_vertical
            and not is_scene_documentary
            and getattr(self, "style", "") in ("streamer", "vtuber", "reaccion")
        )
        if show_hud:
            font_p = FileManager.get_system_font_path()
            font_param = f"fontfile='{font_p}':" if font_p else ""
            clean_tag = re.sub(r"[^\w\s-]", "", scene.name).strip()[:35] or "RESUMEN"
            wm_text = getattr(self, "brand_watermark", "AetherCut")
            hud_fontsize = 20
            wm_fontsize = 18
            hud_text = f"● EN VIVO  |  {clean_tag.upper()}" if not self.is_anime else f"{self.anime_series_name.upper()}  |  {clean_tag.upper()}"
            filter_parts.append(
                f"[{cur_v}]drawtext={font_param}text='{hud_text}':fontcolor=white:fontsize={hud_fontsize}:x=44:y=34:box=1:boxcolor=black@0.65:boxborderw=8,"
                f"drawtext={font_param}text='{wm_text}':fontcolor=white@0.45:fontsize={wm_fontsize}:x=w-tw-44:y=34:box=1:boxcolor=black@0.35:boxborderw=6[v_out]"
            )
        else:
            filter_parts.append(f"[{cur_v}]copy[v_out]")

        # Audio mix: voz de la escena + BGM sutil + SFX de transición
        # Aseguramos que la pista de voz llene la duración si es necesario con apad
        inputs.extend(["-i", str(audio_path)])
        voice_in_idx = num_in
        num_in += 1

        # Verificación y activación de la presencia sonora real del protagonista (soundbite)
        should_use_clip_audio = is_soundbite_scene and bool(clip_audio_candidate and clip_audio_candidate.exists()) and not self.is_anime
        clip_audio_source = clip_audio_candidate if should_use_clip_audio else None
        has_clip_audio = bool(clip_audio_source and clip_audio_source.exists())

        # Audio profesional: loudnorm EBU R128 para broadcast (-16 LUFS target)
        has_bgm = bool(bgm_path and bgm_path.exists())
        if self.audio_normalize:
            v_prep = f"[{voice_in_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,{VOICE_PRO_CHAIN},loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur={dur_str}"
        else:
            v_prep = f"[{voice_in_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,{VOICE_PRO_CHAIN},apad=whole_dur={dur_str}"

        # Control de sidechain para BGM
        if has_bgm:
            voice_norm = f"{v_prep},asplit=2[a_voice][a_voice_ctrl_bgm]"
        else:
            voice_norm = f"{v_prep}[a_voice]"

        audio_filter_parts = [voice_norm]
        audio_mix_inputs = ["[a_voice]"]

        # Punto exacto donde KAI cede el turno y comienza el soundbite del protagonista con respiración estratégica
        sb_pause_before = 0.0 if self.is_anime else 0.40
        soundbite_start = round(tts_duration + sb_pause_before, 2)

        if has_bgm:
            inputs.extend(["-t", dur_str, "-stream_loop", "-1", "-i", str(bgm_path)])
            bgm_idx = num_in
            num_in += 1
            bgm_vol = getattr(self, 'bgm_volume', 0.12)
            # La musica debe sentirse: cama audible bajo la voz (-18/-20 dB utiles)
            # con ducking moderado, y aun mas baja durante el soundbite del protagonista.
            if has_clip_audio:
                sb_duck_start = max(0.0, soundbite_start - 0.20)
                sb_duck_end = round(soundbite_start + soundbite_window + 0.25, 2)
                sb_bed_vol = max(0.06, round(bgm_vol * 0.55, 3))
                bgm_vol_expr = f"volume='if(between(t,{sb_duck_start:.2f},{sb_duck_end:.2f}),{sb_bed_vol},{bgm_vol:.3f})':eval=frame"
            else:
                bgm_vol_expr = f"volume={bgm_vol:.3f}"
            audio_filter_parts.append(
                f"[{bgm_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,{bgm_vol_expr}[a_bgm_raw];"
                f"[a_bgm_raw][a_voice_ctrl_bgm]sidechaincompress=threshold=0.08:ratio=2.5:attack=40:release=320[a_bgm]"
            )
            audio_mix_inputs.append("[a_bgm]")

        if has_clip_audio:
            # Entrada con offset estratégico exacto para que el audio empiece desde la primera palabra de la frase lógica
            inputs.extend(["-ss", f"{soundbite_offset:.3f}", "-t", f"{soundbite_window:.3f}", "-i", str(clip_audio_source)])
            clip_a_idx = num_in
            num_in += 1
            delay_ms = int(soundbite_start * 1000)
            # REGLA DE ORO DE SOUNDBITES / CORTES DE DECLARACIÓN:
            # 1. Mientras KAI habla y durante la pausa previa de suspense (t < soundbite_start): silencio total (adelay mantiene la pista en espera)
            # 2. Cuando entra la declaración (t >= soundbite_start): la voz real entra nítida con fade-in suave (120ms)
            #    y un fade-out gradual (280ms) antes de terminar el corte para evitar cualquier corte seco, click digital o sensación de truncado.
            sb_fade_in_d = 0.12
            sb_fade_out_d = 0.28
            sb_fade_out_st = round(max(soundbite_start + 0.5, soundbite_start + soundbite_window - sb_fade_out_d), 2)
            audio_filter_parts.append(
                f"[{clip_a_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"adelay={delay_ms}|{delay_ms},volume=0.92,"
                f"afade=t=in:st={soundbite_start:.2f}:d={sb_fade_in_d:.2f},"
                f"afade=t=out:st={sb_fade_out_st:.2f}:d={sb_fade_out_d:.2f}[a_clip]"
            )
            audio_mix_inputs.append("[a_clip]")
            safe_log(f"[SceneEngine] 🎙️ Audio original estratégico del protagonista activo en t={soundbite_start:.2f}s (pre-pausa={sb_pause_before}s, offset={soundbite_offset:.2f}s, dur={soundbite_window:.2f}s, fade_out={sb_fade_out_st:.2f}s, clip={clip_audio_source.name})")

        # SFX de escena general (si aplica)
        sfx_path = self._get_sfx_path(scene.sfx)
        if sfx_path and sfx_path.exists():
            inputs.extend(["-i", str(sfx_path)])
            sfx_idx = num_in
            num_in += 1
            audio_filter_parts.append(f"[{sfx_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,adelay=delays=150:all=1,volume=0.35[a_sfx]")
            audio_mix_inputs.append("[a_sfx]")

        # SFX sincronizado al instante exacto de aparición para elementos visuales
        if card_img_path and card_img_path.exists():
            sfx_map_by_type = {
                "verdict_badge": "pop",
                "step_badge": "pop",
                "source_chip": "pop",
                "stat_counter": "chime",
                "versus_split": "impact",
                "alert_banner": "alert",
                "tech_card": "whoosh",
                "quote_evidence": "whoosh",
                "quote": "pop",
                "bento": "whoosh",
                "map": "alert",
                "geointel_map": "alert",
                "newspaper_clipping": "paper",
                "newspaper": "paper",
                "press_clipping": "paper",
                "workflow_diagram": "chime",
                "workflow": "chime",
                "router_pattern": "chime",
                "terminal_hud": "pop",
                "terminal": "pop",
                "cli_console": "pop",
                "spec_matrix": "impact",
                "benchmark_table": "impact",
            }
            card_sfx_type = sfx_map_by_type.get(card_visual_type, "whoosh")
            c_sfx_path = self._get_sfx_path(card_sfx_type)
            if c_sfx_path and c_sfx_path.exists():
                inputs.extend(["-i", str(c_sfx_path)])
                c_sfx_idx = num_in
                num_in += 1
                c_del_ms = max(50, int(card_start_time * 1000))
                card_vol = 0.45 if card_sfx_type == "alert" else 0.70
                audio_filter_parts.append(
                    f"[{c_sfx_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                    f"adelay=delays={c_del_ms}:all=1,volume={card_vol:.2f}[a_card_sfx]"
                )
                audio_mix_inputs.append("[a_card_sfx]")

            # SFX secundario: trazo de rotulador fluorescente sobre el titular (estilo Vox / Adrià Solà)
            if card_visual_type in ("newspaper_clipping", "newspaper", "press_clipping"):
                m_sfx = self._get_sfx_path("marker")
                if m_sfx and m_sfx.exists():
                    inputs.extend(["-i", str(m_sfx)])
                    m_idx = num_in
                    num_in += 1
                    m_del = max(50, int((card_start_time + 0.35) * 1000))
                    audio_filter_parts.append(
                        f"[{m_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                        f"adelay=delays={m_del}:all=1,volume=0.60[a_marker_sfx]"
                    )
                    audio_mix_inputs.append("[a_marker_sfx]")

        if popup_img_path and popup_img_path.exists():
            p_sfx_path = self._get_sfx_path("pop")
            if p_sfx_path and p_sfx_path.exists():
                inputs.extend(["-i", str(p_sfx_path)])
                p_sfx_idx = num_in
                num_in += 1
                p_del_ms = max(50, int(popup_start_time * 1000))
                audio_filter_parts.append(
                    f"[{p_sfx_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                    f"adelay=delays={p_del_ms}:all=1,volume=0.80[a_pop_sfx]"
                )
                audio_mix_inputs.append("[a_pop_sfx]")

        if chips_img_path and chips_img_path.exists():
            ch_sfx_path = self._get_sfx_path("pop")
            if ch_sfx_path and ch_sfx_path.exists():
                inputs.extend(["-i", str(ch_sfx_path)])
                ch_sfx_idx = num_in
                num_in += 1
                ch_del_ms = max(50, int(chip_start_time * 1000))
                audio_filter_parts.append(
                    f"[{ch_sfx_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                    f"adelay=delays={ch_del_ms}:all=1,volume=0.75[a_chip_sfx]"
                )
                audio_mix_inputs.append("[a_chip_sfx]")

        # SFX sincronizado al instante de aparición de tarjetas de persona / spotlight
        if person_spotlight_overlays:
            for ps_idx, ps in enumerate(person_spotlight_overlays[:2]):
                ps_sfx = self._get_sfx_path("pop")
                if ps_sfx and ps_sfx.exists():
                    inputs.extend(["-i", str(ps_sfx)])
                    ps_sfx_idx = num_in
                    num_in += 1
                    ps_del_ms = max(50, int(ps["start_time"] * 1000))
                    audio_filter_parts.append(
                        f"[{ps_sfx_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                        f"adelay=delays={ps_del_ms}:all=1,volume=0.35[a_ps_sfx_{ps_idx}]"
                    )
                    audio_mix_inputs.append(f"[a_ps_sfx_{ps_idx}]")

        # Diseño sonoro de retención: un whoosh sutil en cada corte de plano (técnica Vox/Magnates)
        # y un chime al entrar la cifra animada Remotion.
        try:
            cut_times = [float(t) for _, t in bg_clips[1:]] if bg_clips else []
            cut_sfx = self._get_sfx_path("whoosh")
            if cut_sfx and cut_sfx.exists():
                for c_i, c_t in enumerate(cut_times[:5]):
                    if c_t < 0.4 or c_t > duration - 0.4:
                        continue
                    inputs.extend(["-i", str(cut_sfx)])
                    cs_idx = num_in
                    num_in += 1
                    audio_filter_parts.append(
                        f"[{cs_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                        f"adelay=delays={max(0, int((c_t - 0.08) * 1000))}:all=1,volume=0.22[a_cut_sfx{c_i}]"
                    )
                    audio_mix_inputs.append(f"[a_cut_sfx{c_i}]")
            if remo_active:
                remo_sfx = self._get_sfx_path("chime")
                if remo_sfx and remo_sfx.exists():
                    inputs.extend(["-i", str(remo_sfx)])
                    rs_idx = num_in
                    num_in += 1
                    audio_filter_parts.append(
                        f"[{rs_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                        f"adelay=delays={int(remo_start * 1000)}:all=1,volume=0.6[a_remo_sfx]"
                    )
                    audio_mix_inputs.append("[a_remo_sfx]")
        except Exception as _cse:
            safe_log(f"[SceneEngine] SFX de cortes omitido: {_cse}")

        # Normalizar a espacio de color estándar broadcast (bt709, limitado tv, yuv420p)
        # Esto previene desfases de SPS o decodificación JPEG yuvj420p entre escenas en concat copy
        grade_filter = COLOR_GRADE_FILTERS.get(getattr(self, 'color_grade', 'cinema'), '')
        scale_limit = "scale=out_color_matrix=bt709:out_range=limited,format=yuv420p"
        if grade_filter:
            filter_parts.append(f"[v_out]{scale_limit},{grade_filter}[v_graded]")
            final_v = "v_graded"
        else:
            filter_parts.append(f"[v_out]{scale_limit}[v_graded]")
            final_v = "v_graded"

        # Corte directo limpio entre escenas (eliminando el apagón dip-to-black de 0.5s)
        # Permite continuidad fluida sin parpadeos negros que causaban pausas perceptibles en el reproductor
        filter_parts.append(f"[{final_v}]copy[v_final]")
        final_v = "v_final"

        inputs_tags = "".join(audio_mix_inputs)
        # normalize=0: amix por defecto divide cada entrada entre el número de
        # entradas activas → la voz bajaba 3-6 dB con BGM/SFX y sufría un "swell"
        # al expirar el SFX (dropout_transition). Sin normalización, la voz
        # mantiene el -16 LUFS del loudnorm y cada pista conserva su volumen.
        audio_filter_parts.append(f"{inputs_tags}amix=inputs={len(audio_mix_inputs)}:duration=longest:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[a_out]")

        full_filter = ";\n".join(filter_parts + audio_filter_parts)
        filter_file = scene_dir / "scene_filter.txt"
        filter_file.write_text(full_filter, encoding="utf-8")

        scene_fps = getattr(self, 'fps', 30)
        scene_crf = getattr(self, 'crf', 18)
        cmd = [
            "ffmpeg", "-y",
            "-threads", "4",
            *inputs,
            "-filter_complex_script", str(filter_file),
            "-map", f"[{final_v}]",
            "-map", "[a_out]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(scene_crf),
            "-pix_fmt", "yuv420p",
            "-color_range", "tv",
            "-colorspace", "bt709",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-r", str(scene_fps),
            "-x264-params", "threads=2:rc-lookahead=10:colorprim=bt709:transfer=bt709:colormatrix=bt709:fullrange=off",
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", "48000",
            "-max_muxing_queue_size", "1024",
            "-t", dur_str,
            str(scene_tmp),
        ]

        if self.cancel_event and self.cancel_event.is_set():
            raise asyncio.CancelledError("Render cancelado.")

        # Diagnóstico persistente: el comando completo queda junto al filtro de la
        # escena; si FFmpeg falla, su stderr completo se escribe en la carpeta
        # (antes solo iba a la consola del servidor y se perdía).
        try:
            (scene_dir / "scene_cmd.txt").write_text(" ".join(cmd), encoding="utf-8")
        except Exception:
            pass

        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        except asyncio.CancelledError:
            try:
                proc.kill()
            except Exception:
                pass
            if sys.platform == "win32":
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)
                except Exception:
                    pass
            raise
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            if sys.platform == "win32":
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)
                except Exception:
                    pass
            raise RuntimeError(f"FFmpeg agotó el tiempo (600 s) renderizando la escena {scene.scene_id}.")

        if self.cancel_event and self.cancel_event.is_set():
            raise asyncio.CancelledError("Render cancelado tras ejecución de escena.")

        if not scene_tmp.exists() or scene_tmp.stat().st_size < 10000:
            err_msg = stderr.decode(errors="replace") if stderr else "No stderr"
            try:
                (scene_dir / "scene_ffmpeg_stderr.log").write_text(err_msg, encoding="utf-8")
            except Exception:
                pass
            print(f"[SceneEngine] ERROR FFmpeg escena {scene.scene_id}:\n{err_msg}")
            raise RuntimeError(f"Fallo al renderizar la escena {scene.scene_id}: {err_msg[-300:]}")

        # Escena completa y válida: publicar atómicamente y registrar su firma (con reintentos para Windows).
        for attempt in range(5):
            try:
                scene_tmp.replace(scene_out)
                break
            except OSError:
                if attempt == 4:
                    raise
                await asyncio.sleep(0.2)
        self._write_cache_meta(meta_path, scene)

        # Extraer miniatura visual de alta definición para el monitor en vivo del frontend
        # (Se captura en t=1.8s cuando los gráficos y tarjetas Bento ya hicieron slide-in completo)
        thumb_path = scene_dir / "scene_thumb.jpg"
        try:
            import subprocess
            await asyncio.to_thread(subprocess.run, [
                "ffmpeg", "-y", "-ss", "1.8", "-i", str(scene_out),
                "-vframes", "1", "-q:v", "3", str(thumb_path)
            ], capture_output=True, timeout=5)
        except Exception:
            pass

        safe_log(f"[SceneEngine] Escena {scene.scene_id} ({scene.name}) lista: {duration:.1f}s")
        return scene_out

    async def assemble_broadcast(
        self,
        plan: DirectorBroadcastPlan,
        avatar_clip: Optional[Path] = None,
        avatar_webm: Optional[Path] = None,
        output_file: Optional[Path] = None,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """Renderiza todas las escenas y las concatena en el master broadcast final."""
        # Selección de track BGM según preferencia de usuario.
        # Rutas absolutas contra BASE_DIR: relativas al CWD, un lanzamiento desde
        # otro directorio mataba el BGM y los SFX en silencio.
        _audio_dir = settings.BASE_DIR / "assets" / "audio"
        BGM_TRACKS = {
            "default":   _audio_dir / "bgm_streamer.wav",
            "tension":   _audio_dir / "bgm_tension.wav",
            "upbeat":    _audio_dir / "bgm_upbeat.wav",
            "ambient":   _audio_dir / "bgm_ambient.wav",
            "silent":    None,  # Sin música
        }
        bgm_track_key = getattr(self, 'bgm_track', 'default') if hasattr(self, 'bgm_track') else 'default'
        # 1. Si bgm_track_key es una ruta directa a un archivo de audio existente
        if isinstance(bgm_track_key, Path) and bgm_track_key.exists():
            bgm_candidate = bgm_track_key
        elif isinstance(bgm_track_key, str) and (Path(bgm_track_key).is_file() and Path(bgm_track_key).exists()):
            bgm_candidate = Path(bgm_track_key)
        else:
            # 2. Buscar si existe un track dedicado en la Biblioteca de YouTube (assets/audio/youtube_library/bgm/)
            yt_bgm = get_youtube_bgm_track(str(bgm_track_key))
            if yt_bgm and yt_bgm.exists():
                bgm_candidate = yt_bgm
            elif str(bgm_track_key).lower() == "silent":
                bgm_candidate = None
            else:
                bgm_candidate = BGM_TRACKS.get(str(bgm_track_key), BGM_TRACKS["default"])
        # Si el track específico no existe, caer al default
        if bgm_candidate and not bgm_candidate.exists():
            bgm_candidate = BGM_TRACKS["default"]
        bgm_path = bgm_candidate  # None = sin música

        # Chat overlay pre-generado
        chat_overlay_path = self.workdir / "chat_overlay.png"
        raw_comments = plan.chat_comments or [
            {"user": "TechFan", "badge": "VIP", "text": "¡Increíble análisis KAI!"},
            {"user": "DevLucas", "badge": "SUB", "text": "Dato mata relato siempre."},
        ]
        formatted = [
            (f"[{c.get('badge', 'VIP')}] @{c.get('user', 'Viewer')}", "cyan" if i % 2 == 0 else "amber", c.get("text", "¡Gran dato!"))
            for i, c in enumerate(raw_comments[:3])
        ]
        self.chat_renderer.render(formatted, chat_overlay_path)

        scene_files: List[Path] = []
        total_scenes = len(plan.scenes)
        self._total_scenes = total_scenes

        # Renderizado concurrente de múltiples escenas a la vez para aprovechar la máquina y los recursos
        sem = asyncio.Semaphore(2)  # Procesar 2 escenas en paralelo de forma óptima
        completed_count = 0

        async def render_single_scene(idx: int, sc: DirectorScene) -> tuple[int, Path]:
            nonlocal completed_count
            async with sem:
                if self.cancel_event and self.cancel_event.is_set():
                    raise asyncio.CancelledError("Render cancelado por el usuario.")

                safe_log(f"[SceneEngine] Grabando en paralelo escena {sc.scene_id}/{total_scenes}: {sc.name} ({sc.type})...")
                try:
                    sc_path = await self.render_scene(
                        scene=sc,
                        avatar_clip=avatar_clip,
                        avatar_webm=avatar_webm,
                        bgm_path=bgm_path,
                        chat_overlay_path=chat_overlay_path,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as scene_err:
                    safe_log(f"[SceneEngine] Reintentando escena {sc.scene_id} tras fallo transitorio: {str(scene_err)[:120]}")
                    sc_path = await self.render_scene(
                        scene=sc,
                        avatar_clip=avatar_clip,
                        avatar_webm=avatar_webm,
                        bgm_path=bgm_path,
                        chat_overlay_path=chat_overlay_path,
                    )

                # QA del plano renderizado (3 fotogramas): texto cortado, collage, marcas de agua, incoherencia.
                try:
                    from core.vision_qa import vision_qa
                    audit = await asyncio.to_thread(
                        vision_qa.audit_video,
                        video_path=sc_path,
                        expected_niche=self.brand_watermark,
                        forbidden_elements=[
                            "anime", "caricaturas", "collage", "texto cortado",
                            "marcas de agua", "elementos incoherentes",
                        ],
                        channel_name=self.brand_watermark,
                    )
                    if not audit.get("approved", True):
                        safe_log(
                            f"[VisionQA] Escena {sc.scene_id} rechazada: "
                            f"{audit.get('forbidden_found')} {audit.get('critique')}"
                        )
                        import shutil as _shutil
                        _shutil.rmtree(self.workdir / f"scene_{sc.scene_id}", ignore_errors=True)
                        sc.card = None
                        sc.visual_beats = []
                        sc.visual_query = "modern studio background clean minimal real photo"
                        sc.visual_query2 = ""
                        sc_path = await self.render_scene(
                            scene=sc,
                            avatar_clip=avatar_clip,
                            avatar_webm=avatar_webm,
                            bgm_path=bgm_path,
                            chat_overlay_path=chat_overlay_path,
                        )
                        safe_log(f"[VisionQA] Escena {sc.scene_id} re-renderizada con fondo seguro y sin card.")
                except Exception as _qa_err:
                    safe_log(f"[VisionQA] Aviso auditando escena {sc.scene_id}: {_qa_err}")

                completed_count += 1
                pct = 70.0 + (float(completed_count) / max(1, total_scenes)) * 18.0
                if progress_cb:
                    progress_cb(pct, f"Grabando {completed_count}/{total_scenes} escenas en paralelo: {sc.name}...")
                return (idx, sc_path)

        tasks = [render_single_scene(i, scene) for i, scene in enumerate(plan.scenes)]
        results = await asyncio.gather(*tasks)
        # Ordenar rigurosamente por índice original para preservar la secuencia exacta del guion
        results.sort(key=lambda x: x[0])
        scene_files = [path for _, path in results]

        # Concatenación final instantánea
        if progress_cb:
            progress_cb(90.0, "Concatenando y masterizando transmisión final...")

        concat_list_file = self.workdir / "concat_scenes.txt"
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for sc in scene_files:
                f.write(f"file '{sc.resolve().as_posix()}'\n")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c", "copy",
            "-movflags", "+faststart",
            "-max_muxing_queue_size", "1024",
            str(output_file),
        ]

        proc = await asyncio.create_subprocess_exec(*concat_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        concat_out, concat_err = await proc.communicate()

        # 1) Verificar el código de salida: antes NO se comprobaba — un FFmpeg
        # interrumpido (p. ej. servidor reiniciado durante el +faststart de un
        # master de cientos de MB) dejaba el archivo con los datos pero SIN el
        # índice moov, pasaba el chequeo de tamaño y la transmisión terminaba
        # "done" con un video que ningún reproductor podía abrir.
        if proc.returncode != 0 or not output_file.exists() or output_file.stat().st_size < 50000:
            err_txt = (concat_err or b"").decode(errors="replace")[-300:]
            raise RuntimeError(
                f"Error concatenando las escenas de la transmisión (código {proc.returncode}): {err_txt}. "
                "Reanudar reconstruye el master al instante: las escenas están en caché."
            )

        # 2) Validar integridad real del MP4: el átomo moov (índice) debe existir.
        # Es una lectura de cabecera de milisegundos que evita entregar como
        # "done" un master decapitado.
        probe = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(output_file),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        probe_out, _ = await probe.communicate()
        if probe.returncode != 0 or not probe_out.strip():
            output_file.unlink(missing_ok=True)
            raise RuntimeError(
                "El master quedó corrupto (sin índice MP4), se eliminó para forzar su reconstrucción. "
                "Reanudar la transmisión lo regenera en segundos con las escenas en caché."
            )

        # Liberar inmediatamente archivos temporales pesados de las escenas (.mov intermedios)
        # conservando el video master, thumbnails y metadata intactos
        try:
            for sc in scene_files:
                sc_dir = sc.parent
                for mov in sc_dir.glob("*.mov"):
                    try: mov.unlink()
                    except Exception: pass
            # Limpiar avatar base intermedio del workdir si existe — PERO conservar
            # kai_avatar.mov: es la caché del loop base que StreamerPipeline reutiliza
            # entre ejecuciones (dos estrategias de caché no deben pelearse).
            for mov in self.workdir.glob("*.mov"):
                if mov.name == "kai_avatar.mov":
                    continue
                try: mov.unlink()
                except Exception: pass
        except Exception as _e_clean:
            safe_log(f"[SceneEngine] Limpieza post-render: {_e_clean}")

        # Generar empaque de YouTube con capítulos SEO y timestamps automáticos
        try:
            await self._generate_youtube_packaging(output_file, plan.scenes, scene_files)
        except Exception as _e_yt:
            safe_log(f"[SceneEngine] Aviso: no se generó empaque YouTube: {_e_yt}")

        safe_log(f"[SceneEngine] Transmisión completa masterizada con {total_scenes} escenas en: {output_file}")
        return output_file

    async def _generate_youtube_packaging(
        self,
        output_file: Path,
        scenes: List[DirectorScene],
        scene_files: List[Path],
    ) -> Dict[str, Any]:
        """Genera automáticamente la descripción SEO de YouTube con marcas de tiempo,
        capítulos clicables, hashtags y miniatura heroica para publicación instantánea.
        """
        try:
            timestamps = []
            cur_time = 0.0
            for i, (sc, f_path) in enumerate(zip(scenes, scene_files)):
                m = int(cur_time // 60)
                s = int(cur_time % 60)
                ts_str = f"{m:02d}:{s:02d}"
                chapter_title = re.sub(r"^[0-9]+[\.\-\s]*", "", sc.name).strip() or f"Parte {i+1}"
                timestamps.append((ts_str, chapter_title, cur_time))

                try:
                    p = await asyncio.create_subprocess_exec(
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        str(f_path),
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    out, _ = await p.communicate()
                    cur_time += float(out.strip()) if out.strip() else sc.duration_est
                except Exception:
                    cur_time += sc.duration_est

            thumb_hero = self.workdir / "thumbnail_hero.jpg"
            if not thumb_hero.exists() and output_file.exists():
                try:
                    await asyncio.create_subprocess_exec(
                        "ffmpeg", "-y", "-ss", "00:00:02.500", "-i", str(output_file),
                        "-vframes", "1", "-q:v", "2", str(thumb_hero),
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                except Exception:
                    pass

            chapters_text = "\n".join([f"{ts} - {title}" for ts, title, _ in timestamps])
            tags = ["#Documental", "#Investigacion", "#Analisis", "#Historia", "#Explicacion"]
            
            full_desc = (
                f"Capítulos:\n{chapters_text}\n\n"
                f"─── Sobre este informe ───\n"
                f"Análisis documental e investigación audiovisual realizada con fuentes verificadas.\n\n"
                f"{' '.join(tags)}"
            )

            pkg_data = {
                "chapters": [{"timestamp": ts, "title": title, "seconds": sec} for ts, title, sec in timestamps],
                "description": full_desc,
                "thumbnail_path": str(thumb_hero) if thumb_hero.exists() else None,
                "total_scenes": len(scenes),
                "total_duration_est": round(cur_time, 2),
            }

            (self.workdir / "youtube_chapters.txt").write_text(chapters_text, encoding="utf-8")
            (self.workdir / "youtube_description.txt").write_text(full_desc, encoding="utf-8")
            (self.workdir / "youtube_packaging.json").write_text(json.dumps(pkg_data, indent=2, ensure_ascii=False), encoding="utf-8")

            safe_log(f"[SceneEngine] 🎬 Empaque de YouTube generado: {len(timestamps)} capítulos en youtube_chapters.txt")
            return pkg_data
        except Exception as _e_pkg:
            safe_log(f"[SceneEngine] Error generando empaque YouTube: {_e_pkg}")
            return {}

    def _settings_signature(self) -> Dict[str, Any]:
        """Huella de los parámetros que cambian el pixel/sonido de una escena.

        La caché de escenas la compara antes de reutilizar: reanudar con otro
        formato (9:16 ↔ 16:9), voz, calidad u otra línea de guion debe re-renderizar.
        """
        return {
            "aspect_ratio": self.aspect_ratio,
            "voice": self.voice,
            "fps": self.fps,
            "crf": self.crf,
            "color_grade": self.color_grade,
            "sub_style": self.sub_style,
            "subs_enabled": self.subs_enabled,
            "burn_subtitles": getattr(self, "burn_subtitles", False),
            "audio_normalize": self.audio_normalize,
            "bgm_volume": self.bgm_volume,
            "bgm_track": self.bgm_track,
            "card_theme": self.card_theme,
        }

    def _cache_meta_valid(self, meta_path: Path, scene: "DirectorScene") -> bool:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        expected = self._settings_signature()
        expected["speech_hash"] = hashlib.md5((scene.speech or "").encode("utf-8")).hexdigest()
        return meta == expected

    def _write_cache_meta(self, meta_path: Path, scene: "DirectorScene") -> None:
        try:
            meta = self._settings_signature()
            meta["speech_hash"] = hashlib.md5((scene.speech or "").encode("utf-8")).hexdigest()
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _get_audio_duration(self, audio_path: Path) -> float:
        try:
            res = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
                capture_output=True, text=True, check=True
            )
            return float(res.stdout.strip())
        except Exception:
            return 8.0

    def _get_media_provenance(self, media_path: Optional[Path]) -> Optional[Dict[str, Any]]:
        """Recupera los metadatos de procedencia, licencia y verificación del archivo multimedia."""
        if not media_path:
            return None
        cand_files = [
            media_path.with_name(f"{media_path.stem}_provenance.json"),
            media_path.parent / f"{media_path.stem.split('_')[0]}_provenance.json",
            self.orchestrator.target_dir / f"{media_path.stem}_provenance.json",
        ]
        for cf in cand_files:
            if cf.exists():
                try:
                    return json.loads(cf.read_text(encoding="utf-8"))
                except Exception:
                    pass
    def _get_clip_with_audio(self, bg_clips: List[Any]) -> Optional[Path]:
        """Encuentra el primer clip de video en bg_clips que contenga una pista de audio decodificable real."""
        for item in bg_clips:
            p = item[0] if isinstance(item, (tuple, list)) else item
            if not p or not getattr(p, "exists", lambda: False)() or p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            try:
                chk = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(p)],
                    capture_output=True, text=True, timeout=8
                )
                if "audio" in chk.stdout.lower():
                    return p
            except Exception:
                pass
        return None

    async def _plan_anime_precise_clips(
        self,
        scene: Any,
        scene_dir: Path,
        speech_text: str,
        audio_path: Optional[Path],
        sentence_boundaries: List[Tuple[float, float, str]],
        duration: float,
    ) -> List[Tuple[Path, float]]:
        """Solo anime: corta del episodio canónico el plano exacto de lo que la voz menciona.

        Devuelve [(clip, t_inicio_en_escena)] o [] si el índice no está listo (método base).
        """
        from core.anime_scene_matcher import AnimeSceneMatcher, parse_episode_range
        from core.anime_episode_manager import AnimeEpisodeManager

        series = getattr(self, "anime_series_name", "Black Clover")
        episodes = parse_episode_range(str(getattr(self, "topic", "") or ""))
        if not episodes:
            return []
        m = re.search(r"\d+", str(getattr(scene, "scene_id", "1")))
        num = int(m.group(0)) if m else 1
        total = max(1, int(getattr(self, "_total_scenes", 8) or 8))
        num = max(1, min(num, total))
        label = str(getattr(scene, "scene_id", num))

        cuts = await asyncio.to_thread(
            AnimeSceneMatcher.plan_scene,
            series, episodes, speech_text, sentence_boundaries, audio_path, duration,
            (num - 1) / total, 1.0 / total, self._anime_used_src, label,
        )
        if not cuts:
            return []

        out: List[Tuple[Path, float]] = []
        for i, c in enumerate(cuts):
            seg_dur = float(c["dur"]) + 0.8
            clip_path = scene_dir / f"anime_precise_{i}.mp4"
            res = await asyncio.to_thread(
                AnimeEpisodeManager.extract_clip_at,
                series, int(c["ep"]), float(c["src"]), seg_dur, clip_path,
            )
            if not res:
                continue
            t_start = 0.0 if not out else round(float(c["t"]), 2)
            out.append((res, t_start))
            safe_log(
                f"[SceneEngine] 🎯 Escena {label} t={c['t']:.1f}s «{c.get('text','')}» → Ep {c['ep']} @ {c['src']:.1f}s ({c.get('why','')})"
            )
        return out if len(out) >= 2 or (out and duration < 5.0) else []

    async def _get_scene_visual(
        self,
        query: str,
        scene_dir: Path,
        is_video_scene: bool = False,
        intent: Optional[Any] = None,
    ) -> Optional[Path]:
        """Obtiene un recurso visual verificado de stock o archivo documental para la escena."""
        try:
            from core.models import BRollCue
            from core.smart_media_curator import SmartMediaCurator

            # REGLA ESTRICTA DE ANIME: Método 1 (Corte directo de episodios canónicos completos)
            # En resúmenes de anime, NUNCA se busca en YouTube. Se extrae directamente del capítulo oficial.
            if self.is_anime:
                from core.anime_episode_manager import AnimeEpisodeManager
                anime_title = getattr(self, "anime_series_name", "Black Clover")
                range_m = re.search(r'(?:episodios?|episodes?|ep\.?)\s*(\d+)\s*(?:-|a|to)\s*(\d+)', str(getattr(self, "topic", "")), re.IGNORECASE)
                single_m = re.search(r'(?:episodios?|episodes?|ep\.?)\s*(\d+)', str(query), re.IGNORECASE)

                if single_m:
                    scene_ep = int(single_m.group(1))
                elif range_m:
                    min_ep = int(range_m.group(1))
                    max_ep = int(range_m.group(2))
                    sc_num = getattr(self, "_current_scene_num", 1)
                    tot_sc = len(getattr(self, "scenes", [])) or 6
                    calc_ep = min_ep + int(((sc_num - 1) / max(1, tot_sc)) * (max_ep - min_ep + 0.99))
                    scene_ep = int(min(max_ep, max(min_ep, calc_ep)))
                else:
                    scene_ep = 1

                cue_count = len(getattr(self, "used_visual_paths", set()))
                out_clip = scene_dir / f"anime_canonical_ep{scene_ep}_{cue_count}.mp4"

                clip_p = AnimeEpisodeManager.extract_clip_for_scene(
                    series_name=anime_title,
                    episode_num=scene_ep,
                    scene_num=getattr(self, "_current_scene_num", 1),
                    total_scenes=len(getattr(self, "scenes", [])) or 6,
                    duration=10.0,
                    out_path=out_clip,
                    sub_clip_idx=cue_count,
                )
                if clip_p and clip_p.exists():
                    p_str = str(clip_p.resolve()) if hasattr(clip_p, "resolve") else str(clip_p)
                    self.used_visual_paths.add(p_str)
                    if hasattr(self, "used_clip_names"):
                        self.used_clip_names.add(clip_p.name)
                    return clip_p

                # Respaldo Canónico Estricto: Reintentar corte seguro del episodio sin jamás salir a YouTube
                safe_retry_clip = AnimeEpisodeManager.extract_clip_for_scene(
                    series_name=anime_title,
                    episode_num=scene_ep,
                    scene_num=1,
                    total_scenes=6,
                    duration=10.0,
                    out_path=scene_dir / f"anime_canonical_ep{scene_ep}_safe_{cue_count}.mp4",
                    sub_clip_idx=0,
                )
                if safe_retry_clip and safe_retry_clip.exists():
                    p_str = str(safe_retry_clip.resolve()) if hasattr(safe_retry_clip, "resolve") else str(safe_retry_clip)
                    self.used_visual_paths.add(p_str)
                    return safe_retry_clip

                # Reutilizar metraje canónico previo de la serie si ya existe
                for prev in getattr(self, "used_visual_paths", set()):
                    if Path(prev).exists() and ("anime_canonical" in str(prev) or "episode" in str(prev)):
                        return Path(prev)

                return None

            search_q = query
            if intent:
                search_q = SmartMediaCurator.build_targeted_search_query(intent, query)
            elif query and len(query.split()) <= 2:
                search_q = f"{query} documentary evidence 4k"

            cue_count = len(getattr(self, "used_visual_paths", set()))
            cue_id = f"scene_cue_{abs(hash(search_q or query)) % 10000}_{cue_count}"
            fallback_q = (intent.entity_name if intent else "") or query or "noticia prensa investigacion"
            cue = BRollCue(
                cue_id=cue_id,
                start_sec=0.0,
                end_sec=10.0,
                concept=query or fallback_q,
                search_query_en=search_q or query or fallback_q,
                reasoning="Escena visual de fondo",
                asset_type="video" if (is_video_scene or self.is_anime) else "photo",
            )
            res = await self.orchestrator._resolve_single_cue(cue)
            if self.is_anime and (not res.local_file_path or Path(res.local_file_path).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")):
                safe_log(f"[SceneEngine] 🎬 Fallback anime clip para '{query}'...")
                anime_title = getattr(self, "anime_series_name", "Black Clover")
                cue.cue_id = f"{cue_id}_anifall"
                cue.search_query_en = f"{anime_title} episode {scene_ep} {content_kw} scene".strip()
                cue.asset_type = "video"
                res = await self.orchestrator._resolve_single_cue(cue)

            if res.local_file_path and Path(res.local_file_path).exists():
                p = Path(res.local_file_path)
                if self.is_anime and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    return None
                p_str = str(p.resolve()) if hasattr(p, "resolve") else str(p)
                # Si el asset ya fue utilizado previamente en el proyecto, intentar obtener una variante no repetida
                if hasattr(self, "used_visual_paths") and p_str in self.used_visual_paths:
                    safe_log(f"[SceneEngine] ⚠️ Clip ya usado previamente en el proyecto ({p.name}), buscando ángulo alternativo...")
                    alt_q = f"{search_q or query} cobertura archivo perspectiva diferente {cue_count + 1}"
                    cue.cue_id = f"{cue_id}_var{cue_count}"
                    cue.search_query_en = alt_q
                    res_alt = await self.orchestrator._resolve_single_cue(cue)
                    if res_alt.local_file_path and Path(res_alt.local_file_path).exists():
                        p_alt = Path(res_alt.local_file_path)
                        p_alt_str = str(p_alt.resolve()) if hasattr(p_alt, "resolve") else str(p_alt)
                        if p_alt_str not in self.used_visual_paths:
                            p = p_alt
                            p_str = p_alt_str
                # Registrar de forma estricta en used_visual_paths y used_clip_names para que ninguna escena futura repita esta imagen
                if hasattr(self, "used_visual_paths"):
                    self.used_visual_paths.add(p_str)
                if hasattr(self, "used_clip_names"):
                    self.used_clip_names.add(p.name)

                # Copiar sidecar de procedencia al directorio de la escena si existe
                prov_file = self.orchestrator.target_dir / f"{cue_id}_provenance.json"
                if prov_file.exists():
                    dest_prov = scene_dir / f"{p.stem}_provenance.json"
                    try:
                        dest_prov.write_text(prov_file.read_text(encoding="utf-8"), encoding="utf-8")
                    except Exception:
                        pass
                return p
        except Exception as exc:
            safe_log(f"[SceneEngine] No se pudo descargar visual para '{query}': {exc}")
        return None
    def _render_chips_overlay(self, chips: List[str], out_path: Path) -> Optional[Path]:
        """Renderiza una hilera horizontal de pastillas (chips) con banderas/iconos para referencias dinámicas."""
        if not chips:
            return None
        try:
            return self.web_renderer.render_chips_to_image(chips, out_path)
        except Exception as _ce:
            safe_log(f"[SceneEngine] Fallback de chips a Pillow: {_ce}")

        import io
        import urllib.request
        from PIL import Image, ImageDraw, ImageFont, ImageFilter

        scale = 2
        pill_h = 60 * scale
        pad_x = 26 * scale
        gap = 16 * scale

        COUNTRY_CODES = {
            "estados unidos": "us", "ee.uu": "us", "eeuu": "us", "usa": "us", "us": "us",
            "china": "cn", "cn": "cn",
            "argentina": "ar", "ar": "ar",
            "españa": "es", "espana": "es", "es": "es",
            "colombia": "co", "co": "co",
            "méxico": "mx", "mexico": "mx", "mx": "mx",
            "chile": "cl", "cl": "cl",
            "brasil": "br", "brazil": "br", "br": "br",
            "alemania": "de", "germany": "de", "de": "de",
            "reino unido": "gb", "uk": "gb", "inglaterra": "gb", "gb": "gb",
            "francia": "fr", "fr": "fr",
            "japón": "jp", "japon": "jp", "jp": "jp",
            "italia": "it", "it": "it",
            "canadá": "ca", "canada": "ca", "ca": "ca",
            "rusia": "ru", "ru": "ru",
            "australia": "au", "au": "au",
            "perú": "pe", "peru": "pe", "pe": "pe",
        }

        flags_dir = settings.BASE_DIR / "assets" / "flags_cache"
        flags_dir.mkdir(parents=True, exist_ok=True)

        def _get_flag_img(country_code: str, target_h: int) -> Optional[Image.Image]:
            cache_file = flags_dir / f"{country_code}.png"
            if not cache_file.exists():
                try:
                    url = f"https://flagcdn.com/w80/{country_code}.png"
                    req = urllib.request.Request(url, headers={"User-Agent": "AetherCut-Studio/2.0"})
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        cache_file.write_bytes(resp.read())
                except Exception:
                    pass
            if cache_file.exists():
                try:
                    im = Image.open(cache_file).convert("RGBA")
                    tw = int(im.width * (target_h / im.height))
                    res = im.resize((tw, target_h), Image.LANCZOS)
                    # Mascara redondeada sutil para la bandera
                    fmask = Image.new("L", (tw, target_h), 0)
                    ImageDraw.Draw(fmask).rounded_rectangle((0, 0, tw - 1, target_h - 1), radius=4 * scale, fill=255)
                    flag_rounded = Image.new("RGBA", (tw, target_h), (0, 0, 0, 0))
                    flag_rounded.paste(res, (0, 0), fmask)
                    return flag_rounded
                except Exception:
                    pass
            return None

        f_font = None
        for fn in ["segoeuib.ttf", "arialbd.ttf", "seguiemj.ttf"]:
            p = Path("C:/Windows/Fonts") / fn
            if p.exists():
                try:
                    f_font = ImageFont.truetype(str(p), 22 * scale)
                    break
                except Exception:
                    pass
        if not f_font:
            f_font = ImageFont.load_default()

        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        pills_data = []
        flag_h = int(30 * scale)

        for c in chips[:6]:
            raw = str(c).strip()
            if not raw:
                continue

            # Detectar si hay bandera emoji o código de 2 letras
            clean_name = raw
            c_code = None

            # 1. Buscar código al inicio (ej: 'us Estados Unidos', 'CN China')
            m_code = re.match(r"^([A-Za-z]{2})\s+(.+)$", raw)
            if m_code and m_code.group(1).lower() in COUNTRY_CODES:
                c_code = COUNTRY_CODES[m_code.group(1).lower()]
                clean_name = m_code.group(2).strip()
            else:
                # 2. Buscar por nombre de país: SOLO palabra completa ("us" dentro
                # de "Museo" o "Discusión" no es EE.UU.). Antes este fallback por
                # substring pintaba banderas falsas en chips corrientes.
                low_raw = raw.lower()
                for k, code_val in COUNTRY_CODES.items():
                    m_flag = re.search(rf"\b{re.escape(k)}\b", low_raw)
                    if not m_flag:
                        continue
                    # Claves cortas solo como SIGLAS en mayúsculas: "Usa energía"
                    # es el verbo español, no Estados Unidos.
                    if len(k) <= 4 and not raw[m_flag.start():m_flag.end()].isupper():
                        continue
                    c_code = code_val
                    break
                # Nota: ya NO se recorta el prefijo de 2 letras aquí — el re.sub
                # anterior destruía palabras legítimas ("IA avances" → "avances")
                # en el caso en que ni siquiera hubo código de país detectado.

            flag_img = _get_flag_img(c_code, flag_h) if c_code else None
            txt_w = int(probe.textlength(clean_name, font=f_font))
            extra_w = (flag_img.width + int(8 * scale)) if flag_img else 0
            w = int(txt_w + extra_w + (pad_x * 2))
            pills_data.append((clean_name, flag_img, w))

        if not pills_data:
            return None

        total_w = sum(w for _, _, w in pills_data) + (len(pills_data) - 1) * gap
        margin = 16 * scale
        W = total_w + (margin * 2)
        H = pill_h + (margin * 2)

        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        cur_x = margin
        for name_txt, f_img, w in pills_data:
            rect = (cur_x, margin, cur_x + w, margin + pill_h)
            # Pastilla obsidian dark con borde suave
            d.rounded_rectangle(rect, radius=pill_h // 2, fill=(18, 18, 22, 245), outline=(255, 255, 255, 60), width=1 * scale)
            content_x = cur_x + pad_x
            if f_img:
                f_y = margin + ((pill_h - f_img.height) // 2)
                im.paste(f_img, (content_x, f_y), f_img)
                content_x += f_img.width + int(8 * scale)
            d.text((content_x, margin + (pill_h // 2)), name_txt, font=f_font, fill=(255, 255, 255, 255), anchor="lm")
            cur_x += w + gap

        # Sombra suave difusa
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        cur_x = margin
        for _, _, w in pills_data:
            s_draw.rounded_rectangle((cur_x, margin + 4, cur_x + w, margin + pill_h + 4), radius=pill_h // 2, fill=(0, 0, 0, 160))
            cur_x += w + gap
        shadow = shadow.filter(ImageFilter.GaussianBlur(6 * scale))

        comp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        comp.paste(shadow, (0, 0), shadow)
        comp.paste(im, (0, 0), im)

        final_w = W // scale
        final_h = H // scale
        comp = comp.resize((final_w, final_h), Image.LANCZOS)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        comp.save(out_path, "PNG")
        return out_path

    def _get_sfx_path(self, sfx_name: str) -> Optional[Path]:
        # El LLM puede emitir "sfx": null — sin este guard el AttributeError
        # ("NoneType no tiene .lower") abortaba el broadcast completo.
        if not sfx_name or not isinstance(sfx_name, str):
            return None
        # 1. Priorizar SFX de alta definición desde la Biblioteca de YouTube si está disponible
        yt_sfx = get_youtube_sfx_path(sfx_name)
        if yt_sfx and yt_sfx.exists():
            return yt_sfx
        # 2. Fallback a efectos estándar del sistema
        _audio_dir = settings.BASE_DIR / "assets" / "audio"
        sfx_map = {
            "whoosh": _audio_dir / "whoosh.wav",
            "chime": _audio_dir / "chime.wav",
            "impact": _audio_dir / "impact.wav",
            "alert": _audio_dir / "alert.wav",
            "pop": _audio_dir / "pop.wav",
            "paper": _audio_dir / "paper.wav",
            "marker": _audio_dir / "marker.wav",
            "riser": _audio_dir / "riser.wav",
            "none": None,
        }
        return sfx_map.get(sfx_name.lower().strip())

    def _generate_scene_subtitles(
        self,
        speech: str,
        duration: float,
        scene_dir: Path,
        boundaries: Optional[List[tuple]] = None,
        word_times: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Path]:
        srt_path = scene_dir / "scene_subtitles.srt"
        srt_lines = []

        def _fmt_srt(t: float) -> str:
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t - int(t)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        def _chunk_words(text_str: str) -> List[str]:
            """Subdivide el texto en bloques concisos de 3 a 4 palabras para que nunca saturen la pantalla."""
            raw_w = text_str.split()
            if not raw_w:
                return []
            chunks = []
            cur = []
            for i, w in enumerate(raw_w):
                cur.append(w)
                remaining = len(raw_w) - (i + 1)
                has_punct = bool(re.search(r"[.,!?;:]", w))
                # Cortar si llegamos a 4 palabras, o a 3 palabras si hay puntuación o quedan palabras suficientes
                if len(cur) >= 4 or (len(cur) >= 3 and remaining != 1) or (has_punct and len(cur) >= 2 and remaining >= 2):
                    chunks.append(" ".join(cur))
                    cur = []
            if cur:
                if len(cur) <= 2 and chunks:
                    prev_words = chunks[-1].split()
                    if len(prev_words) <= 3:
                        chunks[-1] = chunks[-1] + " " + " ".join(cur)
                    else:
                        chunks.append(" ".join(cur))
                else:
                    chunks.append(" ".join(cur))
            return chunks

        # 1. Si tenemos timestamps precisos de Edge TTS por oración
        # 0. Maxima precision: palabras alineadas con el audio real (Whisper).
        #    Cada bloque de 3-4 palabras usa el inicio real de su primera palabra y
        #    el fin real de la ultima, asi el subtitulo cambia exactamente al hablar.
        if word_times:
            word_chunks: List[List[Dict[str, Any]]] = []
            cur_w: List[Dict[str, Any]] = []
            for i, wt in enumerate(word_times):
                cur_w.append(wt)
                remaining = len(word_times) - (i + 1)
                has_punct = bool(re.search(r"[.,!?;:]$", str(wt.get("word", ""))))
                if len(cur_w) >= 4 or (len(cur_w) >= 3 and remaining >= 2) or (has_punct and len(cur_w) >= 2 and remaining >= 2):
                    word_chunks.append(cur_w)
                    cur_w = []
            if cur_w:
                if len(cur_w) <= 2 and word_chunks:
                    word_chunks[-1].extend(cur_w)
                else:
                    word_chunks.append(cur_w)

            idx = 1
            for ci, chunk in enumerate(word_chunks):
                st = float(chunk[0]["start"])
                en = float(chunk[-1]["end"]) + 0.10
                if ci + 1 < len(word_chunks):
                    en = min(en, float(word_chunks[ci + 1][0]["start"]) - 0.02)
                if en <= st:
                    en = st + 0.35
                clean_txt = " ".join(str(w.get("word", "")) for w in chunk).strip().replace(":", "")
                if not clean_txt:
                    continue
                srt_lines.append(f"{idx}\n{_fmt_srt(st)} --> {_fmt_srt(en)}\n{clean_txt}\n")
                idx += 1
            if srt_lines:
                srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
                return srt_path

        if boundaries and len(boundaries) > 0:
            idx = 1
            for st, en, text in boundaries:
                sentence_chunks = _chunk_words(text)
                if not sentence_chunks:
                    continue
                total_chars = sum(len(c) for c in sentence_chunks) or 1
                span = max(0.4, en - st)
                c_start = st
                for chunk_idx, chunk in enumerate(sentence_chunks):
                    weight = len(chunk) / total_chars
                    c_dur = span * weight
                    c_end = en if chunk_idx == len(sentence_chunks) - 1 else round(c_start + c_dur, 3)
                    clean_txt = chunk.strip().replace(":", "")
                    srt_lines.append(f"{idx}\n{_fmt_srt(c_start)} --> {_fmt_srt(c_end)}\n{clean_txt}\n")
                    idx += 1
                    c_start = c_end
            if srt_lines:
                srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
                return srt_path

        # 2. Fallback ponderado por caracteres en fragmentos cortos de 3 a 4 palabras
        words = speech.split()
        if not words:
            return None
        sub_chunks = _chunk_words(speech)
        if not sub_chunks:
            return None

        start_lead = 0.12
        total_chars = sum(len(c) for c in sub_chunks) or 1
        active_speech_time = max(2.0, duration - 0.45)

        curr_t = start_lead
        for idx, chunk in enumerate(sub_chunks):
            chunk_weight = len(chunk) / total_chars
            chunk_dur = max(0.7, active_speech_time * chunk_weight)
            st = curr_t
            en = min(duration - 0.1, curr_t + chunk_dur)
            curr_t = en

            clean = chunk.strip().replace(":", "")
            srt_lines.append(f"{idx + 1}\n{_fmt_srt(st)} --> {_fmt_srt(en)}\n{clean}\n")

        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
        return srt_path
