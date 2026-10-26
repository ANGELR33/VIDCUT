"""Motor de Precisión Quirúrgica para Anime Recap (AetherCut AI).

Objetivo: cuando la narración nombra a un personaje, una acción o un evento
(«Asta», «Noelle», «el golpe», «la espada»...), en ese INSTANTE exacto debe
aparecer en pantalla justo eso, tomado del episodio canónico.

Cómo lo logra (100% exclusivo de anime; el resto de formatos no lo usa):

1. INDEXADO (una sola vez por episodio, cacheado en disco):
   - Cortes de plano reales del episodio (detección de escena con FFmpeg).
   - Transcripción con marcas de tiempo del audio del episodio (faster-whisper).
   - Análisis visual con Gemini sobre hojas de contacto: qué personajes y qué
     acción aparecen cada ~4 s.
2. PLANIFICACIÓN POR ESCENA:
   - Se alinea el guion con la voz del narrador (Whisper + alineación) para
     saber el segundo exacto en que se pronuncia cada nombre/acción.
   - Cada mención genera un corte; se busca el plano del episodio donde ese
     personaje/acción realmente aparece (visión + transcripción + cronología).
   - El corte arranca al inicio del plano (snap a cortes reales).
"""

from __future__ import annotations

import difflib
import json
import math
import re
import shutil
import subprocess
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.settings import settings
from core.llm import safe_log
from core.anime_episode_manager import AnimeEpisodeManager

INDEX_VERSION = 1
USEFUL_START = 90.0          # salta opening
FRAME_STEP = 4.0             # un fotograma analizado cada 4 s
SHEET_COLS, SHEET_ROWS = 4, 3
CELL_W, CELL_H = 480, 270

# ---------------------------------------------------------------------------
# Rosters por serie (nombre canónico -> alias hablados + pista de aspecto)
# ---------------------------------------------------------------------------
BLACK_CLOVER_ROSTER: Dict[str, Dict[str, Any]] = {
    "Asta": {"aliases": ["asta"], "look": "chico de cabello rubio ceniza erizado, sin magia, grimorio negro de cinco hojas, espadas negras antimagia"},
    "Yuno": {"aliases": ["yuno"], "look": "chico de cabello negro, grimorio verde de cuatro hojas, magia de viento"},
    "Noelle": {"aliases": ["noelle", "noel"], "look": "chica de cabello plateado con coletas, magia de agua, familia real Silva"},
    "Yami": {"aliases": ["yami", "sukehiro"], "look": "hombre alto de cabello negro con katana, capitán de los Toros Negros"},
    "Sekke": {"aliases": ["sekke", "bronzazza"], "look": "noble de cabello castaño peinado atrás, magia de bronce, arrogante"},
    "Vanessa": {"aliases": ["vanessa", "enoteca"], "look": "mujer de cabello rojizo con vestimenta de bruja, magia de hilo"},
    "Luck": {"aliases": ["luck", "voltia"], "look": "chico rubio con sonrisa de combate, magia de trueno"},
    "Magna": {"aliases": ["magna", "swing"], "look": "chico alto de cabello oscuro con abrigo, magia de fuego"},
    "Finral": {"aliases": ["finral", "roulacase"], "look": "chico rubio con lunar, magia de portales espaciales"},
    "Gauche": {"aliases": ["gauche", "adlai"], "look": "chico de cabello oscuro azulado, magia de espejos"},
    "Gordon": {"aliases": ["gordon", "agrippa"], "look": "chico pálido de cabello morado con capucha, magia de maldiciones"},
    "Grey": {"aliases": ["grey"], "look": "chica que se transforma en pájaro"},
    "Charmy": {"aliases": ["charmy", "pappitson"], "look": "niña pequeña de cabello rosado que come mucho, magia de algodón"},
    "Zora": {"aliases": ["zora", "ideale"], "look": "chico de cabello claro con cicatriz, magia de trampas"},
    "Secre": {"aliases": ["secre", "swallowtail"], "look": "chica con hábito de monja"},
    "Klaus": {"aliases": ["klaus", "lunettes"], "look": "chico con gafas, magia de plantas"},
    "Mimosa": {"aliases": ["mimosa", "vermillion"], "look": "chica de cabello rosa claro, magia de plantas y curación"},
    "Fuegoleon": {"aliases": ["fuegoleon"], "look": "hombre de cabello rojo con barba, capitán Leones Carmesí, magia de fuego"},
    "Nozel": {"aliases": ["nozel"], "look": "hombre de cabello plateado, capitán Águilas Plateadas"},
    "William": {"aliases": ["william", "vangeance"], "look": "hombre de cabello castaño, capitán Alba Dorada"},
    "Julius": {"aliases": ["julius", "novachrono"], "look": "Rey Mago, barba blanca, capa de rey"},
    "Licht": {"aliases": ["licht"], "look": "líder de Ojo de la Noche Blanca, magia de luz"},
    "Mars": {"aliases": ["mars"], "look": "guerrero del Reino del Diamante, magia de cristal/mineral"},
    "Fanzell": {"aliases": ["fanzell"], "look": "anciano maestro con bastón"},
    "Lily": {"aliases": ["lily"], "look": "hermana de la iglesia del pueblo"},
    "Orsi": {"aliases": ["orsi"], "look": "padre de la iglesia"},
    "Marx": {"aliases": ["marx"], "look": "mago evaluador del examen"},
    "Langris": {"aliases": ["langris"], "look": "mago de cabello rubio con ropas elegantes, magia de espadas"},
    "Nacht": {"aliases": ["nacht"], "look": "mago de pelo oscuro, magia de sombras"},
}

