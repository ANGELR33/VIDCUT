"""Extractor Inteligente de Clips y Reels Virales 9:16 con Subtítulos y Títulos Enganchables.

Analiza la estructura completa del video (guion, escenas, datos clave, clímax y picos de atención)
para identificar dinámicamente TODOS los momentos con alto potencial viral (sin limitar a 3).
Genera clips verticales en formato 9:16 (1080x1920) optimizados para TikTok, YouTube Shorts e Instagram Reels,
con subtítulos quemados en zona segura y titulares magnéticos (hook titles) con ortografía impecable.
"""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings
from core.llm import LLMClient, safe_log
from core.project_store import ProjectStore
from utils.file_manager import FileManager


def parse_srt_time(ts_str: str) -> float:
    """Convierte un timestamp SRT '00:01:23,456' a segundos (float)."""
    ts_str = ts_str.strip().replace(",", ".")
    parts = ts_str.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return float(ts_str)


def format_srt_time(sec: float) -> str:
    """Convierte segundos a formato SRT '00:01:23,456'."""
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@dataclass
class ViralClipTarget:
    index: int
    title: str
    hook_type: str
    start_sec: float
    duration_sec: float
    scene_ids: List[int]
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ViralClipsExtractor:
    """Analizador y extractor de momentos virales con subtítulos y titulares de alto CTR."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.store = ProjectStore(task_id)
        self.workdir = self.store.workdir
        self.metadata_file = self.workdir / "extracted_clips_metadata.json"

    def get_existing_clips(self) -> List[Dict[str, Any]]:
        """Devuelve los clips ya generados leyendo los metadatos o escaneando disco."""
        if self.metadata_file.exists():
            try:
                data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    # Validar que los archivos existan en outputs o auto-reparar referencias
                    valid_clips = []
                    metadata_modified = False
                    for idx_item, c in enumerate(data, start=1):
                        fn = c.get("filename", "")
                        fp = settings.OUTPUTS_DIR / fn
                        if not fp.exists() or fp.stat().st_size < 30000:
                            # Buscar por índice de clip short_{task_id}_{idx}_*.mp4
                            cands = list(settings.OUTPUTS_DIR.glob(f"short_{self.task_id}_{idx_item}_*.mp4"))
                            if cands:
                                best = max(cands, key=lambda p: p.stat().st_mtime)
                                c["filename"] = best.name
                                c["url"] = f"/outputs/{best.name}"
                                fp = best
                                metadata_modified = True
                        if fp.exists() and fp.stat().st_size > 30000:
                            c["size_mb"] = round(fp.stat().st_size / (1024 * 1024), 2)
                            valid_clips.append(c)
                    if metadata_modified and valid_clips:
                        try:
                            self.metadata_file.write_text(json.dumps(valid_clips, ensure_ascii=False, indent=2), encoding="utf-8")
                        except Exception:
                            pass
                    if valid_clips:
                        return valid_clips
            except Exception as e:
                safe_log(f"[ClipsExtractor] Error leyendo metadata de clips: {e}")

        # Escanear disco de respaldo
        clips = []
        prefix = f"short_{self.task_id}_"
        if settings.OUTPUTS_DIR.exists():
            for p in sorted(settings.OUTPUTS_DIR.glob(f"{prefix}*.mp4"), key=lambda x: x.stat().st_mtime):
                try:
                    stem = p.stem[len(prefix):]
                    clean_name = re.sub(r"^\d+_", "", stem).replace("_", " ").strip() or p.stem
                    dur = 30.0
                    try:
                        p_res = subprocess.run(
                            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                            capture_output=True, text=True, check=True, timeout=5
                        )
                        dur = float(p_res.stdout.strip())
                    except Exception:
                        pass
                    clips.append({
                        "filename": p.name,
                        "name": clean_name,
                        "url": f"/outputs/{p.name}",
                        "duration": round(dur, 1),
                        "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                        "hook_type": "Momento Viral",
                        "has_subtitles": True,
                    })
                except Exception:
                    continue
        return clips

    def _resolve_master_video(self) -> Path:
        """Encuentra el archivo master final del proyecto."""
        master_file = settings.OUTPUTS_DIR / f"{self.task_id}_master.mp4"
        if master_file.exists():
            return master_file
        document = self.store.read()
        res = document.get("result") or {}
        cand = Path(res.get("output_file") or "")
        if cand.exists() and cand.is_file():
            return cand
        prev = Path(document.get("preview_file") or "")
        if prev.exists() and prev.is_file():
            return prev
        raise FileNotFoundError(f"Video master del proyecto {self.task_id} no encontrado.")

    def _probe_duration(self, video_path: Path) -> float:
        try:
            res = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
                capture_output=True, text=True, check=True, timeout=10
            )
            return float(res.stdout.strip())
        except Exception:
            return 60.0

    def _load_scenes(self) -> List[Dict[str, Any]]:
        """Carga la lista de escenas del plan de producción con sus duraciones reales."""
        plan_path = self.workdir / "broadcast_plan.json"
        scenes = []
        if plan_path.exists():
            try:
                plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                scenes = plan_data.get("scenes", [])
            except Exception:
                pass
        if not scenes:
            document = self.store.read()
            plan = document.get("plan") or {}
            scenes = plan.get("scenes", [])
        return scenes

    def _compile_or_get_full_srt(self, scenes: List[Dict[str, Any]]) -> Optional[Path]:
        """Obtiene o compila el archivo completo de subtítulos del proyecto."""
        full_srt = self.workdir / "full_subtitles.srt"
        if full_srt.exists() and full_srt.stat().st_size > 100:
            return full_srt

        all_srt_blocks = []
        sub_index = 1
        cum_offset = 0.0

        for sc in scenes:
            sid = sc.get("scene_id", 1)
            sc_dir = self.workdir / f"scene_{sid}"
            srt_path = sc_dir / "scene_subtitles.srt"
            scene_mp4 = sc_dir / f"scene_{sid}.mp4"

            sc_dur = 0.0
            if scene_mp4.exists():
                try:
                    sc_dur = FileManager.get_media_metadata(scene_mp4).get("duration", 0.0)
                except Exception:
                    pass
            if sc_dur <= 0:
                sc_dur = float(sc.get("duration_est") or 15.0)

            if srt_path.exists():
                try:
                    raw_srt = srt_path.read_text(encoding="utf-8").strip()
                    if raw_srt:
                        blocks = raw_srt.split("\n\n")
                        for blk in blocks:
                            lns = [l.strip() for l in blk.splitlines() if l.strip()]
                            if len(lns) >= 3 and "-->" in lns[1]:
                                tp = lns[1].split("-->")
                                t_start = parse_srt_time(tp[0]) + cum_offset
                                t_end = parse_srt_time(tp[1]) + cum_offset
                                text_content = "\n".join(lns[2:])
                                all_srt_blocks.append(
                                    f"{sub_index}\n{format_srt_time(t_start)} --> {format_srt_time(t_end)}\n{text_content}"
                                )
                                sub_index += 1
                except Exception as _e:
                    safe_log(f"[ClipsExtractor] Error compilando SRT escena {sid}: {_e}")
            cum_offset += sc_dur

        if all_srt_blocks:
            try:
                full_srt.write_text("\n\n".join(all_srt_blocks), encoding="utf-8")
                return full_srt
            except Exception as _e:
                safe_log(f"[ClipsExtractor] Error guardando full_subtitles.srt: {_e}")
        return None

    def _slice_subtitles(self, full_srt_path: Path, start_sec: float, dur_sec: float, out_srt_path: Path) -> bool:
        """Extrae y re-sincroniza los subtítulos para el rango exacto del clip."""
        if not full_srt_path or not full_srt_path.exists():
            return False

        try:
            content = full_srt_path.read_text(encoding="utf-8").strip()
            if not content:
                return False

            blocks = content.split("\n\n")
            end_sec = start_sec + dur_sec
            clip_blocks = []
            idx = 1

            for blk in blocks:
                lns = [l.strip() for l in blk.splitlines() if l.strip()]
                if len(lns) >= 3 and "-->" in lns[1]:
                    tp = lns[1].split("-->")
                    sub_st = parse_srt_time(tp[0])
                    sub_en = parse_srt_time(tp[1])

                    # Comprobar solapamiento
                    if sub_st < end_sec and sub_en > start_sec:
                        rel_st = max(0.0, sub_st - start_sec)
                        rel_en = min(dur_sec, sub_en - start_sec)
                        if (rel_en - rel_st) >= 0.25:
                            text_content = "\n".join(lns[2:])
                            clip_blocks.append(
                                f"{idx}\n{format_srt_time(rel_st)} --> {format_srt_time(rel_en)}\n{text_content}"
                            )
                            idx += 1

            if clip_blocks:
                out_srt_path.write_text("\n\n".join(clip_blocks), encoding="utf-8")
                return True
        except Exception as _e:
            safe_log(f"[ClipsExtractor] Error al recortar subtítulos para clip: {_e}")
        return False

    def _identify_viral_moments_ai(
        self,
        scenes: List[Dict[str, Any]],
        total_duration: float,
        project_topic: str,
    ) -> List[ViralClipTarget]:
        """Utiliza IA para analizar todas las escenas e identificar dinámicamente cada momento viral."""
        # 1. Calcular timestamps acumulados reales por escena
        scene_timings = []
        acc = 0.0
        for idx, sc in enumerate(scenes):
            sid = sc.get("scene_id", idx + 1)
            mp4_file = self.workdir / f"scene_{sid}" / f"scene_{sid}.mp4"
            dur = 0.0
            if mp4_file.exists():
                try:
                    dur = FileManager.get_media_metadata(mp4_file).get("duration", 0.0)
                except Exception:
                    pass
            if dur <= 0:
                dur = float(sc.get("duration_est") or 18.0)

            scene_timings.append({
                "scene_id": sid,
                "index": idx,
                "name": sc.get("name", f"Escena {sid}"),
                "type": sc.get("type", "video_reaction"),
                "emotion": sc.get("emotion", "excited"),
                "speech": (sc.get("speech") or "")[:200],
                "start_sec": acc,
                "duration_sec": dur,
                "headline": (sc.get("card") or {}).get("headline") if isinstance(sc.get("card"), dict) else "",
                "stat": (sc.get("card") or {}).get("stat") if isinstance(sc.get("card"), dict) else "",
            })
            acc += dur

        # 2. Intentar análisis con LLM
        targets: List[ViralClipTarget] = []
        try:
            llm = LLMClient()
            brief_scenes = [
                {
                    "idx": s["index"],
                    "scene_id": s["scene_id"],
                    "name": s["name"],
                    "type": s["type"],
                    "emotion": s["emotion"],
                    "stat": s["stat"],
                    "speech_summary": s["speech"][:120],
                    "duration": round(s["duration_sec"], 1),
                }
                for s in scene_timings
            ]

            prompt = f"""Eres un estratega y editor senior de contenido viral de YouTube Shorts, TikTok e Instagram Reels.
