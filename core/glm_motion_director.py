"""
GLM 5.3 Motion Graphics Director
Diseña microelementos visuales sutiles (partículas, formas geométricas finas,
elementos fugaces y profundidad) para cada escena usando z-ai/glm-5.3-flash vía NVIDIA NIM.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
from openai import OpenAI
from config import settings

logger = logging.getLogger("aethercut.glm_motion")


class GLMMotionDirector:
    def __init__(self):
        self.api_key = getattr(settings, "NVIDIA_API_KEY", "")
        self.model = getattr(settings, "NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        self.fallback_model = "nvidia/nemotron-3.5-lightning-30b-a3b"
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        if self._client is None and self.api_key:
            self._client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.api_key,
                timeout=3.0,
            )
        return self._client

    def design_motion_spec(
        self,
        scene_name: str,
        speech_text: str,
        duration: float,
        accent_color: str = "#ff9436",
        scene_type: str = "broll_narration",
    ) -> Dict[str, Any]:
        """
        Pide a GLM-5.3 diseñar la receta de microelementos cinéticos para la escena.
        Garantiza que los elementos sean sutiles, no intrusivos y mantengan despejado el centro.
        """
        if not self.client:
            return self._build_deterministic_fallback(accent_color, duration)

        prompt = f"""Eres el Diseñador Visual y Motion Graphics Director de élite del estudio AetherCut, impulsado por GLM-5.3.
Diseña un JSON conciso con microelementos cinéticos sutiles para la escena:
- Nombre: {scene_name}
- Tipo: {scene_type}
- Duración: {duration:.1f} segundos
- Color de acento: {accent_color}
- Discurso: "{speech_text[:200]}"

Directrices:
1. El centro (tarjetas) y la esquina inferior derecha (avatar streamer) deben quedar 100% despejados.
2. Partículas tenues (14 a 22 puntos, opacidad 0.15 a 0.35).
3. Acentos geométricos finos (corner_brackets o tech_marker).
4. Elementos fugaces (1 o 2 destellos sutiles de 1.5s a 2.5s).

RESPONDE EXCLUSIVAMENTE CON ESTE OBJETO JSON VÁLIDO:
{{
  "theme": "tech_cinematic",
  "particles": {{
    "enabled": true,
    "count": 16,
    "color": "{accent_color}",
    "opacity_min": 0.15,
    "opacity_max": 0.35,
    "speed": "slow",
    "drift": "upward"
  }},
  "geometric_accents": [
    {{
      "type": "corner_brackets",
      "stroke": 1.5,
      "size": 34,
      "color": "{accent_color}",
      "opacity": 0.40
    }},
    {{
      "type": "tech_marker",
      "position": "top_left",
      "text": "SYS // REC",
      "opacity": 0.30
    }}
  ],
  "fleeting_accents": [
    {{
      "start_sec": 4.0,
      "duration_sec": 2.0,
      "type": "subtle_light_shimmer",
      "color": "{accent_color}"
    }}
  ]
}}
"""
        for m in (self.model, self.fallback_model):
            try:
                resp = self.client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": "Responde EXCLUSIVAMENTE con el objeto JSON pedido."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1400,
                    temperature=0.2,
                )
                msg = resp.choices[0].message
                raw = (msg.content or getattr(msg, "reasoning_content", "") or "").strip()
                m_json = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
                if m_json:
                    return json.loads(m_json.group(1))
                m_curly = re.search(r"(\{.*\})", raw, re.DOTALL)
                if m_curly:
                    return json.loads(m_curly.group(1))
            except Exception as exc:
                logger.warning(f"[GLMMotionDirector] Modelo {m} falló: {exc}")

        return self._build_deterministic_fallback(accent_color, duration)

    def _build_deterministic_fallback(self, accent_color: str, duration: float) -> Dict[str, Any]:
        """Plantilla elegante y probada en caso de indisponibilidad de API."""
        return {
            "theme": "ambient_minimal",
            "particles": {
                "enabled": True,
                "count": 16,
                "color": accent_color,
                "opacity_min": 0.15,
                "opacity_max": 0.32,
                "speed": "slow",
                "drift": "upward",
            },
            "geometric_accents": [
                {
                    "type": "corner_brackets",
                    "stroke": 1.5,
                    "size": 34,
                    "color": accent_color,
                    "opacity": 0.40,
                },
                {
                    "type": "tech_marker",
                    "position": "top_left",
                    "text": "SIG // ACTV",
                    "opacity": 0.30,
                },
            ],
            "fleeting_accents": [
                {
                    "start_sec": max(1.5, min(4.5, duration * 0.25)),
                    "duration_sec": 2.0,
                    "type": "subtle_light_shimmer",
                    "color": accent_color,
                }
            ],
        }
