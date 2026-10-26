"""Módulo de integración para síntesis de voz y preescucha con Speechify API.

Soporta múltiples claves de API con conmutación automática ante agotamiento
de créditos (failover), validación de saldo disponible y generación de audio MP3.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("speechify_tts")

_raw_speechify_keys = (
    os.getenv("SPEECHIFY_API_KEYS")
    or os.getenv("SPEECHIFY_API_KEY")
    or ""
).replace("\n", ",").replace(";", ",")
SPEECHIFY_API_KEYS = [key.strip() for key in _raw_speechify_keys.split(",") if key.strip()]

_active_key_index: int = 0
_credits_available: bool = True
_exhausted_keys: set[int] = set()

# Catálogo oficial de voces Speechify integradas en Lumen Studio
SPEECHIFY_VOICES: List[Dict[str, Any]] = [
    {
        "id": "speechify:alejandro",
        "voice_id": "alejandro",
        "name": "Alejandro · Speechify",
        "desc": "Cálida · 1.0×",
        "provider": "speechify",
        "locale": "es-MX",
        "sample_file": "speechify_alejandro.mp3",
    },
    {
        "id": "speechify:aitana",
        "voice_id": "aitana",
        "name": "Aitana · Speechify",
        "desc": "Brillante · 1.0×",
        "provider": "speechify",
        "locale": "es-MX",
        "sample_file": "speechify_aitana.mp3",
    },
    {
        "id": "speechify:alejandra",
        "voice_id": "alejandra",
        "name": "Alejandra · Speechify",
        "desc": "Narrativa · 0.95×",
        "provider": "speechify",
        "locale": "es-MX",
        "sample_file": "speechify_alejandra.mp3",
    },
    {
        "id": "speechify:alexa",
        "voice_id": "alexa",
        "name": "Alexa · Speechify",
        "desc": "Estudio · 1.0×",
        "provider": "speechify",
        "locale": "es-MX",
        "sample_file": "speechify_alexa.mp3",
    },
    {
        "id": "speechify:alondra",
        "voice_id": "alondra",
        "name": "Alondra · Speechify",
        "desc": "Documental · 0.95×",
        "provider": "speechify",
        "locale": "es-MX",
        "sample_file": "speechify_alondra.mp3",
    },
]


def has_speechify_credits() -> bool:
    """Verifica si aún existen créditos utilizables en alguna de las API keys."""
    global _credits_available
    return _credits_available and len(_exhausted_keys) < len(SPEECHIFY_API_KEYS)


def get_speechify_status() -> Dict[str, Any]:
    return {
        "has_credits": has_speechify_credits(),
        "active_key_index": _active_key_index + 1,
        "total_keys": len(SPEECHIFY_API_KEYS),
        "exhausted_keys": list(_exhausted_keys),
    }


import re

def _split_text_into_chunks(text: str, max_chars: int = 1400) -> List[str]:
    """Divide texto en fragmentos respetando pausas de oraciones para no exceder el límite de 2000 chars de Speechify."""
    clean = text.strip()
    if len(clean) <= max_chars:
        return [clean]
    
    sentences = re.split(r'(?<=[.!?;\n])\s+', clean)
    chunks: List[str] = []
    curr = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # Si una sola oración supera max_chars, dividir por comas o palabras
        if len(s) > max_chars:
            words = s.split()
            sub_curr = ""
            for w in words:
                if len(sub_curr) + len(w) + 1 <= max_chars:
                    sub_curr = f"{sub_curr} {w}".strip()
                else:
                    if sub_curr:
                        chunks.append(sub_curr)
                    sub_curr = w
            if sub_curr:
                curr = sub_curr
            continue

        if len(curr) + len(s) + 1 <= max_chars:
            curr = f"{curr} {s}".strip()
        else:
            if curr:
                chunks.append(curr)
            curr = s
    if curr:
        chunks.append(curr)
    return chunks or [clean]


def _synthesize_single_chunk(text: str, voice_id: str) -> Optional[bytes]:
    """Sintetiza un bloque individual <= 1500 chars usando Speechify probando la clave activa y conmutando si se agotan créditos."""
    global _active_key_index, _credits_available, _exhausted_keys

    clean_voice = voice_id.replace("speechify:", "").strip()
    clean_text = text.strip()
    if not clean_text:
        return None

    # Envolver en tag SSML speak requerido por Speechify
    if not clean_text.startswith("<speak>"):
        clean_text = f"<speak>{clean_text}</speak>"

    payload = json.dumps({
        "input": clean_text,
        "voice_id": clean_voice,
        "audio_format": "mp3"
    }).encode("utf-8")

    for attempt in range(len(SPEECHIFY_API_KEYS)):
        current_idx = (_active_key_index + attempt) % len(SPEECHIFY_API_KEYS)
        if current_idx in _exhausted_keys:
            continue

        api_key = SPEECHIFY_API_KEYS[current_idx]
        url = "https://api.sws.speechify.com/v1/audio/speech"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    raw_data = resp.read()
                    if raw_data.startswith(b"{") and b"audio_data" in raw_data:
                        try:
                            parsed = json.loads(raw_data.decode("utf-8"))
                            b64_audio = parsed.get("audio_data")
                            if b64_audio:
                                mp3_bytes = base64.b64decode(b64_audio)
                                if len(mp3_bytes) > 200:
                                    _active_key_index = current_idx
                                    return mp3_bytes
                        except Exception as _p_err:
                            logger.warning(f"[Speechify] Error decodificando audio_data: {_p_err}")
                    elif len(raw_data) > 200:
                        _active_key_index = current_idx
                        return raw_data
        except urllib.error.HTTPError as err:
            err_body = ""
            try:
                err_body = err.read().decode("utf-8", errors="ignore")
            except Exception:
                pass

            logger.warning(
                f"[Speechify] Error HTTP {err.code} en clave #{current_idx + 1}: {err_body}"
            )

            # 402 = Payment Required (Sin créditos) / 429 = Rate Limit / 403 = Forbidden
            if err.code in (402, 403, 429) or "credit" in err_body.lower() or "quota" in err_body.lower() or "balance" in err_body.lower():
                _exhausted_keys.add(current_idx)
                logger.error(f"[Speechify] Créditos agotados en clave #{current_idx + 1}. Conmutando...")
            else:
                pass
        except Exception as exc:
            logger.error(f"[Speechify] Excepción conectando a API: {exc}")

    # Si todas las claves se agotaron
    if len(_exhausted_keys) >= len(SPEECHIFY_API_KEYS):
        _credits_available = False
        logger.critical("[Speechify] TODAS las claves de Speechify han agotado sus créditos. Bloqueando selección.")

    return None


def synthesize_speechify(text: str, voice_id: str) -> Optional[bytes]:
    """Sintetiza texto usando Speechify. Si el texto supera 1400 caracteres, lo segmenta y concatena limpiamente."""
    if not text or not text.strip():
        return None
    
    clean_voice = voice_id.replace("speechify:", "").strip()
    chunks = _split_text_into_chunks(text, max_chars=1400)
    
    if len(chunks) == 1:
        return _synthesize_single_chunk(chunks[0], clean_voice)
    
    audio_parts: List[bytes] = []
    for c in chunks:
        part = _synthesize_single_chunk(c, clean_voice)
        if part and len(part) > 200:
            audio_parts.append(part)
        else:
            logger.warning(f"[Speechify] Falló síntesis de fragmento ({len(c)} chars), abortando concatenación.")
            return None
            
    return b"".join(audio_parts) if audio_parts else None
