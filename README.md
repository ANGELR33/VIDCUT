---
title: VIDCUT
emoji: 🎬
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# VIDCUT

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ANGELR33/VIDCUT/blob/main/AetherCut_AI_Colab.ipynb)

> 🚀 **Ejecutar 100% Gratis en la Nube con GPU**: Haz clic en el botón **Open in Colab** arriba para abrir el estudio en Google Cloud con GPU Nvidia T4 gratuita, sin consumir la memoria RAM de tu computadora ni gastar batería.

VIDCUT (antes AetherCut AI) es un estudio completo para preparar videos hablados y streams con Inteligencia Artificial. Analiza el video con Gemini, detecta pausas largas en el audio y genera una versión editada con cortes, material de apoyo, tarjetas informativas verificadas, subtítulos dinámicos de 2-4 palabras y Shorts verticales.

## Funciones

- Recibe videos MP4, MOV, MKV, WEBM, AVI y M4V de hasta 2 GB.
- Usa Gemini para analizar el contenido y proponer una línea de tiempo, momentos destacados y apoyos visuales. Cada edición usa un proyecto a la vez; solo cambia al siguiente si recibe una cuota, un permiso denegado, un error temporal o vence el límite de espera. Dentro del mismo proyecto prueba los modelos estables disponibles antes de cambiar de clave.
- Detecta silencios con FFmpeg y elimina las pausas que superan el umbral configurado.
- Puede buscar B-Roll y datos de contexto en la web. Las tarjetas pueden confirmar, refutar, aclarar o advertir que no hay evidencia suficiente, con las fuentes consultadas.
- **Investigación con fact sheet**: descarga las fuentes completas (no solo snippets), extrae cifras y fechas, corrobora entre medios independientes y entrega al director un gancho recomendado. El guion solo puede usar esas cifras y las cards muestran su fuente real.
- **Sincronización por palabra**: un alineador local (faster-whisper) marca el inicio y fin de cada palabra del audio y agenda cards, keywords, cortes y subtítulos en el instante exacto en que se pronuncian.
- **Sistema editorial de tarjetas**: layouts sobrios (dato, cita, comparativa, cronología, paso, fuente) con jerarquía tipográfica fija, sin emojis ni estilos de "dashboard IA".
- **Escenas explicativas animadas (15 estilos)**: además de diagramas de flujo, comparación, causa-efecto y cronología, puede crear aperturas editoriales, ventanas de código ilustrativas, diagramas de arquitectura/ciberseguridad y equipos pixel-art de agentes. Gemini elige el estilo por contexto y la escena se coloca en la ventana temporal de la frase objetivo; no sustituye material real verificable. La alineación fonética exacta por palabra aún requiere validación adicional.
- **Motor narrativo avanzado con Remotion**: para las escenas explicativas, VIDCUT puede preferir composiciones transparentes React/Remotion con entradas suaves, código animado, diagramas que se construyen progresivamente y equipos pixel-art. Si Node/Remotion no está disponible, conserva el motor Pillow/FFmpeg. La skill de OpenCode `.opencode/skills/narrative-motion/SKILL.md` define criterios de dirección visual y control de calidad.
- **Count-up animado**: las cifras protagonistas suben de 0 al valor real dentro de la propia tarjeta (video con alfa), solo cuando el número es inequívoco.
- **Miniaturas y ganchos**: la miniatura 16:9 se construye con un fotograma real, el gancho del fact sheet, su fuente y la cifra protagonista; se generan 3 variantes de gancho para título/descripción.
- Puede transcribir localmente con Whisper, quemar subtítulos y crear todos los Shorts verticales que el contenido justifique.
- Construye una previsualización ligera y una línea de tiempo visible durante el trabajo: cortes, tarjetas, B-Rolls y Shorts aparecen cuando se detectan.
- Analiza localmente cambios de plano con PySceneDetect y ubica las tarjetas automáticas fuera del hablante con OpenCV. No envía esos fotogramas a otro servicio.
- Conserva cada proyecto con su plan, fuentes, recursos y exportaciones. Después puedes reabrirlo, mover o desactivar tarjetas y B-Rolls, guardar los cambios y exportar una nueva versión sin repetir Gemini.