ROSTERS: Dict[str, Dict[str, Dict[str, Any]]] = {"black clover": BLACK_CLOVER_ROSTER}

# Palabras de acción/objeto que, al pronunciarse, justifican un corte visual
ACTION_WORDS = [
    "golpe", "golpea", "puño", "patada", "espada", "espadas", "grimorio", "ataque", "explosión",
    "explota", "pelea", "duelo", "combate", "batalla", "examen", "fuego", "llamas", "agua",
    "viento", "rayo", "trueno", "cadenas", "salta", "corre", "llora", "grita", "abraza",
    "dragón", "mazmorra", "tesoro", "sombra", "escudo", "hechizo", "trébol", "castillo",
    "bosque", "derrota", "victoria", "corte", "tormenta", "iglesia", "aldea",
]

STOPWORDS = set("""
a al algo algun alguna algunos ante aqui asi aun aunque cada como con contra cual cuando de del desde donde
dos el ella ellas ello ellos en entre era eran es esa esas ese eso esos esta estaba estan estas este esto estos
fue fueron ha han hasta hay la las le les lo los mas me mi mientras muy ni no nos nuestro o otra otro para pero
poco por porque pues que quien se sera si sido sin sobre solo son su sus tambien tan tanto te tiene tienen todo
todos tras tu un una uno unos ya y yo cuya cuyo ser estar hacer hace hacen puede pueden luego entonces ahora
""".split())


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _norm_tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", _strip_accents((text or "").lower()))


def _stem(tok: str) -> str:
    return tok[:5] if len(tok) > 5 else tok


ACTION_STEMS = {_stem(t) for w in ACTION_WORDS for t in _norm_tokens(w)}


def parse_episode_range(text: str) -> List[int]:
    """'Episodios 4 - 6' -> [4, 5, 6]. Vacío si no se encuentra."""
    m = re.search(r"(?:episodios?|episodes?|ep\.?)\s*(\d+)\s*(?:-|–|a|to)\s*(\d+)", text or "", re.IGNORECASE)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < a <= b <= a + 12:
            return list(range(a, b + 1))
    m = re.search(r"(?:episodios?|episodes?|ep\.?)\s*(\d+)", text or "", re.IGNORECASE)
    return [int(m.group(1))] if m else []


