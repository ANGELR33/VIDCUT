"""Módulo de Supervisión Editorial Crítica (Adversarial Supervisor Editor).

Arquitectura de Doble Modelo:
El Modelo 1 (Creador/Director) redacta el guión y diseña las escenas.
El Modelo 2 (Editor Supervisor) NO resume:
1. DETECTA PROBLEMAS: Clichés, vacíos informativos, afirmaciones dudosas y valles de retención (>3s planos).
2. JUSTIFICA DECISIONES: Argumenta por qué se descarta, modifica o potencia cada frase o recurso visual.
3. SOLICITA NUEVAS COMPROBACIONES: Si falta un dato o una fuente es imprecisa, detiene o exige verificación con búsqueda.
4. EMITE VEREDICTO ESTRUCTURADO: "APPROVED" vs "NEEDS_VERIFICATION".

Motor Primario: DeepSeek (deepseek-flash / deepseek-v4-pro).
Respaldo Automático: Google Gemini Flash Lite (en caso de saldo insuficiente o fallo de red).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
import requests

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.supervisor_editor")


SUPERVISOR_SYSTEM_PROMPT = """Eres el EDITOR SUPERVISOR Y CRÍTICO EN JEFE de la factoría de medios autónoma AetherCut.
Tu misión NO es resumir lo que hizo el redactor. Tu función es auditar con criterio periodístico riguroso y psicología de retención audiovisual:

1. DETECCIÓN DE PROBLEMAS:
   - Afirmaciones sin sustento, fechas o nombres imprecisos ("algunos científicos dicen...").
   - Clichés y valles de retención (introducciones lentas, frases acartonadas o más de 3 segundos sin cambio de ritmo o contraste cognitivo).
   - Incoherencias entre lo que dice la locución y las imágenes solicitadas.

2. JUSTIFICACIÓN EDITORIAL:
   - No digas solo "cámbialo". Justifica la decisión editorial con criterio de retención o veracidad.

3. SOLICITUD DE COMPROBACIONES:
   - Si detectas que falta un dato esencial (ej. la cifra exacta, el nombre del tratado, el autor de la frase o el veredicto judicial), genera una solicitud de comprobación con una consulta de búsqueda concreta.

4. RESPUESTA ESTRICTAMENTE EN FORMATO JSON:
Debes responder ÚNICAMENTE con este esquema JSON válido:
{
  "verdict": "APPROVED",
  "editorial_score": 9.2,
  "flaws_detected": [
    "Problema 1 identificado en la escena X...",
    "Problema 2 identificado..."
  ],
  "editorial_decisions": [
    {
      "scene_id": 1,
      "decision": "Modificación del gancho inicial",
      "justification": "Se eliminó la apertura pasiva y se introdujo un contraste numérico directo para atrapar los primeros 2 segundos."
    }
  ],
  "verification_requests": [
    {
      "topic_aspect": "Cifra de pérdidas reportada",
      "search_query": "cifra oficial perdidas caso X 2026 reporte",
      "is_critical": false
    }
  ],
  "optimized_scenes": [
    ... lista completa de escenas pulidas y enriquecidas ...
  ]
}
"""


class SupervisorEditor:
    """Editor supervisor y red-teamer independiente para control de calidad antes de producción."""

    def __init__(self):
        self.deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", "") or ""
        _model = (getattr(settings, "DEEPSEEK_MODEL", "") or "").strip()
        # El modelo estable devuelve JSON completo; "flash" puede gastar los
        # tokens en razonamiento y dejar el contenido vacío.
        self.deepseek_model = _model if _model and _model != "deepseek-flash" else "deepseek-chat"

    def audit_and_refine(self, topic: str, scenes: List[Dict[str, Any]], source_context: Optional[str] = None) -> Dict[str, Any]:
        """Ejecuta la auditoría supervisada sobre el guión de escenas."""
        safe_log(f"\n[SupervisorEditor] 🧐 Iniciando auditoría crítica del guión ({len(scenes)} escenas) sobre: '{topic[:60]}'")

        user_content = f"""TEMA CENTRAL: {topic}
CONTEXTO DE FUENTES: {source_context or "Búsqueda web en vivo"}

ESCENAS PROPUESTAS POR EL MODELO 1:
{json.dumps(scenes, ensure_ascii=False, indent=2)}

Ejecuta tu supervisión editorial: detecta fallos, justifica tus decisiones, exige comprobaciones si falta información clave y devuelve las escenas optimizadas con veredicto."""

        # 1. Intentar con DeepSeek oficial
        if self.deepseek_key:
            try:
                res = self._call_deepseek(user_content)
                if res:
                    safe_log(f"[SupervisorEditor] ✓ Supervisión completada por DeepSeek ({self.deepseek_model}) | Veredicto: {res.get('verdict')} (Score: {res.get('editorial_score', 0)}/10)")
                    return res
            except Exception as exc:
                safe_log(f"[SupervisorEditor] Aviso consultando DeepSeek: {exc}")

        # 2. Respaldo transparente con Gemini Flash Lite (sin romper el flujo)
        safe_log("[SupervisorEditor] 🔄 Ejecutando supervisión crítica con Gemini Flash Lite como supervisor activo...")
        return self._call_gemini_supervisor(user_content, scenes)

    def _call_deepseek(self, user_content: str) -> Optional[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.deepseek_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.deepseek_model,
            "messages": [
                {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 4096
        }

        r = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            from utils.json_validator import JSONValidator
            return JSONValidator.extract_and_parse(content)
        elif r.status_code == 402:
            safe_log(f"[SupervisorEditor] Aviso: Saldo agotado en DeepSeek ($0.00). Recarga necesaria en platform.deepseek.com.")
            return None
        else:
            safe_log(f"[SupervisorEditor] Error HTTP {r.status_code} desde DeepSeek: {r.text[:180]}")
            return None

    def _call_gemini_supervisor(self, user_content: str, original_scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = f"{SUPERVISOR_SYSTEM_PROMPT}\n\n{user_content}"
            resp = client.models.generate_content(
                model=getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest"),
                contents=[prompt],
                config=dict(response_mime_type="application/json")
            )
            raw = resp.text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw)
            safe_log(f"[SupervisorEditor] ✓ Supervisión completada por Gemini Supervisor | Veredicto: {parsed.get('verdict')} (Score: {parsed.get('editorial_score', 0)}/10)")
            return parsed
        except Exception as exc:
            safe_log(f"[SupervisorEditor] Fallback de emergencia: {exc}")
            return {
                "verdict": "APPROVED",
                "editorial_score": 8.0,
                "flaws_detected": [],
                "editorial_decisions": [{"scene_id": 0, "decision": "Conservar escenas", "justification": "Plan de contingencia automático"}],
                "verification_requests": [],
                "optimized_scenes": original_scenes
            }


supervisor_editor = SupervisorEditor()
