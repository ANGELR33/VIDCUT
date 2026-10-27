from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    KEEP = "KEEP"
    CUT_SILENCE = "CUT_SILENCE"
    CUT_FILLER = "CUT_FILLER"

class BRollCue(BaseModel):
    """Instrucción para buscar e insertar material de stock en un momento específico."""
    cue_id: str = Field(description="Identificador único del cue (ej. broll_1)")
    start_sec: float = Field(ge=0.0, description="Segundo de inicio de la sobreposición del B-Roll")
    end_sec: float = Field(gt=0.0, description="Segundo de fin de la sobreposición del B-Roll")
    concept: str = Field(description="Concepto o entidad mencionada por el hablante (ej. 'Cataratas del Niágara')")
    search_query_en: str = Field(description="Término optimizado en inglés para buscar en Pexels API (ej. 'niagara falls aerial')")
    asset_type: str = Field(default="video", description="'video' o 'photo'")
    transition: str = Field(default="fade", description="Tipo de transición de entrada/salida (fade, slide)")
    reasoning: str = Field(description="Por qué este momento amerita apoyo visual")
    local_file_path: Optional[str] = Field(default=None, description="Ruta local del asset descargado")
    download_status: str = Field(default="PENDING", description="PENDING, DOWNLOADING, COMPLETED, FAILED")
    frame_path: Optional[str] = Field(default=None, description="Interno: foto enmarcada como tarjeta flotante")
    enabled: bool = Field(default=True, description="Permite retirar un apoyo visual desde el editor")
    spoken_phrase: str = Field(default="", description="Frase EXACTA del hablante que justifica este apoyo visual")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Seguridad (0-1) de que este apoyo visual aporta algo concreto y mostrable")
    relevance_score: Optional[float] = Field(default=None, description="Interno: puntaje 0-10 del filtro de relevancia visual")
    relevance_note: str = Field(default="", description="Interno: motivo de aceptación o rechazo del filtro de relevancia")
    rights_status: str = Field(default="unknown", description="Interno: cleared, attribution_required, review o risky")
    rights_note: str = Field(default="", description="Interno: motivo del estado de derechos")
    attribution: str = Field(default="", description="Interno: línea de crédito para la descripción, si la licencia lo exige")

class SourceRef(BaseModel):
    """Fuente web real que respalda una tarjeta informativa."""
    title: str = Field(default="", description="Título de la página")
    url: str = Field(default="", description="URL de la fuente")
    domain: str = Field(default="", description="Dominio legible (ej. es.wikipedia.org)")

class InfoCard(BaseModel):
    """
    Tarjeta informativa para mostrar en pantalla mientras el hablante menciona un dato concreto
    (ley, cifra, fecha, persona, lugar, organización).
    Los campos verdict, body, sources, image_path y card_path los completa el verificador, NO Gemini.
    """
    card_id: str = Field(description="Identificador único (ej. card_1)")
    start_sec: float = Field(ge=0.0, description="Segundo en que se menciona el dato")
    end_sec: float = Field(gt=0.0, description="Segundo de fin de la tarjeta (duración 4 a 7 s)")
    kind: str = Field(default="dato", description="ley, cifra, fecha, persona, lugar, organizacion, hardware, concepto, complemento, refuerzo o dato")
    card_style: str = Field(default="reference", description="reference (Platzi/Nate Gentile callout), stat_highlight (gran cifra/porcentaje), mockup_browser (ventana de artículo/wiki), tech_spec (especificaciones técnicas)")
    headline: str = Field(default="", description="Titular corto o nombre del concepto/término/persona/ley (máx. 60 caracteres)")
    claim: str = Field(default="", description="Afirmación EXACTA que hace el hablante, parafraseada sin añadir datos propios")
    search_query: str = Field(default="", description="Consulta de búsqueda web para confirmar la afirmación o buscar el artículo (en español)")
    image_query: Optional[str] = Field(default=None, description="Nombre de la entidad principal para buscar una foto real en Wikipedia o logo")
    verdict: str = Field(default="pending", description="Lo completa el verificador: supported, contradicted o insufficient")
    body: str = Field(default="", description="Lo completa el verificador: resumen basado SOLO en evidencia")
    sources: List[SourceRef] = Field(default_factory=list, description="Lo completa el verificador")
    image_path: Optional[str] = Field(default=None, description="Lo completa el verificador")
    card_path: Optional[str] = Field(default=None, description="Lo completa el renderizador de tarjetas")
    note: str = Field(default="", description="Motivo del veredicto, para mostrar al usuario")
    stat_value: str = Field(default="", description="Lo completa el verificador: cifra protagonista confirmada")
    # --- Correction Engine fields ---
    correction: str = Field(default="", description="Lo completa el verificador: texto de corrección cuando el dato es contradicted")
    corrected_value: str = Field(default="", description="Lo completa el verificador: dato real preciso (cifra, fecha, nombre correcto)")
    correction_source: str = Field(default="", description="Lo completa el verificador: dominio de la fuente autoritativa de la corrección")
    is_myth: bool = Field(default=False, description="Si la afirmación es un mito popular, pon true para habilitar tarjeta gamificada.")
    enabled: bool = Field(default=True, description="Permite al editor ocultar la tarjeta sin borrar su investigación")
    screen_position: str = Field(default="auto", description="auto, upper_left, upper_right, lower_left o lower_right")
    display_duration_sec: float = Field(default=7.0, ge=4.5, le=12.0, description="Tiempo visible para que la tarjeta pueda leerse")
    # --- Avatar Copilot fields ---
    avatar_spoken_text: Optional[str] = Field(default=None, description="Frase hablada que el avatar pronuncia")
    avatar_audio_path: Optional[str] = Field(default=None, description="Ruta al archivo de audio MP3 de voz generado")
    avatar_video_path: Optional[str] = Field(default=None, description="Ruta al clip de video WebM con canal alfa del avatar")
    avatar_enabled: bool = Field(default=True, description="Habilita que el avatar intervenga hablando en esta tarjeta")

