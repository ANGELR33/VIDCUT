"""Módulo de verificación de conexión.

Contiene la lógica de health check: ping lógico, validación de estado
y timestamp de respuesta. Sin dependencias externas, solo stdlib (datetime).
"""

from datetime import datetime, timezone
from typing import Any, Dict


def _utc_now_iso() -> str:
    """Retorna el timestamp actual en formato ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def _utc_now_iso_safe() -> str:
    """Genera timestamp UTC de forma segura; devuelve cadena vacía si falla."""
    try:
        return _utc_now_iso()
    except Exception:
        return ""


def health_check() -> Dict[str, Any]:
    """Ejecuta la verificación de conexión (ping lógico).

    Realiza una validación básica del estado del sistema y devuelve
    un diccionario con el resultado y el timestamp de la respuesta.

    Returns:
        Dict con las claves:
            - 'status': 'ok' si la verificación fue exitosa, 'error' ante fallos.
            - 'timestamp': timestamp de respuesta en formato ISO 8601 UTC.
            - 'detail': mensaje descriptivo del resultado.
    """
    try:
        timestamp: str = _utc_now_iso()

        # Ping lógico: validación de que el sistema genera una respuesta válida.
        if not timestamp:
            return {
                "status": "error",
                "timestamp": "",
                "detail": "No se pudo generar un timestamp válido.",
            }

        return {
            "status": "ok",
            "timestamp": timestamp,
            "detail": "Conexión verificada correctamente.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "timestamp": _utc_now_iso_safe(),
            "detail": f"Error durante la verificación de conexión: {exc}",
        }
