import asyncio
import contextvars
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from config.settings import settings
from cancellation import CancellationRequested
from core.asset_providers import AssetProviderFactory  # noqa: F401  (usado por AssetOrchestrator)
from core.card_renderer import InfoCardRenderer
from core.fact_checker import FactChecker
from core.gemini_analyzer import GeminiVideoAnalyzer
from core.llm import LLMClient, safe_log
from core.models import ActionType, VideoEditingPlan
from core.project_store import ProjectStore, editor_snapshot
from core.editorial_qa import audit_plan
from core.filler_cutter import apply_filler_cuts, clean_captions, enabled as filler_cut_enabled, find_fillers
from core.hook_scorer import rank_highlights, trim_leading_filler
from core.quality_gate import PlanQualityGate
from core.short_snapper import snap_highlights
from core.orchestrator import AssetOrchestrator
from core.broll_sync import resync_broll_to_captions
from core.render_engine import VideoRenderEngine
from core.run_log import RunLog
from core.silence_detector import SilenceDetector
from core.timeline import TimelineMapper
from core.transcriber import WhisperTranscriber, highlight_terms_from_plan
from core.visual_analysis import VisualAnalyzer
from utils.file_manager import FileManager

StateCb = Callable[..., None]


class PipelineOptions:
    def __init__(self, silence_threshold: float = 1.5, broll: bool = True, captions: bool = True,
                 shorts: bool = True, cards: bool = True, voice: str = "es-MX-JorgeNeural"):
        self.silence_threshold = silence_threshold
        self.broll = broll
        self.captions = captions
        self.shorts = shorts
        self.cards = cards
        self.voice = voice


