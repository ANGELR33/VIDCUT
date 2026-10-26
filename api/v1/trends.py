"""Endpoints para el Radar de Viralidad y replicación de tendencias."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.schemas import ApiResponse, TrendReplicateRequest
from api.security import verify_api_key
from api.state import api_state
from core.trend_radar import TrendRadar

router = APIRouter(prefix="/trends", tags=["Trend Radar & Viral Intelligence"])


@router.get("", response_model=ApiResponse[Dict[str, Any]])
async def get_trending_topics(
    region: Optional[str] = Query(None, description="Código de región ISO alpha-2, ej: US, ES, MX"),
    _auth: bool = Depends(verify_api_key),
):
    """Consulta los videos y temas virales en tiempo real detectados por el Radar."""
    radar = TrendRadar()
    data = radar.get_snapshot()
    return ApiResponse(
        success=True,
        message="Tendencias virales obtenidas",
        data=data,
    )


@router.post("/refresh", response_model=ApiResponse[Dict[str, Any]])
async def refresh_trends(_auth: bool = Depends(verify_api_key)):
    """Ejecuta una búsqueda y actualización en vivo de videos más virales en YouTube."""
    radar = TrendRadar()
    loop = asyncio.get_running_loop()
    refreshed = await loop.run_in_executor(None, radar.refresh)
    return ApiResponse(
        success=True,
        message="Radar de viralidad actualizado en vivo",
        data=refreshed,
    )


@router.post("/replicate", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_202_ACCEPTED)
async def replicate_trending_topic(
    payload: TrendReplicateRequest,
    _auth: bool = Depends(verify_api_key),
):
    """Convierte un tema viral detectado directamente en un video autónomo de alta retención."""
    from api.v1.streamer import create_autonomous_broadcast
    from api.schemas import StreamerCreateRequest

    req = StreamerCreateRequest(
        topic=payload.topic,
        style=payload.style,
        duration_sec=payload.duration_sec,
        aspect_ratio=payload.aspect_ratio,
        webhook_url=payload.webhook_url,
    )
    res = await create_autonomous_broadcast(req, _auth=True)
    return ApiResponse(
        success=True,
        message=f"Replicación viral iniciada para «{payload.topic}».",
        data=res.data.model_dump(),
    )
