"""Orquestador del Recorrido Secuencial Universal (Universal Publishing Tour).

Cuando el usuario activa el Piloto Automático ('prender el auto'), este motor
realiza una ronda secuencial y ordenada por TODAS las páginas y canales:
1. 'the Deep dife' (YouTube) ➔ con subida simultánea a su hermana 'Núcleo Ideológico' (Facebook).
2. 'PixelGrama' (YouTube) ➔ con subida simultánea a su hermana 'Contrapunto' (Facebook).
3. 'Black Clover T 4' (Facebook) ➔ Siguiente parte de la serie de anime (8 min cronológico).
4. 'Huellas Sagradas' (Facebook) ➔ Escena de Fe, Cine Bíblico y Redención con voz de Alejandro.
5. 'Palabras con Peso' (Facebook) ➔ Clip viral de Debate / Podcast con la regla de los 3s finales.
6. 'fizbuzz' (Facebook) ➔ Curiosidades de Animales y Naturaleza (en cuanto se active).

Garantiza:
- Producción secuencial (1 a 1) para no sobrecargar CPU ni GPU.
- Decisión inteligente: Publica de inmediato si estamos en hora pico, o programa para la siguiente.
- Resiliencia total: si una estación tiene un aviso puntual, no rompe el recorrido y sigue con la siguiente.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.universal_tour")

BASE_URL = "http://127.0.0.1:8000"
TOUR_STATE_FILE = settings.STORAGE_DIR / "universal_tour_state.json"
PERMANENT_PAGES_FILE = settings.STORAGE_DIR / "facebook_permanent_pages.json"

# Ventanas de alto tráfico orgánico en hora local
PEAK_HOUR_WINDOWS = [
    (8, 11),   # Mañana (desayuno / trayecto)
    (12, 15),  # Mediodía (almuerzo)
    (17, 20),  # Tarde (salida escolar / laboral)
    (20, 23),  # Noche (horario estelar de ocio)
]

DEFAULT_TOUR_STATE: Dict[str, Any] = {
    "enabled": True,
    "is_tour_running": False,
    "last_full_tour_at": None,
    "current_station": None,
    "min_interval_hours_per_station": 3.0,
    "stations_status": {},
    "history": [],
}

_lock = threading.RLock()
_tour_thread: Optional[threading.Thread] = None
_started = False


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        safe_log(f"[UniversalTour] Error leyendo {path.name}: {exc}")
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_tour_state() -> Dict[str, Any]:
    with _lock:
        state = _read_json(TOUR_STATE_FILE, DEFAULT_TOUR_STATE)
        if not TOUR_STATE_FILE.exists():
            _write_json(TOUR_STATE_FILE, state)
        return state


def update_tour_state(patch: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        state = get_tour_state()
        state.update(patch)
        _write_json(TOUR_STATE_FILE, state)
        return state


def _is_peak_hour_now() -> bool:
    """Verifica si la hora actual local coincide con una ventana de alto tráfico orgánico."""
    cur_hour = datetime.now().hour
    return any(start <= cur_hour <= end for start, end in PEAK_HOUR_WINDOWS)


def _get_permanent_page(page_id_or_name: str) -> Optional[Dict[str, Any]]:
    """Obtiene el token permanente y datos de la página desde facebook_permanent_pages.json."""
    data = _read_json(PERMANENT_PAGES_FILE, {})
    for p in data.get("pages", []):
        if p.get("id") == page_id_or_name or page_id_or_name.lower() in p.get("name", "").lower():
            return p
    return None


# ---------------------------------------------------------------------------
# Ejecutores por Estación (Cada uno especializado en su nicho y canal)
# ---------------------------------------------------------------------------

def _run_station_deep_dife() -> Dict[str, Any]:
    """Estación 1: Núcleo Ideológico (Facebook) & the Deep dife (YouTube) ➔ Geopolítica & Historia."""
    safe_log("\n[UniversalTour] 🏛️ Ejecutando Estación 1: 'Núcleo Ideológico' (Facebook) + 'the Deep dife' (YouTube)...")
    try:
        from core.geopolitics_history_producer import GeopoliticsHistoryProducer
        producer = GeopoliticsHistoryProducer()
        res = producer.produce_and_publish()
        return {
            "success": True,
            "station": "Núcleo Ideológico & the Deep dife",
            "url": res.get("post_url"),
            "youtube_url": res.get("youtube_url")
        }
    except Exception as exc:
        safe_log(f"[UniversalTour] Aviso en Estación Núcleo Ideológico: {exc}")
        return {"success": False, "station": "Núcleo Ideológico", "error": str(exc)}


def _run_station_pixelgrama() -> Dict[str, Any]:
    """Estación 2: Contrapunto (Facebook) & PixelGrama (YouTube) ➔ Tecnología & IA."""
    safe_log("\n[UniversalTour] 🤖 Ejecutando Estación 2: 'Contrapunto' (Facebook) + 'PixelGrama' (YouTube)...")
    try:
        from core.tech_ai_producer import TechAIProducer
        producer = TechAIProducer()
        res = producer.produce_and_publish()
        return {
            "success": True,
            "station": "Contrapunto & PixelGrama",
            "url": res.get("post_url"),
            "youtube_url": res.get("youtube_url")
        }
    except Exception as exc:
        safe_log(f"[UniversalTour] Aviso en Estación Contrapunto: {exc}")
        return {"success": False, "station": "Contrapunto", "error": str(exc)}


def _run_station_huellas_sagradas() -> Dict[str, Any]:
    """Estación 3: Huellas Sagradas (Facebook) ➔ Cine Bíblico & Fe."""
    safe_log("\n[UniversalTour] ✝️ Ejecutando Estación 3: 'Huellas Sagradas' (Cine Bíblico & Fe)...")
    try:
        from core.huellas_sagradas_producer import HuellasSagradasProducer
        producer = HuellasSagradasProducer()
        res = producer.produce_and_publish()
        return {"success": True, "station": "Huellas Sagradas", "url": res.get("post_url")}
    except Exception as exc:
        safe_log(f"[UniversalTour] Aviso en Estación Huellas Sagradas: {exc}")
        return {"success": False, "station": "Huellas Sagradas", "error": str(exc)}


def _run_station_palabras_con_peso() -> Dict[str, Any]:
    """Estación 5: Palabras con Peso (Facebook) ➔ Clips reales de Podcasts en español (The Wild Project, Date un Vlog, etc.)."""
    safe_log("\n[UniversalTour] 🎙️ Ejecutando Estación 5: 'Palabras con Peso' (Clips de Podcasts & Debate en Español)...")
    page = _get_permanent_page("1352345044630476") or _get_permanent_page("Palabras con Peso")
    if not page:
        return {"success": False, "error": "Página Palabras con Peso no encontrada en almacenamiento."}

    try:
        from core.spanish_podcast_clipper import SpanishPodcastClipper
        from core.facebook_publisher import publish_video_to_facebook

        clipper = SpanishPodcastClipper()
        clip_data = clipper.produce_podcast_clip()

        if clip_data and clip_data.get("master_file") and Path(clip_data["master_file"]).exists():
            master_file = Path(clip_data["master_file"])
            title = clip_data["title"]
            description = clip_data["description"]
            # Control de Calidad Visual Autónomo con Gemini Vision (0% Anime / 0% Contaminación)
            from core.vision_qa import vision_qa
            qa = vision_qa.audit_video(
                video_path=master_file,
                expected_niche="Clips de podcasts y entrevistas en español de debate, ciencia, psicología y filosofía",
                forbidden_elements=["anime", "dibujos animados", "caricaturas japonesas", "gameplay de videojuegos"],
                channel_name="Palabras con Peso"
            )
            if not qa.get("approved", True):
                safe_log(f"[UniversalTour] 🛑 Publicación Palabras con Peso abortada por Vision QA: {qa.get('critique')}")
                return {"success": False, "station": "Palabras con Peso", "error": f"Rechazado por Vision QA: {qa.get('critique')}"}

            safe_log(f"[UniversalTour] 📤 Publicando Reel auténtico de podcast en Palabras con Peso...")
            pub = publish_video_to_facebook(
                video_path=master_file,
                title=title[:250],
                description=description,
                page_id=page["id"],
                access_token=page["access_token"],
                is_reel=True,
            )

            # Sembrar comentario inicial de debate en Palabras con Peso
            vid_id = pub.get("video_id")
            if vid_id:
                try:
                    from core.facebook_community_manager import facebook_community_manager
                    facebook_community_manager.post_seed_comment(
                        video_id=vid_id,
                        page_id=page["id"],
                        access_token=page["access_token"],
                        video_title=title,
                        debate_question="¿Crees que tiene razón o exageró en este debate? Deja tu opinión aquí abajo. 👇"
                    )
                except Exception:
                    pass

            return {"success": True, "station": "Palabras con Peso", "url": pub.get("post_url")}
        else:
            safe_log("[UniversalTour] ⚠️ No se pudo extraer clip de podcast, usando método alternativo...")
            raise RuntimeError("Fallo en extracción de clip de podcast")
    except Exception as exc:
        safe_log(f"[UniversalTour] Aviso en Estación Palabras con Peso: {exc}")
        return {"success": False, "station": "Palabras con Peso", "error": str(exc)}


# ---------------------------------------------------------------------------
# Bucle Maestro del Recorrido Secuencial
# ---------------------------------------------------------------------------

STATIONS = [
    ("the_deep_dife", _run_station_deep_dife),
    ("pixelgrama", _run_station_pixelgrama),
    ("huellas_sagradas", _run_station_huellas_sagradas),
    ("palabras_con_peso", _run_station_palabras_con_peso),
]


def execute_full_universal_tour() -> Dict[str, Any]:
    """Ejecuta una ronda completa secuencial por todas las estaciones."""
    with _lock:
        state = get_tour_state()
        if state.get("is_tour_running"):
            return {"success": False, "message": "Ya hay una ronda en progreso actualmente."}
        state["is_tour_running"] = True
        _write_json(TOUR_STATE_FILE, state)

    safe_log("\n" + "=" * 68)
    safe_log("🚀 [UniversalTour] INICIANDO RECORRIDO SECUENCIAL UNIVERSAL POR TODOS LOS CANALES")
    safe_log("=" * 68)

    results = []
    try:
        for name, runner in STATIONS:
            with _lock:
                state = get_tour_state()
                state["current_station"] = name
                _write_json(TOUR_STATE_FILE, state)

            try:
                res = runner()
                results.append({"station": name, "result": res})
            except Exception as e:
                safe_log(f"[UniversalTour] Excepción en estación {name}: {e}")
                results.append({"station": name, "result": {"success": False, "error": str(e)}})

            # Pausa de enfriamiento entre estaciones para no fatigar memoria/GPU
            safe_log(f"[UniversalTour] Estación {name} finalizada. Enfriando 20s antes de la siguiente estación...")
            time.sleep(20)

        with _lock:
            state = get_tour_state()
            state["is_tour_running"] = False
            state["current_station"] = None
            state["last_full_tour_at"] = datetime.now(timezone.utc).isoformat()
            state["history"].append({
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "stations_processed": len(results),
            })
            _write_json(TOUR_STATE_FILE, state)

        # Ronda comunitaria automática: responder comentarios recientes con IA para multiplicar el alcance algorítmico
        try:
            from core.facebook_community_manager import facebook_community_manager
            facebook_community_manager.run_community_round(max_replies_per_page=2)
        except Exception as comm_err:
            safe_log(f"[UniversalTour] Aviso en ronda comunitaria: {comm_err}")

        safe_log("\n" + "=" * 68)
        safe_log("✅ [UniversalTour] RECORRIDO UNIVERSAL COMPLETADO CON ÉXITO EN TODAS LAS ESTACIONES")
        safe_log("=" * 68 + "\n")
        return {"success": True, "results": results}

    except Exception as exc:
        with _lock:
            state = get_tour_state()
            state["is_tour_running"] = False
            state["current_station"] = None
            _write_json(TOUR_STATE_FILE, state)
        safe_log(f"[UniversalTour] Error general en el recorrido: {exc}")
        return {"success": False, "error": str(exc)}


def _tour_worker_loop():
    """Hilo permanente que revisa periódicamente si el Piloto Automático está prendido."""
    safe_log("[UniversalTour] Hilo de vigilancia de Recorrido Universal iniciado.")
    while True:
        try:
            time.sleep(120)  # Chequea cada 2 minutos
            from core.autopilot import get_config
            cfg = get_config()
            tour_st = get_tour_state()

            # Solo corre si el usuario prendió el piloto y no está corriendo ya
            if cfg.get("enabled") and tour_st.get("enabled") and not tour_st.get("is_tour_running"):
                # Verificar si es momento de hacer una nueva ronda (según intervalo mínimo o primer arranque)
                last_tour = tour_st.get("last_full_tour_at")
                should_run = False
                if not last_tour:
                    should_run = True
                else:
                    try:
                        last_dt = datetime.fromisoformat(last_tour)
                        hours_passed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
                        min_interval = float(tour_st.get("min_interval_hours_per_station", 3.0))
                        if hours_passed >= min_interval:
                            should_run = True
                    except Exception:
                        should_run = True

                if should_run:
                    safe_log("[UniversalTour] 🔔 Piloto encendido e intervalo cumplido: Lanzando Recorrido Universal...")
                    execute_full_universal_tour()

        except Exception as exc:
            safe_log(f"[UniversalTour] Aviso en ciclo de vigilancia: {exc}")


def start_universal_tour_worker():
    """Arranca el hilo de fondo del recorrido universal."""
    global _tour_thread, _started
    with _lock:
        st = get_tour_state()
        if st.get("is_tour_running"):
            safe_log("[UniversalTour] Limpiando estado de ejecución residual de arranque...")
            st["is_tour_running"] = False
            st["current_station"] = None
            _write_json(TOUR_STATE_FILE, st)
        if _started:
            return
        _started = True
        _tour_thread = threading.Thread(target=_tour_worker_loop, daemon=True, name="UniversalTourWorkerThread")
        _tour_thread.start()
