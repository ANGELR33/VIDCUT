"""Endpoints para locución neuronal, síntesis de voz (TTS) y catálogo vocal."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import edge_tts
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from config.settings import settings
from api.schemas import ApiResponse, TTSGenerateRequest, VoiceSummary
from api.security import verify_api_key
from utils.speech_normalizer import normalize_speech_for_tts

router = APIRouter(prefix="/tts", tags=["Voiceover & TTS Studio"])

PRESET_VOICES = [
    VoiceSummary(id="es-MX-JorgeNeural", name="Jorge (Neural)", language="Español", accent="México (Latino Cálido)", gender="Masculino", preview_url="/api/tts-preview?voice=es-MX-JorgeNeural"),
    VoiceSummary(id="es-ES-AlvaroNeural", name="Álvaro (Neural)", language="Español", accent="España (Divulgación)", gender="Masculino", preview_url="/api/tts-preview?voice=es-ES-AlvaroNeural"),
    VoiceSummary(id="es-CO-GonzaloNeural", name="Gonzalo (Neural)", language="Español", accent="Colombia (Documental Profundo)", gender="Masculino", preview_url="/api/tts-preview?voice=es-CO-GonzaloNeural"),
    VoiceSummary(id="es-US-AlonsoNeural", name="Alonso (Neural)", language="Español", accent="Estados Unidos (Dinámico)", gender="Masculino", preview_url="/api/tts-preview?voice=es-US-AlonsoNeural"),
    VoiceSummary(id="es-AR-TomasNeural", name="Tomás (Neural)", language="Español", accent="Argentina (Urbano)", gender="Masculino", preview_url="/api/tts-preview?voice=es-AR-TomasNeural"),
    VoiceSummary(id="es-MX-DaliaNeural", name="Dalia (Neural)", language="Español", accent="México (Narrativa Femenina)", gender="Femenino", preview_url="/api/tts-preview?voice=es-MX-DaliaNeural"),
    VoiceSummary(id="es-AR-ElenaNeural", name="Elena (Neural)", language="Español", accent="Argentina (Docente Femenina)", gender="Femenino", preview_url="/api/tts-preview?voice=es-AR-ElenaNeural"),
]


@router.get("/voices", response_model=ApiResponse[List[VoiceSummary]])
async def list_available_voices(_auth: bool = Depends(verify_api_key)):
    """Lista las voces neuronales disponibles para narración y doblaje de videos."""
    return ApiResponse(
        success=True,
        message=f"{len(PRESET_VOICES)} voces disponibles",
        data=PRESET_VOICES,
    )


@router.post("/synthesize", response_model=ApiResponse[Dict[str, Any]])
async def synthesize_speech(
    payload: TTSGenerateRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Sintetiza audio a partir de texto utilizando modelos neuronales EdgeTTS."""
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El texto a sintetizar no puede estar vacío.")

    clean_text = normalize_speech_for_tts(text) or text
    out_id = uuid.uuid4().hex[:10]
    out_file = settings.OUTPUTS_DIR / f"tts_{out_id}.mp3"

    try:
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=payload.voice,
            rate=payload.rate,
            pitch=payload.pitch,
        )
        await communicate.save(str(out_file))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fallo al sintetizar la locución neuronal: {exc}")

    size_kb = round(out_file.stat().st_size / 1024, 1)

    return ApiResponse(
        success=True,
        message="Audio sintetizado exitosamente.",
        data={
            "filename": out_file.name,
            "url": f"/media/{out_file.name}",
            "size_kb": size_kb,
            "voice": payload.voice,
            "characters_count": len(text),
        },
    )
