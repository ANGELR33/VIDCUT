# Observabilidad: logs, costos y reportes por ejecución

Cada ejecución crea tres archivos dentro de la carpeta del proyecto (`storage/projects/<id>/`):

| Archivo | Contenido |
|---|---|
| `run_events.jsonl` | Un evento por línea: tiempo, etapa, nivel, mensaje y datos. Útil para `grep`/`jq`. |
| `run_report.json` | Resumen legible por máquina (para la interfaz o para dashboards). |
| `run_report.md` | Resumen legible por personas: etapas, modelos, costo, avisos, salidas. |
| `assets/broll_decisions.json` | Por cada B-Roll: proveedor, puntaje de relevancia, aceptado/rechazado y motivo. |

## Qué mide el reporte

- **Etapas:** duración de cada paso (transcripción, Gemini, silencios, enriquecimiento, render...).
- **Modelos de IA:** llamadas, fallos, llamadas de respaldo (fallback), tokens de entrada/salida y latencia media
  por proveedor y modelo, con el propósito de cada llamada (`plan_edicion`, `verificacion_dato`, `relevancia_visual`).
- **Otros servicios:** búsquedas web, TTS, Whisper local, etc. (`record_service`).
- **Contadores:** B-Roll aceptados/rechazados/fallidos, veredictos de tarjetas (`tarjeta_supported`, ...).
- **Costo estimado:** tokens × tarifa de `config/pricing.json`. Es una estimación, no una factura.
- **Avisos y errores:** los últimos 25, ya sin claves ni tokens (`redact`).

## Configurar costos

Edita `config/pricing.json` con las tarifas oficiales de cada proveedor (USD por millón de tokens, por prefijo
de modelo). Mientras un modelo tenga `null`, el reporte lo marca como **"sin tarifa"** y el total aparece como
parcial. Pon `0` si usas un cupo gratuito.

## Instrumentar otro tipo de contenido

Cualquier flujo (anime, podcast, geopolítica, streamer...) puede tener su reporte con una línea:

```python
from core.run_log import logged_run, log_count, log_service

@logged_run(content_type="podcast_clips", mechanism="SpanishPodcastClipper")
async def run(self, workdir, ...):
    ...
    log_count("clips_generados", 5)
    log_service("speechify", units=1200, unit_name="caracteres")
```

Las llamadas a `LLMClient.generate(..., purpose="mi_proposito")` se registran solas. Si un hilo se lanza con
`loop.run_in_executor`, usa `contextvars.copy_context().run` (como hace `VideoPipeline`) para que herede la
ejecución activa; `asyncio.to_thread` ya lo hace.

## Seguridad

Nada de lo que pasa por el log conserva claves: `redact` oculta formatos de NVIDIA, Gemini, DeepSeek, Google OAuth,
Speechify, `Bearer ...` y pares `api_key=...`. Aun así, **no pegues claves en prompts, issues ni chats**; si ya lo
hiciste, rótalas.

## Calidad editorial en el reporte

Además de tiempos y costos, `run_events.jsonl` registra en la etapa `quality`:

- `Auditoría editorial N/100`: métricas (`broll_per_minute`, `longest_static_gap_sec`), B-Roll retirados y avisos.
- Ajustes de Shorts: qué clip se movió a límites de frase y cuáles se descartaron por duplicados.
- Contadores: `qa_broll_retirados`, `shorts_ajustados`, `shorts_duplicados`, `tarjeta_fuentes_debiles`,
  `broll_resincronizados`.

Un puntaje bajo repetido indica que el plan de Gemini propone demasiados apoyos o deja tramos largos sin cambio visual.