class CaptionItem(BaseModel):
    """Segmento de subtítulo con temporización para subtitulado dinámico."""
    start_sec: float = Field(ge=0.0, description="Segundo de inicio de la frase")
    end_sec: float = Field(gt=0.0, description="Segundo de fin de la frase")
    text: str = Field(description="Texto exacto hablado")
    highlight_words: List[str] = Field(default_factory=list, description="Palabras clave para resaltar con color de impacto")
    speaker_id: int = Field(default=1, description="ID simulado del locutor (1 o 2)")
    censor_words: List[str] = Field(default_factory=list, description="Palabras exactas a censurar con bleep")

class TimelineSegment(BaseModel):
    """Segmento de la línea de tiempo principal indicando qué retener y qué podar."""
    start_sec: float = Field(ge=0.0, description="Segundo inicial en el video original")
    end_sec: float = Field(gt=0.0, description="Segundo final en el video original")
    action: ActionType = Field(description="KEEP para mantener en el corte final, CUT_SILENCE para descartar")
    reasoning: Optional[str] = Field(default=None, description="Justificación técnica (ej. 'Pausa muerta de 2.1s', 'Habla activa')")

class HighlightClip(BaseModel):
    """Clip de alto impacto detectado para generar Shorts / Reels verticales."""
    clip_id: str = Field(description="Identificador del clip corto (ej. short_1)")
    start_sec: float = Field(ge=0.0, description="Segundo inicial del short")
    end_sec: float = Field(gt=0.0, description="Segundo final del short")
    title: str = Field(description="Título viral sugerido")
    hook: str = Field(description="Frase gancho en los primeros 3 segundos")
    virality_score: int = Field(ge=1, le=100, description="Puntuación estimada de retención/impacto (1-100)")


class VisualScene(BaseModel):
    """Escena explicativa procedimental, sincronizada con una frase concreta."""
    scene_id: str = Field(description="ID único, por ejemplo visual_1")
    start_sec: float = Field(ge=0.0, description="Inicio sobre el video original")
    end_sec: float = Field(gt=0.0, description="Fin sobre el video original; entre 1 y 15 segundos de duración")
    kind: str = Field(default="concept", description="automation, comparison, cause_effect o concept")
    title: str = Field(default="", max_length=100, description="Titular breve y claro, no una frase larga")
    label_a: str = Field(default="PERSONA", max_length=48, description="Etiqueta del elemento de origen")
    label_b: str = Field(default="SISTEMA", max_length=48, description="Etiqueta del resultado o segundo elemento")
    spoken_phrase: str = Field(default="", description="Fragmento exacto de la narración que justifica la escena")
    reasoning: str = Field(default="", description="Qué explica la representación y por qué ayuda a entender")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    enabled: bool = Field(default=True, description="Permite desactivar esta escena sin borrarla")

class VideoEditingPlan(BaseModel):
    """Plan maestro estructurado de edición generado por Gemini 1.5 Pro."""
    video_summary: str = Field(description="Resumen temático general del video analizado")
    topic_en: str = Field(default="", description="Tema principal del video en inglés, 2 a 4 palabras (ej. 'Argentine economy'); se usa como contexto de toda búsqueda")
    total_original_duration_sec: float = Field(ge=0.0, description="Duración total detectada del video original")
    timeline: List[TimelineSegment] = Field(description="Segmentos cronológicos secuenciales de poda/corte")
    b_rolls: List[BRollCue] = Field(default_factory=list, description="Superposiciones de B-Roll sincronizadas")
    captions: List[CaptionItem] = Field(default_factory=list, description="Transcripción sincronizada para subtítulos dinámicos")
    highlights: List[HighlightClip] = Field(default_factory=list, description="Segmentos ideales para formato Short vertical")
    info_cards: List[InfoCard] = Field(default_factory=list, description="Datos concretos mencionados que merecen una tarjeta informativa verificada")
    visual_scenes: List[VisualScene] = Field(default_factory=list, description="Escenas animadas explicativas, solo cuando aclaren visualmente la narración")
