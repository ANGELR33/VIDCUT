"""DeepSeek Motion & Visual Director (deepseek-flash).

Diseña elementos visuales avanzados y dinámicos para cada escena:
1. Revelación Secuencial de Elementos (Staggered Badges):
   - Cuando se mencionan países, hitos, empresas o conceptos clave (ej. EE.UU., China, Rusia),
     genera insignias que aparecen una por una en marcha sincronizada.
2. Estadísticas Cinéticas Animadas:
   - Medidores de porcentaje, cifras de impacto y métricas destacadas.
3. Micro-elementos Ambientales (partículas, brackets HUD, destellos de luz).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
import requests

from config.settings import settings
from core.llm import safe_log

logger = logging.getLogger("aethercut.deepseek_motion")


class DeepSeekMotionDirector:
    """Director cinético y visual de élite impulsado por DeepSeek V4.1 Flash."""

    def __init__(self):
        self.api_key = (getattr(settings, "DEEPSEEK_API_KEY", "") or "").strip()
        self.model = getattr(settings, "DEEPSEEK_MODEL", "deepseek-flash")

    def design_motion_spec(
        self,
        scene_name: str,
        speech_text: str,
        duration: float,
        accent_color: str = "#ff9436",
        scene_type: str = "broll_narration",
    ) -> Dict[str, Any]:
        """Diseña la receta cinemática de microelementos y tarjetas secuenciales con DeepSeek Flash."""
        if not self.api_key:
            return self._build_deterministic_fallback(accent_color, duration, speech_text)

        prompt = f"""Eres el Director de Motion Graphics y Arte Audiovisual de élite en AetherCut, impulsado por DeepSeek Flash.
Analiza la locución de esta escena y diseña las animaciones dinámicas exactas:
- Escena: "{scene_name}"
- Duración: {duration:.1f} segundos
- Color de acento: {accent_color}
- Locución hablada: "{speech_text[:280]}"

MISIONES DE EDICIÓN AVANZADA:
1. REVELACIÓN SECUENCIAL (sequential_badges): Si la locución enumera países, empresas, fechas o hitos (ej. "países como Japón, Alemania y Francia" o "hitos de 1914, 1917 y 1918"):
   - Extrae los elementos en un array de insignias para que aparezcan uno por uno escalonados mientras se habla.
   - Cada uno debe tener: "label" (nombre corto), "emoji" (bandera o ícono representativo) y "delay_sec" (retraso en segundos para sincronizar con la mención).
2. DATO O ESTADÍSTICA CINÉTICA (kinetic_stat): Si se menciona un porcentaje, cifra económica o multiplicador (ej. "85%", "$4 Billones", "10x"):
   - "value": "85%", "label": "ADOPCIÓN GLOBAL", "type": "percentage_bar".
3. PARTÍCULAS Y HUD: Partículas tenues periféricas y esquineros HUD que enmarquen la toma sin tapar el centro.

RESPONDE EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO:
{{
  "theme": "glassmorphism_elite",
  "sequential_badges": [
    {{ "label": "Japón", "emoji": "🇯🇵", "delay_sec": 1.2 }},
    {{ "label": "Alemania", "emoji": "🇩🇪", "delay_sec": 2.4 }}
  ],
  "kinetic_stat": {{
    "enabled": false,
    "value": "",
    "label": "",
    "type": "none"
  }},
  "particles": {{
    "enabled": true,
    "count": 18,
    "color": "{accent_color}",
    "opacity_min": 0.15,
    "opacity_max": 0.35,
    "speed": "slow",
    "drift": "upward"
  }},
  "geometric_accents": [
    {{ "type": "corner_brackets", "stroke": 1.5, "size": 34, "color": "{accent_color}", "opacity": 0.40 }},
    {{ "type": "tech_marker", "position": "top_left", "text": "LIVE // INTEL", "opacity": 0.35 }}
  ],
  "fleeting_accents": [
    {{ "start_sec": 2.5, "duration_sec": 2.0, "type": "subtle_light_shimmer", "color": "{accent_color}" }}
  ]
}}
"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Eres un Director de Motion Graphics y Arte Digital. Responde estrictamente con JSON válido."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 1200
        }

        try:
            r = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=12)
            if r.status_code == 200:
                raw_json = r.json()["choices"][0]["message"]["content"]
                spec = json.loads(raw_json)
                n_badges = len(spec.get("sequential_badges", []))
                has_stat = spec.get("kinetic_stat", {}).get("enabled", False)
                safe_log(f"[DeepSeekMotion] 🎨 Escena '{scene_name}': Diseñada con éxito ({n_badges} insignias escalonadas, stat animado: {has_stat})")
                return spec
        except Exception as exc:
            safe_log(f"[DeepSeekMotion] Aviso generando motion spec con DeepSeek: {exc}")

        return self._build_deterministic_fallback(accent_color, duration, speech_text)

    def _build_deterministic_fallback(self, accent_color: str, duration: float, speech: str = "") -> Dict[str, Any]:
        """Respaldo determinista sin dependencias externas."""
        # Detección heurística rápida de porcentajes o países
        badges = []
        words = speech.split()
        countries_map = {
            "estados unidos": "🇺🇸", "ee.uu": "🇺🇸", "eeuu": "🇺🇸", "china": "🇨🇳", "rusia": "🇷🇺",
            "japon": "🇯🇵", "japón": "🇯🇵", "alemania": "🇩🇪", "francia": "🇫🇷", "reino unido": "🇬🇧",
            "espana": "🇪🇸", "españa": "🇪🇸", "mexico": "🇲🇽", "méxico": "🇲🇽", "colombia": "🇨🇴",
            "argentina": "🇦🇷", "brasil": "🇧🇷", "chile": "🇨🇱", "peru": "🇵🇪", "perú": "🇵🇪"
        }
        sp_lower = speech.lower()
        found_idx = 0
        for name, flag in countries_map.items():
            if name in sp_lower:
                badges.append({"label": name.title(), "emoji": flag, "delay_sec": round(1.0 + found_idx * 1.2, 1)})
                found_idx += 1
                if found_idx >= 4:
                    break

        pct_match = re.search(r"(\d+(?:\.\d+)?\s*%)", speech)
        stat = {"enabled": False, "value": "", "label": "", "type": "none"}
        if pct_match:
            stat = {"enabled": True, "value": pct_match.group(1), "label": "MÉTRICA CLAVE", "type": "percentage_bar"}

        return {
            "theme": "glassmorphism_elite",
            "sequential_badges": badges,
            "kinetic_stat": stat,
            "particles": {
                "enabled": True,
                "count": 16,
                "color": accent_color,
                "opacity_min": 0.15,
                "opacity_max": 0.35,
                "speed": "slow",
                "drift": "upward",
            },
            "geometric_accents": [
                {"type": "corner_brackets", "stroke": 1.5, "size": 34, "color": accent_color, "opacity": 0.40},
                {"type": "tech_marker", "position": "top_left", "text": "SYS // REC", "opacity": 0.30},
            ],
            "fleeting_accents": [
                {"start_sec": max(1.0, duration * 0.4), "duration_sec": 2.0, "type": "subtle_light_shimmer", "color": accent_color}
            ],
        }


deepseek_motion_director = DeepSeekMotionDirector()
