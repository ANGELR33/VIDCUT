import json
import shutil
import subprocess
from threading import Event
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from config.settings import settings
from core.models import CaptionItem, HighlightClip, VideoEditingPlan
from core.subtitle_generator import SubtitleGenerator
from core.timeline import TimelineMapper
from process_runner import run_process
from core.visual_analysis import VisualAnalyzer

ProgressCb = Optional[Callable[[str, float], None]]

VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv")
ENC_FINAL = [
    "-c:v", "libx264", "-preset", "medium", "-crf", "17",
    "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-b:a", "256k"
]
ENC_INTERMEDIATE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p"]


def probe_size(path: Path) -> Tuple[int, int]:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "json", str(path)], capture_output=True, text=True, timeout=30,
        ).stdout
        s = json.loads(out)["streams"][0]
        return int(s["width"]), int(s["height"])
    except Exception:
        return 1920, 1080


def probe_duration(path: Path) -> float:
    """Obtiene la duración exacta en segundos de un archivo de audio o video vía ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)], capture_output=True, text=True, timeout=15,
        ).stdout
        d = json.loads(out).get("format", {}).get("duration")
        return float(d) if d is not None else 0.0
    except Exception:
        return 0.0


def _ff_path(p: Path) -> str:
    """Ruta escapada para filtros de FFmpeg (ass=...) en Windows."""
    return str(p.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


class VideoRenderEngine:
    """
    Motor de render 100% FFmpeg (sin MoviePy):
      Pasada 1: Smart Cut (trim + concat) -> intermedio de alta calidad.
      Pasada 2: overlays animados (tarjetas, fotos, B-Roll de video) + subtítulos ASS opcionales.
    Cada overlay se desplaza en el tiempo con setpts, así su fade-in/out ocurre en el momento exacto.
    """

    def __init__(self, fps: int = 30, cancel_event: Optional[Event] = None):
        self.fps = fps
        self.cancel_event = cancel_event

    def _run(self, cmd: List[str], desc: str) -> bool:
        print(f"[RenderEngine] {desc}...")
        try:
            proc = run_process(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace",
                               cancel_event=self.cancel_event)
        except FileNotFoundError:
            print("[RenderEngine] No se encontró FFmpeg. Instálalo y asegúrate de que ffmpeg y ffprobe estén en PATH.")
            return False
        if proc.returncode != 0:
            print(f"[RenderEngine] {desc} falló:\n{proc.stderr[-1200:]}")
            return False
        return True

    # ------------------------------------------------------------------ pasada 1
    def cut_silences(self, input_video: Path, mapper: TimelineMapper, out: Path) -> Path:
        keep = mapper.keep
        if len(keep) <= 1:
            seg = keep[0] if keep else None
            cmd = ["ffmpeg", "-y", "-i", str(input_video)]
            if seg:
                cmd = ["ffmpeg", "-y", "-ss", f"{seg.start_sec:.3f}", "-i", str(input_video),
                       "-t", f"{seg.end_sec - seg.start_sec:.3f}"]
            cmd += [*ENC_INTERMEDIATE, "-c:a", "aac", "-b:a", "192k", str(out)]
            if not self._run(cmd, "Normalizando video (sin silencios que cortar)") or not out.exists():
                raise RuntimeError("FFmpeg no pudo preparar el video para el render.")
            return out

        # El grafo se escribe en un archivo: con cientos de cortes la línea de comandos excede el límite de Windows.
        parts, pairs = [], []
        for i, seg in enumerate(keep):
            s, e = max(0.0, seg.start_sec), max(seg.start_sec + 0.05, seg.end_sec)
            parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
            parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
            pairs.append(f"[v{i}][a{i}]")
        parts.append(f"{''.join(pairs)}concat=n={len(keep)}:v=1:a=1[vc][ac]")
        script = out.with_suffix(".cut.txt")
        script.write_text(";\n".join(parts), encoding="utf-8")

        cmd = ["ffmpeg", "-y", "-i", str(input_video), "-filter_complex_script", str(script),
               "-map", "[vc]", "-map", "[ac]", *ENC_INTERMEDIATE, "-c:a", "aac", "-b:a", "192k", str(out)]
        try:
            ok = self._run(cmd, f"Smart Cut de {len(keep)} tramos")
        finally:
            script.unlink(missing_ok=True)
        if not ok or not out.exists():
            raise RuntimeError("FFmpeg no pudo aplicar los cortes de silencio; no se generó una edición válida.")
        return out

    # ------------------------------------------------------------------ overlays
    @staticmethod
    def collect_overlays(plan: VideoEditingPlan, mapper: TimelineMapper) -> List[Dict]:
        total = mapper.total_duration
        items: List[Dict] = []

        for card in plan.info_cards:
            if not card.enabled or card.verdict not in ("supported", "contradicted", "insufficient") or not card.card_path:
                continue
            
            # Comprobar que todos los paths existan (para el mito vs realidad hay dos separados por |)
            paths = str(card.card_path).split("|")
            if any(not Path(p).exists() for p in paths):
                continue
                
            placed = mapper.map_first(card.start_sec, card.end_sec)
            if placed:
                s = placed[0]
                d = min(max(float(card.display_duration_sec), 4.5), 12.0, total - s)
                if d >= 2.5:
                    position = card.screen_position or "auto"
                    if len(paths) == 2:
                        items.append({"kind": "card", "path": paths[0], "start": s, "dur": 1.5, "position": position})
                        items.append({"kind": "card", "path": paths[1], "start": s + 1.5, "dur": d - 1.5, "position": position})
                    else:
                        items.append({"kind": "card", "path": paths[0], "start": s, "dur": d, "position": position})

                    # Avatar Copilot overlay si está configurado y renderizado
                    if getattr(card, "avatar_enabled", False) and getattr(card, "avatar_video_path", None):
                        av_p = Path(card.avatar_video_path)
                        if av_p.exists():
                            aud_p = getattr(card, "avatar_audio_path", None)
                            aud_dur = probe_duration(Path(aud_p)) if aud_p and Path(aud_p).exists() else 0.0
                            vid_dur = probe_duration(av_p)
                            # El avatar dura todo lo que dure su audio/video real sin recorte prematuro
                            av_dur = max(aud_dur + 0.4, vid_dur, 3.5) if (aud_dur > 0 or vid_dur > 0) else min(d, 8.0)
                            # La tarjeta informativa debe acompañar al avatar todo el tiempo
                            if len(items) > 0 and items[-1]["kind"] == "card":
                                items[-1]["dur"] = max(items[-1]["dur"], av_dur + 0.5)
                            av_pos = "lower_right" if position in ("auto", "upper_right") else "lower_left"
                            items.append({
                                "kind": "avatar",
                                "path": str(av_p),
                                "audio_path": getattr(card, "avatar_audio_path", None),
                                "start": s,
                                "dur": av_dur,
                                "position": av_pos,
                            })

        for cue in plan.b_rolls:
            if not cue.enabled or cue.download_status != "COMPLETED" or not cue.local_file_path:
                continue
            path = Path(cue.local_file_path)
            if not path.exists():
                continue
            placed = mapper.map_first(cue.start_sec, cue.end_sec)
            if placed:
                s = placed[0]
                # En los primeros 30 segundos (el gancho), B-Rolls más ágiles (2.0 a 3.5s)
                max_broll_dur = 3.5 if s < 30.0 else 4.5
                d = min(max(placed[1] - s, 2.0), max_broll_dur, total - s)
                if d >= 1.5:
                    is_video = path.suffix.lower() in VIDEO_EXT
                    # las fotos ya llegan enmarcadas como tarjeta (photo_frame_path)
                    p = cue.local_file_path if is_video else (getattr(cue, "frame_path", None) or "")
                    if p and Path(p).exists():
                        items.append({"kind": "video" if is_video else "photo", "path": p, "start": s, "dur": d})

        # Sin choques: si dos elementos ocurren en sucesión rápida, alternar zona libre (upper_right, upper_left, lower_right, lower_left)
        items.sort(key=lambda x: x["start"])
        zone_free: Dict[str, float] = {}
        final = []
        alt_positions = ["upper_right", "upper_left", "lower_right", "lower_left"]

        for it in items:
            if it["kind"] == "video":
                # Video B-roll toma toda la pantalla
                if zone_free.get("full", -1) > it["start"]:
                    continue
                zone_free["full"] = it["start"] + it["dur"] + 0.3
                final.append(it)
                continue

            current_pos = it.get("position", "auto")
            preferred_pos = "upper_right" if current_pos in ("auto", "right") else current_pos

            # Si la zona preferida está ocupada en este timestamp, buscar una alternativa disponible
            assigned_pos = preferred_pos
            if zone_free.get(assigned_pos, -1) > it["start"]:
                for candidate in alt_positions:
                    if zone_free.get(candidate, -1) <= it["start"]:
                        assigned_pos = candidate
                        break

            # Si todas las zonas están ocupadas simultáneamente, omitir para no saturar
            if zone_free.get(assigned_pos, -1) > it["start"]:
                continue

            it["position"] = assigned_pos
            zone_free[assigned_pos] = it["start"] + it["dur"] + 0.35
            final.append(it)

        return final

    def compose(self, base_video: Path, overlays: List[Dict], ass_file: Optional[Path], out: Path, zoom_segments: Optional[List[Dict]] = None, censor_segments: Optional[List[Dict]] = None) -> bool:
        W, H = probe_size(base_video)
        margin_x, margin_y = int(W * 0.025), int(H * 0.05)
        cmd = ["ffmpeg", "-y", "-i", str(base_video)]
        chains, cur = [], "0:v"
        audio_map = "0:a?"
        audio_filters: List[str] = []
        audio_mix_inputs: List[Tuple[str, float, float]] = []
        
        # 1. Dynamic Zoom (Punch-ins)
        if zoom_segments:
            chains.append(f"[0:v]scale={int(W*1.2)}:{int(H*1.2)},crop={W}:{H},setsar=1[v_zoom]")
            for i, z in enumerate(zoom_segments):
                nxt = f"z{i}"
                chains.append(
                    f"[{cur}][v_zoom]overlay=x=0:y=0:eof_action=pass:"
                    f"enable='between(t,{z['start']:.3f},{z['start'] + z['dur']:.3f})'[{nxt}]"
                )
                cur = nxt

        for i, it in enumerate(overlays, start=1):
            s, d = it["start"], it["dur"]
            fo = max(0.0, d - 0.35)
            if it["kind"] == "video":
                cmd += ["-t", f"{d:.2f}", "-i", it["path"]]
                chains.append(
                    f"[{i}:v]scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={self.fps},"
                    f"format=yuva420p,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={fo:.2f}:d=0.35:alpha=1,"
                    f"setpts=PTS-STARTPTS+{s:.3f}/TB[o{i}]"
                )
                pos_x, pos_y = "0", "0"
            elif it["kind"] == "avatar":
                cmd += ["-c:v", "libvpx-vp9", "-t", f"{d:.2f}", "-i", it["path"]]
                av_size = int(min(W, H) * 0.28)
                chains.append(
                    f"[{i}:v]scale={av_size}:{av_size},fps={self.fps},format=rgba,"
                    f"fade=t=in:st=0:d=0.25:alpha=1,fade=t=out:st={fo:.2f}:d=0.3:alpha=1,"
                    f"setpts=PTS-STARTPTS+{s:.3f}/TB[o{i}]"
                )
                slide = int(W * 0.03)
                ease = f"pow(1-min((t-{s:.3f})/0.4\\,1)\\,3)"
                position = it.get("position", "lower_right")
                right = position in ("upper_right", "lower_right")
                upper = position in ("upper_left", "upper_right")
                pos_x = f"W-w-{margin_x}+{slide}*{ease}" if right else f"{margin_x}-{slide}*{ease}"
                pos_y = str(margin_y) if upper else f"H-h-{margin_y}"
                if it.get("audio_path") and Path(it["audio_path"]).exists():
                    aud_dur = probe_duration(Path(it["audio_path"]))
                    # Ducking activo durante todo el audio de la voz más 0.4s de margen para salida suave
                    duck_dur = max(aud_dur + 0.4, d)
                    audio_mix_inputs.append((it["audio_path"], s, duck_dur))
            else:
                cmd += ["-loop", "1", "-framerate", str(self.fps), "-t", f"{d:.2f}", "-i", it["path"]]
                chains.append(
                    f"[{i}:v]format=rgba,fade=t=in:st=0:d=0.35:alpha=1,fade=t=out:st={fo:.2f}:d=0.35:alpha=1,"
                    f"setpts=PTS-STARTPTS+{s:.3f}/TB[o{i}]"
                )
                slide = int(W * 0.04)
                ease = f"pow(1-min((t-{s:.3f})/0.45\\,1)\\,3)"  # ease-out cúbico
                position = it.get("position", "auto")
                right = position in ("upper_right", "lower_right", "auto", "right")
                upper = position in ("upper_left", "upper_right", "auto")
                pos_x = f"W-w-{margin_x}+{slide}*{ease}" if right else f"{margin_x}-{slide}*{ease}"
                pos_y = str(margin_y) if upper else f"H-h-{margin_y}"
            nxt = f"b{i}"
            chains.append(
                f"[{cur}][o{i}]overlay=x='{pos_x}':y='{pos_y}':eof_action=pass:format=auto:"
                f"enable='between(t,{s:.3f},{s + d:.3f})'[{nxt}]"
            )
            cur = nxt

        if ass_file and ass_file.exists():
            chains.append(f"[{cur}]ass='{_ff_path(ass_file)}'[vout]")
            cur = "vout"
            
        # Audio Composition: mezcla de voz de avatar con ducking o censura
        if audio_mix_inputs:
            duck_expr = "+".join(f"between(t,{st:.3f},{st+dr:.3f})" for _, st, dr in audio_mix_inputs)
            chains.append(f"[0:a]volume='if({duck_expr},0.22,1.0)':eval=frame[a_base_ducked]")
            mix_tags = ["[a_base_ducked]"]
            for k, (a_path, st, dr) in enumerate(audio_mix_inputs):
                cmd += ["-i", str(a_path)]
                in_idx = len(overlays) + 1 + k
                delay_ms = int(st * 1000)
                tag = f"a_av_{k}"
                chains.append(f"[{in_idx}:a]adelay={delay_ms}|{delay_ms},volume=1.25[{tag}]")
                mix_tags.append(f"[{tag}]")
            chains.append(f"{''.join(mix_tags)}amix=inputs={len(mix_tags)}:duration=first:dropout_transition=2[a_mixed]")
            chains.append("[a_mixed]loudnorm=I=-16:LRA=11:TP=-1.5[a_norm]")
            audio_map = "[a_norm]"
        elif censor_segments:
            # Silence original audio in censor windows
            mute_expr = "+".join(f"between(t,{c['start']:.3f},{c['start']+c['dur']:.3f})" for c in censor_segments)
            chains.append(f"[0:a]volume='1-min(1,({mute_expr}))':eval=frame[a_muted]")
            # Generate continuous 1000Hz sine wave and only unmute during censor windows
            chains.append("sine=f=1000[bleep]")
            chains.append(f"[bleep]volume='0.15*min(1,({mute_expr}))':eval=frame[bleep_vol]")
            # Mix them together
            chains.append(f"[a_muted][bleep_vol]amix=inputs=2:duration=first[aout]")
            chains.append("[aout]loudnorm=I=-16:LRA=11:TP=-1.5[a_norm]")
            audio_map = "[a_norm]"
        else:
            # Nivel consistente para la versión final: voz audible sin picos
            # que distorsionen al cambiar entre tomas o recursos externos.
            audio_filters = ["-af", "loudnorm=I=-16:LRA=11:TP=-1.5"]

        if not chains:
            shutil.copy(base_video, out)
            return True

        script = out.with_suffix(".fx.txt")
        script.write_text(";\n".join(chains), encoding="utf-8")
        cmd += ["-filter_complex_script", str(script), "-map", f"[{cur}]", "-map", audio_map, *audio_filters,
                *ENC_FINAL, "-c:a", "aac", "-movflags", "+faststart", str(out)]
        try:
            ok = self._run(cmd, f"Componiendo {len(overlays)} overlays" + (" + subtítulos" if ass_file else ""))
        finally:
            script.unlink(missing_ok=True)
        return ok and out.exists()

    # ------------------------------------------------------------------ API principal
    def render(self, input_video: Path, plan: VideoEditingPlan, mapper: TimelineMapper, workdir: Path,
               out: Path, captions_provider: Optional[Callable[[Path], List[CaptionItem]]] = None,
               progress: ProgressCb = None) -> Dict:
        # El motor también se usa al reexportar un proyecto guardado. No dependemos de
        # que el llamador haya creado antes su directorio temporal.
        workdir.mkdir(parents=True, exist_ok=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        say = progress or (lambda m, p: None)

        say("Smart Cut con FFmpeg (eliminando silencios)...", 0.05)
        cut = self.cut_silences(input_video, mapper, workdir / "cut.mp4")

        captions: List[CaptionItem] = []
        ass_file = None
        if captions_provider:
            say("Transcribiendo audio para subtítulos sincronizados...", 0.30)
            captions = captions_provider(cut) or []
            if captions:
                W, H = probe_size(cut)
                ass_file = SubtitleGenerator.generate_ass(captions, workdir / "subs.ass", W, H)

        overlays = self.collect_overlays(plan, mapper)
        
        # Extraer segmentos de zoom y de censura basados en captions importantes
        zoom_segments = []
        censor_segments = []
        for cap in captions:
            dur = cap.end_sec - cap.start_sec
            if cap.highlight_words and dur >= 0.4:
                zoom_segments.append({"start": cap.start_sec, "dur": min(dur, 2.5)})
            if getattr(cap, "censor_words", None):
                censor_segments.append({"start": cap.start_sec, "dur": dur})
                
        say(f"Componiendo {len(overlays)} overlays, {len(zoom_segments)} jump-cuts y {len(censor_segments)} censuras...", 0.55)
        ok = self.compose(cut, overlays, ass_file, out, zoom_segments=zoom_segments, censor_segments=censor_segments)
        if not ok and ass_file:
            say("Reintentando sin subtítulos...", 0.8)
            ok = self.compose(cut, overlays, None, out, zoom_segments=zoom_segments, censor_segments=censor_segments)
        if not ok:
            say("Reintentando sin overlays...", 0.85)
            ok = self.compose(cut, [], ass_file, out)
        if not ok:
            raise RuntimeError("FFmpeg no pudo componer el video final después de los reintentos.")
        return {"overlays": overlays, "captions": len(captions)}

    # ------------------------------------------------------------------ shorts
    def extract_vertical_short(self, video_path: Path, highlight: HighlightClip, output_dir: Path) -> Optional[Path]:
        duration = max(1.0, highlight.end_sec - highlight.start_sec)
        out_path = output_dir / f"short_{highlight.clip_id}_{video_path.stem[:40]}.mp4"
        source_w, source_h = probe_size(video_path)
        scale = max(1080 / max(1, source_w), 1920 / max(1, source_h))
        scaled_w = max(1080, int(source_w * scale) // 2 * 2)
        scaled_h = max(1920, int(source_h * scale) // 2 * 2)
        focus_x = VisualAnalyzer(cancel_event=self.cancel_event).dominant_face_focus(
            video_path, highlight.start_sec, highlight.end_sec,
        )
        crop_x = min(max(0, int(focus_x * scaled_w - 540)), scaled_w - 1080)
        crop_y = max(0, (scaled_h - 1920) // 2)
        # Recorte vertical con prioridad a la persona principal. Es un enfoque
        # local inspirado en AutoFlip: si no hay rostro, conserva el centro.
        fc = f"[0:v]scale={scaled_w}:{scaled_h},crop=1080:1920:{crop_x}:{crop_y},setsar=1[v]"
        cmd = ["ffmpeg", "-y", "-ss", f"{highlight.start_sec:.2f}", "-i", str(video_path), "-t", f"{duration:.2f}",
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-af", "loudnorm=I=-16:LRA=11:TP=-1.5", *ENC_FINAL, "-c:a", "aac",
               "-movflags", "+faststart", str(out_path)]
        return out_path if self._run(cmd, f"Short 9:16 '{highlight.title}'") and out_path.exists() else None
