"""
AI Remotion Dynamic Generator
Permite a modelos de IA (Gemini / NVIDIA NIM) generar y adaptar componentes React
en Remotion al vuelo según el guion y contenido de cada escena.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings
from core.llm import LLMClient
from core.remotion_engine import RemotionEngine

logger = logging.getLogger("aethercut.remotion_ai")


class AIStyleDirector:
    """Director de Estilo Audiovisual: define automáticamente la paleta de colores,
    tipografía y tono base del video según su temática y potencia."""

    PALETTES: Dict[str, Dict[str, str]] = {
        "cyber_cyan": {
            "name": "cyber_cyan",
            "primary": "#FF9436",
            "accent": "#FFE14D",
            "bg": "#0C0D12",
            "card_theme": "orange_noir",
            "sub_style": "viral",
            "font_family": "Space Grotesk",
            "vibe": "Ciencia, astronomía, IA, tecnología y futuro en estética obsidiana ámbar",
        },
        "emerald_matrix": {
            "name": "emerald_matrix",
            "primary": "#00F5A0",
            "accent": "#10B981",
            "bg": "#0A130E",
            "card_theme": "emerald_matrix",
            "sub_style": "viral",
            "font_family": "Plus Jakarta Sans",
            "vibe": "Cripto, finanzas, productividad, crecimiento y negocios",
        },
        "crimson_hazard": {
            "name": "crimson_hazard",
            "primary": "#FF3366",
            "accent": "#EF4444",
            "bg": "#140A0E",
            "card_theme": "crimson_hazard",
            "sub_style": "hormozi",
            "font_family": "Segoe UI Black",
            "vibe": "Urgente, alertas, breaking news, impacto, polémica o peligro",
        },
        "royal_gold": {
            "name": "royal_gold",
            "primary": "#FFB703",
            "accent": "#F59E0B",
            "bg": "#141009",
            "card_theme": "royal_gold",
            "sub_style": "cinema",
            "font_family": "Playfair Display",
            "vibe": "Historia, misterio antiguo, cine, filosofía y prestigio",
        },
        "orange_noir": {
            "name": "orange_noir",
            "primary": "#FF9436",
            "accent": "#FFE14D",
            "bg": "#0C0D12",
            "card_theme": "orange_noir",
            "sub_style": "viral",
            "font_family": "Outfit",
            "vibe": "Divulgación de alto impacto, curiosidades, ciencia cotidiana y narrativa viral",
        },
        "frosted_white": {
            "name": "frosted_white",
            "primary": "#FFFFFF",
            "accent": "#94A3B8",
            "bg": "#12141C",
            "card_theme": "frosted_white",
            "sub_style": "minimal",
            "font_family": "Inter",
            "vibe": "Minimalista, diseño elegante, sobrio y documental frío",
        },
    }

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    def determine_style(self, topic: str, style_mode: str = "divulgacion", extra_notes: str = "") -> Dict[str, Any]:
        """Analiza el tema y extrae la paleta, tipografía y estilo visual de forma inteligente."""
        t_low = (topic + " " + style_mode + " " + extra_notes).lower()

        detected_palette = "orange_noir"
        if any(w in t_low for w in ["nasa", "espacio", "telescopio", "astronom", "galaxia", "universo", "ia", "inteligencia artificial", "cyber", "robot", "quantum", "ciencia"]):
            detected_palette = "orange_noir"
        elif any(w in t_low for w in ["dinero", "cripto", "bitcoin", "millon", "finanz", "econom", "negocio", "inversi", "dolar", "empresa"]):
            detected_palette = "emerald_matrix"
        elif any(w in t_low for w in ["urgente", "alerta", "breaking", "guerra", "peligro", "escandalo", "crisis", "muerte", "amenaza"]):
            detected_palette = "crimson_hazard"
        elif any(w in t_low for w in ["historia", "antiguo", "arqueolog", "imperio", "siglo", "filosof", "arte", "misterio", "secreto"]):
            detected_palette = "royal_gold"
        elif any(w in t_low for w in ["minimal", "elegante", "documental sobrio", "blanco"]):
            detected_palette = "frosted_white"

        spec = dict(self.PALETTES[detected_palette])
        spec["topic"] = topic
        return spec


class AIRemotionGenerator:
    """Generador y orquestador de componentes React dinámicos para Remotion."""

    def __init__(self, remotion_engine: Optional[RemotionEngine] = None):
        self.remotion = remotion_engine or RemotionEngine()
        self.llm = LLMClient()
        self.style_director = AIStyleDirector(self.llm)

    def decide_overlay_for_scene(
        self,
        scene_name: str,
        speech_text: str,
        duration: float,
        vertical: bool = False,
        theme_spec: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Analiza el discurso de la escena para determinar si requiere un overlay animado
        de alto impacto (MetricCounter, VersusComparison o Callout) y genera sus props en React,
        utilizando la paleta de colores y tono definidos por el Director de Estilos.
        """
        prompt = f"""Eres el Director de Motion Graphics en Remotion (React + TypeScript).
Analiza el fragmento hablado de esta escena y determina si se beneficia de un gráfico animado clave en pantalla.

Información de la escena:
- Nombre: {scene_name}
- Duración: {duration:.1f}s
- Discurso hablado: "{speech_text}"
- Orientación: {"Vertical 9:16 (TikTok/Shorts)" if vertical else "Horizontal 16:9"}

Tipos de componentes disponibles en React:
1. "MetricCounter": Para cifras, estadísticas, porcentajes, montos económicos, años o récords (ej: "+250%", "$10M", "99%").
2. "VersusComparison": Para contrastes, mitos vs verdades, antes vs ahora, o dos bandos enfrentados.
3. null: Si la escena es puramente narrativa y los subtítulos bastan.

Responde ÚNICAMENTE con un objeto JSON sin formato markdown extra:
{{
  "should_render": true | false,
  "component": "MetricCounter" | "VersusComparison",
  "props": {{
    // Si es MetricCounter:
    // "title": "TITULO CORTO",
    // "fromValue": 0,
    // "toValue": 250,
    // "prefix": "+",
    // "suffix": "%",
    // "subtitle": "ACLARACIÓN CORTA"
    
    // Si es VersusComparison:
    // "tagA": "ANTES", "labelA": "TEXTO",
    // "tagB": "AHORA", "labelB": "TEXTO",
    // "category": "CATEGORIA"
  }}
}}
"""
        try:
            raw_resp = self.llm.generate(prompt, json_mode=True)
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_resp.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)
            if data.get("should_render") and data.get("component") in ("MetricCounter", "VersusComparison"):
                props = data.get("props", {})
                props["durationSec"] = round(min(duration, 3.8), 2)
                props["width"] = 1080 if vertical else 1920
                props["height"] = 1920 if vertical else 1080
                props["fps"] = 30
                props["vertical"] = vertical
                # Inyectar paleta cromática del Director de Estilos
                if theme_spec:
                    props["theme"] = {
                        "primary": theme_spec.get("primary", "#00E5FF"),
                        "accent": theme_spec.get("accent", "#FFE14D"),
                    }
                data["props"] = props
                return data
        except Exception as e:
            logger.warning("[AIRemotionGenerator] Fallback en decisión IA: %s", e)
        return None

    def build_props_from_intent_or_card(
        self,
        scene_name: str,
        speech_text: str,
        duration: float,
        vertical: bool = False,
        theme_spec: Optional[Dict[str, Any]] = None,
        card: Optional[Any] = None,
        intent: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Construye props directas para Remotion desde un card o un intent detectado sin latencia de red."""
        c_template = ""
        c_headline = ""
        c_body = ""
        c_stat = ""
        if card:
            c_template = str(getattr(card, "template", "") if hasattr(card, "template") else (card.get("template", "") if isinstance(card, dict) else "")).lower()
            c_headline = str(getattr(card, "headline", "") if hasattr(card, "headline") else (card.get("headline", "") if isinstance(card, dict) else ""))
            c_body = str(getattr(card, "body", "") if hasattr(card, "body") else (card.get("body", "") if isinstance(card, dict) else ""))
            c_stat = str(getattr(card, "stat", "") if hasattr(card, "stat") else (card.get("stat", "") if isinstance(card, dict) else ""))

        # 1. Caso Métrica Numérica (MetricCounter)
        raw_stat = c_stat or (getattr(intent, "stat_value", "") if intent else "")
        is_stat = (
            c_template in ("stat_counter", "stat_card")
            or (intent and getattr(intent, "intent_type", None) and intent.intent_type.value == "stat_number")
            or ("%" in raw_stat or (raw_stat and any(ch.isdigit() for ch in raw_stat) and len(raw_stat) < 14))
        )
        if is_stat and raw_stat:
            m_num = re.search(r"(\d+(?:[.,]\d+)?)", raw_stat)
            if m_num:
                num_str = m_num.group(1).replace(",", ".")
                try:
                    val = float(num_str) if "." in num_str else int(num_str)
                    pref = "+" if "+" in raw_stat else ("$" if "$" in raw_stat else "")
                    suff = "%" if "%" in raw_stat else ("M" if ("m" in raw_stat.lower() or "millon" in speech_text.lower()) else ("x" if "x" in raw_stat.lower() else ""))
                    title_txt = c_headline or (getattr(intent, "entity_name", "") if intent else "") or scene_name or "MÉTRICA CLAVE"
                    sub_txt = c_body or (getattr(intent, "raw_sentence", "")[:60] if intent else "") or "DATO VERIFICADO"
                    props: Dict[str, Any] = {
                        "durationSec": round(min(duration, 3.8), 2),
                        "width": 1080 if vertical else 1920,
                        "height": 1920 if vertical else 1080,
                        "fps": 30,
                        "vertical": vertical,
                        "title": title_txt.upper(),
                        "fromValue": 0,
                        "toValue": val,
                        "prefix": pref,
                        "suffix": suff,
                        "subtitle": sub_txt[:70],
                        "theme": {
                            "primary": (theme_spec or {}).get("primary", "#38BDF8"),
                            "accent": (theme_spec or {}).get("accent", "#FFE14D"),
                        },
                    }
                    return {"component": "MetricCounter", "props": props}
                except Exception:
                    pass

        # 2. Caso Comparativa Versus (VersusComparison)
        is_versus = (
            c_template in ("versus_split", "versus", "vs")
            or (intent and getattr(intent, "intent_type", None) and intent.intent_type.value == "versus_comparison")
            or (" vs " in c_headline.lower() or " vs " in c_body.lower())
        )
        if is_versus:
            s_a = c_headline or (getattr(intent, "entity_name", "") if intent else "") or "ANTES"
            s_b = c_body or (getattr(intent, "secondary_entity", "") if intent else "") or "AHORA"
            if " vs " in c_headline.lower():
                parts = c_headline.split(" vs ", 1)
                s_a, s_b = parts[0].strip(), parts[1].strip()
            props = {
                "durationSec": round(min(duration, 3.8), 2),
                "width": 1080 if vertical else 1920,
                "height": 1920 if vertical else 1080,
                "fps": 30,
                "vertical": vertical,
                "tagA": "LADO A",
                "labelA": s_a.upper()[:40],
                "tagB": "LADO B",
                "labelB": s_b.upper()[:40],
                "category": "ANÁLISIS COMPARATIVO",
                "theme": {
                    "primary": (theme_spec or {}).get("primary", "#F43F5E"),
                    "accent": (theme_spec or {}).get("accent", "#10B981"),
                },
            }
            return {"component": "VersusComparison", "props": props}

        return None

    async def render_ai_overlay(
        self,
        scene_name: str,
        speech_text: str,
        duration: float,
        out_dir: Path,
        vertical: bool = False,
        theme_spec: Optional[Dict[str, Any]] = None,
        card: Optional[Any] = None,
        intent: Optional[Any] = None,
    ) -> Optional[Path]:
        """Ejecuta la decisión de Remotion y renderiza el componente React en MOV ProRes 4444 con canal alpha."""
        if not self.remotion.available():
            return None

        # 1. Intentar construir props directas desde el card o el intent (0ms latencia)
        spec = self.build_props_from_intent_or_card(
            scene_name, speech_text, duration, vertical=vertical, theme_spec=theme_spec, card=card, intent=intent
        )

        # 2. Si no hay datos directos, consultar al Director IA de Remotion
        if not spec:
            spec = self.decide_overlay_for_scene(scene_name, speech_text, duration, vertical, theme_spec=theme_spec)

        if not spec:
            return None

        comp_id = spec["component"]
        props = spec["props"]
        logger.info("[AIRemotionGenerator] ⚛️ Renderizando overlay React Remotion '%s' con paleta %s para '%s'",
                    comp_id, props.get("theme", {}), scene_name)
        return await self.remotion.render_overlay(comp_id, props, out_dir)

