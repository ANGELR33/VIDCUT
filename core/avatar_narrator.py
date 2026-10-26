"""Módulo de narración y voz con Inteligencia Artificial para el avatar asistente (KAI).

Combina modelos de lenguaje de última generación (Gemini) para redactar intervenciones
argumentadas, hiper-humanas y dinámicas, con tecnología Microsoft Edge Neural TTS (edge-tts),
100% gratuita, ilimitada y de código abierto para la síntesis de voz broadcast en español.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional, Tuple

import edge_tts

from core.models import InfoCard

DEFAULT_VOICE = "speechify:alejandro"   # Voz predeterminada: Alejandro Speechify (con failover automático si no hay créditos)
VOICE_MEXICO = "es-MX-JorgeNeural"     # Voz conversacional mexicana
VOICE_LATINO = "es-US-AlonsoNeural"    # Voz neutra estilo locutor internacional
VOICE_COLOMBIA = "es-CO-GonzaloNeural" # Voz neutra colombiana
VOICE_FEMALE = "es-MX-DaliaNeural"     # Voz femenina cálida y amigable


class AvatarNarrator:
    """Generador de diálogos hablados con IA y síntesis neural de voz para el avatar."""

    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice

    @staticmethod
    def craft_dialogue(card: InfoCard) -> str:
        """Redacta una intervención amigable, chistosa, irónica y enriquecedora con datos de peso."""
        verdict = (card.verdict or "").lower()
        headline = (card.headline or "").strip()
        clean_headline = re.sub(r'[\.\,\;]+$', '', headline)

        # 1. Contradicción / Dato falso
        if verdict == "contradicted":
            correction = (card.corrected_value or card.correction or card.note or "").strip()
            if correction:
                corr_clean = re.sub(r'[\.\,]+$', '', correction)
                templates = [
                    f"¡Un momento! Ese dato sobre {clean_headline} no coincide con la realidad: los registros verificados demuestran que {corr_clean}. Es un detalle crucial.",
                    f"Atención a esta afirmación: respecto a {clean_headline}, los datos oficiales confirman que {corr_clean}. Es un giro que cambia la perspectiva.",
                    f"Miren este detalle: sobre {clean_headline}, la información documentada prueba que {corr_clean}. Siempre conviene revisar la fuente directa.",
                ]
                idx = abs(hash(card.card_id or clean_headline)) % len(templates)
                return templates[idx]
            return f"¡Atención ahí! Sobre {clean_headline}, los registros oficiales contradicen totalmente esa conclusión. Conviene contrastar la evidencia."

        # 2. Cifra o estadística clave
        if card.stat_value:
            stat = card.stat_value.strip()
            detail = card.body or card.claim
            detail_short = " ".join(detail.split()[:14]).rstrip(".,;") if detail else ""
            templates = [
                f"Fíjense en esta cifra sorprendente: el número real para {clean_headline} es {stat}. {detail_short}. Es el dato que pone todo en perspectiva.",
                f"Miren este número insólito: las métricas oficiales marcan {stat} en {clean_headline}. Una cifra concreta que deja las cosas claras.",
            ]
            idx = abs(hash(card.card_id or stat)) % len(templates)
            return templates[idx]

        # 3. Confirmado / Complemento / Ley / Ciencia
        if verdict == "supported":
            kind = (card.kind or "dato").lower()
            if kind in ("complemento", "refuerzo", "dato_extra", "impacto", "contexto"):
                detail = card.body or card.claim
                detail_short = " ".join(detail.split()[:14]).rstrip(".,;") if detail else ""
                templates = [
                    f"Totalmente acertado. Y hay un dato fascinante que pocos conocen sobre {clean_headline}: {detail_short}. Aporta muchísimo valor al debate.",
                    f"Exacto, y súmenle esta curiosidad clave: sobre {clean_headline}, los registros confirman que {detail_short}. Refuerza perfectamente el punto.",
                    f"Buen apunte, y para sumar aún más contexto: {detail_short}. Los hechos reales terminan de confirmar la idea.",
                ]
                idx = abs(hash(card.card_id or clean_headline)) % len(templates)
                return templates[idx]
            if kind in ("ley", "normativa", "articulo"):
                return f"Un acierto total: {clean_headline} está respaldado al cien por ciento por el marco legal vigente. Punto clave para el análisis."
            return f"Exactamente: los estudios técnicos y registros oficiales respaldan plenamente {clean_headline}. Así da gusto profundizar en el tema."

        # 4. Evidencia insuficiente / mito sin sustento
        if verdict == "insufficient":
            templates = [
                f"Curioso punto, pero ojo: no existe ningún registro oficial ni estudio científico que sustente {clean_headline}. Conviene tomarlo con pinzas.",
                f"Suena llamativo en el discurso, pero en los reportes contrastados no hay evidencia de semejante afirmación. Queda en duda la hipótesis.",
            ]
            idx = abs(hash(card.card_id or clean_headline)) % len(templates)
            return templates[idx]

        return f"Un dato muy interesante: sobre {clean_headline}, los registros verificados confirman el punto. Sigamos atentos."

    async def craft_dialogue_with_ai(
        self,
        card: InfoCard,
        surrounding_context: str = "",
        llm: Optional[Any] = None
    ) -> str:
        """Formula una intervención amigable, chistosa, irónica y cargada de datos increíbles con Gemini."""
        prompt = f"""Eres KAI, el copiloto y analista de video en vivo. Eres muy carismático, súper amigable, chistoso, con una chispa de sana ironía y picardía (como un podcaster o streamer divulgador brillante que interviene en vivo con mucho humor y onda).