# ---------------------------------------------------------------------------
# ASR (faster-whisper) compartido
# ---------------------------------------------------------------------------
_ASR_LOCK = threading.Lock()
_ASR_MODEL = None
_ASR_NAME = ""


def _asr_model():
    global _ASR_MODEL, _ASR_NAME
    with _ASR_LOCK:
        if _ASR_MODEL is None:
            from faster_whisper import WhisperModel
            for size in ("small", "base"):
                try:
                    _ASR_MODEL = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=6)
                    _ASR_NAME = size
                    safe_log(f"[AnimeMatcher] Whisper '{size}' cargado para indexado/alineación.")
                    break
                except Exception as exc:
                    safe_log(f"[AnimeMatcher] No se pudo cargar Whisper '{size}': {exc}")
            if _ASR_MODEL is None:
                raise RuntimeError("faster-whisper no disponible")
        return _ASR_MODEL


_TRANSCRIBE_LOCK = threading.Lock()   # CTranslate2: una inferencia a la vez

_index_locks: Dict[Tuple[str, int], threading.Lock] = {}
_index_locks_guard = threading.Lock()
_used_lock = threading.Lock()
_prepared_cache: Dict[Tuple[str, int, float], Dict[str, Any]] = {}


def _lock_for(series: str, ep: int) -> threading.Lock:
    with _index_locks_guard:
        return _index_locks.setdefault((series.lower(), ep), threading.Lock())


