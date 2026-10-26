"""Auditor y Revisor Crítico Autónomo con GLM-5.3-flash.

GLM-5.3-flash audita y optimiza a velocidad ultra-rápida:
1. El guión y las escenas (coherencia, dicción para TTS, hooks, datos falsos o clichés).
2. Los términos visuales y beats (especificidad en inglés, eliminación de términos genéricos).
3. Los subtítulos dinámicos (ortografía, puntuación, longitud de líneas para no saturar la pantalla).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from core.llm import safe_log
from core.multiagent.models import get_implementer_model


class FlashContentReviewer:
    """Inspector de calidad y optimizador automático con DeepSeek Flash (Supervisor Editor)."""

    def __init__(self):
        try:
            from core.supervisor_editor import supervisor_editor
            self.supervisor = supervisor_editor
            self.available = bool(getattr(self.supervisor, "deepseek_key", ""))
        except Exception:
            self.supervisor = None
            self.available = False

        try:
            self.model = get_implementer_model()
            if not self.available:
                self.available = bool(getattr(self.model, "api_key", ""))
        except Exception:
            self.model = None

    def review_and_optimize_plan(self, plan_dict: Dict[str, Any], topic: str) -> Dict[str, Any]:
        """Audita el plan del director: pule la locución TTS, afina queries visuales y corrige incoherencias con razonamiento profundo."""
        scenes = plan_dict.get("scenes", [])
        if not scenes:
            return plan_dict

        safe_log(f"[FlashReviewer] ⚡ Auditando y razonando guión de {len(scenes)} escenas para máxima retención...")

        prompt_review = f"""Eres el Auditor y Editor Jefe de Producción Audiovisual de élite.
Tu objetivo es elevar la calidad de este plan de video sobre el tema: "{topic}".

REVISA Y OPTIMIZA CADA ESCENA:
1. "speech" (Locución para síntesis de voz):
   - Elimina muletillas o frases acartonadas.
   - NUNCA MENCIONAR TIEMPO: Si la locución dice "en estos 30 minutos", "en los próximos minutos", "en este video de media hora", ELIMÍNALO por completo. La locución debe ser atemporal.
   - DESPEDIDAS SOLO EN LA ÚLTIMA ESCENA: Si una escena intermedia (cualquiera excepto la última) contiene despedidas ("gracias por acompañarme", "suscríbanse", "nos vemos en el próximo video"), ELIMÍNALAS y sustitúyelas por una transición lógica hacia el siguiente punto.
   - PRESERVA LA EXTENSIÓN Y PROFUNDIDAD DEL TEXTO: Si una escena contiene un párrafo extenso y detallado, MANTÉN esa misma longitud y riqueza de datos. ESTRICTAMENTE PROHIBIDO recortar o resumir la narración a 2 o 3 oraciones, ya que acortaría la duración del video final.
   - Números y siglas: Escribe números en palabras si conviene (ej: "diez por ciento" en vez de "10%"). NUNCA uses guiones entre las letras de una sigla (escribe "ADN", "NASA", "IA", NUNCA "A-D-N" ni "N-A-S-A", ya que los guiones hacen que la voz neuronal de Microsoft tartamudee o suene robótica con pausas forzadas).
2. "name" (Título de la escena):
   - NUNCA uses nombres genéricos como "Relleno" o "Relleno Estructural". Asigna un título descriptivo real sobre el dato o evento que se narra.
3. "visual_query" y "visual_query2":
   - Asegura que estén en inglés, sean HIPER-ESPECÍFICOS (evita términos vagos como 'abstract 4k' o 'cinematic background').
   - Si la escena nombra a una persona, mandatario o figura pública, DEBE buscar a la persona real en acción (ej: 'Pedro Sanchez press speech', 'Elon Musk interview', 'Javier Milei speech'), NUNCA metáforas abstractas de stock (como billetes, carreteras o edificios genéricos vacíos).
   - Deben reflejar exactamente la entidad, lugar o acción concreta mencionada en ese segundo.
4. "visual_beats":
   - Comprueba que el 'trigger' sea una subcadena literal que sí existe dentro del 'speech'. Si no coincide, ajústalo.
