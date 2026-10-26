"""Analizador Inteligente de Soundbites y Declaraciones Estratégicas.

Permite analizar videos completos (videos fuente de casos, entrevistas, ruedas de prensa)
o clips descargados para identificar fragmentos donde el protagonista habla con:
1. Puntos estratégicos y lógica discursiva completa (oraciones completas, no fragmentos cortados).
2. Relevancia semántica con lo que el avatar está narrando.
3. Cero murmullos, saludos de relleno ("buenos días", "gracias por venir") ni carraspeos.
4. Extracción limpia de audio y video con amortiguación natural (lead-in/lead-out).
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings
from core.llm import safe_log

# Saludos, fórmulas de cortesía y muletillas a filtrar del inicio de un soundbite
GREETINGS_AND_FILLERS = {
    "buenos dias", "buenos días", "buenas tardes", "buenas noches",
    "hola a todos", "hola que tal", "hola qué tal", "muchas gracias a todos",
    "muchas gracias", "un saludo cordial", "un saludo a todos", "bienvenidos a todos",
    "bienvenidos", "gracias por venir", "agradezco a los medios", "se escucha",
    "probando sonido", "probando micrófono", "uno dos tres", "este...", "eh...",
    "bueno pues", "o sea", "la verdad es que pues", "como les decía", "como decia"
}

# Verbos y conectores que denotan declaraciones, argumentos o revelaciones de peso
DECLARATIVE_MARKERS = {
    "afirmó", "afirmo", "declaró", "declaro", "aseguró", "aseguro", "vamos a",
    "hemos decidido", "no permitiremos", "la realidad es", "el problema es",
    "esto demuestra", "quiero dejar claro", "nuestra postura es", "el resultado fue",
    "la cifra supera", "hemos comprobado", "no es posible que", "la verdad es que",
    "estamos ante", "se confirma que", "advierto que", "la decisión es", "rechazamos",
    "reconozco que", "el objetivo principal", "hemos logrado", "la ley establece"
}

# Conectores, preposiciones y partículas incompletas que NUNCA deben cerrar un soundbite o frase
INCOMPLETE_ENDINGS = {
    "que", "de", "del", "al", "a", "en", "con", "por", "para", "sin", "sobre", "hacia", "hasta", "desde", "entre",
    "y", "e", "o", "u", "pero", "sino", "porque", "pues", "ya que", "puesto que",
    "cuando", "si", "como", "donde", "mientras", "aunque", "el", "la", "los", "las",
    "un", "una", "unos", "unas", "su", "sus", "mi", "mis", "tu", "tus", "nuestro",
    "nuestra", "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    "es", "son", "fue", "era", "ha", "han", "ser", "estar", "haber",
    "muy", "tan", "más", "mas", "menos"
}


@dataclass
class StrategicSoundbite:
    start_sec: float
    end_sec: float
    duration: float
    quote: str
    confidence: float = 1.0
    clip_path: Optional[Path] = None
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_sec": round(self.start_sec, 2),
            "end_sec": round(self.end_sec, 2),
            "duration": round(self.duration, 2),
            "quote": self.quote,
            "confidence": round(self.confidence, 2),
            "clip_path": str(self.clip_path) if self.clip_path else None,
            "keywords": self.keywords,
        }


class StrategicSoundbiteAnalyzer:
    """Motor de análisis de audio y discurso para detectar declaraciones estratégicas."""

    def __init__(self, language: str = "es"):
        self.language = language

    @staticmethod
    def _is_filler_start(text: str) -> bool:
        """Determina si la frase comienza con fórmulas de cortesía o relleno no informativo."""
        clean = re.sub(r"[^\w\s]", "", text.lower()).strip()
        for filler in GREETINGS_AND_FILLERS:
            if clean.startswith(filler):
                return True
        return False

    @staticmethod
    def _is_incomplete_ending(text: str) -> bool:
        """Determina si la frase termina en un conector incompleto, preposición o partícula colgante."""
        clean = re.sub(r"[^\w\s]", "", text.lower()).strip()
        words = clean.split()
        if not words:
            return True
        return words[-1] in INCOMPLETE_ENDINGS

    @staticmethod
    def _score_soundbite(
        text: str,
        duration: float,
        target_keywords: Optional[List[str]] = None,
    ) -> float:
        """Calcula un puntaje de idoneidad periodística y lógica del soundbite."""
        score = 1.0
        words = text.split()
        word_count = len(words)

        # 1. Penalizar fragmentos demasiado cortos o sin sustancia
        if word_count < 4 or duration < 1.8:
            return 0.1

        # 2. Premiar ventana ideal para soundbite broadcast (2.4s - 5.0s)
        if 2.4 <= duration <= 4.8:
            score += 2.0
        elif 4.8 < duration <= 6.5:
            score += 1.0
        elif duration > 7.0:
            score -= 1.5

        # 3. Penalizar inicios con saludos o muletillas
        if StrategicSoundbiteAnalyzer._is_filler_start(text):
            score -= 3.0

        # 3b. Penalizar fuertemente oraciones truncadas que terminan en conectores o incompletas
        if StrategicSoundbiteAnalyzer._is_incomplete_ending(text):
            score -= 6.0

        # 4. Premiar presencia de verbos declarativos y asertivos
        text_lower = text.lower()
        declarative_hits = sum(1 for marker in DECLARATIVE_MARKERS if marker in text_lower)
        score += min(3.0, declarative_hits * 1.5)

        # 5. Coincidencia con palabras clave del tema o de lo que KAI está narrando
        if target_keywords:
            clean_targets = {k.lower().strip() for k in target_keywords if len(k.strip()) >= 3}
            matches = sum(1 for kw in clean_targets if kw in text_lower)
            score += matches * 2.0

        # 6. Puntuación ortográfica: termina en punto, exclamación o interrogación
        if re.search(r"[.!?]$", text.strip()) and not StrategicSoundbiteAnalyzer._is_incomplete_ending(text):
            score += 1.2

        return max(0.1, score)

    def analyze_full_video(
        self,
        video_path: Path,
        topic: str = "",
        workdir: Optional[Path] = None,
        max_soundbites: int = 4,
    ) -> List[StrategicSoundbite]:
        """Analiza el video completo mediante transcripción con Whisper y extrae los mejores soundbites estratégicos."""
        if not video_path.exists():
            return []

        out_dir = workdir or video_path.parent
        soundbites_dir = out_dir / "case_soundbites"
        soundbites_dir.mkdir(parents=True, exist_ok=True)

        safe_log(f"[SoundbiteAnalyzer] 🎙️ Analizando video completo ({video_path.name}) para extraer declaraciones clave...")

        # 1. Extraer audio ligero en 16kHz mono para transcripción rápida
        wav_path = soundbites_dir / "full_audio_16k.wav"
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", "16000",
                    str(wav_path)
                ],
                capture_output=True, check=True, timeout=90
            )
        except Exception as e:
            safe_log(f"[SoundbiteAnalyzer] Error extrayendo audio del video: {e}")
            return []

        # 2. Transcripción con marcas de tiempo por palabra
        from core.transcriber import _model
        try:
            model = _model("base")
            segments, _ = model.transcribe(
                str(wav_path),
                language=self.language,
                word_timestamps=True,
                vad_filter=True,
                beam_size=1,
            )
        except Exception as te:
            safe_log(f"[SoundbiteAnalyzer] Error en Whisper: {te}")
            wav_path.unlink(missing_ok=True)
            return []
        finally:
            wav_path.unlink(missing_ok=True)

        # 3. Agrupar palabras en frases con lógica sintáctica y sentido completo (cero cortes entre frases)
        candidates: List[Tuple[float, float, str]] = []
        cur_words: list = []
        cur_start = 0.0

        for seg in segments:
            for w in (seg.words or []):
                w_txt = (w.word or "").strip()
                if not w_txt:
                    continue
                if not cur_words:
                    cur_start = w.start
                    cur_words.append(w)
                    continue

                prev_w = cur_words[-1]
                gap = w.start - prev_w.end
                cur_words.append(w)

                # Evaluar si la frase actual ya constituye una unidad de sentido completa
                current_text = " ".join(x.word.strip() for x in cur_words)
                ends_in_terminal_punct = bool(re.search(r"[.!?]$", w_txt))
                is_incomplete = self._is_incomplete_ending(current_text)
                cur_dur = w.end - cur_start

                # Regla 1: Fin natural con puntuación terminal y sentido completo
                if ends_in_terminal_punct and len(cur_words) >= 4 and not is_incomplete:
                    candidates.append((cur_start, w.end, current_text))
                    cur_words = []
                    continue

                # Regla 2: Pausa discursiva real (> 1.1s) pero SOLO si la frase NO termina en conector
                if gap >= 1.1 and len(cur_words) >= 5 and not is_incomplete and cur_dur >= 2.0:
                    candidates.append((cur_start, prev_w.end, " ".join(x.word.strip() for x in cur_words[:-1])))
                    cur_words = [w]
                    cur_start = w.start
                    continue

                # Regla 3: Si excede la duración máxima permisible (8.0s), buscar el corte si no es incompleta
                if cur_dur >= 7.8 and len(cur_words) >= 8 and not is_incomplete:
                    candidates.append((cur_start, w.end, current_text))
                    cur_words = []
                    continue

        if cur_words:
            final_text = " ".join(x.word.strip() for x in cur_words)
            if not self._is_incomplete_ending(final_text) and len(cur_words) >= 4:
                candidates.append((cur_start, cur_words[-1].end, final_text))

        # 4. Re-ranking semántico con IA (Tecnología estilo OpusClip / Klap):
        # Permite evaluar el contexto discursivo completo y priorizar frases con lógica y fuerza argumental
        topic_words = re.findall(r"\w{3,}", topic.lower()) if topic else []
        llm_selected_indices = set()
        clean_candidates = [
            (idx, st, en, txt) for idx, (st, en, txt) in enumerate(candidates)
            if not self._is_filler_start(txt) and not self._is_incomplete_ending(txt) and 2.0 <= (en - st) <= 7.5
        ]

        if len(clean_candidates) >= 2:
            try:
                from core.llm import LLMClient
                from utils.json_validator import JSONValidator
                client = LLMClient()
                sample_lines = "\n".join(
                    f"[{c_idx}] ({c_st:.1f}s - {c_en:.1f}s): «{c_txt}»"
                    for c_idx, c_st, c_en, c_txt in clean_candidates[:24]
                )
                eval_prompt = f"""Eres un editor audiovisual experto en extraer soundbites y declaraciones de alto impacto periodístico.