class AnimeSceneMatcher:
    """Indexa episodios y planifica cortes sincronizados con la narración."""

    # ------------------------------------------------------------------ util
    @classmethod
    def roster_for(cls, series: str) -> Dict[str, Dict[str, Any]]:
        return ROSTERS.get(series.lower().strip(), {})

    @classmethod
    def _alias_map(cls, series: str) -> Dict[str, str]:
        m: Dict[str, str] = {}
        for canon, info in cls.roster_for(series).items():
            for a in info.get("aliases", []):
                for t in _norm_tokens(a):
                    m[t] = canon
        return m

    @classmethod
    def index_path(cls, series: str, ep: int) -> Path:
        return AnimeEpisodeManager.BASE_DIR / series.strip() / f"episode_{ep:02d}.index.json"

    @classmethod
    def load_index(cls, series: str, ep: int) -> Optional[Dict[str, Any]]:
        p = cls.index_path(series, ep)
        try:
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                if d.get("version") == INDEX_VERSION:
                    return d
        except Exception as exc:
            safe_log(f"[AnimeMatcher] Índice ilegible ({p.name}): {exc}")
        return None

    @classmethod
    def _save_index(cls, series: str, ep: int, data: Dict[str, Any]) -> None:
        p = cls.index_path(series, ep)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)

    @staticmethod
    def _probe_duration(src: Path) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                capture_output=True, text=True, timeout=30,
            )
            return float((r.stdout or "0").strip() or 0)
        except Exception:
            return 0.0

    # --------------------------------------------------------------- indexado
    @classmethod
    def ensure_indexed(cls, series: str, episodes: List[int],
                       progress: Optional[Callable[[str], None]] = None) -> bool:
        """Garantiza índice completo (planos + transcripción + visión) de cada episodio."""
        ok_all = True
        for ep in episodes:
            try:
                if not cls._ensure_one(series, ep, progress):
                    ok_all = False
            except Exception as exc:
                ok_all = False
                safe_log(f"[AnimeMatcher] ❌ Falló indexado Ep {ep}: {exc}")
        return ok_all

    @classmethod
    def _ensure_one(cls, series: str, ep: int, progress=None) -> bool:
        with _lock_for(series, ep):
            data = cls.load_index(series, ep)
            if data and data.get("shots_done") and data.get("asr_done") and data.get("vision_ratio", 0) >= 0.85:
                return True

            src = AnimeEpisodeManager.get_or_download_episode(series, ep)
            if not src:
                safe_log(f"[AnimeMatcher] Sin archivo local del Ep {ep}: no se puede indexar.")
                return False

            dur = cls._probe_duration(src)
            useful_end = max(USEFUL_START + 300.0, min(1335.0, (dur or 1440.0) - 105.0))
            if not data:
                data = {"version": INDEX_VERSION, "series": series, "episode": ep,
                        "start": USEFUL_START, "end": useful_end, "duration": dur,
                        "shots": [], "frames": [], "transcript": [],
                        "shots_done": False, "asr_done": False, "vision_ratio": 0.0}
            data["end"] = useful_end
            say = (lambda m: (progress(m) if progress else None, safe_log(m)))
            say(f"[AnimeMatcher] 🔎 Indexando Ep {ep} de «{series}» (una sola vez)...")

            # A) cortes de plano reales
            if not data.get("shots_done"):
                data["shots"] = cls._detect_shots(src, USEFUL_START, useful_end)
                data["shots_done"] = True
                cls._save_index(series, ep, data)
                say(f"[AnimeMatcher]   ✓ Ep {ep}: {len(data['shots'])} planos detectados.")

            # B) visión (hilos) en paralelo con C) transcripción
            vis_result: Dict[str, Any] = {}

            def _vision():
                try:
                    vis_result["frames"] = cls._build_vision(series, ep, src, data)
                except Exception as exc:
                    vis_result["error"] = str(exc)
                    safe_log(f"[AnimeMatcher] Visión Ep {ep} falló: {exc}")

            vt = None
            if data.get("vision_ratio", 0) < 0.85:
                vt = threading.Thread(target=_vision, daemon=True)
                vt.start()

            if not data.get("asr_done"):
                try:
                    data["transcript"] = cls._transcribe_episode(src, USEFUL_START, useful_end)
                    data["asr_done"] = True
                    cls._save_index(series, ep, data)
                    say(f"[AnimeMatcher]   ✓ Ep {ep}: {len(data['transcript'])} frases transcritas.")
                except Exception as exc:
                    safe_log(f"[AnimeMatcher] Transcripción Ep {ep} falló: {exc}")

            if vt:
                vt.join()
                if vis_result.get("frames"):
                    data["frames"] = vis_result["frames"]
                    lab = sum(1 for f in data["frames"] if f.get("ok"))
                    data["vision_ratio"] = round(lab / max(1, len(data["frames"])), 3)
                    cls._save_index(series, ep, data)
                    say(f"[AnimeMatcher]   ✓ Ep {ep}: visión {lab}/{len(data['frames'])} fotogramas etiquetados.")

            cls._save_index(series, ep, data)
            return bool(data.get("shots_done") and data.get("asr_done") and data.get("vision_ratio", 0) >= 0.85)

    @staticmethod
    def _detect_shots(src: Path, t0: float, t1: float) -> List[float]:
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-ss", f"{t0:.2f}", "-t", f"{t1 - t0:.2f}",
            "-i", str(src), "-vf", "scale=320:-2,select='gt(scene,0.30)',showinfo",
            "-an", "-f", "null", "-",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=1500)
        times = sorted({round(t0 + float(m), 2) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr or "")})
        return times

    @classmethod
    def _transcribe_episode(cls, src: Path, t0: float, t1: float) -> List[Dict[str, Any]]:
        tmp_dir = src.parent / "_tmp_index"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        wav = tmp_dir / f"{src.stem}.16k.wav"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{t0:.2f}", "-t", f"{t1 - t0:.2f}", "-i", str(src),
                 "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                capture_output=True, timeout=600, check=True,
            )
            model = _asr_model()
            names = ", ".join(sorted({k for r in ROSTERS.values() for k in r}))
            out: List[Dict[str, Any]] = []
            with _TRANSCRIBE_LOCK:
                segs, _ = model.transcribe(
                    str(wav), language="es", vad_filter=True, beam_size=1,
                    condition_on_previous_text=False,
                    initial_prompt=f"Anime Black Clover. Personajes: {names}.",
                )
                for s in segs:
                    txt = (s.text or "").strip()
                    if txt:
                        out.append({"s": round(t0 + float(s.start), 2), "e": round(t0 + float(s.end), 2), "text": txt})
            return out
        finally:
            wav.unlink(missing_ok=True)
            try:
                tmp_dir.rmdir()
            except OSError:
                pass

    @classmethod
    def _build_vision(cls, series: str, ep: int, src: Path, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        import cv2
        import numpy as np
        from google.genai import types as gtypes
        from core.llm import LLMClient

        t0, t1 = float(data["start"]), float(data["end"])
        tmp_dir = src.parent / f"_tmp_frames_{ep:02d}"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{t0:.2f}", "-t", f"{t1 - t0:.2f}", "-i", str(src),
                 "-vf", f"fps=1/{FRAME_STEP:g},scale={CELL_W}:{CELL_H}:force_original_aspect_ratio=decrease,"
                        f"pad={CELL_W}:{CELL_H}:(ow-iw)/2:(oh-ih)/2",
                 "-q:v", "4", str(tmp_dir / "f_%04d.jpg")],
                capture_output=True, timeout=900, check=True,
            )
            files = sorted(tmp_dir.glob("f_*.jpg"))
            frames: List[Dict[str, Any]] = [
                {"t": round(t0 + i * FRAME_STEP, 2), "chars": [], "accion": "", "tags": [], "ok": False}
                for i in range(len(files))
            ]
            per = SHEET_COLS * SHEET_ROWS
            roster = cls.roster_for(series)
            roster_txt = "\n".join(f"- {n}: {i.get('look', '')}" for n, i in roster.items()) or "(sin lista: deja personajes vacío)"

            def label_sheet(start: int) -> None:
                chunk = files[start:start + per]
                canvas = np.zeros((CELL_H * SHEET_ROWS, CELL_W * SHEET_COLS, 3), dtype=np.uint8)
                for k, fp in enumerate(chunk):
                    img = cv2.imread(str(fp))
                    if img is None:
                        continue
                    r, c = divmod(k, SHEET_COLS)
                    cell = cv2.resize(img, (CELL_W, CELL_H))
                    tag = f"t={int(frames[start + k]['t'])}"
                    cv2.putText(cell, tag, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 5, cv2.LINE_AA)
                    cv2.putText(cell, tag, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
                    canvas[r * CELL_H:(r + 1) * CELL_H, c * CELL_W:(c + 1) * CELL_W] = cell
                okj, buf = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if not okj:
                    return
                prompt = (
                    f"Eres analista del anime «{series}». La imagen es una hoja de contacto con {len(chunk)} fotogramas "
                    f"del episodio {ep}; cada celda lleva su etiqueta amarilla 't=SEGUNDOS'.\n"
                    "Para CADA celda devuelve: 'personajes' (SOLO nombres de esta lista; si dudas o es otro personaje, déjalo fuera), "
                    "'accion' (frase corta en español, máx 12 palabras, de lo que ocurre) y 'tags' (3 a 6 palabras clave en español, minúsculas: "
                    "objetos, magia, lugar, emoción, acción).\n"
                    f"Personajes y pistas de aspecto:\n{roster_txt}\n"
                    'Responde SOLO JSON: {"frames":[{"t":123,"personajes":["Asta"],"accion":"...","tags":["..."]}]}'
                )
                for attempt in range(3):
                    try:
                        llm = LLMClient()
                        raw = llm.generate(
                            [gtypes.Part.from_bytes(data=buf.tobytes(), mime_type="image/jpeg"), prompt],
                            json_mode=True, max_models=2, deadline_sec=100,
                        )
                        parsed = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
                        by_t = {int(round(f["t"])): f for f in frames[start:start + len(chunk)]}
                        for item in parsed.get("frames", []):
                            try:
                                tt = int(round(float(item.get("t"))))
                            except Exception:
                                continue
                            tgt = by_t.get(tt) or by_t.get(min(by_t, key=lambda x: abs(x - tt))) if by_t else None
                            if tgt is None:
                                continue
                            valid = {n for n in roster}
                            tgt["chars"] = [p for p in (item.get("personajes") or []) if p in valid]
                            tgt["accion"] = str(item.get("accion") or "")[:120]
                            tgt["tags"] = [str(x).lower()[:30] for x in (item.get("tags") or [])][:8]
                            tgt["ok"] = True
                        return
                    except Exception as exc:
                        safe_log(f"[AnimeMatcher] Hoja visual Ep {ep} #{start // per} intento {attempt + 1}/3: {str(exc)[:90]}")
                        time.sleep(2 + attempt * 3)

            starts = list(range(0, len(files), per))
            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(label_sheet, starts))
            return frames
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ----------------------------------------------------------- planificación
    @classmethod
    def _prepare(cls, series: str, ep: int, data: Dict[str, Any]) -> Dict[str, Any]:
        key = (series.lower(), ep, cls.index_path(series, ep).stat().st_mtime)
        if key in _prepared_cache:
            return _prepared_cache[key]
        segs = data.get("transcript", [])
        frames = []
        for f in data.get("frames", []):
            t = float(f["t"])
            asr_txt = " ".join(s["text"] for s in segs if s["e"] >= t - 3.0 and s["s"] <= t + 5.0)
            frames.append({
                "t": t,
                "chars": set(f.get("chars", [])),
                "tags": {_stem(x) for tag in f.get("tags", []) for x in _norm_tokens(tag)},
                "act": {_stem(x) for x in _norm_tokens(f.get("accion", "")) if x not in STOPWORDS},
                "asr": {_stem(x) for x in _norm_tokens(asr_txt) if x not in STOPWORDS},
                "asr_tokens": set(_norm_tokens(asr_txt)),
                "ok": bool(f.get("ok")),
            })
        prep = {"frames": frames, "shots": sorted(data.get("shots", [])),
                "start": data.get("start", USEFUL_START), "end": data.get("end", 1330.0)}
        _prepared_cache[key] = prep
        return prep

    @classmethod
    def _script_times(cls, audio_path: Optional[Path], speech_text: str,
                      sentence_boundaries: List[Tuple[float, float, str]], duration: float
                      ) -> List[Tuple[str, float]]:
        """Tokens del guion con su segundo exacto en la voz del narrador."""
        script = _norm_tokens(speech_text)
        if not script:
            return []
        asr: List[Tuple[str, float]] = []
        if audio_path and Path(audio_path).exists():
            try:
                model = _asr_model()
                with _TRANSCRIBE_LOCK:
                    segs, _ = model.transcribe(
                        str(audio_path), language="es", word_timestamps=True, vad_filter=False,
                        beam_size=1, condition_on_previous_text=False,
                    )
                    for s in segs:
                        for w in (s.words or []):
                            for tk in _norm_tokens(w.word):
                                asr.append((tk, float(w.start)))
            except Exception as exc:
                safe_log(f"[AnimeMatcher] ASR de la voz falló, uso tiempos proporcionales: {exc}")
        times: List[Optional[float]] = [None] * len(script)
        if len(asr) >= max(3, len(script) // 4):
            sm = difflib.SequenceMatcher(None, script, [a[0] for a in asr], autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    for k in range(i2 - i1):
                        times[i1 + k] = asr[j1 + k][1]
                elif tag == "replace":
                    span = max(1, i2 - i1)
                    for k in range(i1, i2):
                        j = j1 + int((k - i1) * (j2 - j1) / span)
                        times[k] = asr[min(j, j2 - 1)][1]
        else:
            # Proporcional por caracteres sobre el audio completo
            tot = max(1, sum(len(t) for t in script))
            acc = 0
            for i, t in enumerate(script):
                times[i] = (acc / tot) * duration
                acc += len(t)
        # interpolar huecos
        known = [i for i, v in enumerate(times) if v is not None]
        if not known:
            return [(t, i * duration / max(1, len(script))) for i, t in enumerate(script)]
        for i in range(len(script)):
            if times[i] is None:
                prev = max((k for k in known if k < i), default=None)
                nxt = min((k for k in known if k > i), default=None)
                if prev is None:
                    times[i] = max(0.0, times[nxt] - 0.25 * (nxt - i))
                elif nxt is None:
                    times[i] = min(duration, times[prev] + 0.25 * (i - prev))
                else:
                    frac = (i - prev) / (nxt - prev)
                    times[i] = times[prev] + frac * (times[nxt] - times[prev])
        return [(script[i], float(times[i])) for i in range(len(script))]

    @classmethod
    def plan_scene(cls, series: str, episodes: List[int], speech_text: str,
                   sentence_boundaries: List[Tuple[float, float, str]], audio_path: Optional[Path],
                   duration: float, scene_pos: float, scene_span: float,
                   used: List[Tuple[int, float]], scene_label: str = "") -> List[Dict[str, Any]]:
        """Devuelve cortes [{t, dur, ep, src, why}] sincronizados con la narración."""
        preps: Dict[int, Dict[str, Any]] = {}
        for ep in episodes:
            d = cls.load_index(series, ep)
            if not d or not d.get("shots_done") or d.get("vision_ratio", 0) < 0.5:
                safe_log(f"[AnimeMatcher] Índice incompleto del Ep {ep}; escena {scene_label} usa método base.")
                return []
            preps[ep] = cls._prepare(series, ep, d)

        alias = cls._alias_map(series)
        toks = cls._script_times(audio_path, speech_text, sentence_boundaries, duration)
        if not toks:
            return []

        # --- eventos (menciones) con su segundo exacto
        events: List[Tuple[float, str, str]] = []
        for tk, t in toks:
            if tk in alias:
                events.append((t, "ent", alias[tk]))
            elif _stem(tk) in ACTION_STEMS and tk not in STOPWORDS:
                events.append((t, "act", tk))
        events.sort()

        # --- anclas de corte
        anchors: List[float] = [0.0]
        for t, kind, _v in events:
            a = max(0.0, t - 0.20)
            gap = 1.5 if kind == "ent" else 2.4
            if a - anchors[-1] >= gap and a <= duration - 1.2:
                anchors.append(round(a, 2))
        MAX_GAP = 4.6
        filled: List[float] = []
        for i, a in enumerate(anchors):
            filled.append(a)
            nxt = anchors[i + 1] if i + 1 < len(anchors) else duration
            g = nxt - a
            if g > MAX_GAP:
                n = math.ceil(g / 4.0)
                step = g / n
                for k in range(1, n):
                    filled.append(round(a + k * step, 2))
        anchors = sorted(set(filled))
        if len(anchors) > 1 and duration - anchors[-1] < 1.2:
            anchors.pop()

        segs: List[Dict[str, Any]] = []
        for i, a in enumerate(anchors):
            b = anchors[i + 1] if i + 1 < len(anchors) else duration
            words = [(tk, t) for tk, t in toks if a - 0.05 <= t < b + 0.20]
            ents: List[str] = []
            for tk, _t in words:
                if tk in alias and alias[tk] not in ents:
                    ents.append(alias[tk])
            kws = {_stem(tk) for tk, _t in words if len(tk) >= 4 and tk not in STOPWORDS and tk not in alias}
            segs.append({"a": a, "b": b, "ents": ents, "kws": kws,
                         "text": " ".join(tk for tk, _ in words)})

        n_eps = len(episodes)
        cuts: List[Dict[str, Any]] = []
        local_used: List[Tuple[int, float]] = []

        prev_pick: Optional[Tuple[int, float]] = None
        for sg in segs:
            best = None
            p_exp = min(1.0, scene_pos + (sg["a"] / max(0.1, duration)) * scene_span)
            with _used_lock:
                all_used = list(used) + local_used
            for ei, ep in enumerate(episodes):
                prep = preps[ep]
                span = max(1.0, prep["end"] - prep["start"])
                for fr in prep["frames"]:
                    s = 0.0
                    for k, e in enumerate(sg["ents"]):
                        w = 4.0 if k == 0 else 2.5
                        if e in fr["chars"]:
                            s += w
                        elif any(_stem(x) in fr["asr"] for a_ in [e] for x in _norm_tokens(a_)):
                            s += w * 0.45
                    if sg["ents"] and not any(e in fr["chars"] for e in sg["ents"]):
                        s -= 1.5
                    kw = sg["kws"]
                    if kw:
                        s += min(len(kw & fr["tags"]), 3) * 1.0
                        s += min(len(kw & fr["act"]), 3) * 1.2
                        s += min(len(kw & fr["asr"]), 3) * 0.5
                    g = (ei + (fr["t"] - prep["start"]) / span) / n_eps
                    s += 3.0 * math.exp(-((g - p_exp) / 0.12) ** 2)
                    # Continuidad narrativa: el siguiente corte debe avanzar desde
                    # el anterior en el mismo episodio, como un scroll temporal.
                    if prev_pick is not None:
                        dp = fr["t"] - prev_pick[1]
                        if ep == prev_pick[0] and 0 <= dp <= 80.0:
                            # Avance natural (0 a 80s despues): bonus grande
                            s += 4.5 * math.exp(-((dp - 15.0) / 35.0) ** 2)
                        elif ep == prev_pick[0] and dp < 0:
                            # Retroceder en el mismo episodio: penalizar
                            s -= 6.0
                        else:
                            # Saltar a otro episodio o zona muy lejana: penalizar
                            s -= 8.0
                    for uep, ut in all_used:
                        if uep == ep:
                            d = abs(ut - fr["t"])
                            if d < 7.0:
                                s -= 50.0
                            elif d < 16.0:
                                s -= 3.0 * (1.0 - (d - 7.0) / 9.0)
                    if best is None or s > best[0]:
                        best = (s, ep, fr)
            if best is None:
                continue
            score, ep, fr = best
            prep = preps[ep]
            ft = fr["t"]
            shots = [c for c in prep["shots"] if c <= ft]
            shot_start = shots[-1] if shots else ft
            start = max(shot_start, ft - 2.5, prep["start"])
            seg_dur = max(1.2, sg["b"] - sg["a"])
            start = min(start, prep["end"] - (seg_dur + 1.0))
            local_used.append((ep, start))
            prev_pick = (ep, float(start))
            why = []
            if sg["ents"]:
                vis = [e for e in sg["ents"] if e in fr["chars"]]
                why.append(("visible: " + ", ".join(vis)) if vis else ("sin coincidencia visual de " + ", ".join(sg["ents"])))
            matched_kw = sorted((sg["kws"] & (fr["tags"] | fr["act"])))[:3]
            if matched_kw:
                why.append("acción: " + ", ".join(matched_kw))
            cuts.append({
                "t": float(sg["a"]), "dur": float(seg_dur), "ep": ep, "src": round(float(start), 2),
                "score": round(score, 2), "ents": sg["ents"], "why": "; ".join(why) or "cronología",
                "text": sg["text"][:70],
            })

        with _used_lock:
            used.extend(local_used)
        return cuts