TU SELLO DISTINTIVO:
No te limitas a decir "esto es falso" o "la ley dice". Tu especialidad es soltar DATOS INCREÍBLES, enriquecedores y de alto impacto (citas a entidades de peso como la NASA, OIT, tribunales supremos, estudios científicos, comparativas internacionales o normas exactas) que dejen al espectador diciendo: "¡Wow, qué tremendo dato!".

SITUACIÓN EN EL VIDEO:
El orador en pantalla acaba de decir:
"{card.claim}"

Contexto inmediato de lo que se venía hablando:
"{surrounding_context[:300] if surrounding_context else 'Debate en video'}"

EVIDENCIA Y DATOS TÉCNICOS VERIFICADOS:
- Tema / Entidad: {card.headline}
- Muestreo, hechos o explicación: {card.body or card.note or 'Marco y registros oficiales'}
- Cifra o corrección clave: {card.corrected_value or card.stat_value or card.correction or 'Respaldado por datos oficiales'}
- Veredicto de los datos: {card.verdict}

TU MISIÓN:
Crear una intervención hablada CORTA, AMIGABLE, CURIOSA Y SORPRENDENTE (entre 20 y 35 palabras, 1 o 2 oraciones con pausas naturales).

ESTRUCTURA OBLIGATORIA:
1. GANCHO NATURAL E INTRIGANTE:
   - Si es corrección/error: "¡Un momento! Ese dato no coincide con los registros...", "Ojo con esa conclusión: la realidad documentada muestra algo muy diferente..."
   - Si es COMPLEMENTO / REFUERZO DE DATOS: "Exactamente, y hay un detalle fascinante que pocos conocen...", "Buen apunte, y súmenle esta curiosidad que pone todo en perspectiva..."
2. EL DATO SORPRENDENTE / REVELACIÓN:
   - Introduce un dato concreto, una cifra exacta o una comparación insólita que despierte la curiosidad del espectador.
3. REMATE LIMPIO Y CONVERSACIONAL:
   - "Un detalle clave para entender el panorama."
   - "Los hechos documentados hablan por sí solos."
   - "Un giro que cambia por completo el análisis."

