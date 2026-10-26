"""Motor autónomo de transmisión broadcast con KAI (Modo Libre / KAI Streamer).

Genera videos de divulgación o noticias 100% de forma autónoma:
1. Investigación web en tiempo real (noticias, datos verificados, cifras clave).
2. Redacción de guión de alto impacto con Gemini (humor, chispa, datos de peso).
3. Síntesis de voz neural de alta calidad (edge-tts).
4. Animación del presentador KAI (lip-sync reactivo, parpadeo, HUD interactivo).
5. B-rolls cinematográficos de apoyo y tarjetas estilo Pinterest Bento Glassmorphism.
6. Ensamble broadcast en alta definición (1080p o Short vertical 9:16).
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from core.orchestrator import AssetOrchestrator
from core.avatar_narrator import AvatarNarrator, DEFAULT_VOICE
from core.avatar_renderer import AvatarRenderer
from core.director import AIDirector, DirectorBroadcastPlan, DirectorScene
from core.llm import LLMClient, safe_log
from core.models import ActionType, BRollCue, CaptionItem, InfoCard, SourceRef, TimelineSegment, VideoEditingPlan
from core.project_store import ProjectStore
from core.scene_engine import SceneEngine

STYLE_PROMPTS: Dict[str, str] = {
    "divulgacion": """ESTILO DE COMUNICACIÓN: DIVULGACIÓN CIENTÍFICA & TECH
- Tono: Fresco, dinámico, chispeante, con analogías cotidianas y humor inteligente ("¡Dato mata relato!").
- Enfoque: Descomponer conceptos técnicos o científicos complejos en ideas claras, entretenidas y con cifras contundentes.""",

    "debate": """ESTILO DE COMUNICACIÓN: DEBATE, DILEMAS ÉTICOS Y PREGUNTAS A LA MESA
- Tono: Crítico, reflexivo, prudente e intelectualmente provocador.
- Misión: Dejar dilemas profundos y preguntas abiertas sobre la mesa:
  * "¿Hasta qué punto debemos permitir esto?", "¿Quién gana y quién asume los riesgos?", "¿Qué precauciones debemos plantearnos antes de que sea tarde?".
  * Llama a tener cuidado con el optimismo ciego, contrasta al menos dos posturas opuestas con datos duros y pide al chat/audiencia que compartan su postura.""",

    "analisis": """ESTILO DE COMUNICACIÓN: ANÁLISIS PROFUNDO & VIDEOENSAYO
- Tono: Riguroso, ordenado, pedagógico y exhaustivo.
- Estructura paso a paso:
  1. Origen histórico y contexto del problema.
  2. Mecanismo técnico real y cómo funciona en la práctica.
  3. Cifras económicas, impacto social comprobado y actores clave.
  4. Escenarios futuros y ramificaciones a mediano y largo plazo.""",

    "noticias": """ESTILO DE COMUNICACIÓN: NOTICIERO BROADCAST & BREAKING NEWS
- Tono: Periodístico, urgente, directo y de alto impacto.
- Estructura: Titular de impacto en los primeros segundos, citas de fuentes oficiales o declaraciones clave, análisis rápido de causas y consecuencias inmediatas.""",

    "podcast": """ESTILO DE COMUNICACIÓN: PÓDCAST & CHARLA STREAMER CERCANA
- Tono: Conversacional, íntimo, reflexivo y pausado ("Charla de café con KAI").
- Estilo oral: Pausas pensativas con puntos suspensivos (...), reflexiones sinceras en primera persona, interacción directa con comentarios del chat y anécdotas.""",

    "mitos": """ESTILO DE COMUNICACIÓN: MITOS AL DESCUBIERTO (DESMINTIENDO CREENCIAS POPULARES)
- Tono: Frontal, desafiante y desmitificador.
- Estructura: "¿Qué es lo que casi todo el mundo cree erróneamente?" vs "¿Qué dice la evidencia y la ciencia real?". Desarma falacias populares con datos incontestables.""",

    "directo": """ESTILO DE COMUNICACIÓN: DIRECTO, AL GRANO & SIN RODEOS
- Tono: Contundente, directo al punto, enérgico y sin filtro ni rodeos innecesarios.
- Estructura: Va directo a los hechos sin introducciones largas. Lenguaje franco, claro y certero que dice las cosas como son.""",

    "humor": """ESTILO DE COMUNICACIÓN: HUMORÍSTICO, JUGUETÓN & ENTRETENIDO
- Tono: Divertido, ocurrente, con comentarios cómicos, remates ingeniosos y comparaciones exageradas o chistosas.
- Dinámica: Mantiene al público sonriendo y enganchado, intercalando bromas inteligentes sobre los personajes o situaciones sin perder el hilo.""",

    "sarcastico": """ESTILO DE COMUNICACIÓN: SARCÁSTICO, IRÓNICO & ÁCIDO
- Tono: Mordaz, con fina ironía, cinismo elegante y sarcasmo punzante ("Vaya sorpresa, quién se lo hubiera imaginado...").
- Dinámica: Señala contradicciones obvias, hipocresías o absurdos con frases afiladas y ceja levantada.""",

    "storytelling": """ESTILO DE COMUNICACIÓN: STORYTELLING & RELATOS INMERSIVOS
- Tono: Cinematográfico, envolvente, con tensión narrativa y suspenso ("Todo comenzó un martes que parecía normal...").
- Estructura: Planteamiento, giro dramático, clímax y resolución moral o impactante. Pinta escenas vívidas con palabras.""",

    "top_ranking": """ESTILO DE COMUNICACIÓN: TOP & RANKING DINÁMICO
- Tono: Competitivo, de cuenta regresiva emocionante (ej. Puesto 10 al Puesto 1).
- Estructura: Cada posición tiene nombre claro, motivo del puesto, datos o cifras específicas que justifican su lugar, y sorpresa para el podio.""",

    "reaccion": """ESTILO DE COMUNICACIÓN: REACCIÓN & ANÁLISIS EN VIVO (MÓDULO A)