Tema del video: "{project_topic}"
Duración total: {int(total_duration)}s.

Escenas producidas en el video:
{json.dumps(brief_scenes, ensure_ascii=False, indent=2)}

TU MISIÓN:
Analiza la lista completa de escenas e IDENTIFICA TODOS LOS MOMENTOS VIRALES con alto potencial de retención y 'ganas de ver'.
NO te limites a 3 clips: si el video tiene 5, 7 o 9 momentos llamativos, extráelos TODOS.

Para cada momento viral:
1. "scene_indices": Lista con los índices de escena que abarca.
   - Si una escena dura entre 18s y 55s, puede ser un clip por sí sola (ej: [0]).
   - Si una escena es breve (< 18s), combínala con la escena siguiente para que el clip dure entre 22s y 50s (ej: [1, 2]).
2. "title": Título enganchable ("Viral Hook Title") de ALTO CTR para TikTok/Shorts (máximo 42 caracteres, en español, ortografía perfecta, sin comillas).
   Ejemplos: "¡El Dato Que Nadie Esperaba!", "¿Por Qué Ocultaron Esto?", "La Revelación Definitiva", "El Error Que Costó Millones".
3. "hook_type": Uno de: "Gancho Inicial", "Dato Revelador", "Giro Inesperado", "Polémica & Debate", "Clímax Viral", "Conclusión Épica".