La interfaz presenta las etapas de edición y solo registra acciones confirmadas. Si Gemini tarda, indica que aún espera el plan y deja claro que los cortes, la investigación y el render todavía no han empezado.

Durante una tarea activa puedes solicitar su cancelación desde la interfaz. La app detiene las búsquedas y procesos locales que admiten interrupción y no inicia nuevas etapas. Si hay una solicitud síncrona en curso con Gemini, espera a que responda o venza su tiempo límite antes de confirmar la cancelación.

## Requisitos

- Windows 10/11 y Python 3.10 o posterior.
- FFmpeg y `ffprobe` instalados y disponibles en `PATH`. AetherCut usa ambos para analizar y renderizar video. Descarga los ejecutables desde [la página oficial de FFmpeg](https://ffmpeg.org/download.html) y comprueba la instalación en PowerShell:

  ```powershell
  ffmpeg -version
  ffprobe -version
  ```

- Una clave de Gemini API. El análisis del video requiere conexión a internet y envía el video a Gemini.
- Opcional: claves de Pixabay o Pexels para buscar material de apoyo en esos servicios.

## Instalación en Windows

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` y configura `GEMINI_API_KEY` con una clave de Gemini, o con varias separadas por comas. Cada clave debe corresponder a un proyecto Gemini que tenga habilitado el modelo configurado. Puedes dejar vacías las claves de Pixabay y Pexels; la búsqueda de recursos web también puede usarse sin ellas. El modelo predeterminado es `gemini-3.6-flash`, comprobado como disponible en los proyectos configurados; puedes cambiarlo con `GEMINI_MODEL`.

Las cuotas de Gemini se aplican por proyecto, no se multiplican creando varias claves para el mismo proyecto. Cuando un proyecto no puede completar una solicitud (por ejemplo, por cuota o permiso), AetherCut vuelve a subir el video al siguiente proyecto y lo analiza con la clave de ese proyecto. Cada archivo se procesa siempre con la clave que lo subió. El cambio de proyecto puede añadir tiempo de carga, pero permite seguir con otro proyecto mientras se recupera la cuota del anterior; no hace que las cuotas sean ilimitadas.

Si PowerShell bloquea la activación del entorno, ejecuta `Set-ExecutionPolicy -Scope Process Bypass` en esa misma ventana y vuelve a activar `.venv`.

## Iniciar la aplicación

Con el entorno virtual activado:

```powershell
python server.py
```

Abre [http://127.0.0.1:8000](http://127.0.0.1:8000), selecciona un video y pulsa **Iniciar edición**. Deja abierta la terminal mientras se procesa el video. Para detener el servidor, pulsa `Ctrl+C`.

Los videos originales subidos se guardan en `storage/inputs/`, los resultados en `storage/outputs/` y los proyectos editables en `storage/projects/`. No borres esa carpeta si quieres conservar la línea de tiempo, las tarjetas y las fuentes para revisarlas después.

## Primera prueba recomendada

Para confirmar el flujo completo, usa primero un video corto de prueba (por ejemplo, 30–60 segundos), con voz clara y pista de audio, en MP4 o MOV. AetherCut crea una copia de análisis ligera para los videos grandes; el render final siempre usa el archivo original.

Los subtítulos usan `faster-whisper` localmente y pueden tardar más la primera vez mientras se descarga el modelo. Gemini, la búsqueda web y los proveedores de recursos aplican límites de uso y requieren conexión a internet. Un análisis de video largo puede tardar varios minutos, pero una etapa sin señales no demuestra que el trabajo siga avanzando.

## Operación y calidad

- `python scripts/doctor.py`: diagnóstico previo del entorno (FFmpeg, dependencias, claves configuradas, almacenamiento).
- `python scripts/check_secrets.py`: busca claves escritas en el código. Se ejecuta también en CI.
- Cada ejecución deja `run_report.md`, `run_report.json` y `run_events.jsonl` en la carpeta del proyecto
  (etapas, tokens, latencia, costo estimado, avisos). Ver [docs/OBSERVABILIDAD.md](docs/OBSERVABILIDAD.md).
- Cambios y correcciones: [CHANGELOG.md](CHANGELOG.md).

## Pruebas locales

Antes de subir un video puedes ejecutar una comprobación sin navegador, sin Gemini y sin servicios externos:

```powershell
python -m unittest tests.test_local_pipeline -v
```

La prueba crea un clip temporal, revisa el análisis de audio y de escena, genera una tarjeta y compone un MP4 final con FFmpeg. Los archivos temporales se eliminan al terminar. La comprobación de las claves de Gemini se hace por separado porque el proveedor puede estar temporalmente saturado aunque una clave sea válida.

## Archivos principales

- `server.py`: servidor web, carga de videos y seguimiento de progreso.
- `core/pipeline.py`: flujo completo de análisis y edición.
- `core/gemini_analyzer.py` y `core/llm.py`: análisis con Gemini.
- `core/silence_detector.py` y `core/timeline.py`: detección de silencios y sincronización de tiempos.
- `core/asset_providers.py` y `core/fact_checker.py`: recursos visuales y verificación de datos.
- `core/research_agent.py`: investigación con fuentes completas, fact sheet, corroboración y auditoría de cifras.
- `core/word_aligner.py`: alineación por palabra del audio (timing exacto de overlays y subtítulos).
- `core/editorial_cards.py`: sistema de tarjetas editoriales usado por el render.
- `core/animated_stat_card.py`: count-up animado de cifras con alfa para el render.
- `core/fact_thumbnail.py`: miniaturas editoriales 16:9/9:16 desde el fact sheet.
- `core/render_engine.py`: cortes, subtítulos, overlays y exportación de Shorts con FFmpeg.
- `web/`: interfaz, estilos y JavaScript del navegador.
- `frontend/`: interfaz React + Vite (fuente en `frontend/src`, compilada en `frontend/dist`).
- `api/`: API RESTful v1 pública, SSE y Webhooks para aplicaciones externas.
- `API_DOCUMENTATION.md`: especificación técnica completa y ejemplos de integración.
- `tests/`: pruebas automatizadas (`python -m pytest tests -q`).

## API RESTful v1 y Webhooks

AetherCut AI incluye una API RESTful completa bajo el prefijo `/api/v1` para conectar cualquier aplicación externa (móviles, bots de Discord/Telegram, microservicios, o automatizaciones en n8n, Make y Zapier):

- **Portal para Desarrolladores**: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
- **Documentación Interactiva Swagger**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Especificación Técnica Completa**: consulta [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

Permite ingesta por archivo o URL remota, generación autónoma de videos, consulta en tiempo real vía SSE, extracción de Shorts 9:16, síntesis de voz TTS, radar viral y descargas directas con notificaciones webhook automáticas.

## Solución de problemas

- **La clave de Gemini no es válida o falta:** revisa `GEMINI_API_KEY` en `.env`.
- **No se encuentra FFmpeg o falla el render:** comprueba `ffmpeg -version` y `ffprobe -version`; ambos comandos deben funcionar en la terminal desde la que iniciaste el servidor.
- **La búsqueda web o los recursos no aparecen:** verifica la conexión a internet. Las claves de Pixabay y Pexels son opcionales.
- **El proceso tarda o falla por límites:** AetherCut prueba los cinco proyectos uno por uno y detiene el análisis si ninguno responde. El mensaje final especifica si fue cuota, permiso o saturación. Puedes volver a intentarlo cuando el proveedor se recupere.
- **El video supera el límite:** la carga está limitada a 2 GB.