REGLAS ESTRICTAS:
- Cero relleno pomposo, cero frases complejas vacías ("marco empírico", "confluencia de factores").
- Cero diminutivos paternalistas ("amiguito"). Escribe como un divulgador inteligente conversando en un podcast.
- Máximo 35 palabras, oraciones directas de 8 a 14 palabras con comas y pausas para respirar.
- Devuelve ÚNICAMENTE la frase exacta que KAI dirá en voz alta, sin comillas, sin explicaciones ni prefijos."""

        try:
            from core.llm import LLMClient
            client = llm or LLMClient()
            loop = asyncio.get_running_loop()
            raw_text = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: client.generate(prompt, max_models=2)),
                timeout=15.0
            )
            cleaned = re.sub(r'^["\'«»]+|["\'«»]+$', '', raw_text.strip())
            # Validar que no devolvió texto vacío o error genérico
            if len(cleaned.split()) >= 4 and not cleaned.startswith("{"):
                return cleaned
        except Exception as exc:
            print(f"[AvatarNarrator] Fallback a redacción local para {card.card_id}: {exc}")

        return self.craft_dialogue(card)

    async def synthesize(
        self,
        text: str,
        out_path: Path,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
    ) -> Tuple[Path, float]:
        """Genera el archivo de audio MP3 y devuelve su duración exacta en segundos con entonación y cadencia natural."""
        chosen_voice = voice or self.voice or DEFAULT_VOICE
        effective_rate = rate or "-2%"
        effective_pitch = pitch or "+0Hz"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        from utils.speech_normalizer import normalize_speech_for_tts
        norm_text = normalize_speech_for_tts(text)
        content_text = norm_text or text

        if chosen_voice == "voicestudio-omni-es":
            chosen_voice = "es-CO-GonzaloNeural"
        elif chosen_voice == "voicestudio-piper-dave":
            chosen_voice = "es-US-AlonsoNeural"

        # Determinar acento / tld regional
        cv_lower = chosen_voice.lower()
        tld = "com.mx"
        accent_desc = "español latinoamericano cálido y amigable"
        if any(x in cv_lower for x in ["es-es", "alvaro", "es_es"]):
            tld = "es"
            accent_desc = "español neutro de España con ritmo claro de divulgación"
        elif any(x in cv_lower for x in ["es-co", "gonzalo", "clon", "clone", "muestra"]):
            tld = "com.co"
            accent_desc = "voz profunda de narrador documental de estudio"
        elif any(x in cv_lower for x in ["es-ar", "tomas", "elena"]):
            tld = "com.ar"
            accent_desc = "español rioplatense dinámico y expresivo"

        generated = False

        # Mapeo de identidad vocal única para que cada locutor suene con voz humana propia y distinta
        studio_voice_map = {
            "es-mx-jorgeneural": "angel",
            "jorge": "angel",
            "es-us-alonsoneural": "fernando",
            "alonso": "fernando",
            "es-co-gonzaloneural": "jesus",
            "gonzalo": "jesus",
            "es-ar-tomasneural": "carlos",
            "tomas": "carlos",
            "tomás": "carlos",
            "es-mx-dalianeural": "carmen",
            "dalia": "carmen",
            "es-ar-elenaneural": "carolina",
            "elena": "carolina",
            "es-es-alvaroneural": "unai",
            "alvaro": "unai",
            "álvaro": "unai",
            "voicestudio-omni-es": "mariana",
            "omni": "mariana",
            "voicestudio-piper-dave": "maximiliano",
            "piper-dave": "maximiliano",
            "clon-propio": "emiliano",
            "neural-clon": "emiliano",
            "clone": "emiliano",
        }
        sp_target = studio_voice_map.get(cv_lower)
        if not sp_target:
            if any(x in cv_lower for x in ["gonzalo", "es-co"]):
                sp_target = "jesus"
            elif any(x in cv_lower for x in ["jorge", "es-mx"]):
                sp_target = "angel"
            elif any(x in cv_lower for x in ["alonso", "es-us"]):
                sp_target = "fernando"
            elif any(x in cv_lower for x in ["tomas", "tomás", "es-ar-tomas"]):
                sp_target = "carlos"
            elif any(x in cv_lower for x in ["dalia", "es-mx-dalia"]):
                sp_target = "carmen"
            elif any(x in cv_lower for x in ["elena", "es-ar-elena"]):
                sp_target = "carolina"
            elif any(x in cv_lower for x in ["alvaro", "álvaro", "es-es"]):
                sp_target = "unai"
            else:
                sp_target = chosen_voice.replace("speechify:", "").strip()

        # 0. Intentar síntesis con Speechify
        try:
            from utils.speechify_tts import synthesize_speechify, has_speechify_credits
            if has_speechify_credits():
                loop = asyncio.get_running_loop()
                sp_bytes = await loop.run_in_executor(None, lambda: synthesize_speechify(content_text, sp_target))
                if sp_bytes and len(sp_bytes) > 500:
                    with open(out_path, "wb") as f:
                        f.write(sp_bytes)
                    generated = True
        except Exception:
            pass

        # 1. Intentar edge-tts prioritario o como respaldo si Speechify se quedó sin créditos o falló
        if not generated:
            edge_fallback = chosen_voice if not chosen_voice.startswith("speechify:") else "es-MX-JorgeNeural"
            try:
                communicate = edge_tts.Communicate(content_text, edge_fallback, rate=effective_rate, pitch=effective_pitch)
                await asyncio.wait_for(communicate.save(str(out_path)), timeout=35.0)
                if out_path.exists() and out_path.stat().st_size > 500:
                    generated = True
            except Exception:
                pass

        # 2. Respaldo con Gemini TTS si está configurado y edge-tts no pudo generar
        if not generated:
            try:
                from config.settings import settings
                import google.generativeai as genai
                key = (getattr(settings, "GEMINI_API_KEY", "") or "").split(",")[0].strip()
                if key:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel("models/gemini-2.5-flash-preview-tts")
                    prompt = f"Lee con {accent_desc}: {content_text}"

                    loop = asyncio.get_running_loop()
                    res = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: model.generate_content(
                            prompt,
                            generation_config={"response_modalities": ["AUDIO"]}
                        )),
                        timeout=8.0
                    )
                    pcm = None
                    for p in res.candidates[0].content.parts:
                        if p.inline_data:
                            pcm = p.inline_data.data
                            break
                    if pcm:
                        cmd = [
                            "ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                            "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", "128k", "-f", "mp3", str(out_path)
                        ]
                        proc = await asyncio.to_thread(
                            subprocess.run, cmd, input=pcm, capture_output=True
                        )
                        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 500:
                            generated = True
            except Exception:
                pass

        # 3. Respaldo infalible con gTTS (cero caídas, prosodia regional)
        if not generated:
            from gtts import gTTS
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: gTTS(text=content_text, lang="es", tld=tld).save(str(out_path)))

        duration = self.get_audio_duration(out_path)
        return out_path, duration

    @staticmethod
    def get_audio_duration(path: Path) -> float:
        """Lee la duración exacta del audio usando ffprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json", str(path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            data = json.loads(res.stdout)
            return float(data["format"]["duration"])
        except Exception as exc:
            print(f"[AvatarNarrator] No se pudo leer duración de {path}: {exc}")
            return 3.5