Analiza estos fragmentos extraídos de un video real sobre el tema: "{topic or 'Declaraciones generales'}".

Elige los 2 a 4 mejores fragmentos que funcionen como SOUNDBITES ESTRATÉGICOS:
1. REGLA ESTRICTA DE SENTIDO COMPLETO: Deben tener lógica discursiva y sintáctica 100% cerrada (sujeto, verbo y predicado claros).
2. CERO FRASES INCOMPLETAS: Queda ESTRICTAMENTE PROHIBIDO elegir fragmentos que terminen a la mitad, que corten la idea antes del final o que terminen en conectores ("que", "pero", "y", "porque", "de").
3. Deben ser declaraciones de peso, revelaciones, argumentos o datos clave (CERO saludos o muletillas).
4. Deben complementar de forma lógica la narración de un video periodístico.

Fragmentos:
{sample_lines}

Responde ÚNICAMENTE en JSON con los índices elegidos:
{{"selected_indices": [0, 2], "reason": "declaración contundente con lógica completa"}}"""
                raw_res = client.generate(eval_prompt, json_mode=True, deadline_sec=14)
                data_res = JSONValidator.extract_and_parse(raw_res)
                if isinstance(data_res, dict) and "selected_indices" in data_res:
                    llm_selected_indices = set(data_res["selected_indices"])
                    safe_log(f"[SoundbiteAnalyzer] 🤖 IA OpusClip-Ranker seleccionó {len(llm_selected_indices)} soundbites estratégicos.")
            except Exception as _llm_e:
                safe_log(f"[SoundbiteAnalyzer] Heurística local activa (fallback LLM: {_llm_e})")

        scored: List[Tuple[float, float, float, str]] = []
        for c_idx, st, en, txt in clean_candidates:
            dur = en - st
            sc = self._score_soundbite(txt, dur, topic_words)
            if c_idx in llm_selected_indices:
                sc += 8.0  # Gran impulso para fragmentos elegidos por el LLM por su lógica y contundencia
            if sc > 2.0:
                scored.append((sc, st, en, txt))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 5. Seleccionar los mejores soundbites sin solapamiento temporal
        chosen: List[StrategicSoundbite] = []
        used_ranges: List[Tuple[float, float]] = []

        for sc, st, en, txt in scored:
            if len(chosen) >= max_soundbites:
                break
            # Verificar no solapamiento con márgenes
            if any(not (en < (u_st - 1.0) or st > (u_en + 1.0)) for u_st, u_en in used_ranges):
                continue

            # Micro-amortiguación generosa (0.16s antes, 0.24s después) para proteger fonemas iniciales y finales
            pad_st = max(0.0, st - 0.16)
            pad_en = en + 0.24
            clip_dur = round(pad_en - pad_st, 3)
            clip_name = f"case_soundbite_{len(chosen)}.mp4"
            clip_path = soundbites_dir / clip_name

            # Extraer el clip de video+audio preciso con ffmpeg, micro-fade in/out y normalización broadcast
            fade_in_d = 0.035
            fade_out_d = 0.045
            fade_out_st = max(0.0, clip_dur - fade_out_d)
            af_filter = f"afade=t=in:st=0:d={fade_in_d},afade=t=out:st={fade_out_st:.3f}:d={fade_out_d},loudnorm=I=-16:TP=-1.5:LRA=11"

            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-ss", f"{pad_st:.3f}",
                        "-t", f"{clip_dur:.3f}",
                        "-i", str(video_path),
                        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                        "-af", af_filter,
                        "-c:a", "aac", "-b:a", "128k",
                        "-avoid_negative_ts", "make_zero",
                        str(clip_path)
                    ],
                    capture_output=True, timeout=30
                )
            except Exception as _fe:
                safe_log(f"[SoundbiteAnalyzer] Aviso extrayendo clip soundbite: {_fe}")
                clip_path = None

            sb = StrategicSoundbite(
                start_sec=pad_st,
                end_sec=pad_en,
                duration=round(en - st, 2),
                quote=txt,
                confidence=sc,
                clip_path=clip_path if (clip_path and clip_path.exists()) else None,
                keywords=[w for w in topic_words if w in txt.lower()],
            )
            chosen.append(sb)
            used_ranges.append((pad_st, pad_en))
            safe_log(f"[SoundbiteAnalyzer] 🎯 Soundbite #{len(chosen)} detectado ({clip_dur}s en t={st:.1f}s): «{txt}»")

        return chosen

    def find_best_soundbite_in_clip(
        self,
        clip_path: Path,
        scene_speech: str = "",
        keywords: Optional[List[str]] = None,
        min_dur: float = 2.4,
        max_dur: float = 5.8,
    ) -> Optional[StrategicSoundbite]:
        """Para un clip de B-Roll o YouTube ya descargado (ej: 14s-35s), encuentra el punto exacto donde la persona habla con sentido."""
        if not clip_path or not clip_path.exists():
            return None

        # 1. Probar transcripción rápida del clip
        wav_clip = clip_path.with_suffix(".temp_sb.wav")
        try:
            chk = subprocess.run(
                ["ffmpeg", "-y", "-i", str(clip_path), "-vn", "-ac", "1", "-ar", "16000", str(wav_clip)],
                capture_output=True, timeout=15
            )
            if not wav_clip.exists() or wav_clip.stat().st_size < 1000:
                return None

            from core.transcriber import _model
            model = _model("base")
            segments, _ = model.transcribe(
                str(wav_clip),
                language=self.language,
                word_timestamps=True,
                vad_filter=True,
                beam_size=1,
            )

            all_words = []
            for seg in segments:
                for w in (seg.words or []):
                    if (w.word or "").strip():
                        all_words.append(w)

            target_kw = list(keywords or [])
            if scene_speech:
                target_kw.extend([w for w in re.findall(r"\w{4,}", scene_speech.lower())])

            # Agrupar en oraciones coherentes con sentido completo dentro del clip
            if all_words:
                candidates: List[Tuple[float, float, str, float]] = []
                c_words = []
                for w in all_words:
                    if not c_words:
                        c_words.append(w)
                        continue

                    prev_cw = c_words[-1]
                    c_gap = w.start - prev_cw.end
                    c_words.append(w)

                    cur_text = " ".join(x.word.strip() for x in c_words)
                    ends_punct = bool(re.search(r"[.!?]$", (w.word or "").strip()))
                    is_incomp = self._is_incomplete_ending(cur_text)
                    cur_d = w.end - c_words[0].start

                    # Corte por puntuación terminal de sentido completo
                    if ends_punct and len(c_words) >= 4 and not is_incomp:
                        sc = self._score_soundbite(cur_text, cur_d, target_kw)
                        candidates.append((c_words[0].start, w.end, cur_text, sc))
                        c_words = []
                        continue

                    # Corte por pausa natural discursiva si la frase previa ya es completa
                    if c_gap >= 0.95 and len(c_words) >= 5 and not is_incomp and cur_d >= 2.0:
                        prev_text = " ".join(x.word.strip() for x in c_words[:-1])
                        prev_d = prev_cw.end - c_words[0].start
                        sc = self._score_soundbite(prev_text, prev_d, target_kw)
                        candidates.append((c_words[0].start, prev_cw.end, prev_text, sc))
                        c_words = [w]
                        continue

                    # Límite de duración
                    if cur_d >= 6.0 and len(c_words) >= 7 and not is_incomp:
                        sc = self._score_soundbite(cur_text, cur_d, target_kw)
                        candidates.append((c_words[0].start, w.end, cur_text, sc))
                        c_words = []
                        continue

                if c_words:
                    txt = " ".join(x.word.strip() for x in c_words)
                    dur = c_words[-1].end - c_words[0].start
                    if not self._is_incomplete_ending(txt):
                        sc = self._score_soundbite(txt, dur, target_kw)
                        candidates.append((c_words[0].start, c_words[-1].end, txt, sc))

                # Ordenar por puntaje garantizando sentido completo y sin fillers
                valid = [
                    c for c in candidates
                    if (c[1] - c[0]) >= 2.0 and not self._is_filler_start(c[2]) and not self._is_incomplete_ending(c[2])
                ]
                if valid:
                    valid.sort(key=lambda x: x[3], reverse=True)
                    best = valid[0]
                    # Lead-in generoso de 0.16s y margen de salida de 0.38s para evitar mutilar fonemas o respiraciones finales
                    clean_st = max(0.0, best[0] - 0.16)
                    clean_dur = min(max_dur, max(min_dur, (best[1] + 0.38) - clean_st))
                    return StrategicSoundbite(
                        start_sec=clean_st,
                        end_sec=clean_st + clean_dur,
                        duration=clean_dur,
                        quote=best[2],
                        confidence=best[3],
                        clip_path=clip_path,
                        keywords=[k for k in target_kw if k in best[2].lower()],
                    )
        except Exception as e:
            safe_log(f"[SoundbiteAnalyzer] Aviso analizando clip con Whisper: {e}")
        finally:
            wav_clip.unlink(missing_ok=True)

        # 2. Fallback Inteligente: Detección de silencios para evitar arrancar a mitad de palabra
        # Busca el primer punto tras una pausa de silencio de al menos 0.25s
        try:
            detect_run = subprocess.run(
                [
                    "ffmpeg", "-i", str(clip_path),
                    "-af", "silencedetect=noise=-30dB:d=0.25",
                    "-f", "null", "-"
                ],
                capture_output=True, text=True, timeout=10
            )
            # Buscar finales de silencio (silence_end: X.XX)
            silence_ends = [
                float(m.group(1))
                for m in re.finditer(r"silence_end:\s*([0-9.]+)", detect_run.stderr)
            ]
            if silence_ends:
                # Elegir el primer inicio de voz limpio después de segundo 1.0 (evita ruidos de cabecera)
                chosen_start = next((s for s in silence_ends if s >= 0.8), silence_ends[0])
                return StrategicSoundbite(
                    start_sec=round(chosen_start, 2),
                    end_sec=round(chosen_start + 3.2, 2),
                    duration=3.2,
                    quote="[Declaración del protagonista]",
                    confidence=1.0,
                    clip_path=clip_path,
                )
        except Exception:
            pass

        # Fallback seguro por omisión: 1.5s (después de cualquier cabecera o ruido inicial)
        return StrategicSoundbite(
            start_sec=1.5,
            end_sec=4.7,
            duration=3.2,
            quote="[Declaración del protagonista]",
            confidence=0.5,
            clip_path=clip_path,
        )