5. "case_frame" (SI EXISTE):
   - CONSERVA el valor exacto sin cambios en cada escena que lo tenga. Es el índice de un fotograma REAL del video fuente del caso: modificarlo o eliminarlo rompe el análisis visual.
6. AUDITORÍA ESPECIAL PARA RESÚMENES DE ANIME (SI EL TEMA ES ANIME/MANGA/SHONEN):
   - "speech": Debe narrar en tercera persona presente continuo inmersivo (como un thriller de acción, nunca una reseña escolar).
   - "visual_beats": Cada escena debe traer entre 2 y 4 visual_beats vinculados palabra por palabra a los momentos clave del speech.
   - Cero anacronismos: Elimina cualquier mención de villanos o poderes de sagas avanzadas que no pertenezcan al arco actual.

PLAN ACTUAL:
{json.dumps(scenes, ensure_ascii=False, indent=2)}

RESPONDE EXCLUSIVAMENTE CON UN JSON VÁLIDO conteniendo el array de escenas optimizadas:
{{
  "optimized_scenes": [ ... ]
}}
"""

        # 1. Intentar supervisión editorial crítica adversarial (Supervisor Editor: DeepSeek / Gemini)
        try:
            from core.supervisor_editor import supervisor_editor
            sup_res = supervisor_editor.audit_and_refine(topic, scenes)
            opt_scenes = sup_res.get("optimized_scenes")
            if opt_scenes and isinstance(opt_scenes, list) and len(opt_scenes) == len(scenes):
                plan_dict["supervisor_audit"] = {
                    "verdict": sup_res.get("verdict"),
                    "editorial_score": sup_res.get("editorial_score"),
                    "flaws_detected": sup_res.get("flaws_detected", []),
                    "editorial_decisions": sup_res.get("editorial_decisions", []),
                    "verification_requests": sup_res.get("verification_requests", [])
                }
                # Continuar al procesamiento determinista de campos y TTS
                data = {"optimized_scenes": opt_scenes}
            else:
                data = None
        except Exception as _sup_err:
            safe_log(f"[FlashReviewer] Aviso consultando SupervisorEditor: {_sup_err}")
            data = None

        if not data:
            # Respaldo: Intentar auditoría tradicional
            try:
                from core.llm import LLMClient
                from utils.json_validator import JSONValidator
                client = LLMClient()
                raw = client.generate(prompt_review, json_mode=True, deadline_sec=35)
                data = JSONValidator.extract_and_parse(raw)
            except Exception as _fb_err:
                safe_log(f"[FlashReviewer] Fallback en auditor de respaldo: {_fb_err}")
                data = None

        if data:
            opt_scenes = data.get("optimized_scenes") if isinstance(data, dict) else (data if isinstance(data, list) else None)
            if opt_scenes and isinstance(opt_scenes, list) and len(opt_scenes) == len(scenes):
                orig_words = sum(len(str(orig.get("speech", "")).split()) for orig in scenes if isinstance(orig, dict))
                new_words = sum(len(str(sc.get("speech", "")).split()) for sc in opt_scenes if isinstance(sc, dict))
                if orig_words > 80 and new_words < orig_words * 0.70:
                    safe_log(f"[FlashReviewer] El auditor recortó la locución ({new_words} vs {orig_words} palabras). Conservando extensión del plan original.")
                    return plan_dict

                for i, orig in enumerate(scenes):
                    if isinstance(orig, dict):
                        for fld in ("case_frame", "soundbite_clip", "soundbite_quote", "soundbite_offset", "soundbite_dur"):
                            if orig.get(fld) is not None and isinstance(opt_scenes[i], dict) and opt_scenes[i].get(fld) is None:
                                opt_scenes[i][fld] = orig[fld]
                from utils.speech_normalizer import clean_hyphenated_acronyms, normalize_speech_for_tts
                for sc_idx, sc in enumerate(opt_scenes):
                    if isinstance(sc, dict):
                        is_last = (sc_idx == len(opt_scenes) - 1)
                        if "speech" in sc and isinstance(sc["speech"], str):
                            sc["speech"] = normalize_speech_for_tts(sc["speech"], is_final_scene=is_last)
                        c = sc.get("card")
                        if isinstance(c, dict):
                            for k in ("headline", "body", "stat"):
                                if k in c and isinstance(c[k], str):
                                    c[k] = clean_hyphenated_acronyms(c[k])

                # Validación Determinista de Beats: asegurar que cada trigger exista literalmente en speech
                for sc in opt_scenes:
                    if isinstance(sc, dict):
                        sp = sc.get("speech", "")
                        beats = sc.get("visual_beats", [])
                        if isinstance(beats, list):
                            for b in beats:
                                if isinstance(b, dict):
                                    tr = str(b.get("trigger", "")).strip()
                                    if tr and tr.lower() not in sp.lower():
                                        # Si el modelo alucinó un trigger no existente, recuperar frase real del speech
                                        words = [w for w in re.findall(r"\w{3,}", tr) if len(w) > 3]
                                        fixed_tr = ""
                                        for sent in re.split(r'[,.\n;]', sp):
                                            if any(w.lower() in sent.lower() for w in words):
                                                fixed_tr = " ".join(sent.strip().split()[:4])
                                                break
                                        if not fixed_tr and sp.split():
                                            fixed_tr = " ".join(sp.split()[:4])
                                        if fixed_tr:
                                            b["trigger"] = fixed_tr

                reviewer_tag = getattr(locals().get("client"), "last_model_used", "supervisor-editor-v4")
                safe_log(f"[FlashReviewer] ✓ {len(opt_scenes)} escenas auditadas y optimizadas exitosamente con razonamiento ({reviewer_tag}).")
                plan_dict["scenes"] = opt_scenes
                plan_dict["reviewed_by"] = reviewer_tag
                return plan_dict
            else:
                safe_log("[FlashReviewer] La respuesta no coincidió en número de escenas, conservando plan original.")

        # 2. Respaldo secundario si fuera necesario
        if self.available and self.model:
            try:
                import concurrent.futures
                from utils.json_validator import JSONValidator
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(
                        self.model.generate,
                        system_prompt="Eres un auditor editorial experto. Devuelve únicamente JSON válido.",
                        user_prompt=prompt_review,
                        temperature=0.2,
                        json_mode=True,
                    )
                    raw = fut.result(timeout=10.0)
                data = JSONValidator.extract_and_parse(raw)
                opt_scenes = data.get("optimized_scenes") if isinstance(data, dict) else (data if isinstance(data, list) else None)
                if opt_scenes and isinstance(opt_scenes, list) and len(opt_scenes) == len(scenes):
                    for i, orig in enumerate(scenes):
                        if isinstance(orig, dict):
                            for fld in ("case_frame", "soundbite_clip", "soundbite_quote", "soundbite_offset", "soundbite_dur"):
                                if orig.get(fld) is not None and isinstance(opt_scenes[i], dict) and opt_scenes[i].get(fld) is None:
                                    opt_scenes[i][fld] = orig[fld]
                    safe_log(f"[FlashReviewer] ✓ {len(opt_scenes)} escenas auditadas por implementador secundario.")
                    plan_dict["scenes"] = opt_scenes
                    plan_dict["reviewed_by"] = "secondary-implementer"
            except Exception as sec_err:
                safe_log(f"[FlashReviewer] Fallback secundario omitido: {sec_err}")

        return plan_dict

    def review_captions(self, captions_text: List[str]) -> List[str]:
        """Pule la ortografía y quiebres de línea de los subtítulos."""
        if not self.available or not self.model or not captions_text:
            return captions_text

        prompt = f"""Corrige y pule estos textos de subtítulos en español.
Mantén las mismas líneas en el mismo orden exacto.
Corrige tildes, signos de puntuación y capitalización adecuada.
Lista:
{json.dumps(captions_text, ensure_ascii=False)}

Devuelve solo JSON:
{{
  "polished_captions": [ ... ]
}}
"""
        try:
            from utils.json_validator import JSONValidator
            raw = self.model.generate(
                system_prompt="Pule subtítulos. Devuelve solo JSON válido.",
                user_prompt=prompt,
                temperature=0.1,
                json_mode=True,
            )
            data = JSONValidator.extract_and_parse(raw)
            polished = data.get("polished_captions")
            if polished and len(polished) == len(captions_text):
                return polished
        except Exception:
            pass

        return captions_text