class VideoPipeline:
    """
    Orquesta el flujo completo:
    Gemini (plan) -> silencios reales (audio) -> [B-Roll || verificación web + tarjetas] -> render -> subtítulos -> Short.
    """

    def __init__(self, task_id: str, input_file: Path, options: PipelineOptions, on_state: StateCb,
                 cancel_event: Optional[threading.Event] = None,
                 project_store: Optional[ProjectStore] = None,
                 render_lock: Optional[asyncio.Lock] = None):
        self.task_id = task_id
        self.input_file = input_file
        self.opt = options
        self.on_state = on_state
        self.cancel_event = cancel_event or threading.Event()
        self.project_store = project_store or ProjectStore(task_id)
        self.render_lock = render_lock
        self.workdir = self.project_store.workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.runlog: Optional[RunLog] = None

    def _state(self, step: str, progress: float, message: str, **extra: Any) -> None:
        if self.runlog and not extra.get("heartbeat"):
            self.runlog.on_state(step, message)
        self.on_state(step, progress, message, **extra)

    def _publish_plan(self, plan: VideoEditingPlan, step: str, progress: float, message: str) -> None:
        """Guarda una versión editable y actualiza el editor mientras trabaja."""
        self.project_store.save_plan(plan, status=step)
        self._state(step, progress, message, editor=editor_snapshot(plan))

    async def _run_with_heartbeat(self, loop, fn, step: str, progress: float,
                                  activity: str, last_signal=None, interval: int = 10):
        """Mantiene visible una espera real cuando una tarea síncrona ocupa el worker."""
        if self.cancel_event.is_set():
            raise CancellationRequested()
        # copy_context: el hilo del executor hereda la ejecución activa del RunLog.
        future = loop.run_in_executor(None, contextvars.copy_context().run, fn)
        started = time.monotonic()
        while not future.done():
            cancelling = self.cancel_event.is_set()
            await asyncio.wait((future,), timeout=1 if cancelling else interval)
            if future.done():
                break
            if self.cancel_event.is_set():
                self._state("cancelling", progress,
                            "Cancelación solicitada; esperando que termine la operación actual de forma segura.")
                continue
            elapsed = int(time.monotonic() - (last_signal[0] if last_signal else started))
            if elapsed >= interval:
                self._state(
                    step,
                    progress,
                    activity,
                    heartbeat=True,
                    waiting_seconds=elapsed,
                )
        if self.cancel_event.is_set():
            try:
                future.result()
            except Exception:
                pass
            raise CancellationRequested()
        return future.result()

    async def run(self) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        self.runlog = RunLog.start(
            self.workdir, content_type="video_editado", mechanism="VideoPipeline",
            run_id=self.task_id,
            meta={"input": self.input_file.name, "broll": self.opt.broll, "cards": self.opt.cards,
                  "captions": self.opt.captions, "shorts": self.opt.shorts,
                  "silence_threshold": self.opt.silence_threshold},
        )
        try:
            result = await self._run(loop)
        except CancellationRequested:
            self.runlog.finalize("cancelled")
            raise
        except BaseException as exc:
            self.runlog.error("run", f"{type(exc).__name__}: {exc}")
            self.runlog.finalize("failed")
            raise
        report = self.runlog.finalize("completed", outputs={
            k: result.get(k) for k in ("master_video_url", "silences_cut_count", "brolls_count",
                                       "cards_shown", "captions_count", "model_used")
        })
        result["run_summary"] = {
            "run_id": report["run_id"], "duration_sec": report["duration_sec"],
            "estimated_cost_usd": report["cost"]["estimated_total"],
            "cost_partial": report["cost"]["partial"],
            "warnings": report["issue_counts"]["warnings"], "errors": report["issue_counts"]["errors"],
            "files": ["run_report.md", "run_report.json", "run_events.jsonl"],
        }
        return result

    async def _run(self, loop) -> Dict[str, Any]:
        opt = self.opt
        self._state("inspect", 1.0, "Leyendo duración y resolución del video con FFprobe.")
        meta = await self._run_with_heartbeat(
            loop, lambda: FileManager.get_media_metadata(self.input_file, self.cancel_event),
            "inspect", 1.0, "FFprobe está leyendo la duración y resolución",
        )
        duration = float(meta.get("duration") or 0.0)
        if duration <= 0:
            raise RuntimeError("No se pudo leer la duración del video. ¿El archivo está dañado?")
        frame_w, frame_h = meta.get("width") or 1920, meta.get("height") or 1080

        # Los videos grandes se reducen solo para Gemini. El original no se
        # modifica y se usa más adelante para los cortes y la exportación.
        analysis_file = self.input_file
        if self.input_file.stat().st_size > 150 * 1024 * 1024:
            proxy = self.workdir / "analysis_proxy.mp4"
            analysis_file = FileManager.reusable_analysis_proxy(self.input_file, proxy)
            if analysis_file:
                self._state("inspect", 4.0, "Reutilizando la copia ligera ya preparada para este proyecto.")
            else:
                self._state("inspect", 3.0,
                            "Creando una copia ligera para analizar el contenido sin subir el original completo.")
                analysis_file = await self._run_with_heartbeat(
                    loop,
                    lambda: FileManager.create_analysis_proxy(self.input_file, proxy, self.cancel_event),
                    "inspect", 3.0, "FFmpeg está creando la copia ligera para el análisis",
                )
            proxy_mb = analysis_file.stat().st_size / 1024 / 1024
            self._state("inspect", 5.0,
                        f"Copia de análisis lista ({proxy_mb:.0f} MB). El render final conservará el video original.")
            self.project_store.set_status("inspect", preview_file=str(analysis_file.resolve()))
            self._state("inspect", 5.0, "La previsualización ligera está lista para el editor.",
                        preview_url=f"/api/projects/{self.task_id}/preview")
        else:
            self.project_store.set_status("inspect", preview_file=str(self.input_file.resolve()))
            self._state("inspect", 5.0, "El archivo está listo para previsualizar en el editor.",
                        preview_url=f"/api/projects/{self.task_id}/preview")

        # ---- 0.5 Whisper Transcription (Full Text for LLM and Subtitles) ----
        self._state("transcribe", 2.0, "Preparando transcripción local para apoyar el análisis.")
        transcript_text = None
        whisper_caps = None
        whisper_words: list = []
        transcriber = WhisperTranscriber()
        try:
            whisper_caps = await self._run_with_heartbeat(
                loop, lambda: transcriber.transcribe(self.input_file, [], cancel_event=self.cancel_event),
                "transcribe", 2.0, "Whisper está transcribiendo el audio localmente",
            )
            whisper_words = list(transcriber.last_words)
            if whisper_caps:
                transcript_text = "\n".join(f"[{c.start_sec:.1f}-{c.end_sec:.1f}] {c.text}" for c in whisper_caps)
                self._state("transcribe", 5.0, f"Transcripción local lista ({len(whisper_caps)} frases).")
                if self.runlog:
                    self.runlog.record_service("whisper_local", units=duration, unit_name="s de audio", cost_usd=0.0)
        except CancellationRequested:
            raise
        except Exception as exc:
            safe_log(f"[Pipeline] Error en Whisper pre-análisis: {exc}")
            self._state("transcribe", 5.0, "Continuando análisis directamente con Gemini.")

        # ---- 1. Gemini ----
        llm = LLMClient()
        self._state("gemini", 8.0, "Enviando el video y las instrucciones a Gemini para proponer cortes y momentos clave.")
        analyzer = GeminiVideoAnalyzer(llm=llm)
        # Las tarjetas disparan búsquedas, contrastes y composición. Un máximo
        # editorial evita que un clip corto quede esperando decenas de consultas
        # y sigue cubriendo los momentos realmente relevantes.
        calculated_cards = min(10, max(2, round(duration / 30))) if opt.cards else 0
        gemini_signal = [time.monotonic()]

        def gemini_progress(message: str) -> None:
            gemini_signal[0] = time.monotonic()
            self._state("gemini", 12.0, message)

        plan: VideoEditingPlan = await self._run_with_heartbeat(
            loop, lambda: analyzer.analyze_video(
                analysis_file, opt.silence_threshold,
                max_cards=calculated_cards,
                progress=gemini_progress,
                transcript=transcript_text,
                cancel_event=self.cancel_event,
            ),
            "gemini", 12.0, "Gemini está analizando el video",
            last_signal=gemini_signal,
        )
        self._publish_plan(plan, "gemini", 25.0,
                    f"Plan recibido: {len(plan.timeline)} tramos, {len(plan.b_rolls)} apoyos visuales, "
                    f"{len(plan.info_cards)} datos y {len(plan.highlights)} momentos para Shorts.")
        if not opt.broll:
            plan.b_rolls = []
        if not opt.cards:
            plan.info_cards = []
        if not opt.captions:
            plan.captions = []
        if not opt.shorts:
            plan.highlights = []

        # ---- 2. Silencios reales del audio (sobrescribe la estimación de Gemini) ----
        self._state("silence", 26.0, f"Analizando la pista de audio; buscando pausas mayores a {opt.silence_threshold:.1f} s.")
        detected = await self._run_with_heartbeat(
            loop, lambda: SilenceDetector().build_timeline(
                self.input_file, duration, opt.silence_threshold, cancel_event=self.cancel_event),
            "silence", 26.0, "FFmpeg está recorriendo la pista de audio",
        )
        if detected:
            plan.timeline = detected
            cut_count = sum(1 for segment in detected if segment.action == ActionType.CUT_SILENCE)
            self._state("silence", 30.0, f"Audio analizado: {cut_count} pausas cumplen el umbral y se marcaron para corte.")
        else:
            safe_log("[Pipeline] No se pudo analizar el audio; se usa la línea de tiempo de Gemini.")
            self._state("silence", 30.0, "No se detectaron pausas con FFmpeg; se conserva la propuesta de Gemini.")
        # ---- 2.1 Muletillas y tartamudeos (usa los tiempos por palabra de Whisper) ----
        filler_report = None
        if whisper_words and filler_cut_enabled():
            try:
                fillers = find_fillers(whisper_words)
                plan.timeline, filler_report = apply_filler_cuts(plan.timeline, fillers, duration)
                if filler_report["applied"]:
                    self._state("silence", 30.5,
                                f"Se cortaron {filler_report['applied']} muletillas o tartamudeos "
                                f"({filler_report['seconds_cut']:.1f} s).")
                if self.runlog:
                    self.runlog.count("muletillas_cortadas", filler_report["applied"])
                    self.runlog.event("silence", f"Muletillas: {filler_report['applied']} de {filler_report['detected']} detectadas",
                                      **{k: v for k, v in filler_report.items() if k != "detected"})
            except Exception as exc:
                safe_log(f"[Filler] No se pudieron cortar muletillas: {exc}")
        plan.total_original_duration_sec = duration
        self._publish_plan(plan, "silence", 30.0, "La línea de tiempo se actualizó con las pausas detectadas.")

        # ---- 2.5 Sincronización y Subtítulos ----
        if whisper_caps:
            import re
            terms = highlight_terms_from_plan(plan)
            # Asignar highlight_words a whisper_caps
            for c in whisper_caps:
                hl = [w.strip(" .,;:!?¡¿\"'") for w in c.text.split() if w.strip(" .,;:!?¡¿\"'").lower() in terms]
                if hl:
                    c.highlight_words = hl[:2]
            
            # Sincronizar info_cards con Whisper!
            for card in plan.info_cards:
                card_words = set(re.findall(r"\w+", (card.headline + " " + card.claim).lower()))
                best_match = None
                best_score = 0
                for cap in whisper_caps:
                    if abs(cap.start_sec - card.start_sec) > 15: continue
                    cap_words = set(re.findall(r"\w+", cap.text.lower()))
                    score = len(card_words & cap_words)
                    if score > best_score:
                        best_score = score
                        best_match = cap.start_sec
                if best_match is not None and best_score > 0:
                    safe_log(f"[Sync] Tarjeta '{card.headline}' ajustada de {card.start_sec} a {best_match}")
                    card.start_sec = best_match
                    card.end_sec = best_match + 5.0
                    
            # Los apoyos visuales también se alinean con la voz real (Gemini suele errar 1-2 s).
            try:
                moved = resync_broll_to_captions(plan.b_rolls, whisper_caps)
                if moved:
                    safe_log(f"[Sync] {len(moved)} B-Roll realineados con la transcripción.")
                    if self.runlog:
                        self.runlog.count("broll_resincronizados", len(moved))
                        self.runlog.event("sync", f"{len(moved)} B-Roll realineados con Whisper", adjustments=moved)
            except Exception as exc:
                safe_log(f"[Sync] No se pudo realinear el B-Roll: {exc}")

            if filler_cut_enabled():
                clean_captions(whisper_caps)  # los subtítulos no muestran lo que ya no se oye
            plan.captions = whisper_caps

        # ---- 2.6 Lectura visual local (cortes de plano + lado del hablante) ----
        # Se ejecuta sobre la copia ligera cuando existe. No consume Gemini ni
        # altera los tiempos: las tarjetas siguen entrando al decir la frase.
        self._state("visual", 31.0, "Detectando cambios de plano y el lado del hablante para ubicar las tarjetas.")
        visual = VisualAnalyzer(cancel_event=self.cancel_event)
        scene_cuts = await self._run_with_heartbeat(
            loop, lambda: visual.detect_scene_cuts(analysis_file),
            "visual", 31.0, "PySceneDetect está buscando cambios de plano",
        )
        positioned_cards = await self._run_with_heartbeat(
            loop, lambda: visual.place_cards_away_from_speaker(analysis_file, plan.info_cards),
            "visual", 31.0, "OpenCV está comprobando dónde aparece el hablante",
        )
        self._state(
            "visual", 32.0,
            f"Análisis visual listo: {len(scene_cuts)} cambios de plano y {positioned_cards} tarjetas ubicadas fuera del hablante.",
            scene_cuts=scene_cuts,
        )
        self._publish_plan(plan, "visual", 32.0, "Las tarjetas ya respetan el encuadre detectado.")

        # ---- 3. B-Roll y verificación web en paralelo ----
        self._state("enrich", 32.0, "Investigando fuentes y buscando recursos visuales para los momentos seleccionados.")
        tasks = []
        if plan.b_rolls:
            def asset_progress(event: str, data: Dict[str, Any]) -> None:
                concept = data.get("concept", data.get("cue_id", "recurso"))
                if event == "broll_downloading":
                    message = f"Buscando B-Roll para «{concept}» en los proveedores configurados."
                elif event == "broll_completed":
                    message = f"B-Roll descargado para «{concept}» ({data.get('provider', 'proveedor web')})."
                elif event == "broll_rejected":
                    message = (f"Candidato de {data.get('provider', 'un proveedor')} descartado para «{concept}» "
                               f"por poca relevancia ({data.get('score')}). Probando otra fuente.")
                else:
                    message = f"No se encontró B-Roll para «{concept}»; se omitirá ese apoyo."
                self._state("enrich", 32.0, message)

            # La frase exacta del hablante es lo que el filtro de relevancia compara con la imagen.
            for cue in plan.b_rolls:
                if not cue.spoken_phrase and whisper_caps:
                    overlapping = [c.text for c in whisper_caps
                                   if c.end_sec >= cue.start_sec - 0.5 and c.start_sec <= cue.end_sec + 0.5]
                    cue.spoken_phrase = " ".join(overlapping).strip()[:240]
            tasks.append(AssetOrchestrator(target_dir=self.workdir / "assets", llm=llm).process_all_brolls(
                plan, progress_callback=asset_progress
            ))
        if plan.info_cards:
            checker = FactChecker(llm, self.workdir)
            tasks.append(checker.verify_plan(plan, progress=lambda m: self._state("enrich", 32.0, m)))
        if tasks:
            pending = [asyncio.create_task(task) for task in tasks]
            try:
                while any(not task.done() for task in pending):
                    if self.cancel_event.is_set():
                        self._state("cancelling", 44.0,
                                    "Cancelación solicitada; deteniendo las búsquedas web activas.")
                        for task in pending:
                            task.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        raise CancellationRequested()
                    await asyncio.wait(pending, timeout=1)
                await asyncio.gather(*pending)
            except Exception:
                for task in pending:
                    if not task.done():
                        task.cancel()
                raise
        else:
            self._state("enrich", 44.0, "No hay B-Roll ni datos para contrastar; se omite la búsqueda web.")
        if self.runlog:
            for cue in plan.b_rolls:
                self.runlog.count(f"broll_{(cue.download_status or 'pending').lower()}")
            for card in plan.info_cards:
                self.runlog.count(f"tarjeta_{card.verdict}")
            self.runlog.count("tarjetas_planificadas", len(plan.info_cards))
            self.runlog.count("broll_planificados", len(plan.b_rolls))
        self._publish_plan(plan, "enrich", 44.0, "Investigación y recursos incorporados a la línea de tiempo.")

        # ---- 4. Tarjetas (solo las confirmadas) + fotos enmarcadas ----
        self._state("cards", 46.0, "Diseñando tarjetas informativas...")
        renderer = InfoCardRenderer(frame_w, frame_h)

        def design():
            renderer.render_all(plan.info_cards, self.workdir)
            for cue in plan.b_rolls:
                p = cue.local_file_path
                if cue.download_status == "COMPLETED" and p and Path(p).suffix.lower() not in (".mp4", ".mov", ".webm", ".mkv"):
                    framed = renderer.render_photo_frame(p, cue.concept, self.workdir / f"{cue.cue_id}_frame.png")
                    cue.frame_path = str(framed) if framed else None

        await self._run_with_heartbeat(loop, design, "cards", 47.0,
                                       "Diseñando tarjetas y preparando los apoyos visuales")

        # ---- 4.2 Narración y Avatar Reactivo Copiloto IA (Microsoft Neural TTS) ----
        self._state("cards", 47.5, "Preparando voz neural y animación reactiva para el avatar copiloto...")
        try:
            from core.avatar_narrator import AvatarNarrator
            from core.avatar_renderer import AvatarRenderer

            narrator = AvatarNarrator(voice=getattr(self.opt, "voice", "es-MX-JorgeNeural"))
            avatar_rnd = AvatarRenderer(badge_size=int(min(frame_w, frame_h) * 0.28))

            async def prepare_avatars():
                eligible = [
                    c for c in plan.info_cards
                    if c.enabled and c.verdict in ("supported", "contradicted", "insufficient")
                ]
                eligible.sort(key=lambda c: 0 if c.verdict == "contradicted" else (1 if c.stat_value else 2))
                for card in eligible[:4]:
                    if self.cancel_event and self.cancel_event.is_set():
                        raise CancellationRequested()
                    try:
                        if not card.avatar_spoken_text:
                            # Extraer contexto inmediato de la transcripción de Whisper alrededor del argumento
                            surrounding_context = ""
                            if plan.captions:
                                chunks = [
                                    c.text for c in plan.captions
                                    if (card.start_sec - 14.0) <= c.start_sec <= (card.start_sec + 4.0)
                                ]
                                surrounding_context = " ".join(chunks).strip()
                            card.avatar_spoken_text = await narrator.craft_dialogue_with_ai(
                                card, surrounding_context=surrounding_context, llm=llm
                            )
                        
                        audio_file = self.workdir / f"{card.card_id}_voice.mp3"
                        _p, dur = await narrator.synthesize(card.avatar_spoken_text, audio_file)
                        card.avatar_audio_path = str(audio_file)

                        video_file = self.workdir / f"{card.card_id}_avatar.webm"
                        # to_thread: mismo motivo que en server.run_export_task —
                        # el render del avatar es síncrono y bloqueaba el event loop.
                        rendered = await asyncio.to_thread(
                            avatar_rnd.render_reaction_clip, dur + 0.5, video_file, audio_path=audio_file
                        )
                        if rendered:
                            card.avatar_video_path = str(rendered)
                            card.avatar_enabled = True
                            # Sincronizar duración de la tarjeta para que permanezca visible mientras habla
                            card.display_duration_sec = max(card.display_duration_sec, dur + 1.0)
                            safe_log(f"[Pipeline] Avatar reactivo listo para {card.card_id} ({dur:.1f}s): {card.avatar_spoken_text}")
                    except Exception as exc:
                        safe_log(f"[Pipeline] No se pudo generar avatar para {card.card_id}: {exc}")

            await prepare_avatars()
        except Exception as exc:
            safe_log(f"[Pipeline] Error inicializando Avatar Copilot: {exc}")

        self._publish_plan(plan, "cards", 49.0, "Tarjetas y avatar reactivo listos para el montaje.")

        # ---- 4.5 Control de calidad local antes de gastar CPU en el render ----
        report = PlanQualityGate(duration).apply(plan)
        quality_message = "Control técnico listo: la línea de tiempo puede exportarse."
        if report.fixes:
            quality_message = f"Control técnico corrigió {len(report.fixes)} elemento(s) fuera de rango."
        if report.warnings:
            quality_message += f" Avisos: {len(report.warnings)}."
        # Auditoría editorial: choques entre overlays, ritmo y gancho (antes el render los descartaba en silencio).
        try:
            qa = audit_plan(plan, duration)
            quality_message += f" Auditoría editorial: {qa.score}/100"
            if qa.dropped:
                quality_message += f", {len(qa.dropped)} B-Roll retirados por choques o saturación"
            quality_message += "."
            if self.runlog:
                self.runlog.count("qa_broll_retirados", len(qa.dropped))
                self.runlog.event("quality", f"Auditoría editorial {qa.score}/100", metrics=qa.metrics,
                                  dropped=qa.dropped, warnings=qa.warnings)
                for warning in qa.warnings:
                    if "retirado" not in warning:
                        self.runlog.warn("quality", warning)
        except Exception as exc:
            safe_log(f"[QA] No se pudo auditar el montaje: {exc}")

        # Shorts: empezar y terminar en límites de frase y quitar duplicados.
        try:
            if plan.highlights:
                trimmed = {c.clip_id: round(trim_leading_filler(c, plan.captions), 2) for c in plan.highlights}
                trimmed = {k: v for k, v in trimmed.items() if v}
                changes = snap_highlights(plan.highlights, plan.captions, duration)
                ranking = rank_highlights(plan.highlights, plan.captions)
                if self.runlog:
                    self.runlog.event("quality", "Ranking de Shorts por gancho + viralidad",
                                      ranking=ranking, arranques_recortados=trimmed)
                if changes and self.runlog:
                    self.runlog.count("shorts_ajustados", sum(1 for c in changes if c["action"] == "snapped"))
                    self.runlog.count("shorts_duplicados", sum(1 for c in changes if c["action"] == "dropped"))
                    self.runlog.event("quality", f"{len(changes)} ajustes en Shorts", changes=changes)
        except Exception as exc:
            safe_log(f"[QA] No se pudieron ajustar los Shorts: {exc}")

        self._publish_plan(plan, "quality", 49.5, quality_message)

        # ---- 5. Render (Smart Cut + overlays + subtítulos opcionales) ----
        mapper = TimelineMapper.from_plan_segments(plan.timeline, duration)
        engine = VideoRenderEngine(fps=30, cancel_event=self.cancel_event)
        final_master = settings.OUTPUTS_DIR / f"{self.task_id}_master.mp4"

        captions_provider = None
        if opt.captions:
            def captions_provider(cut_video: Path):
                return mapper.remap_captions(plan.captions)

        def render_cb(msg: str, pct: float) -> None:
            self._state("subtitles" if "ubt" in msg or "ranscrib" in msg else "render", 50.0 + pct * 42.0, msg)

        async def _execute_render():
            self._state("render", 50.0, "Preparando el corte y la composición final con FFmpeg.")
            info = await self._run_with_heartbeat(
                loop, lambda: engine.render(self.input_file, plan, mapper, self.workdir, final_master,
                                            captions_provider, render_cb),
                "render", 55.0, "FFmpeg está renderizando el master",
            )

            # ---- 6. Short vertical (sale del master: incluye tarjetas y subtítulos) ----
            shorts: list[Path] = []
            if plan.highlights:
                for index, highlight in enumerate(plan.highlights, start=1):
                    self._state("finalizing", 94.0,
                                f"Generando Short {index} de {len(plan.highlights)}: «{highlight.title}».")
                    placed = mapper.map_first(highlight.start_sec, highlight.end_sec)
                    if placed:
                        mapped = highlight.model_copy(update={"start_sec": placed[0], "end_sec": placed[1]})
                        short_file = await self._run_with_heartbeat(
                            loop, lambda: engine.extract_vertical_short(final_master, mapped, settings.OUTPUTS_DIR),
                            "finalizing", 95.0, f"FFmpeg está generando el Short {index} de {len(plan.highlights)}",
                        )
                        if short_file:
                            shorts.append(short_file)
            return info, shorts

        if self.render_lock:
            if self.render_lock.locked():
                self._state("render", 50.0, "En cola de render: esperando turno de codificación para proteger CPU/GPU.")
            async with self.render_lock:
                render_info, short_files = await _execute_render()
        else:
            render_info, short_files = await _execute_render()

        cut = [s for s in plan.timeline if s.action == ActionType.CUT_SILENCE]
        placed_cards = {o["path"] for o in render_info["overlays"] if o["kind"] == "card"}
        return {
            "master_video_url": f"/media/{final_master.name}",
            "short_video_url": f"/media/{short_files[0].name}" if short_files else None,
            "shorts": [
                {"title": clip.title, "hook": clip.hook, "score": clip.virality_score,
                 "url": f"/media/{file.name}"}
                for clip, file in zip(plan.highlights, short_files)
            ],
            "silences_cut_count": len(cut),
            "brolls_count": sum(1 for o in render_info["overlays"] if o["kind"] != "card"),
            "time_saved_sec": round(sum(s.end_sec - s.start_sec for s in cut), 2),
            "fillers_cut_count": sum(1 for s in plan.timeline if s.action == ActionType.CUT_FILLER),
            "filler_time_saved_sec": round(sum(s.end_sec - s.start_sec for s in plan.timeline
                                               if s.action == ActionType.CUT_FILLER), 2),
            "cards_shown": len(placed_cards),
            "captions_count": render_info["captions"],
            "cards": [
                {
                    "headline": c.headline, "kind": c.kind, "verdict": c.verdict, "body": c.body,
                    "claim": c.claim, "note": c.note, "shown": bool(c.card_path and c.card_path in placed_cards),
                    "at_sec": round(c.start_sec, 1),
                    "avatar_spoken_text": c.avatar_spoken_text,
                    "sources": [s.model_dump() for s in c.sources],
                }
                for c in plan.info_cards
            ],
            "model_used": llm.last_model_used,
        }
