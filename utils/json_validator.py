import json
import re
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import VideoEditingPlan

class JSONParsingError(Exception):
    """Excepción lanzada cuando la respuesta no puede ser parseada a JSON válido."""
    pass

class JSONValidator:
    """Utilidad para sanear y validar respuestas JSON procedentes de modelos LLM."""

    @staticmethod
    def extract_and_parse(raw_text: str) -> Dict[str, Any]:
        """Limpia bloques de código markdown y parsea el string a un diccionario Python."""
        cleaned = raw_text.strip()
        
        # Eliminar bloques markdown ```json ... ``` si existen
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
            
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as err:
            # Fallback: intentar encontrar el primer '{' y el último '}'
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                substring = cleaned[first_brace:last_brace + 1]
                try:
                    return json.loads(substring)
                except json.JSONDecodeError:
                    pass
            raise JSONParsingError(f"No fue posible parsear el JSON de Gemini: {err}\nTexto original:\n{raw_text[:500]}...")

    @classmethod
    def validate_editing_plan(cls, raw_text: str):
        """Valida que el texto cumpla con el modelo VideoEditingPlan."""
        from core.models import VideoEditingPlan
        data = cls.extract_and_parse(raw_text)
        return VideoEditingPlan.model_validate(data)
