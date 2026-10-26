"""Optimizador de Títulos Virales de YouTube con IA.

Corrige faltas ortográficas, errores gramaticales y transforma el tema crudo
del usuario en un título magnético de alto impacto (High CTR / retención)
respetando estrictamente los límites de caracteres de YouTube (máximo 100 caracteres,
longitud recomendada de 50 a 75 caracteres).
"""

from __future__ import annotations

import re
from typing import Optional
from core.llm import LLMClient, safe_log

# Límite estricto de YouTube es 100 caracteres. Dejamos margen de seguridad a 95 chars.
YOUTUBE_MAX_TITLE_CHARS = 95
YOUTUBE_RECOMMENDED_MIN_CHARS = 45
YOUTUBE_RECOMMENDED_MAX_CHARS = 75


def clean_title_formatting(title: str) -> str:
    """Elimina prefijos no deseados, comillas exteriores y normaliza espacios."""
    if not title:
        return ""
    t = str(title).strip()
    # Eliminar comillas envolventes
    t = re.sub(r'^["\'«“]+|["\'»”]+$', '', t).strip()
    # Eliminar prefijos comunes automáticos
    t = re.sub(r'^(?:Título|Title|Video|KAI Stream|Transmisión|KAI|Tema)\s*:\s*', '', t, flags=re.I).strip()
    # Eliminar comillas envolventes restantes si quedaron
    t = re.sub(r'^["\'«“]+|["\'»”]+$', '', t).strip()
    # Normalizar espacios múltiples
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def enforce_youtube_character_limit(title: str, max_chars: int = YOUTUBE_MAX_TITLE_CHARS) -> str:
    """Asegura que el título nunca exceda los límites de caracteres de YouTube cortando por palabra."""
    t = clean_title_formatting(title)
    if len(t) <= max_chars:
        return t

    # Cortar por límite de palabras para no dejar palabras a medias
    truncated = t[:max_chars].rstrip()
    last_space = truncated.rfind(' ')
    if last_space > 30:
        truncated = truncated[:last_space].rstrip()

    # Limpiar puntuación huérfana al final
    truncated = re.sub(r'[,;:\-–—\(\[\{]+$', '', truncated).strip()
    return truncated


def optimize_youtube_title(
    raw_topic: str,
    style: str = "divulgacion",
    duration_sec: int = 45,
    existing_plan_title: Optional[str] = None,
) -> str:
    """Transforma el tema del usuario en un título viral para YouTube sin faltas ortográficas."""
    clean_raw = (raw_topic or "").strip()
    if not clean_raw:
        return "Video de Impacto"

    # Si ya tenemos un título de plan que es de alta calidad y no repite simplemente el raw
    if existing_plan_title:
        candidate = clean_title_formatting(existing_plan_title)
        if candidate and candidate.lower() != clean_raw.lower() and len(candidate) >= 20:
            if len(candidate) <= YOUTUBE_MAX_TITLE_CHARS:
                return candidate
            return enforce_youtube_character_limit(candidate)

    # Invocar LLM para generar el título de YouTube optimizado
    try:
        llm = LLMClient()
        format_hint = "Short / Reel vertical 9:16" if duration_sec <= 90 else "Video largo 16:9"
        prompt = f"""Eres el mejor estratega de contenido y Copywriter de YouTube en español del mundo (especialista en alto CTR y viralidad).

El usuario quiere hacer un video sobre este tema, pero su entrada puede tener faltas ortográficas, errores de tipeo o ser aburrida:
"{clean_raw}"

Formato del video: {format_hint}
Estilo de comunicación: {style}

TU MISIÓN:
Crea un ÚNICO título para YouTube que:
1. CORRECCIÓN ESTRICTA: Corrige al 100% cualquier falta ortográfica, de acentuación, puntuación o sintaxis del tema original.
2. ALTO CTR Y RETENCIÓN: Despierte curiosidad irresistible, intriga o sorpresa ("ganas de verlo"), usando ganchos comprobados de YouTube (revelación, paradoja, verdad oculta o pregunta directa).
3. LÍMITE DE CARACTERES DE YOUTUBE:
   - El límite absoluto de YouTube son 100 caracteres.
   - Tu título DEBE tener entre {YOUTUBE_RECOMMENDED_MIN_CHARS} y {YOUTUBE_RECOMMENDED_MAX_CHARS} caracteres (MÁXIMO ABSOLUTO: {YOUTUBE_MAX_TITLE_CHARS} caracteres).
   - NUNCA superes {YOUTUBE_MAX_TITLE_CHARS} caracteres para que no se corte en teléfonos móviles.

RESPONDE EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO:
{{"title": "Tu título optimizado aquí"}}
"""
        generated = llm.generate(prompt, json_mode=True, deadline_sec=25.0)
        
        from utils.json_validator import JSONValidator
        parsed = JSONValidator.extract_and_parse(generated)
        best_title = ""
        if isinstance(parsed, dict) and parsed.get("title"):
            best_title = str(parsed["title"])
        else:
            m = re.search(r'"title"\s*:\s*"([^"]+)"', generated)
            if m:
                best_title = m.group(1)
            else:
                lines = [line.strip() for line in generated.splitlines() if line.strip() and not line.strip().startswith("{") and not line.strip().startswith("}")]
                best_title = lines[0] if lines else generated

        # Quitar comillas y prefijos si el modelo los añadió
        best_title = clean_title_formatting(best_title)
        if best_title and len(best_title) >= 15:
            final_title = enforce_youtube_character_limit(best_title)
            safe_log(f"[TitleOptimizer] ✓ Título optimizado para YouTube: «{final_title}» ({len(final_title)} caracteres)")
            return final_title

    except Exception as exc:
        safe_log(f"[TitleOptimizer] Aviso en optimización con LLM: {exc}")

    # Fallback inteligente si el LLM falla
    fallback = clean_title_formatting(clean_raw)
    # Poner primera letra en mayúscula
    if fallback:
        fallback = fallback[0].upper() + fallback[1:]
    return enforce_youtube_character_limit(fallback)