RESPONDE EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO:
{{
  "viral_clips": [
    {{
      "scene_indices": [0],
      "title": "Título Enganchable 1",
      "hook_type": "Gancho Inicial"
    }}
  ]
}}
"""
            raw = llm.generate(prompt, json_mode=True, deadline_sec=25.0)
            from utils.json_validator import JSONValidator
            parsed = JSONValidator.extract_and_parse(raw)
            clips_plan = parsed.get("viral_clips", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])

            if isinstance(clips_plan, list) and len(clips_plan) >= 1:
                from core.youtube_title_optimizer import clean_title_formatting, enforce_youtube_character_limit
                for c_idx, c_item in enumerate(clips_plan):
                    sc_indices = c_item.get("scene_indices", [])
                    if not sc_indices:
                        continue
                    valid_indices = [i for i in sc_indices if 0 <= i < len(scene_timings)]
                    if not valid_indices:
                        continue

                    start_t = scene_timings[valid_indices[0]]["start_sec"]
                    dur_t = sum(scene_timings[i]["duration_sec"] for i in valid_indices)
                    dur_t = min(58.0, max(12.0, dur_t))

                    raw_t = c_item.get("title") or scene_timings[valid_indices[0]]["name"]
                    clean_t = enforce_youtube_character_limit(clean_title_formatting(raw_t), max_chars=45)
                    hook_t = c_item.get("hook_type") or "Momento Viral"

                    targets.append(
                        ViralClipTarget(
                            index=c_idx + 1,
                            title=clean_t,
                            hook_type=hook_t,
                            start_sec=round(start_t, 2),
                            duration_sec=round(dur_t, 2),
                            scene_ids=[scene_timings[i]["scene_id"] for i in valid_indices],
                            summary=scene_timings[valid_indices[0]]["speech"][:90],
                        )
                    )

                if targets:
                    safe_log(f"[ClipsExtractor] ✓ IA identificó {len(targets)} momentos virales óptimos.")
                    return targets

        except Exception as _ai_err:
            safe_log(f"[ClipsExtractor] Fallback heurístico inteligente por aviso en IA: {_ai_err}")

        # 3. Fallback heurístico inteligente (extrae TODOS los momentos de alto valor sin límite artificial de 3)
        targets = []
        i = 0
        clip_num = 1
        while i < len(scene_timings):
            sc = scene_timings[i]
            cur_st = sc["start_sec"]
            cur_dur = sc["duration_sec"]
            used_ids = [sc["scene_id"]]

            # Si la escena dura menos de 18s y hay otra escena siguiente, agruparlas
            if cur_dur < 18.0 and (i + 1) < len(scene_timings):
                next_sc = scene_timings[i + 1]
                cur_dur += next_sc["duration_sec"]
                used_ids.append(next_sc["scene_id"])
                i += 1

            cur_dur = min(55.0, max(14.0, cur_dur))

            # Determinar tipo de gancho y titular
            if clip_num == 1:
                h_type = "Gancho Inicial"
                t_str = "¡El Enigma Que Nadie Vio!"
            elif sc.get("stat"):
                h_type = "Dato Revelador"
                t_str = f"La Cifra Oculta: {sc.get('stat')}"
            elif sc["type"] == "chat_debate":
                h_type = "Polémica & Debate"
                t_str = "El Gran Debate Que Divide a Todos"
            elif sc["emotion"] in ("surprised", "skeptical"):
                h_type = "Giro Inesperado"
                t_str = "El Giro Que Cambia la Historia"
            elif i >= len(scene_timings) - 1:
                h_type = "Conclusión Épica"
                t_str = "La Conclusión Que Debes Conocer"
            else:
                h_type = "Pico Viral"
                t_str = sc["name"][:35]

            targets.append(
                ViralClipTarget(
                    index=clip_num,
                    title=t_str,
                    hook_type=h_type,
                    start_sec=round(cur_st, 2),
                    duration_sec=round(cur_dur, 2),
                    scene_ids=used_ids,
                    summary=sc["speech"][:90],
                )
            )
            clip_num += 1
            i += 1

        return targets

    def extract_all_clips(self, force: bool = False) -> List[Dict[str, Any]]:
        """Ejecuta el análisis y renderizado de todos los clips virales con subtítulos y formato 9:16."""
        master_file = self._resolve_master_video()
        total_duration = self._probe_duration(master_file)

        document = self.store.read()
        project_topic = (
            (document.get("options") or {}).get("topic")
            or (document.get("result") or {}).get("topic")
            or document.get("original_name")
            or "Video KAI"
        )

        scenes = self._load_scenes()
        safe_log(f"[ClipsExtractor] Analizando estructura de {len(scenes)} escenas para '{project_topic}'...")

        # 1. Identificar todos los momentos virales dinámicamente
        targets = self._identify_viral_moments_ai(scenes, total_duration, project_topic)
        if not targets:
            # Fallback simple si no hay escenas
            chunk_len = 30.0
            num_chunks = max(1, int(total_duration // chunk_len))
            for idx in range(num_chunks):
                targets.append(
                    ViralClipTarget(
                        index=idx + 1,
                        title=f"Momento Viral #{idx + 1}",
                        hook_type="Pico Viral",
                        start_sec=idx * chunk_len,
                        duration_sec=min(chunk_len, total_duration - (idx * chunk_len)),
                        scene_ids=[idx + 1],
                    )
                )

        # 2. Compilar subtítulos del proyecto
        full_srt = self._compile_or_get_full_srt(scenes)
        font_p = FileManager.get_system_font_path()
        font_param = f"fontfile='{font_p}':" if font_p else ""

        created_clips: List[Dict[str, Any]] = []

        for target in targets:
            idx = target.index
            st = target.start_sec
            dur = target.duration_sec
            title = target.title
            hook_type = target.hook_type

            # Slug seguro y normalizado a ASCII puro para evitar errores de codificación en Windows, URLs y descargas
            norm_ascii = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
            clean_tag = re.sub(r"[^\w\s-]", "", norm_ascii).strip()[:30] or f"Clip_{idx}"
            safe_slug = re.sub(r"[\s_-]+", "_", clean_tag)[:25].strip("_")
            out_name = f"short_{self.task_id}_{idx}_{safe_slug}.mp4"
            out_path = settings.OUTPUTS_DIR / out_name

            # Subtítulos específicos de este clip
            clip_srt = self.workdir / f"clip_{idx}_subs.srt"
            has_subs = False
            if full_srt and full_srt.exists():
                has_subs = self._slice_subtitles(full_srt, st, dur, clip_srt)

            # Si se fuerza o el clip no existe en disco, renderizar con FFmpeg
            if force or not out_path.exists() or out_path.stat().st_size < 30000:
                clean_hdr = clean_tag.upper().replace("'", "").replace(":", "-")

                # Construir filtros FFmpeg: Escalar a 1080x1920 (9:16), banner de gancho y subtítulos virales
                filters = [
                    "scale=1080:1920:force_original_aspect_ratio=increase",
                    "crop=1080:1920",
                    "setsar=1",
                    # Banner superior con el titular enganchable
                    f"drawtext={font_param}text='{clean_hdr}':fontcolor=white:fontsize=36:x=(w-tw)/2:y=180:box=1:boxcolor=black@0.80:boxborderw=16",
                    f"drawtext={font_param}text='{hook_type.upper()}':fontcolor=white@0.70:fontsize=20:x=(w-tw)/2:y=245",
                ]

                # Si hay subtítulos sincronizados, quemarlos en la zona segura inferior (lower-third)
                if has_subs and clip_srt.exists() and clip_srt.stat().st_size > 20:
                    esc_srt = str(clip_srt.resolve()).replace("\\", "/").replace(":", "\\:")
                    # Tipografía Segoe UI Black en blanco nítido, trazo oscuro limpio y posición inferior segura (MarginV=55)
                    force_style = (
                        "FontName=Segoe UI Black,Bold=1,PrimaryColour=&H00FFFFFF,SecondaryColour=&H00F0F0F0,"
                        "BorderStyle=1,Outline=2.5,Shadow=1.5,OutlineColour=&H00000000,FontSize=16,MarginV=55,MarginL=60,MarginR=60,Alignment=2"
                    )
                    filters.append(f"subtitles='{esc_srt}':force_style='{force_style}'")

                vf_chain = ",".join(filters)
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{st:.2f}",
                    "-t", f"{dur:.2f}",
                    "-i", str(master_file),
                    "-vf", vf_chain,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(out_path)
                ]

                try:
                    safe_log(f"[ClipsExtractor] Renderizando clip #{idx}: «{title}» ({dur}s)...")
                    subprocess.run(cmd, capture_output=True, check=True, timeout=120)
                except Exception as exc:
                    safe_log(f"[ClipsExtractor] Error renderizando clip #{idx}: {exc}")
                    # Reintento sin filtro de subtítulos si falló libass
                    if has_subs:
                        try:
                            fallback_filters = [f for f in filters if not f.startswith("subtitles=")]
                            cmd_fallback = [
                                "ffmpeg", "-y",
                                "-ss", f"{st:.2f}",
                                "-t", f"{dur:.2f}",
                                "-i", str(master_file),
                                "-vf", ",".join(fallback_filters),
                                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                                "-c:a", "aac", "-b:a", "128k",
                                "-movflags", "+faststart",
                                str(out_path)
                            ]
                            subprocess.run(cmd_fallback, capture_output=True, check=True, timeout=90)
                        except Exception as e2:
                            safe_log(f"[ClipsExtractor] Fallback también falló para clip #{idx}: {e2}")
                            continue

            if out_path.exists() and out_path.stat().st_size > 30000:
                created_clips.append({
                    "filename": out_name,
                    "name": title,
                    "url": f"/outputs/{out_name}",
                    "duration": round(dur, 1),
                    "size_mb": round(out_path.stat().st_size / (1024 * 1024), 2),
                    "hook_type": hook_type,
                    "has_subtitles": has_subs,
                })

        # 3. Guardar metadatos enriquecidos de los clips en el workdir del proyecto
        try:
            self.metadata_file.write_text(json.dumps(created_clips, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as _e:
            safe_log(f"[ClipsExtractor] Aviso guardando metadata de clips: {_e}")

        safe_log(f"[ClipsExtractor] ✓ Finalizado: {len(created_clips)} clips verticales 9:16 listos con subtítulos y ganchos.")
        return created_clips
