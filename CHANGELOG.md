# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Añadido
- **Filtro de relevancia visual del B-Roll** (`core/relevance_gate.py`): un modelo con visión puntúa
  cada recurso descargado (0-10) contra la frase del hablante y el tema del video. Los candidatos por
  debajo de `RELEVANCE_THRESHOLD` (6 por defecto) se descartan y se prueba el siguiente proveedor; si
  ninguno pasa, el apoyo se omite. Si no hay modelo de visión disponible, el recurso se acepta (fail-open).
- **Registro estructurado de ejecuciones** (`core/run_log.py`): cada ejecución escribe
  `run_events.jsonl`, `run_report.json` y `run_report.md` con tiempos por etapa, llamadas/tokens/latencia
  por modelo, uso de servicios, costo estimado, contadores, avisos y salidas. Ver `docs/OBSERVABILIDAD.md`.
- `config/pricing.json`: tarifas editables para estimar costos (sin tarifa = "sin tarifa", nunca se inventa).
- Decorador `@logged_run(...)` para instrumentar cualquier otro flujo de contenido.
- `broll_decisions.json` por proyecto: qué se aceptó o rechazó y por qué.
- Campos `spoken_phrase`, `confidence`, `relevance_score` y `relevance_note` en `BRollCue`; `topic_en` en el plan.
- `scripts/check_secrets.py`: escáner de claves en los archivos versionados (sale con código 1 si encuentra alguna).
- `scripts/doctor.py`: diagnóstico previo (Python, FFmpeg, dependencias, claves configuradas, almacenamiento, tarifas).
- CI en GitHub Actions (`.github/workflows/ci.yml`): escaneo de secretos y pruebas en Python 3.10 y 3.12.
- **Auditoría editorial del montaje** (`core/editorial_qa.py`): antes de renderizar resuelve choques entre B-Roll,
  evita que un video a pantalla completa tape una tarjeta verificada, limita la densidad (10 por minuto) y avisa de
  gancho sin apoyo en los primeros 3 s o tramos de más de 15 s sin cambio visual. Antes el render descartaba en
  silencio; ahora cada retiro queda registrado con su motivo y hay un puntaje de 0 a 100.
- **Shorts en límites de frase** (`core/short_snapper.py`): inicio y final se alinean con las frases de Whisper, se
  respeta 15-70 s y se eliminan Shorts duplicados (gana el de mayor puntaje de viralidad).
- **Confianza de fuentes** (`core/source_trust.py`): un dato (cifra, fecha, ley) o una corrección solo se muestra con
  una fuente oficial/científica o dos fuentes independientes; las redes sociales y foros no cuentan. Las entidades
  aceptan una fuente de referencia. Se desactiva con `SOURCE_TRUST_STRICT=0`.
- Pruebas: `tests/test_relevance.py`, `tests/test_run_log.py` y `tests/test_tooling.py`, `tests/test_broll_sync.py` y `tests/test_editorial.py`.

- **Sincronización del B-Roll con la voz** (`core/broll_sync.py`): cada apoyo se alinea con la frase de Whisper que lo respalda (los tiempos de Gemini solían errar 1-2 s). Los ajustes quedan en el log de la ejecución.

### Cambiado
- El prompt del editor ya no obliga a insertar B-Roll con una frecuencia fija ni a extraer "todos" los datos:
  se permite devolver pocos apoyos (o ninguno) y se prioriza la relevancia.
- Las llamadas JSON a Gemini usan `temperature=0.2` para planes reproducibles.
- Las consultas cortas de B-Roll se desambiguan añadiendo el tema del video.
- `.gitignore` ya no oculta `tests/test_*.py` ni `scripts/check_secrets.py`.

### Corregido
- Se eliminó una clave de DeepSeek que estaba escrita como valor por defecto en `core/deepseek_motion_director.py`.
  **Esa clave estuvo en un repositorio público: debe rotarse.**
- `WebPhotoAssetProvider` clasificaba consultas por subcadena (p. ej. "coffee" activaba el modo bíblico por
  contener "fe", y "media" el modo benchmark por contener "ia"). Ahora se compara por palabra completa.
- `OriginalSourceAssetProvider` y `LocalOriginalAssetProvider` aceptaban un candidato con una sola palabra
  coincidente; con consultas de 3 o más palabras ahora exigen al menos 2.