- Tono: Espontáneo, atento, crítico y analítico.
- Dinámica: Presenta el clip o noticia, reacciona genuinamente y aporta análisis propio sustancial. No se limita a narrar lo que ya se ve; descubre detalles que el espectador pasó por alto.""",

    "review": """ESTILO DE COMUNICACIÓN: REVIEW, PRUEBA & COMPARATIVA (MÓDULO E)
- Tono: Imparcial, técnico, transparente y orientado a resolver la duda del consumidor.
- Estructura: Problema a resolver, criterios de evaluación, ventajas, desventajas, limitaciones reales y recomendación final honesta.""",

    "gaming": """ESTILO DE COMUNICACIÓN: GAMING, GAMEPLAY & DESAFÍO (MÓDULO F)
- Tono: Enérgico, inmersivo, competitivo y emocionante.
- Estructura: Objetivo claro, reglas del desafío, obstáculos inesperados, decisiones bajo presión y desenlace épico.""",

    "tutorial": """ESTILO DE COMUNICACIÓN: TUTORIAL & GUÍA EDUCATIVA (MÓDULO H)
- Tono: Didáctico, claro, paciente y práctico.
- Estructura: Resultado prometido, requisitos previos, pasos secuenciales comprobables, errores comunes a evitar y demostración de éxito verificable.""",

    "biografia": """ESTILO DE COMUNICACIÓN: BIOGRAFÍA, HISTORIAS & CASOS REALES (MÓDULO G)
- Tono: Documental, humano, reflexivo y riguroso.
- Estructura: Contexto y protagonistas, decisiones críticas documentadas, consecuencias históricas y legado perdurable sin inventar hechos.""",

    "misterio": """ESTILO DE COMUNICACIÓN: MISTERIOS, ENIGMAS & INVESTIGACIÓN (MÓDULO C)
- Tono: Intrigante, analítico, atmosférico y basado en evidencias.
- Estructura: Incógnita inicial, pistas progresivas, contraste de hipótesis rivales y revelación de lo que la ciencia y la historia pueden confirmar.""",

    "shorts": """ESTILO DE COMUNICACIÓN: SHORT VIRAL VERTICAL (MÓDULO K)
- Tono: Dinámico, directo, ultracompacto y visual.
- Estructura: Gancho visual instantáneo en el segundo 1, una sola idea contundente desarrollada al grano y remate satisfactorio sin relleno.""",

    "hibrido": """ESTILO DE COMUNICACIÓN: COMBO MULTI-ESTILO (DIRECTO + HUMOR + SARCASMO + NARRATIVA)
