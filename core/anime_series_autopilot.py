"""Motor Autónomo de Resúmenes de Series de Anime por Partes (Anime Series Autopilot).

Gestiona de forma 100% autónoma:
1. Memoria de continuidad narrativa de la serie (Black Clover / Shonen) en partes secuenciales (Parte 1, 2, 3...).
2. Creación de videos estándar de 6 a 10 minutos (con micro-cortes dinámicos, voz de Alejandro y OST libre).
3. Programación estratégica anti-saturación (3 a 4 partes por día en horas de alto tráfico).
4. Publicación automática a la Página de Facebook 'Black Clover T 4' (ID: 972321959300050).
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

logger = logging.getLogger("aethercut.anime_autopilot")

STATE_FILE = settings.STORAGE_DIR / "anime_series_state.json"
BASE_URL = "http://127.0.0.1:8000"

# Horas estratégicas recomendadas para publicar 3 o 4 partes al día en Facebook
STRATEGIC_CADENCE_HOURS = {
    2: [13, 20],
    3: [8, 13, 20],
    4: [8, 13, 18, 21],
}

DEFAULT_SERIES_STATE: Dict[str, Any] = {
    "active_series": "Black Clover",
    "facebook_page": {
        "page_id": "972321959300050",
        "page_name": "Black Clover T 4",
        "access_token": "EAAZAizNN8ki4BS3KyUIw0ZAkcWX6CFZBPYkUWBZBfscRZATynTfGJSOd6DQZCcteafA2yEGP4xJF55ZAMTMZBThiqZCU0lU0mxBHExzxZBi03jroidL7eUMXRzHSMHxvW5UFB6IZBhwDlegs7nEtAQ3RTj7JGwHx7WpUz6EDkWcEY3NOMo9EBGcPL0y0woVIX8CIvbcJWjEqAt3kjwkIomHnufq66ZBHYL9BPOwSGqxm78Yt3nQZD",
        "enabled": True,
    },
    "config": {
        "enabled": True,
        "parts_per_day": 3,
        "default_duration_min": 8,
        "voice": "speechify:alejandro",
        "strategic_hours": [8, 13, 20],
        "auto_publish": True,
        "aspect_ratio": "16:9",
        "continuous_mode": True,
    },
    "current_part": 1,
    "is_producing": False,
    "last_produced_at": None,
    "last_published_url": None,
    "series_outline": [
        {
            "part": 1,
            "episodes": "1 - 3",
            "arc": "Arco de Iniciación",
            "subtitle": "El Grimorio de 5 Hojas y el Despertar de la Anti-Magia",
            "topic": "Resumen Black Clover Parte 1: Asta sin magia obtiene el misterioso grimorio negro de 5 hojas y salva a Yuno derrotando al ladron de grimorios con su espada anti-magia",
            "cliffhanger": "Asta y Yuno parten rumbo a la Capital Real para el examen de Caballeros Mágicos donde nadie cree en su poder... ¿Logrará algún capitán fijarse en él?",
        },
        {
            "part": 2,
            "episodes": "4 - 6",
            "arc": "Arco de los Caballeros Mágicos",
            "subtitle": "El Examen de Ingreso y la Prueba de los Toros Negros",
            "topic": "Resumen Black Clover Parte 2: El examen de caballeros magicos en la capital real, la humillacion de Sekke de un solo golpe y la eleccion de Yami Sukehiro de los Toros Negros",
            "cliffhanger": "Yami lleva a Asta a la guarida secreta de la peor orden del reino, pero antes de entrar, una conmoción interna pondrá a prueba su supervivencia...",
        },
        {
            "part": 3,
            "episodes": "7 - 10",
            "arc": "Arco de la Mazmorra",
            "subtitle": "Misión Letal en la Mazmorra: Toros Negros vs Reino del Diamante",
            "topic": "Resumen Black Clover Parte 3: Asta, Noelle y Luck investigan la mazmorra ancestral en la frontera y se enfrentan a los asesinos magicos del Reino del Diamante",
            "cliffhanger": "Mars, el guerrero genéticamente modificado de Diamante, acorrala a Yuno con su magia mineral asesina... Asta está demasiado lejos para intervenir...",
        },
        {
            "part": 4,
            "episodes": "11 - 14",
            "arc": "Arco de la Mazmorra",
            "subtitle": "Yuno vs Mars y el Poder Oculto de la Espada Habitadora",
            "topic": "Resumen Black Clover Parte 4: Combate supremo contra Mars en la camara del tesoro ancestral, Asta despierta su segunda espada y descubren magia arcana milenaria",
            "cliffhanger": "La mazmorra comienza a colapsar sobre ellos mientras un grupo terrorista en las sombras empieza a planear la invasión a la Capital Real...",
        },
        {
            "part": 5,
            "episodes": "15 - 19",
            "arc": "Arco de la Capital Real",
            "subtitle": "Invasión a la Capital: El Ataque del Ojo de la Noche Blanca",
            "topic": "Resumen Black Clover Parte 5: La capital real es asediada por zombis y magia oscura, los Toros Negros y capitanes defienden la ciudad de la aniquilacion",
            "cliffhanger": "El líder terrorista Licht revela una magia de luz inalcanzable para cualquier humano ordinario y el Rey Mago Julius debe intervenir en persona...",
        },
        {
            "part": 6,
            "episodes": "20 - 24",
            "arc": "Arco del Encuentro con Licht",
            "subtitle": "Yami Sukehiro vs Licht: Magia de Oscuridad Desatada",
            "topic": "Resumen Black Clover Parte 6: El choque titanico entre Yami y Licht en la cueva, la dimension de oscuridad y el corte dimensional que parte el espacio",
            "cliffhanger": "Los tres miembros de élite del Tercer Ojo descienden al campo de batalla con un maná monstruoso que supera incluso a los capitanes...",
        },
    ],
    "history": [],
}

_lock = threading.RLock()
_worker_thread: Optional[threading.Thread] = None
_started = False


def _read_state() -> Dict[str, Any]:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        safe_log(f"[AnimeAutopilot] Error leyendo estado: {exc}")
    return json.loads(json.dumps(DEFAULT_SERIES_STATE))


def _write_state(data: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def get_anime_series_state() -> Dict[str, Any]:
    with _lock:
        state = _read_state()
        if not STATE_FILE.exists():
            _write_state(state)
        return state


def update_anime_series_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        state = _read_state()
        if "config" in patch and isinstance(patch["config"], dict):
            state["config"].update(patch["config"])
        if "enabled" in patch:
            state["config"]["enabled"] = bool(patch["enabled"])
        if "active_series" in patch:
            state["active_series"] = str(patch["active_series"]).strip()
        if "current_part" in patch:
            state["current_part"] = max(1, int(patch["current_part"]))
        if "facebook_page" in patch:
            state["facebook_page"].update(patch["facebook_page"])

        ppd = state["config"].get("parts_per_day", 3)
        state["config"]["strategic_hours"] = STRATEGIC_CADENCE_HOURS.get(ppd, [8, 13, 20])

        _write_state(state)
        safe_log(f"[AnimeAutopilot] Configuración actualizada: enabled={state['config'].get('enabled')}, {ppd} partes/día, dur={state['config'].get('default_duration_min')}m")
        return state


def toggle_anime_series(enabled: Optional[bool] = None) -> Dict[str, Any]:
    """Alterna o fuerza el estado de activación de la serie de anime."""
    with _lock:
        state = _read_state()
        current = state.get("config", {}).get("enabled", True)
        new_val = (not current) if enabled is None else bool(enabled)
        state["config"]["enabled"] = new_val
        _write_state(state)
        safe_log(f"[AnimeAutopilot] 🔄 Serie de Anime {'ACTIVADA' if new_val else 'DESACTIVADA'} por el usuario.")
        return {"success": True, "enabled": new_val, "state": state}


def _get_or_create_part_outline(state: Dict[str, Any], part_num: int) -> Dict[str, Any]:
    """Obtiene el esquema de la parte o lo genera dinámicamente si supera las planificadas."""
    outlines = state.get("series_outline", [])
    for item in outlines:
        if item.get("part") == part_num:
            return item

    series = state.get("active_series", "Black Clover")
    new_part = {
        "part": part_num,
        "episodes": f"{(part_num - 1) * 3 + 1} - {part_num * 3}",
        "arc": "Continuación de Temporada",
        "subtitle": f"Batalla Decisiva y Misterio Revelado (Parte {part_num})",
        "topic": f"Resumen {series} Parte {part_num}: Batalla crucial sin relleno, choque de magias y revelaciones clave en la trama de Asta y sus aliados",
        "cliffhanger": f"Un giro inesperado cambia el curso del conflicto... ¡Síguenos para no perderte la Parte {part_num + 1} hoy mismo!",
    }
    outlines.append(new_part)
    state["series_outline"] = outlines
    _write_state(state)
    return new_part


def produce_and_publish_next_part() -> Dict[str, Any]:
    """Anime autopilot está totalmente detenido por orden del usuario."""
    safe_log("[AnimeAutopilot] 🛑 ANIME DETENIDO DEFINITIVAMENTE: Producción y publicación canceladas por el usuario.")
    with _lock:
        state = _read_state()
        state["is_producing"] = False
        state["config"]["enabled"] = False
        state["config"]["continuous_mode"] = False
        state["config"]["auto_publish"] = False
        _write_state(state)
    return {"success": False, "status": "permanently_disabled_by_user", "message": "Anime detenido por el usuario."}

    part_num = state.get("current_part", 1)
    series_name = state.get("active_series", "Black Clover")
    cfg = state.get("config", {})
    fb = state.get("facebook_page", {})
    duration_min = int(cfg.get("default_duration_min", 8))
    voice = cfg.get("voice", "speechify:alejandro")

    part_info = _get_or_create_part_outline(state, part_num)

    safe_log(f"\n[AnimeAutopilot] 🎬 Iniciando producción de «{series_name}» - PARTE {part_num}: {part_info.get('subtitle')}")
    safe_log(f"[AnimeAutopilot] Objetivo: {duration_min} minutos | Voz: {voice} | Página: {fb.get('page_name')}")

    try:
        ep_info = part_info.get('episodes', f"{(part_num - 1) * 3 + 1} - {part_num * 3}")
        arc_info = part_info.get('arc', 'Arco Actual')
        topic_prompt = (
            f"Black Clover {series_name} PARTE {part_num} — '{part_info.get('subtitle')}' (Episodios {ep_info}, {arc_info}).\n"
            f"FASE 1 — ULTRA-HOOK (primeros 15s): Empieza EN MEDIO de la acción más épica del arco. "
            f"Frase de apertura tipo: 'Lo subestimaron... creyeron que nunca llegaría hasta aquí. Gran error.' "
            f"NO empieces con 'Hola' ni 'En el capítulo anterior'. Empieza con tensión pura.\n"
            f"FASE 2 — RUSH narrativo (15s a 4min): Comprime la trama en fragmentos cortos y explosivos en tercera persona presente. "
            f"Modelo de frase: 'Quedan 10 rivales. Nadie espera nada de él. Entonces... saca la espada.' "
            f"Causa y efecto encadenado (Por eso → Pero → En ese momento). Sin relleno.\n"
            f"FASE 3 — CLÍMAX (últimos 90s): El momento más brutal del arco. Un instante de pausa dramática antes del golpe final, luego aceleración al máximo.\n"
            f"FASE 4 — CTA-LOOP (últimos 20s): Termina con el cliffhanger: «{part_info.get('cliffhanger')}». "
            f"Última frase que enganche directo a verlo de nuevo. Invita a seguir la página para la Parte {part_num + 1}.\n"
            f"Trama del arco: {part_info.get('topic')}."
        )

        create_payload = {
            "topic": topic_prompt[:500],
            "style": "divulgacion",
            "duration_sec": duration_min * 60,
            "aspect_ratio": cfg.get("aspect_ratio", "16:9"),
            "voice": voice,
            "flash_audit": True,
            "origin": "anime_autopilot",
            "auto_publish": False,
            "burn_subtitles": True,
            "subs_enabled": True,
            "sub_style": "viral",
            "crf": 17,
            "fps": 30,
            "extra_notes": (
                f"ANIME RECAP VIRAL — REGLAS DE GUION ({series_name} Parte {part_num} | Episodios {ep_info}):\n"
                "REGLA DE ORO DEL GUION: Frases cortas, explosivas, sin respiraderos. "
                "Modelo correcto: 'Quedan 10 rivales. Nadie espera nada de él. Entonces... saca la espada.' "
                "Modelo prohibido: 'Después de que los jueces evaluaron la capacidad destructiva de los participantes, Asta intentó su turno.'\n"
                "1. ULTRA-HOOK EN LOS PRIMEROS 15 SEGUNDOS: Empieza en el pico de la acción. "
                "Usa ganchos de curiosidad: 'Lo tenían muerto. Nadie vio venir lo que hizo después.' "
                "O de traición: 'Le dieron la espalda justo cuando más los necesitaba.' "
                "Prohibido empezar con contexto genérico o saludos.\n"
                "2. RITMO PUNCH: Cada oración máximo 12 palabras. Alterna ritmo rápido → pausa de 1 frase → golpe. "
                "Usa mucho suspense: puntos suspensivos, cortes abruptos, 'Hasta que...', 'Pero entonces...', 'Y ahí fue cuando...'.\n"
                "3. SINCRONIZACIÓN VISUAL 1:1: Cada vez que la narración nombre a Asta, Noelle, Yuno, Yami, Sekke u otro personaje, "
                "el visual_beat DEBE contener ese personaje. El trigger del beat debe ser la frase literal donde se menciona.\n"
                f"4. CERO ANACRONISMOS: Solo episodios {ep_info}. Prohibido Spade Arc, Devil Union, Dante o cualquier saga futura.\n"
                "5. CLÍMAX CON PAUSA DRAMÁTICA: 2 segundos de frase corta antes del golpe final para que el espectador aguante la respiración.\n"
                "6. 100% ANIMACIÓN OFICIAL — Cero personas reales, cero stock genérico."
            ),
        }

        # Precisión quirúrgica: descargar e indexar los episodios del tramo (cacheado, una sola vez)
        try:
            from core.anime_scene_matcher import AnimeSceneMatcher, parse_episode_range
            _eps = parse_episode_range(f"Episodios {ep_info}")
            if _eps:
                safe_log(f"[AnimeAutopilot] 🔎 Indexando episodios {_eps} para sincronía por mención...")
                _ok_idx = AnimeSceneMatcher.ensure_indexed(series_name, _eps, progress=safe_log)
                if not _ok_idx:
                    raise RuntimeError(
                        f"Índice de precisión incompleto para episodios {_eps}; se cancela la producción para no publicar con sincronía imprecisa."
                    )
        except Exception as _ix:
            safe_log(f"[AnimeAutopilot] ⛔ {_ix}")
            raise

        res = requests.post(f"{BASE_URL}/api/streamer/create", json=create_payload, timeout=60)
        res_data = res.json()
        project_id = res_data.get("project_id")
        if not project_id:
            raise RuntimeError(f"No se pudo crear proyecto de anime: {res_data}")

        safe_log(f"[AnimeAutopilot] Proyecto creado con éxito (ID: {project_id}). Esperando renderización...")

        # 2. Polling hasta completar la renderización
        master_file = settings.OUTPUTS_DIR / f"{project_id}_master.mp4"
        max_wait_seconds = 7200  # 2 horas máximo para videos de 6-10 min
        poll_interval = 15
        elapsed = 0

        while elapsed < max_wait_seconds:
            time.sleep(poll_interval)
            elapsed += poll_interval
            if master_file.exists() and master_file.stat().st_size > 1_000_000:
                safe_log(f"[AnimeAutopilot] ✨ Video master completado: {master_file.name} ({master_file.stat().st_size // (1024*1024)} MB)")
                break

        if not master_file.exists():
            raise TimeoutError(f"El renderizado de la Parte {part_num} superó el tiempo límite.")

        # 3. Publicación automática a Facebook
        publish_result = None
        if cfg.get("auto_publish") and fb.get("enabled") and fb.get("page_id") and fb.get("access_token"):
            safe_log(f"[AnimeAutopilot] 🚀 Publicando video en Facebook Page '{fb.get('page_name')}' (ID: {fb.get('page_id')})...")
            from core.facebook_publisher import publish_video_to_facebook

            token_to_use = fb["access_token"]
            try:
                chk_res = requests.get(
                    f"https://graph.facebook.com/v19.0/{fb['page_id']}",
                    params={"fields": "access_token", "access_token": token_to_use},
                    timeout=8
                )
                if chk_res.status_code == 200 and chk_res.text:
                    chk_json = chk_res.json()
                    if chk_json.get("access_token"):
                        token_to_use = chk_json["access_token"]
            except Exception:
                pass

            full_title = f"{series_name} | Temp 1 - Parte {part_num}: {part_info.get('subtitle')} [Resumen Completo]"
            full_description = (
                f"🔥 {full_title}\n\n"
                f"Resumen de los episodios {part_info.get('episodes')}.\n\n"
                f"{part_info.get('topic')}\n\n"
                f"⚡ {part_info.get('cliffhanger')}\n\n"
                f"👉 ¡Dale a Seguir a la página para no perderte la Parte {part_num + 1} hoy mismo!\n\n"
                f"#{series_name.replace(' ', '')} #AnimeRecap #Asta #Shonen #BlackCloverAnime"
            )

            try:
                publish_result = publish_video_to_facebook(
                    video_path=master_file,
                    title=full_title,
                    description=full_description,
                    page_id=fb["page_id"],
                    access_token=token_to_use,
                    is_reel=False,  # Video estándar para formato largo 6-10 min
                )
                safe_log(f"[AnimeAutopilot] ✅ Video publicado exitosamente en Facebook: {publish_result.get('post_url')}")
            except Exception as pub_err:
                safe_log(f"[AnimeAutopilot] ⚠️ Error publicando en Facebook: {pub_err}")

        # 4. Actualizar estado y avanzar al siguiente capítulo
        with _lock:
            state = _read_state()
            state["is_producing"] = False
            state["last_produced_at"] = datetime.now(timezone.utc).isoformat()
            if publish_result and publish_result.get("post_url"):
                state["last_published_url"] = publish_result.get("post_url")

            state["history"].append({
                "part": part_num,
                "project_id": project_id,
                "title": part_info.get("subtitle"),
                "duration_min": duration_min,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "facebook_url": (publish_result or {}).get("post_url"),
                "status": "published" if publish_result else "rendered",
            })

            state["current_part"] = part_num + 1
            _write_state(state)

        safe_log(f"[AnimeAutopilot] ✅ ¡PARTE {part_num} completada con éxito! Siguiente parte en cola: PARTE {part_num + 1}")

        # 5. Modo Continuo: «crea uno, publica, y apenas termine arranca el siguiente sobre la marcha»
        is_continuous = cfg.get("continuous_mode", True)
        if is_continuous and cfg.get("enabled", True):
            next_part_num = part_num + 1
            safe_log(f"[AnimeAutopilot] ⚡ Modo Continuo activo («crea y publica sobre la marcha»): Arrancando automáticamente PARTE {next_part_num} en 8 segundos...")
            import threading
            threading.Timer(8.0, produce_and_publish_next_part).start()

        return {
            "success": True,
            "part": part_num,
            "project_id": project_id,
            "facebook_url": (publish_result or {}).get("post_url"),
            "next_part": part_num + 1,
        }

    except Exception as exc:
        safe_log(f"[AnimeAutopilot] ❌ Error en producción de Parte {part_num}: {exc}")
        with _lock:
            state = _read_state()
            state["is_producing"] = False
            _write_state(state)
        return {"success": False, "error": str(exc), "part": part_num}


def trigger_next_part_async():
    """Lanza la producción de la siguiente parte en un hilo separado sin bloquear la UI."""
    t = threading.Thread(target=produce_and_publish_next_part, daemon=True, name="AnimeAutopilotTriggerThread")
    t.start()


def _cadence_loop():
    """Hilo en segundo plano que revisa periódicamente las horas estratégicas para publicar."""
    safe_log("[AnimeAutopilot] Hilo autónomo de programación de series de anime iniciado.")
    last_triggered_hour = -1

    while True:
        try:
            time.sleep(60)
            state = get_anime_series_state()
            cfg = state.get("config", {})
            if not cfg.get("enabled"):
                continue

            now = datetime.now()
            cur_hour = now.hour
            cur_min = now.minute

            strategic_hours = cfg.get("strategic_hours", [8, 13, 20])

            if cur_hour in strategic_hours and cur_hour != last_triggered_hour and 15 <= cur_min <= 45:
                if not state.get("is_producing"):
                    safe_log(f"[AnimeAutopilot] ⏰ Hora estratégica detectada ({cur_hour}:{cur_min:02d}). Disparando siguiente parte...")
                    last_triggered_hour = cur_hour
                    produce_and_publish_next_part()

        except Exception as exc:
            safe_log(f"[AnimeAutopilot] Aviso en ciclo de cadencia: {exc}")


def start_anime_series_autopilot():
    """Inicia el ciclo autónomo en segundo plano si aún no está iniciado."""
    global _worker_thread, _started
    with _lock:
        state = _read_state()
        if state.get("is_producing"):
            safe_log("[AnimeAutopilot] Limpiando bandera de producción residual al iniciar servidor...")
            state["is_producing"] = False
            _write_state(state)
        if _started:
            return
        _started = True
        _worker_thread = threading.Thread(target=_cadence_loop, daemon=True, name="AnimeAutopilotCadenceThread")
        _worker_thread.start()
