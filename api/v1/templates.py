"""Endpoints para el catálogo de plantillas visuales y generación de vistas previas."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from config.settings import settings
from api.schemas import ApiResponse
from api.security import verify_api_key
from core.visual_templates import VisualTemplatesLibrary

router = APIRouter(prefix="/templates", tags=["Visual Templates & Overlays"])


@router.get("", response_model=ApiResponse[Dict[str, Any]])
async def list_visual_templates(_auth: bool = Depends(verify_api_key)):
    """Devuelve el catálogo completo de plantillas visuales con parámetros y variantes."""
    catalog = VisualTemplatesLibrary.get_catalog()
    return ApiResponse(
        success=True,
        message="Catálogo de plantillas visuales obtenido",
        data=catalog,
    )


@router.get("/preview")
async def preview_template(
    request: Request,
    template: str = Query("editorial_full_canvas", description="ID de la plantilla visual"),
    variant: str = Query("editorial_cream", description="Variante cromática del tema"),
    headline: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    subtitle: Optional[str] = Query(None),
    body: Optional[str] = Query(None),
    stat_value: Optional[str] = Query(None),
    stat_label: Optional[str] = Query(None),
    main_text: Optional[str] = Query(None, description="Texto principal ultra-bold"),
    accent_text: Optional[str] = Query(None, description="Palabra o producto en serif cursiva"),
    step_number: Optional[str] = Query(None, description="Número de paso actual (ej: 03)"),
    total_steps: Optional[str] = Query(None, description="Total de pasos (ej: 10)"),
    step_prefix: Optional[str] = Query(None, description="Prefijo de gamificación: PASO, TRUCO, TIP, FASE"),
    code_comment: Optional[str] = Query(None, description="Comentario técnico superior (ej: cómo abrirlo)"),
    handle: Optional[str] = Query(None, description="Handle del creador (ej: @antonspain_ia)"),
    window_title: Optional[str] = Query(None, description="Título de la ventana macOS (ej: ChatGPT)"),
    highlight_button: Optional[str] = Query(None, description="Botón destacado dentro de la interfaz"),
    placeholder_text: Optional[str] = Query(None, description="Texto dentro del input de la interfaz"),
    grid_style: Optional[str] = Query(None, description="Estilo de fondo: grid_paper, dots, blueprint, clean"),
    canvas_type: Optional[str] = Query(None, description="Tipo de contenido central en full canvas: chat, code, versus, workflow, checklist, stat, file_tree"),
    filename: Optional[str] = Query(None, description="Nombre de archivo en pestañas de código"),
    command: Optional[str] = Query(None, description="Comando en consola/terminal"),
    bad_label: Optional[str] = Query(None),
    bad_text: Optional[str] = Query(None),
    bad_stat: Optional[str] = Query(None),
    good_label: Optional[str] = Query(None),
    good_text: Optional[str] = Query(None),
    good_stat: Optional[str] = Query(None),
    node1_title: Optional[str] = Query(None),
    node2_title: Optional[str] = Query(None),
    node3_title: Optional[str] = Query(None),
    item1_title: Optional[str] = Query(None),
    item2_title: Optional[str] = Query(None),
    item3_title: Optional[str] = Query(None),
    stat_number: Optional[str] = Query(None),
    trend_pct: Optional[str] = Query(None),
    comparison_text: Optional[str] = Query(None),
    target_filename: Optional[str] = Query(None),
    highlight_label: Optional[str] = Query(None),
):
    """Genera y sirve una imagen PNG de muestra renderizada con la plantilla seleccionada."""
    vlib = VisualTemplatesLibrary()
    preview_dir = settings.OUTPUTS_DIR / "template_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    out_file = preview_dir / f"api_preview_{template}_{variant}.png"

    params: Dict[str, Any] = {}
    catalog = vlib.get_catalog()
    for item in catalog["templates"]:
        if item["id"] == template:
            params.update(item.get("sample_params", {}))
            break

    if headline: params["headline"] = headline
    if title: params["title"] = title
    if subtitle: params["subtitle"] = subtitle
    if body: params["body"] = body
    if stat_value: params["stat_value"] = stat_value
    if stat_label: params["stat_label"] = stat_label
    if main_text: params["main_text"] = main_text
    if accent_text: params["accent_text"] = accent_text
    if step_number: params["step_number"] = step_number
    if total_steps: params["total_steps"] = total_steps
    if step_prefix: params["step_prefix"] = step_prefix
    if code_comment: params["code_comment"] = code_comment
    if handle: params["handle"] = handle
    if window_title: params["window_title"] = window_title
    if highlight_button: params["highlight_button"] = highlight_button
    if placeholder_text: params["placeholder_text"] = placeholder_text
    if grid_style: params["grid_style"] = grid_style
    if canvas_type: params["canvas_type"] = canvas_type
    if filename: params["filename"] = filename
    if command: params["command"] = command
    if bad_label: params["bad_label"] = bad_label
    if bad_text: params["bad_text"] = bad_text
    if bad_stat: params["bad_stat"] = bad_stat
    if good_label: params["good_label"] = good_label
    if good_text: params["good_text"] = good_text
    if good_stat: params["good_stat"] = good_stat
    if node1_title: params["node1_title"] = node1_title
    if node2_title: params["node2_title"] = node2_title
    if node3_title: params["node3_title"] = node3_title
    if item1_title: params["item1_title"] = item1_title
    if item2_title: params["item2_title"] = item2_title
    if item3_title: params["item3_title"] = item3_title
    if stat_number: params["stat_number"] = stat_number
    if trend_pct: params["trend_pct"] = trend_pct
    if comparison_text: params["comparison_text"] = comparison_text
    if target_filename: params["target_filename"] = target_filename
    if highlight_label: params["highlight_label"] = highlight_label

    for k, v in request.query_params.items():
        if k not in ("template", "variant") and v is not None and v != "":
            params[k] = v

    rendered = vlib.render_template_to_image(template, out_file, params, variant=variant)
    if not rendered or not rendered.exists():
        raise HTTPException(status_code=500, detail=f"No se pudo generar la vista previa de '{template}'.")

    return FileResponse(rendered, media_type="image/png")