- Tono: Una mezcla explosiva y súper entretenida: arranca directo al grano, mete comentarios sarcásticos y cómicos, y relata los hechos con tensión inmersiva."""
}

def resolve_style_instructions(style_raw: str) -> str:
    """Resuelve las instrucciones de estilo, permitiendo estilos individuales o combinaciones separadas por coma/signo más."""
    if not style_raw:
        return STYLE_PROMPTS["divulgacion"]
    tokens = [t.strip().lower() for t in style_raw.replace("+", ",").replace("&", ",").split(",") if t.strip()]
    matched = []
    for tok in tokens:
        for k, v in STYLE_PROMPTS.items():
            if tok == k or tok in k:
                if v not in matched:
                    matched.append(v)
                break
    if not matched:
        return STYLE_PROMPTS.get(style_raw.lower().strip(), STYLE_PROMPTS["divulgacion"])
    return "\n\n---\n\n".join(matched)

@dataclass
class StreamerOptions:
    topic: str
    style: str = "divulgacion"  # "divulgacion", "debate", "analisis", "noticias", "podcast", "mitos"
    duration_sec: int = 45      # 60, 180, 300, 600, 900
    voice: str = DEFAULT_VOICE
    aspect_ratio: str = "16:9"  # "16:9" o "9:16"
    card_theme: str = "dark"    # "dark" o "light"
    rtmp_url: Optional[str] = None # RTMP stream key URL para YouTube, Twitch o Kick
    # --- Opciones definidas en el compositor (todas con default retrocompatible) ---
    sub_style: str = "classic"     # classic, outline, viral, neon, minimal, cinema
    subs_enabled: bool = True
    burn_subtitles: bool = False   # Subtítulos quemados solo bajo petición explícita de exportación
    visual_mode: str = "mixed"     # mixed | svg (animaciones vectoriales propias) | stock (b-roll)
    enable_broll: bool = True
    enable_cards: bool = True
    enable_avatar: bool = True
    extra_notes: str = ""          # Indicaciones libres del usuario para el director
    flash_audit: bool = True       # Auditoría editorial con GLM-5.3-flash
    # === MODO ANÁLISIS DE CASO ===
    # URL de un video/caso concreto (YouTube u otro sitio soportado por yt-dlp):
    # KAI descarga el video, extrae fotogramas REALES, los analiza con Gemini y
    # el director los usa como fondos — análisis visual de un caso específico.
    source_video_url: Optional[str] = None
    # === PARÁMETROS DE PRODUCCIÓN PROFESIONAL (nuevos) ===
    audio_normalize: bool = True   # Normalización loudnorm EBU R128 (-16 LUFS broadcast)
    color_grade: str = "cinema"    # raw | cinema | broadcast | neon | warm | cool
    fps: int = 30                  # 24 (cine) | 30 (web/YT) | 60 (gaming)
    crf: int = 18                  # Calidad H.264: 16=máxima, 18=alta, 20=buena, 23=media
    bgm_volume: float = 0.12       # Volumen de música de fondo (0.0 = sin BGM, 0.12 = audible)
    intro_style: str = "kai"       # none | kai | minimal | broadcast
    outro_enabled: bool = True     # Agregar segmento de cierre con pantalla de like/sub
    bgm_track: str = "default"     # default | tension | upbeat | ambient | silent
    auto_publish: bool = False     # Publicar automáticamente en YouTube al finalizar renderizado
    origin: str = ""               # Origen del proyecto (tech_contrapunto, geopolitics_nucleo, etc.)


def build_creative_hints(options: "StreamerOptions") -> str:
    """Traduce las opciones del compositor a instrucciones para el AI Director."""
    hints = []
    mode = (options.visual_mode or "mixed").lower()
    if mode == "svg":
        hints.append("PRIORIZA B-Roll de video real cinemático y tarjetas Bento informativas en movimiento.")
    elif mode == "stock":
        hints.append("PRIORIZA B-Roll de video real (video_reaction); usa vector_motion solo si es imprescindible.")
    if not options.enable_broll:
        hints.append("NO uses escenas 'video_reaction' con B-Roll de stock.")
    if not options.enable_cards:
        hints.append("NO uses escenas 'card_focus' (tarjetas Bento); apoya los datos con la voz y los gráficos vectoriales.")

    # Desactivación total y permanente de anime para blindar todos los canales
    is_anime_opts = False

    # Detección de producción de Cine Cristiano & Escenas Bíblicas (Huellas Sagradas)
    is_christian_opts = (
        getattr(options, "origin", "") in ("universal_tour_huellas", "huellas_sagradas", "cristiano_cine")
        or any(k in (options.topic or "").lower() for k in ("cristiano", "cristiana", "bíblico", "biblico", "bíblica", "biblica", "jesús", "jesus", "huellas sagradas", "hacksaw ridge", "war room", "the shack", "la cabaña", "ben-hur", "pasión de cristo", "pasion de cristo", "diez mandamientos", "dios"))
        or any(k in (options.extra_notes or "").lower() for k in ("cine cristiano", "fe", "pelicula cristiana", "películas cristianas", "escena bíblica"))
    )
    if is_christian_opts:
        hints.append(
            "ESTILO CINE CRISTIANO & ESCENAS BÍBLICAS OBLIGATORIO: "
            "B-Roll enfocado en metraje cinematográfico de la película, escena bíblica o corto conmovedor referenciado (1080p, tono épico/emotivo). "
            "CERO personas de oficina, tecnología moderna o entrevistas de noticias genéricas. "
            "La narración debe ser profunda, conmovedora y reflexiva, con la voz pausada y cálida de Alejandro, cerrando con una lección de esperanza y fe."
        )

    if (options.extra_notes or "").strip():
        hints.append(f"INDICACIONES DEL USUARIO (obligatorias): {options.extra_notes.strip()[:600]}")
    if not hints:
        return ""
    return "\n\nPREFERENCIAS DE PRODUCCIÓN:\n- " + "\n- ".join(hints)


class StreamerPipeline:
    """Ejecuta el ciclo de vida completo de una transmisión autónoma de KAI."""

    def __init__(
        self,
        task_id: str,
        options: StreamerOptions,
        on_state: Callable[[str, float, str, Dict[str, Any]], None],
        cancel_event: Optional[threading.Event] = None,
        project_store: Optional[ProjectStore] = None,
        render_lock: Optional[asyncio.Lock] = None,
    ):
        self.task_id = task_id
        self.options = options
        self.on_state = on_state
        self.cancel_event = cancel_event or threading.Event()
        self.project_store = project_store or ProjectStore(task_id)
        self.render_lock = render_lock or asyncio.Lock()
        self.workdir = self.project_store.workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.llm = LLMClient()
        self.deepseek = None
        try:
            from core.deepseek_client import DeepSeekClient
            _ds = DeepSeekClient()
            if _ds.available:
                self.deepseek = _ds
                safe_log(f"[Streamer] DeepSeek activo ({_ds.model}) para ganchos, reparación de datos y auditoría.")
        except Exception as _ds_err:
            safe_log(f"[Streamer] Aviso inicializando DeepSeek: {_ds_err}")
        self.narrator = AvatarNarrator(voice=options.voice)
        self.avatar_rnd = AvatarRenderer(badge_size=360)

    def _state(self, step: str, progress: float, message: str, **extra: Any) -> None:
        self.on_state(step, progress, message, **extra)
        if self.project_store:
            self.project_store.set_status(step, message=message)

    async def run(self) -> Dict[str, Any]:
        """Ejecuta la transmisión completa y genera el video final."""
        safe_log(f"[Streamer] Iniciando transmisión autónoma para: «{self.options.topic}»")
        
        plan_cache_path = self.workdir / "broadcast_plan.json"
        is_resumed_plan = False
        plan = None
        if plan_cache_path.exists():
            try:
                cached_dict = json.loads(plan_cache_path.read_text(encoding="utf-8"))
                plan = DirectorBroadcastPlan.from_dict(cached_dict)
                is_resumed_plan = True
                safe_log(f"[Streamer] Plan de emisión recuperado de disco: {len(plan.scenes)} escenas.")
            except Exception as _e:
                safe_log(f"[Streamer] No se pudo leer plan cacheado, regenerando: {_e}")

        # 0. MODO ANÁLISIS DE CASO: descargar el video fuente, extraer fotogramas
        # REALES y analizarlos con Gemini ANTES de dirigir. Los frames quedan en
        # workdir/case_frames para que scene_engine los use como fondos.
        case_frames: List[Dict[str, Any]] = []
        case_soundbites: List[Dict[str, Any]] = []
        source_url = str(getattr(self.options, "source_video_url", "") or "").strip()
        if source_url and source_url.lower() not in ("none", "null"):
            case_frames, case_soundbites = await self._prepare_case_media(source_url)

        if not plan:
            # 1. Investigación Web
            self._state("research", 10.0, f"Investigando en internet sobre «{self.options.topic}»...")
            evidence = await self._gather_web_facts(self.options.topic)

            if self.cancel_event.is_set():
                raise asyncio.CancelledError()

            # 2. Planificación con el Director de IA
            self._state("script", 25.0, "Director de IA planificando escenas, emociones y encuadres...")
            style_instructions = resolve_style_instructions(self.options.style) + build_creative_hints(self.options)
            director = AIDirector(self.llm)
            plan = await director.direct_broadcast(
                topic=self.options.topic,
                style=self.options.style,
                evidence=evidence,
                duration_target=self.options.duration_sec,
                style_instructions=style_instructions,
                case_frames=case_frames,
                case_soundbites=case_soundbites,
            )

        # Auditoría editorial crítica y optimización de escenas con DeepSeek Flash (Supervisor Editor)
        if not is_resumed_plan:
            try:
                from core.review_critic import FlashContentReviewer
                reviewer = FlashContentReviewer()
                if reviewer.available and getattr(self.options, "flash_audit", True):
                    self._state("script", 32.0, "🧐 DeepSeek Flash auditando guión, locución y recursos visuales...")
                    plan_dict = reviewer.review_and_optimize_plan(plan.to_dict(), self.options.topic)
                    plan = DirectorBroadcastPlan.from_dict(plan_dict)
            except Exception as _rev_err:
                safe_log(f"[Streamer] Aviso en auditoría DeepSeek Flash: {_rev_err}")

        # Fuentes reales en las cards + auditoría y reparación de cifras inventadas
        fact_sheet = getattr(self, "_fact_sheet", None)
        if fact_sheet and fact_sheet.get("facts"):
            try:
                from core.research_agent import (
                    attach_sources_to_plan,
                    audit_plan_numbers,
                    repair_unsupported_numbers,
                )
                attached = attach_sources_to_plan(plan, fact_sheet)
                audit = audit_plan_numbers(plan, fact_sheet)
                fixed = 0
                if audit.get("unsupported") and getattr(self.options, "flash_audit", True):
                    fixed = repair_unsupported_numbers(plan, fact_sheet, self.deepseek or self.llm)
                    if fixed:
                        audit = audit_plan_numbers(plan, fact_sheet)
                safe_log(
                    f"[Streamer] Fuentes adjuntadas a {attached} cards; "
                    f"cifras sin respaldo: {audit.get('count', 0)} (corregidas: {fixed})."
                )
                if audit.get("unsupported"):
                    safe_log(f"[Streamer] Revisar cifras no sustentadas: {audit['unsupported'][:5]}")
                if self.project_store:
                    try:
                        self._fact_audit = audit
                        doc = self.project_store.read()
                        doc["fact_sheet"] = fact_sheet
                        doc["fact_audit"] = audit
                        self.project_store.write(doc)
                    except Exception:
                        pass
            except Exception as _fs_err:
                safe_log(f"[Streamer] Aviso adjuntando fact sheet: {_fs_err}")

        # Optimizar y corregir el título para YouTube (alta curiosidad, sin faltas ortográficas, <= 95 caracteres)
        try:
            from core.youtube_title_optimizer import optimize_youtube_title
            optimized_title = optimize_youtube_title(
                raw_topic=self.options.topic,
                style=self.options.style,
                duration_sec=self.options.duration_sec,
                existing_plan_title=plan.title,
            )
            if optimized_title:
                plan.title = optimized_title
                if self.project_store:
                    try:
                        doc = self.project_store.read()
                        doc["title"] = optimized_title
                        doc["original_name"] = optimized_title
                        self.project_store.write(doc)
                    except Exception:
                        pass
                self._state("script", 35.0, f"Título de YouTube optimizado: «{optimized_title}»", title=optimized_title, file_name=optimized_title)
                safe_log(f"[Streamer] 🏷️ Título de YouTube perfeccionado: «{optimized_title}»")
        except Exception as _t_err:
            safe_log(f"[Streamer] Aviso en optimización de título YouTube: {_t_err}")

        # Guardar plan en workdir y en project_store inmediatamente
        try:
            (self.workdir / "broadcast_plan.json").write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            if self.project_store:
                self.project_store.save_plan(plan.to_dict())
        except Exception as _e:
            safe_log(f"[Streamer] Aviso al guardar plan: {_e}")

        if self.cancel_event.is_set():
            raise asyncio.CancelledError()

        # 3. Renderizado del Avatar Animado: solo si el usuario lo tiene habilitado
        # Y si el plan del Director realmente incluye escenas con cámara de presentador (pip o avatar)
        has_presenter_scene = any(
            str(getattr(sc, "camera", "voice_over")).lower() in ("avatar_cam", "pip_corner", "pip_delayed")
            for sc in getattr(plan, "scenes", [])
        )
        should_render_avatar = getattr(self.options, "enable_avatar", True) and has_presenter_scene
        avatar_clip = self.workdir / "kai_avatar.mov"
        if should_render_avatar:
            if not (avatar_clip.exists() and avatar_clip.stat().st_size > 50000):
                self._state("avatar", 45.0, "Animando expresiones, respiración y lip-sync de KAI...")
                await asyncio.to_thread(
                    self.avatar_rnd.render_reaction_clip,
                    6.0,
                    avatar_clip,
                    fps=24
                )
            else:
                safe_log("[Streamer] Reusando loop dinámico de avatar KAI existente.")
        else:
            safe_log("[Streamer] 🎬 Modo Documental/Geopolítica: Avatar desactivado para dar prioridad 100% al metraje de archivo y mapas.")

        if self.cancel_event.is_set():
            raise asyncio.CancelledError()

        # 4. Motor de Escenas: Modulación emocional, composición reactiva y masterización
        # Aislamiento temático: ninguna consulta visual puede traer anime/wallpapers
        try:
            from core.visual_sanitizer import sanitize_plan_visuals
            fixed_queries = sanitize_plan_visuals(
                plan,
                topic=self.options.topic,
                origin=getattr(self.options, "origin", ""),
            )
            if fixed_queries:
                safe_log(f"[Streamer] {fixed_queries} consultas visuales saneadas (aislamiento temático).")
        except Exception as _vs_err:
            safe_log(f"[Streamer] Aviso saneando consultas visuales: {_vs_err}")

        # Línea de tiempo visual auditable (escenas, cortes, cards y fuentes)
        try:
            from core.render_timeline import build_visual_timeline
            if self.project_store:
                doc = self.project_store.read()
                doc["visual_timeline"] = build_visual_timeline(plan)
                self.project_store.write(doc)
        except Exception as _tl_err:
            safe_log(f"[Streamer] Aviso construyendo timeline visual: {_tl_err}")

        scenes_preview_data = [
            {
                "scene_id": sc.scene_id,
                "name": sc.name,
                "type": sc.type,
                "emotion": sc.emotion,
                "camera": sc.camera,
                "duration_est": round(sc.duration_est, 1),
                "headline": sc.card.headline if sc.card else "",
                "stat": sc.card.stat if sc.card else "",
                "thumb_url": f"/storage/projects/{self.task_id}/work/scene_{sc.scene_id}/scene_thumb.jpg",
                "card_url": f"/storage/projects/{self.task_id}/work/scene_{sc.scene_id}/card_{sc.scene_id}.png",
            }
            for sc in plan.scenes
        ]
        self._state("render", 60.0, f"Scene Engine dirigiendo y grabando {len(plan.scenes)} escenas...", live_scenes=scenes_preview_data)
        output_file = settings.OUTPUTS_DIR / f"{self.task_id}_master.mp4"

        # Director de Estilos: definir paleta y tipografía automáticamente según el tono del tema
        from core.ai_remotion_generator import AIStyleDirector
        style_director = AIStyleDirector(self.llm)
        theme_spec = style_director.determine_style(
            topic=self.options.topic,
            style_mode=self.options.style,
            extra_notes=getattr(self.options, "extra_notes", ""),
        )
        safe_log(f"[StyleDirector] 🎨 Paleta seleccionada: {theme_spec['name']} ({theme_spec['primary']} / {theme_spec['accent']}) | Tipografía/Subtítulos: {theme_spec['sub_style']}")

        # Curador Inteligente de Audio: seleccionar o descargar automáticamente la mejor pista de YouTube Audio Library
        chosen_bgm = getattr(self.options, 'bgm_track', 'default')
        if chosen_bgm != "silent":
            try:
                from core.youtube_audio import async_download_best_audio_for_topic
                pref_mood = None if chosen_bgm in ("default", "auto") else chosen_bgm
                auto_bgm = await async_download_best_audio_for_topic(
                    topic=self.options.topic,
                    style=self.options.style,
                    preferred_mood=pref_mood,
                )
                if auto_bgm and auto_bgm.exists():
                    chosen_bgm = str(auto_bgm)
                    safe_log(f"[StreamerPipeline] 🎶 Pista adaptada de YouTube Audio Library: {auto_bgm.name}")
            except Exception as bgm_err:
                safe_log(f"[StreamerPipeline] Fallback a audio estándar: {bgm_err}")

        scene_engine = SceneEngine(
            workdir=self.workdir,
            aspect_ratio=self.options.aspect_ratio,
            voice=self.options.voice,
            card_theme=self.options.card_theme,
            cancel_event=self.cancel_event,
            sub_style=self.options.sub_style,
            subs_enabled=self.options.subs_enabled,
            burn_subtitles=getattr(self.options, 'burn_subtitles', False),
            fps=getattr(self.options, 'fps', 30),
            crf=getattr(self.options, 'crf', 18),
            audio_normalize=getattr(self.options, 'audio_normalize', True),
            color_grade=getattr(self.options, 'color_grade', 'cinema'),
            bgm_volume=getattr(self.options, 'bgm_volume', 0.12),
            bgm_track=chosen_bgm,
            style_spec=theme_spec,
            topic=getattr(self.options, 'topic', ''),
            origin=getattr(self.options, 'origin', ''),
            extra_notes=getattr(self.options, 'extra_notes', ''),
            is_anime=False,
            enable_avatar=getattr(self.options, 'enable_avatar', True),
        )

        def scene_progress(pct: float, msg: str):
            self._state("render", pct, msg, live_scenes=scenes_preview_data)

        if self.render_lock.locked():
            self._state(
                "queued",
                60.0,
                "En cola de render: esperando turno de codificación para no sobrecargar GPU/CPU...",
                live_scenes=scenes_preview_data,
            )

        async with self.render_lock:
            self._state(
                "render",
                60.0,
                f"Scene Engine dirigiendo y grabando {len(plan.scenes)} escenas...",
                live_scenes=scenes_preview_data,
            )
            await scene_engine.assemble_broadcast(
                plan=plan,
                avatar_clip=avatar_clip,
                output_file=output_file,
                progress_cb=scene_progress,
            )

        # 5. Generar YouTube Cover Thumbnail (1280x720) y Short 9:16 Viral automáticamente
        thumb_output = settings.OUTPUTS_DIR / f"{self.task_id}_thumbnail.jpg"
        short_output = settings.OUTPUTS_DIR / f"{self.task_id}_short.mp4"
        hook_variants: list = []
        try:
            # 5a. Miniatura editorial construida desde el fact sheet (o el título del plan)
            from core.fact_thumbnail import build_thumbnail, extract_frame
            from core.research_agent import generate_hook_variants
            sheet = getattr(self, "_fact_sheet", None) or {}
            hook_fact = sheet.get("hook") or next(iter(sheet.get("facts") or []), None) or {}
            hook_variants = generate_hook_variants(self.options.topic, sheet, self.deepseek or self.llm)
            if hook_variants:
                hook_text = hook_variants[0]["text"]
                source_text = hook_variants[0].get("source") or hook_fact.get("source") or "AetherCut"
            else:
                hook_text = hook_fact.get("claim") or plan.title or self.options.topic
                source_text = hook_fact.get("source") or "AetherCut"
            numbers = hook_fact.get("numbers") or []
            stat_text = numbers[0] if numbers else ""
            if not stat_text:
                stat_text = next((sc.card.stat for sc in plan.scenes if sc.card and sc.card.stat), "") or ""
            frame = None
            try:
                from core.vision_qa import vision_qa as _vqa
                candidates = sorted(
                    [p for p in (self.workdir / "assets").glob("scene_cue_*.jpg") if p.stat().st_size > 80000],
                    key=lambda p: p.stat().st_size,
                    reverse=True,
                )
                for _candidate in candidates[:6]:
                    _info = _vqa.classify_media(_candidate, hook_text)
                    if (
                        _info.get("use_as_background", True)
                        and str(_info.get("kind", "")).lower() in ("photo", "video_frame")
                    ):
                        frame = _candidate
                        break
            except Exception:
                frame = None
            if not frame:
                frame = extract_frame(output_file, self.workdir / "thumb_frame.jpg", 2.0)
            fallback = None
            for sc in plan.scenes:
                sc_thumb = self.workdir / f"scene_{sc.scene_id}" / "scene_thumb.jpg"
                if sc_thumb.exists():
                    fallback = sc_thumb
                    break
            build_thumbnail(
                frame,
                hook_text,
                source_text,
                stat_text,
                thumb_output,
                vertical=False,
                fallback_image=fallback,
            )
            if not thumb_output.exists():
                raise RuntimeError("No se pudo generar la miniatura editorial.")

            if hook_variants and self.project_store:
                try:
                    doc = self.project_store.read()
                    doc["hook_variants"] = hook_variants
                    doc["fact_sheet"] = sheet
                    doc["fact_audit"] = getattr(self, "_fact_audit", {})
                    self.project_store.write(doc)
                except Exception:
                    pass

            # 5b. Short 9:16 de muestra desde la mejor escena disponible
            candidate_scene = None
            for sc in plan.scenes:
                sc_f = self.workdir / f"scene_{sc.scene_id}" / f"scene_{sc.scene_id}.mp4"
                if sc_f.exists() and sc.type in ("card_focus", "video_reaction"):
                    candidate_scene = sc_f
                    break
            if not candidate_scene:
                for sc in plan.scenes:
                    sc_f = self.workdir / f"scene_{sc.scene_id}" / f"scene_{sc.scene_id}.mp4"
                    if sc_f.exists():
                        candidate_scene = sc_f
                        break
            if candidate_scene and candidate_scene.exists():
                import subprocess
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(candidate_scene),
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                    "-threads", "2",
                    "-max_muxing_queue_size", "1024",
                    "-c:a", "aac", "-b:a", "192k", str(short_output)
                ], capture_output=True, timeout=60)
        except Exception as exc:
            safe_log(f"[StreamerPipeline] Generación de thumbnail/short opcional: {exc}")

        # 6. Broadcast RTMP opcional si el usuario proporcionó URL / clave
        if self.options.rtmp_url and str(self.options.rtmp_url).strip() not in ("None", "null", ""):
            rtmp_dest = str(self.options.rtmp_url).strip()
            self._state("render", 95.0, f"Emitiendo en vivo por RTMP a {rtmp_dest[:22]}...")
            asyncio.create_task(self._stream_to_rtmp(output_file, rtmp_dest))

        # Construir y guardar plan enriquecido en ProjectStore con sincronización precisa de pistas
        from utils.file_manager import FileManager
        timeline_segments = []
        info_cards = []
        b_rolls = []
        captions = []
        cum_sec = 0.0

        for sc in plan.scenes:
            sid = sc.scene_id
            mp4_file = self.workdir / f"scene_{sid}" / f"scene_{sid}.mp4"
            dur = 0.0
            if mp4_file.exists():
                try:
                    dur = FileManager.get_media_metadata(mp4_file).get("duration", 0.0)
                except Exception:
                    pass
            if dur <= 0:
                dur = float(sc.duration_est or 6.0)

            sc_start = round(cum_sec, 2)
            sc_end = round(cum_sec + dur, 2)
            cum_sec += dur

            timeline_segments.append(TimelineSegment(
                start_sec=sc_start,
                end_sec=sc_end,
                action=ActionType.KEEP,
                reason=sc.name or f"Escena {sid}"
            ))

            card_data = sc.card if isinstance(sc.card, dict) else (sc.card.__dict__ if hasattr(sc.card, "__dict__") else {})
            if card_data and card_data.get("headline"):
                h_text = str(card_data.get("headline", "")).strip()
                b_text = str(card_data.get("body", "")).strip()
                dur_disp = max(4.5, min(12.0, float(dur - 0.8) if dur > 5.5 else 4.5))
                info_cards.append(InfoCard(
                    card_id=f"card-{sid}",
                    start_sec=sc_start + 0.5,
                    end_sec=sc_start + 0.5 + dur_disp,
                    display_duration_sec=dur_disp,
                    headline=h_text,
                    claim=str(card_data.get("claim") or h_text),
                    search_query=str(card_data.get("search_query") or h_text),
                    body=b_text,
                    stat_value=str(card_data.get("stat") or card_data.get("stat_value") or ""),
                ))

            if sc.visual_query:
                b_rolls.append(BRollCue(
                    cue_id=f"broll-{sid}",
                    start_sec=sc_start,
                    end_sec=sc_end,
                    concept=sc.visual_query,
                    search_query_en=sc.visual_query,
                    reasoning=sc.name or f"Escena {sid}",
                ))

            srt_file = self.workdir / f"scene_{sid}" / "scene_subtitles.srt"
            if srt_file.exists():
                try:
                    blocks = srt_file.read_text(encoding="utf-8").strip().split("\n\n")
                    for blk in blocks:
                        lns = [l.strip() for l in blk.splitlines() if l.strip()]
                        if len(lns) >= 3 and "-->" in lns[1]:
                            tp = lns[1].split("-->")
                            def _pt(ts):
                                pts = ts.strip().replace(",", ".").split(":")
                                return float(pts[0])*3600 + float(pts[1])*60 + float(pts[2])
                            c_st = round(sc_start + _pt(tp[0]), 2)
                            c_en = round(sc_start + _pt(tp[1]), 2)
                            captions.append(CaptionItem(
                                start_sec=c_st,
                                end_sec=c_en,
                                text=" ".join(lns[2:]),
                            ))
                except Exception:
                    pass

        edit_plan = VideoEditingPlan(
            video_summary=plan.title,
            total_original_duration_sec=cum_sec,
            timeline=timeline_segments,
            info_cards=info_cards,
            b_rolls=b_rolls,
            captions=captions,
        )
        self.project_store.save_plan(edit_plan)

        media_url = f"/media/{output_file.name}"
        real_duration = 0.0
        try:
            real_duration = FileManager.get_media_metadata(output_file).get("duration", 0.0)
        except Exception:
            pass
        if not real_duration or real_duration <= 0:
            real_duration = round(cum_sec, 2) if cum_sec > 0 else plan.total_est_duration

        result_payload = {
            "output_file": str(output_file),
            "media_url": media_url,
            "master_video_url": media_url,
            "title": plan.title,
            "duration": real_duration,
            "topic": self.options.topic,
            "style": self.options.style,
            "scenes_count": len(plan.scenes),
            "scenes": [
                {
                    "id": sc.scene_id,
                    "name": sc.name,
                    "type": sc.type,
                    "emotion": sc.emotion,
                    "camera": sc.camera,
                }
                for sc in plan.scenes
            ],
            "cards_shown": sum(1 for sc in plan.scenes if sc.card is not None),
            "brolls_count": len(plan.scenes),
            "silences_cut_count": 0,
            "time_saved_sec": 0.0,
            "thumbnail_url": f"/media/{thumb_output.name}" if thumb_output.exists() else None,
            "short_video_url": f"/media/{short_output.name}" if short_output.exists() else None,
            "hook_variants": hook_variants,
        }

        # 7. Publicación automática desatendida o preparación autónoma multi-canal
        if getattr(self.options, 'auto_publish', False) or getattr(settings, 'AUTO_PUBLISH', False):
            try:
                from core.publish_studio import PublishStudio
                from core.channel_manager import ChannelManager
                import core.youtube_oauth as yt
                
                studio = PublishStudio(self.task_id)
                classification = ChannelManager.classify_content(self.options.topic)
                target_ch = classification.get("channel") or {}
                meta = studio.generate_metadata()
                
                safe_log(f"[AutoPublish] 🎯 Canal clasificado: {target_ch.get('name')} (Confianza: {classification.get('confidence', 0):.0%})")
                
                if yt.is_connected():
                    self._state("publish", 98.0, f"Publicando automáticamente en YouTube ({target_ch.get('name')})...")
                    upload_res = yt.upload_video(
                        video_path=output_file,
                        title=meta["title"],
                        description=meta["description"],
                        tags=meta["tags"],
                        category_id=str(target_ch.get("category_id", "28")),
                    )
                    if thumb_output.exists():
                        yt.set_thumbnail(upload_res["video_id"], thumb_output)
                    result_payload["youtube_upload"] = upload_res
                    safe_log(f"[AutoPublish] 🚀 ¡Video publicado en YouTube con éxito! {upload_res.get('video_url')}")
                else:
                    result_payload["auto_publish_prepared"] = {
                        "channel": target_ch,
                        "metadata": meta,
                        "status": "ready_for_assisted",
                    }
                    safe_log(f"[AutoPublish] 🧭 Paquete SEO y miniatura preparados para publicación asistida en {target_ch.get('name')}")
            except Exception as _ap_err:
                safe_log(f"[AutoPublish] No se pudo completar subida desatendida: {_ap_err}")

        self.project_store.set_status("done", result=result_payload, preview_file=str(output_file))
        self._state("done", 100.0, "¡Transmisión de KAI masterizada exitosamente!", result=result_payload)
        return result_payload

    async def _stream_to_rtmp(self, video_file: Path, rtmp_url: str) -> None:
        """Emite en tiempo real el archivo final hacia YouTube, Twitch o Kick."""
        try:
            cmd = [
                "ffmpeg", "-re",
                "-i", str(video_file),
                "-c", "copy",
                "-f", "flv",
                rtmp_url,
            ]
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
        except Exception as exc:
            safe_log(f"[StreamerPipeline] Error en emisión RTMP: {exc}")

    async def _gather_web_facts(self, topic: str) -> str:
        """Busca noticias y datos reales con DuckDuckGo (priorizando noticias frescas y cobertura reciente)."""
        # 1. Investigación estructurada: fuentes completas, cifras y corroboración.
        try:
            from core.research_agent import research_topic
            sheet = await asyncio.wait_for(asyncio.to_thread(research_topic, topic), timeout=35.0)
            setattr(self, "_fact_sheet", sheet)
            if sheet and sheet.get("facts") and sheet.get("brief"):
                safe_log(f"[Streamer] Fact sheet listo: {len(sheet['facts'])} datos verificados de fuentes reales.")
                return sheet["brief"]
        except Exception as exc:
            safe_log(f"[Streamer] Investigación estructurada no disponible ({exc}); se usan snippets.")

        # 2. Fallback clásico: snippets de DDGS.
        try:
            from ddgs import DDGS
            def search_ddg():
                findings = []
                seen_titles = set()
                with DDGS() as ddgs:
                    # 1. Priorizar noticias de última hora y prensa reciente
                    try:
                        news_results = list(ddgs.news(topic, region="es-es", max_results=5))
                        for n in news_results:
                            t = (n.get("title") or "").strip()
                            b = (n.get("body") or "").strip()
                            d = n.get("date") or ""
                            date_str = f" [{d[:10]}]" if d else ""
                            if t and t.lower() not in seen_titles and b:
                                seen_titles.add(t.lower())
                                findings.append(f"- [NOTICIA RECIENTE{date_str}] {t}: {b[:240]}")
                    except Exception as _e_news:
                        safe_log(f"[Streamer] Aviso en búsqueda ddgs.news: {_e_news}")

                    # 2. Si hay espacio, complementar con cobertura web reciente de la última semana
                    if len(findings) < 4:
                        try:
                            web_results = list(ddgs.text(topic, region="es-es", timelimit="w", max_results=4))
                            for r in web_results:
                                t = (r.get("title") or "").strip()
                                b = (r.get("body") or "").strip()
                                if t and t.lower() not in seen_titles and b:
                                    seen_titles.add(t.lower())
                                    findings.append(f"- [ACTUALIDAD] {t}: {b[:220]}")
                        except Exception:
                            pass

                    # 3. Fallback a búsqueda general si aún no hay resultados
                    if not findings:
                        try:
                            gen_results = list(ddgs.text(topic, region="es-es", max_results=4))
                            for r in gen_results:
                                t = (r.get("title") or "").strip()
                                b = (r.get("body") or "").strip()
                                if t and t.lower() not in seen_titles and b:
                                    seen_titles.add(t.lower())
                                    findings.append(f"- [WEB] {t}: {b[:220]}")
                        except Exception:
                            pass
                return findings

            results = await asyncio.wait_for(asyncio.to_thread(search_ddg), timeout=14.0)
            if results:
                return "\n".join(results[:5])
        except Exception as exc:
            safe_log(f"[Streamer] Búsqueda de soporte falló: {exc}")
        return "Noticia relevante y debate actual sobre el tema en tendencia."

    # ------------------------------------------------------------------
    # MODO ANÁLISIS DE CASO: video fuente real → fotogramas → Gemini
    # ------------------------------------------------------------------

    async def _prepare_case_media(self, source_url: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Descarga el video del caso, extrae fotogramas reales y analiza soundbites estratégicos.

        Devuelve (frames_info, soundbites_info) para el director. Es tolerante a fallos:
        si algo falla, continúa de forma segura con lo disponible.
        """
        frames_dir = self.workdir / "case_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(frames_dir.glob("frame_*.jpg"))
        frames_info: List[Dict[str, Any]] = []
        soundbites_info: List[Dict[str, Any]] = []
        final_video = None

        try:
            candidates = [p for p in self.workdir.glob("case_source.*") if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
            if candidates:
                final_video = candidates[0]

            if not existing and not final_video:
                self._state("case_media", 6.0, "Descargando el video del caso para análisis visual y auditivo...")
                video_file = self.workdir / "case_source.%(ext)s"

                def do_download():
                    import yt_dlp
                    opts = {
                        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/best",
                        "outtmpl": str(video_file),
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "noprogress": True,
                        "socket_timeout": 20,
                        "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
                        "postprocessor_args": {"ffmpeg": ["-threads", "2"]},
                    }
                    for c_cand in [settings.STORAGE_DIR / "cookies.txt", settings.BASE_DIR / "cookies.txt", settings.BASE_DIR / "assets" / "cookies.txt"]:
                        if c_cand.is_file() and c_cand.stat().st_size > 10:
                            opts["cookiefile"] = str(c_cand.resolve())
                            safe_log(f"[Streamer] 🍪 Usando archivo de cookies: {c_cand.name}")
                            break
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([source_url])

                await asyncio.wait_for(asyncio.to_thread(do_download), timeout=180)
                candidates = [p for p in self.workdir.glob("case_source.*") if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
                if not candidates:
                    safe_log("[Streamer] Caso: la descarga no produjo un archivo de video.")
                    return ([], [])
                final_video = candidates[0]

            if self.cancel_event.is_set():
                raise asyncio.CancelledError()

            # 1. Extracción y análisis de soundbites estratégicos del video completo
            if final_video and final_video.exists():
                try:
                    self._state("case_media", 7.5, "Analizando discurso completo del video para soundbites estratégicos...")
                    from core.soundbite_analyzer import StrategicSoundbiteAnalyzer
                    sb_analyzer = StrategicSoundbiteAnalyzer()
                    sbs = await asyncio.to_thread(
                        sb_analyzer.analyze_full_video,
                        final_video,
                        topic=self.options.topic,
                        workdir=self.workdir,
                        max_soundbites=4,
                    )
                    for i, sb in enumerate(sbs):
                        c_name = sb.clip_path.name if sb.clip_path else f"case_soundbite_{i}.mp4"
                        soundbites_info.append({
                            "clip_name": c_name,
                            "quote": sb.quote,
                            "duration": sb.duration,
                            "start_sec": sb.start_sec,
                            "end_sec": sb.end_sec,
                        })
                    safe_log(f"[Streamer] 🎙️ {len(soundbites_info)} soundbites estratégicos extraídos del video fuente.")
                except Exception as sb_err:
                    safe_log(f"[Streamer] Aviso en análisis de soundbites del caso: {sb_err}")

            # 2. Extraer fotogramas repartidos por TODA la duración si aún no existen
            if not existing and final_video:
                self._state("case_media", 8.5, "Extrayendo fotogramas clave del video del caso...")
                def probe_duration():
                    import subprocess
                    r = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(final_video)],
                        capture_output=True, text=True, timeout=20)
                    return float(r.stdout.strip() or 0)
                try:
                    dur = await asyncio.wait_for(asyncio.to_thread(probe_duration), timeout=25)
                except Exception:
                    dur = 60.0
                num = max(3, min(12, int(dur // 8) or 3))
                fps_expr = f"{num}/{max(1.0, dur):.3f}"
                import subprocess

                def extract_frames():
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(final_video),
                        "-vf", f"fps={fps_expr},scale=1280:-2",
                        "-frames:v", str(num), "-q:v", "3",
                        str(frames_dir / "frame_%02d.jpg"),
                    ], capture_output=True, timeout=180)

                await asyncio.wait_for(asyncio.to_thread(extract_frames), timeout=200)
                existing = sorted(frames_dir.glob("frame_*.jpg"))

            if not existing:
                return ([], soundbites_info)

            # 3. Análisis visual con Gemini (multimodal): describir cada fotograma
            self._state("case_media", 9.2, f"Gemini analizando {len(existing)} fotogramas reales del caso...")
            try:
                from google.genai import types as gtypes

                def analyze():
                    parts = []
                    for i, frame in enumerate(existing[:8]):
                        data = frame.read_bytes()
                        parts.append(gtypes.Part.from_bytes(data=data, mime_type="image/jpeg"))
                    parts.append(
                        "Estos son fotogramas (EN ORDEN, índice 0 a N) de un video real. "
                        "Para cada fotograma describe en español qué se ve (máx 25 palabras), "
                        "destacando lo visualmente llamativo o revelador para un análisis. "
                        'Responde SOLO JSON: {"frames": [{"index": 0, "desc": "..."}, ...]}'
                    )
                    return self.llm.generate(parts, json_mode=True, max_models=2)

                raw = await asyncio.wait_for(asyncio.to_thread(analyze), timeout=120)
                parsed = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
                for item in parsed.get("frames", []):
                    if isinstance(item, dict) and isinstance(item.get("index"), int):
                        frames_info.append({"index": item["index"], "desc": str(item.get("desc", ""))[:220]})
            except Exception as ana_exc:
                safe_log(f"[Streamer] Análisis Gemini de fotogramas falló: {ana_exc}")

            if not frames_info:
                frames_info = [{"index": i, "desc": ""} for i in range(len(existing))]
            safe_log(f"[Streamer] Caso listo: {len(frames_info)} fotogramas y {len(soundbites_info)} soundbites disponibles para el director.")
            return (frames_info, soundbites_info)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            safe_log(f"[Streamer] Modo análisis de caso degradado ({exc}): continuando.")
            return ([], soundbites_info)

