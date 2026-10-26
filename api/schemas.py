"""Modelos y esquemas Pydantic para la API RESTful de AetherCut AI (v1).

Define las especificaciones de entrada (requests) y salida (responses)
con tipos estrictos, descripciones y ejemplos para Swagger / OpenAPI.
"""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field, HttpUrl

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = Field(True, description="Indica si la solicitud fue exitosa")
    message: str = Field("Operación completada", description="Mensaje informativo")
    data: Optional[T] = Field(None, description="Datos de la respuesta")


class ApiErrorDetail(BaseModel):
    code: str = Field(..., description="Código de error de la API")
    message: str = Field(..., description="Descripción detallada del error")
    details: Optional[Dict[str, Any]] = Field(None, description="Metadatos auxiliares del error")


class ApiErrorResponse(BaseModel):
    success: bool = Field(False, description="Siempre false en respuestas de error")
    error: ApiErrorDetail


# ==========================================
# 1. Video Processing Schemas
# ==========================================

class VideoProcessOptions(BaseModel):
    silence_threshold: float = Field(1.5, ge=0.5, le=5.0, description="Umbral en segundos para cortar silencios")
    enable_broll: bool = Field(True, description="Buscar y superponer material de apoyo (B-Roll)")
    enable_captions: bool = Field(True, description="Generar y quemar subtítulos dinámicos de alto impacto")
    enable_shorts: bool = Field(True, description="Extraer automáticamente Shorts / Reels verticales 9:16")
    enable_cards: bool = Field(True, description="Generar tarjetas informativas contrastadas con IA")
    voice: str = Field("es-MX-JorgeNeural", description="Voz neuronal para narración o doblaje de tarjetas")
    webhook_url: Optional[str] = Field(None, description="URL de webhook a invocar al finalizar o fallar el proceso")


class VideoProcessUrlRequest(VideoProcessOptions):
    video_url: str = Field(..., description="URL pública del video (enlace directo MP4, YouTube, Drive, etc.)")
    title: Optional[str] = Field(None, description="Título o nombre opcional para identificar el video")


class VideoProcessResponse(BaseModel):
    task_id: str = Field(..., description="ID único asignado a la tarea")
    project_id: str = Field(..., description="ID del proyecto creado")
    status: str = Field("queued", description="Estado inicial de la tarea")
    message: str = Field(..., description="Detalles del inicio del procesamiento")


# ==========================================
# 2. Streamer / AI Broadcast Schemas
# ==========================================

class StreamerCreateRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="Tema o premisa central del video a generar")
    style: str = Field("divulgacion", description="Estilo de guion y ritmo: divulgacion, polemica, misterio, etc.")
    duration_sec: int = Field(45, ge=1, le=2400, description="Duración estimada del video en segundos (o minutos si <= 40)")
    aspect_ratio: str = Field("16:9", description="Relación de aspecto: '16:9' (horizontal) o '9:16' (vertical)")
    card_theme: str = Field("dark", description="Tema visual de tarjetas: dark, light, neon, etc.")
    voice: str = Field("es-MX-JorgeNeural", description="Voz de narración TTS a utilizar")
    visual_mode: str = Field("mixed", description="Modo visual: mixed, ai_remotion, broll_only, motion_graphics")
    rtmp_url: Optional[str] = Field(None, description="URL RTMP opcional para streaming en vivo directo")
    webhook_url: Optional[str] = Field(None, description="URL de webhook a notificar cuando termine la transmisión")
    extra_notes: Optional[str] = Field(None, description="Instrucciones o requerimientos editoriales adicionales")
    auto_publish: bool = Field(False, description="Publicar automáticamente a YouTube al completar")
    enable_avatar: bool = Field(True, description="Habilitar avatar animado o PIP en video")
    burn_subtitles: bool = Field(False, description="Quemar subtítulos cinéticos directamente en el video")
    sub_style: str = Field("classic", description="Estilo visual de subtítulos (classic, viral, hormozi, mrbeast, minimal, cinema)")


class StreamerCreateResponse(BaseModel):
    task_id: str = Field(..., description="ID de la tarea en ejecución")
    project_id: str = Field(..., description="ID del proyecto generado")
    topic: str = Field(..., description="Tema en producción")
    message: str = Field(..., description="Mensaje de confirmación")


# ==========================================
# 3. Tasks / Background Tracking Schemas
# ==========================================

class TaskEvent(BaseModel):
    step: str
    progress: float
    message: str
    at: str


