"""Endpoints para interactuar con el Agente Director IA (Copilot)."""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.schemas import AgentChatRequest, ApiResponse
from api.security import verify_api_key
from core.app_agent import AppAgentController
from core.llm import safe_log

router = APIRouter(prefix="/agent", tags=["AI Director Copilot"])


@router.post("/chat", response_model=ApiResponse[Dict[str, Any]])
async def agent_chat(payload: AgentChatRequest, _auth: bool = Depends(verify_api_key)):
    """Envía un mensaje o instrucción al Agente Director IA y recibe respuestas estructuradas."""
    controller = AppAgentController()
    try:
        res = controller.process_message(
            message=payload.message,
            model_id=payload.model_id,
            app_context=payload.app_context or {},
            history=payload.history or [],
        )
        return ApiResponse(
            success=True,
            message="Respuesta del agente obtenida",
            data=res,
        )
    except Exception as exc:
        safe_log(f"[API Agent] Error: {exc}")
        raise HTTPException(status_code=500, detail=f"Error en el agente: {exc}")


@router.post("/chat/stream")
async def agent_chat_stream(payload: AgentChatRequest):
    """Transmite la respuesta del agente palabra por palabra en tiempo real (SSE)."""
    controller = AppAgentController()

    async def _stream():
        try:
            async for chunk in controller.stream_message(
                message=payload.message,
                model_id=payload.model_id,
                app_context=payload.app_context or {},
                history=payload.history or [],
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