class TaskStatusResponse(BaseModel):
    task_id: str
    step: str = Field(..., description="Etapa actual: init, audio, silence, llm, assets, render, done, error, cancelled")
    progress: float = Field(..., description="Porcentaje de avance (0 a 100)")
    message: str = Field(..., description="Descripción del paso actual")
    completed: bool
    cancelled: bool = False
    error: Optional[str] = None
    file_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = []


# ==========================================
# 4. Project Schemas
# ==========================================

class ProjectSummary(BaseModel):
    id: str
    name: str
    status: str
    duration: float = 0.0
    topic: Optional[str] = None
    thumbnail_url: Optional[str] = None
    master_video_url: Optional[str] = None
    has_plan: bool = False
    has_result: bool = False
    updated_at: Optional[str] = None


class ProjectListResponse(BaseModel):
    projects: List[ProjectSummary]
    total: int


class TimelineCardUpdate(BaseModel):
    id: str
    enabled: Optional[bool] = None
    start: Optional[float] = None
    duration: Optional[float] = None
    position: Optional[str] = None
    avatar_spoken_text: Optional[str] = None
    avatar_enabled: Optional[bool] = None


class TimelineBrollUpdate(BaseModel):
    id: str
    enabled: Optional[bool] = None
    start: Optional[float] = None
    end: Optional[float] = None


class TimelineUpdateRequest(BaseModel):
    cards: Optional[List[TimelineCardUpdate]] = None
    brolls: Optional[List[TimelineBrollUpdate]] = None


# ==========================================
# 5. Clips / Shorts Schemas
# ==========================================

class ClipSummary(BaseModel):
    filename: str
    name: str
    url: str
    size_mb: float
    created_at: Optional[str] = None


class ClipExtractRequest(BaseModel):
    start_sec: Optional[float] = Field(None, ge=0.0, description="Segundo de inicio del clip")
    end_sec: Optional[float] = Field(None, ge=1.0, description="Segundo de finalización del clip")
    aspect_ratio: str = Field("9:16", description="Relación de aspecto: '9:16' o '16:9'")
    title: Optional[str] = Field(None, description="Título del clip / Short")


# ==========================================
# 6. TTS / Audio Schemas
# ==========================================

class VoiceSummary(BaseModel):
    id: str
    name: str
    language: str
    accent: str
    gender: str
    preview_url: Optional[str] = None


class TTSGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Texto a sintetizar con voz neuronal")
    voice: str = Field("es-MX-JorgeNeural", description="Identificador de la voz")
    rate: str = Field("+0%", description="Ajuste de velocidad, ej: '+10%', '-5%'")
    pitch: str = Field("+0Hz", description="Ajuste de tono, ej: '+5Hz'")


# ==========================================
# 7. Trend Radar Schemas
# ==========================================

class TrendTopic(BaseModel):
    id: str
    title: str
    velocity_score: float = 0.0
    views: Optional[str] = None
    channel: Optional[str] = None
    published_at: Optional[str] = None
    tags: List[str] = []
    url: Optional[str] = None


class TrendReplicateRequest(BaseModel):
    topic: str = Field(..., description="Tema a replicar en un nuevo video")
    style: str = Field("divulgacion", description="Estilo narrativo")
    duration_sec: int = Field(45, ge=1, le=2400)
    aspect_ratio: str = Field("16:9")
    webhook_url: Optional[str] = None


# ==========================================
# 8. Publishing & Channels Schemas
# ==========================================

class PublishPrepareRequest(BaseModel):
    project_id: str = Field(..., description="ID del proyecto")
    custom_instructions: Optional[str] = None


class PublishThumbnailRequest(BaseModel):
    project_id: str
    title: str
    topic: Optional[str] = None
    style: str = Field("bold_contrast", description="bold_contrast, minimal, neon, etc.")


class ChannelSchema(BaseModel):
    id: Optional[str] = None
    name: str
    niche: str
    description: Optional[str] = None
    preferred_voice: Optional[str] = None
    target_audience: Optional[str] = None


class YouTubeUploadRequest(BaseModel):
    project_id: str
    title: str
    description: str
    tags: List[str] = []
    privacy: str = Field("private", description="private, unlisted, public")
    category_id: str = Field("27", description="Categoría YouTube (27=Educación, 28=Ciencia y Tecnología)")
    made_for_kids: bool = False


# ==========================================
# 9. Agent / Copilot Schemas
# ==========================================

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Mensaje, consulta o instrucción para el agente")
    model_id: str = Field("gemini", description="Modelo LLM a utilizar")
    app_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


# ==========================================
# 10. System & Health Schemas
# ==========================================

class SystemHealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    server_time: str
    ffmpeg_available: bool
    ffprobe_available: bool
    gpu_available: bool
    storage_free_gb: float
    active_tasks_count: int
