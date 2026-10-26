# 🚀 AetherCut AI — Documentación de la API Pública v1

Esta API RESTful, en tiempo real (SSE) y con soporte para Webhooks permite que **cualquier aplicación externa** (aplicaciones móviles, plataformas web, bots de Discord/Telegram, flujos de automatización en n8n/Zapier/Make, o scripts CLI) se comunique con AetherCut AI y ejecute **todas las operaciones del estudio** de forma programática.

---

## 📌 1. Información General

- **URL Base Local**: `http://127.0.0.1:8000/api/v1`
- **URL Base Pública (con Túnel Cloudflare)**: `https://<tu-subdominio>.trycloudflare.com/api/v1`
- **Portal Interactivo para Desarrolladores**: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- **Formato**: JSON en `UTF-8`
- **CORS**: Habilitado (`*`) para integración directa desde navegadores y frontends externos.

### 🌍 1.1. ¿Cómo conectar agentes y apps desde Internet?

Si tu agente de IA, bot de Discord, o flujo de n8n/Zapier está en la nube o en un servidor externo, `127.0.0.1` no es accesible directamente porque es tu IP local (localhost). 

Para darle acceso mundial a tu API tienes 3 opciones inmediatas:

1. **Túnel Público Gratuito Cloudflare (¡Ya incluido en el proyecto!)**:
   - Ejecuta en Windows: `INICIAR_CON_TUNEL_PUBLICO.bat` (o `python run_studio.py --tunnel`).
   - El sistema generará automáticamente una URL segura HTTPS mundial (ejemplo: `https://abc-xyz.trycloudflare.com`).
   - Tu agente externo podrá invocar la API desde cualquier parte del mundo usando:
     `https://abc-xyz.trycloudflare.com/api/v1/...`
   - *No requiere abrir puertos en tu router ni configurar IP estática.*

2. **Ngrok o LocalTunnel**:
   - Puedes ejecutar `ngrok http 8000` para obtener una URL pública si cuentas con un dominio ngrok reservado.

3. **Despliegue 24/7 en Servidor / VPS / Colab**:
   - Puedes levantar el contenedor en un VPS con el `Dockerfile` incluido o ejecutarlo en la nube con GPU gratuita mediante `AetherCut_AI_Colab.ipynb`.

> [!IMPORTANT]
> **Seguridad al exponer a Internet:**
> Al usar un túnel público o servidor en la nube, asegúrate de configurar `AETHERCUT_API_KEY=tu_clave_secreta` en tu `.env`. Así, solo tus agentes externos con el encabezado `X-API-Key` o `Authorization: Bearer` podrán interactuar con tu API.

---

## 🔐 2. Autenticación y Seguridad

La API soporta autenticación opcional por API Key mediante la variable `AETHERCUT_API_KEY` en tu `.env`.

- **Modo Abierto (por defecto)**: Si `AETHERCUT_API_KEY` está vacía o no configurada, la API acepta solicitudes sin credenciales (ideal para uso local o red doméstica).
- **Modo Seguro**: Si configuras una clave (ej: `AETHERCUT_API_KEY=mi_clave_secreta_123`), cualquier app externa debe enviar uno de los siguientes encabezados:

```http
X-API-Key: mi_clave_secreta_123
```
o
```http
Authorization: Bearer mi_clave_secreta_123
```

---

## 📦 3. Estructura Estándar de Respuesta

Todas las respuestas exitosas de la API v1 siguen el patrón uniforme:

```json
{
  "success": true,
  "message": "Operación completada con éxito",
  "data": { ... }
}
```

En caso de error (códigos HTTP 4xx / 5xx):

```json
{
  "success": false,
  "error": {
    "code": "BAD_REQUEST",
    "message": "Descripción detallada del error"
  }
}
```

---

## 🛠️ 4. Catálogo de Servicios y Endpoints

### 4.1. Salud y Diagnóstico del Sistema

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/system/health` | Estado de FFmpeg, GPU, almacenamiento libre y tareas activas |
| `GET` | `/api/v1/system/status` | Tareas en curso y estado de la cola de renderizado |
| `GET` | `/api/v1/system/models` | Modelos de IA disponibles (Gemini, NVIDIA NIM, GLM, Kimi) |

#### Ejemplo cURL:
```bash
curl http://127.0.0.1:8000/api/v1/system/health
```

---

### 4.2. Ingesta y Procesamiento de Video

Permite procesar un video mediante **archivo binario (multipart)** o mediante **URL remota (enlace directo o YouTube)**.

#### Opción A: Procesar desde URL remota
`POST /api/v1/videos/process-url`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/process-url \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "title": "Mi Video Remoto",
    "silence_threshold": 1.5,
    "enable_broll": true,
    "enable_captions": true,
    "enable_shorts": true,
    "enable_cards": true,
    "voice": "es-MX-JorgeNeural",
    "webhook_url": "https://webhook.site/mi-identificador"
  }'
```

#### Opción B: Subida de archivo local (Multipart)
`POST /api/v1/videos/process`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/process \
  -F "video=@mi_video.mp4" \
  -F "silence_threshold=1.5" \
  -F "enable_broll=true" \
  -F "enable_captions=true" \
  -F "enable_shorts=true" \
  -F "webhook_url=https://webhook.site/mi-identificador"
```

Respuesta (HTTP 202 Accepted):
```json
{
  "success": true,
  "message": "Video cargado correctamente. Tarea de edición iniciada en background.",
  "data": {
    "task_id": "a1b2c3d4",
    "project_id": "a1b2c3d4",
    "status": "queued",
    "message": "Edición iniciada."
  }
}
```

---

### 4.3. Producción Autónoma KAI Streamer

Genera un video completo con IA desde cero a partir de un tema o premisa de texto.

`POST /api/v1/streamer/create`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/streamer/create \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "El futuro de la fusión nuclear y la energía infinita",
    "style": "divulgacion",
    "duration_sec": 60,
    "aspect_ratio": "16:9",
    "card_theme": "dark",
    "voice": "es-MX-JorgeNeural",
    "visual_mode": "mixed",
    "webhook_url": "https://webhook.site/mi-identificador"
  }'
```

---

### 4.4. Seguimiento de Tareas y Streaming SSE

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/tasks` | Lista todas las tareas activas y recientes |
| `GET` | `/api/v1/tasks/{task_id}` | Consulta progreso (0-100), etapa actual y resultado |
| `GET` | `/api/v1/tasks/{task_id}/events` | **Stream SSE en tiempo real** de avance y logs |
| `POST` | `/api/v1/tasks/{task_id}/cancel` | Cancela de inmediato una tarea en ejecución |

#### Ejemplo de consumo SSE en JavaScript:
```javascript
const evtSource = new EventSource("http://127.0.0.1:8000/api/v1/tasks/a1b2c3d4/events");
evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progreso: ${data.progress}% - Etapa: ${data.step} - Mensaje: ${data.message}`);
  if (data.completed) {
    console.log("¡Video completado!", data.result);
    evtSource.close();
  }
};
```

---

### 4.5. Proyectos y Descargas Directas

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/projects` | Lista proyectos con paginación (`limit`, `offset`) y filtros |
| `GET` | `/api/v1/projects/{id}` | Manifiesto completo, cortes, timeline y fuentes |
| `DELETE` | `/api/v1/projects/{id}` | Elimina proyecto y libera espacio en disco |
| `GET` | `/api/v1/projects/{id}/timeline` | Obtiene cortes de silencio, tarjetas y B-Roll |
| `PUT` | `/api/v1/projects/{id}/timeline` | Actualiza decisiones editoriales |
| `POST` | `/api/v1/projects/{id}/export` | Re-renderiza nueva versión con cambios |
| `GET` | `/api/v1/projects/{id}/materials/download` | Descarga archivo ZIP con todos los assets |
| `GET` | `/api/v1/projects/{id}/download/{asset_type}` | Descarga directa de archivos |

#### Descargas Directas:
- **Video Master editado**: `GET /api/v1/projects/{id}/download/master`
- **Short 9:16 vertical**: `GET /api/v1/projects/{id}/download/short`
- **Subtítulos SRT**: `GET /api/v1/projects/{id}/download/subtitles`
- **Transcripción JSON**: `GET /api/v1/projects/{id}/download/transcript`
- **Miniatura JPG**: `GET /api/v1/projects/{id}/download/thumbnail`

---

### 4.6. Shorts y Clips Virales (9:16)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/clips/{project_id}` | Lista todos los Shorts verticales generados |
| `POST` | `/api/v1/clips/{project_id}/extract` | Extrae un clip vertical personalizado con inicio/duración |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/clips/a1b2c3d4/extract \
  -H "Content-Type: application/json" \
  -d '{
    "start_sec": 12.5,
    "end_sec": 42.0,
    "title": "Momento Mas Impactante",
    "aspect_ratio": "9:16"
  }'
```

---

### 4.7. Locución y Síntesis de Voz (TTS)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/tts/voices` | Catálogo de voces neuronales con acentos y géneros |
| `POST` | `/api/v1/tts/synthesize` | Genera archivo de audio MP3 neuronal desde texto |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Bienvenidos a un nuevo video sobre inteligencia artificial y automatización.",
    "voice": "es-MX-JorgeNeural",
    "rate": "+5%",
    "pitch": "+0Hz"
  }'
```

---

### 4.8. Radar de Viralidad

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/trends` | Consulta videos virales de YouTube por velocidad y nicho |
| `POST` | `/api/v1/trends/refresh` | Fuerza actualización en vivo del radar |
| `POST` | `/api/v1/trends/replicate` | Convierte un tema viral en un video con 1 clic |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/trends/replicate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Nuevo descubrimiento arqueológico en Pompeya",
    "duration_sec": 45,
    "webhook_url": "https://webhook.site/mi-identificador"
  }'
```

---

### 4.9. Estudio de Publicación y YouTube

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/v1/publish/prepare` | Genera título de alto CTR, descripción SEO y tags |
| `POST` | `/api/v1/publish/thumbnail` | Genera miniatura de alta resolución con IA |
| `GET` | `/api/v1/publish/youtube/status` | Comprueba vinculación de canal YouTube |
| `POST` | `/api/v1/publish/youtube/upload` | Sube video directo a YouTube |
| `GET` | `/api/v1/publish/channels` | Lista canales y nichos configurados |
| `POST` | `/api/v1/publish/channels` | Crea o actualiza un canal |
| `DELETE` | `/api/v1/publish/channels/{id}` | Elimina un canal |

---

### 4.10. Agente Copilot Director IA

Permite enviar instrucciones en lenguaje natural al director de edición.

`POST /api/v1/agent/chat`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Qué temas virales me recomiendas producir hoy para el nicho de ciencia?",
    "model_id": "gemini"
  }'
```

---

### 4.11. Plantillas Visuales y Previews (Editorial Tech Minimalist)

Permite generar gráficos explicativos de alta retención (estilo Anton / Clean Tech) tanto en modo sticker/overlay transparente recortado como en lienzo vertical completo 9:16 (1080x1920 con papel milimetrado y cabecera de retención).

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/templates` | Catálogo completo con IDs, descripciones, sample_params y animaciones |
| `GET` | `/api/v1/templates/preview` | Renderiza y descarga directamente la imagen PNG renderizada en Chromium |

#### Catálogo de Plantillas Explicativas Disponibles:

| Template ID | Caso de Uso / Explicación | Elementos Clave |
| :--- | :--- | :--- |
| `editorial_code_terminal` | Comandos CLI, snippets de código, llamadas API | Pestaña de archivo (`📄 pipeline.py`), números de línea, línea activa resaltada en rojo/acento, sintaxis coloreada, barra de estado inferior (`✓ 200 OK (28ms) · 0 Tokens`). |
| `editorial_versus_fix` | Comparativas Antes vs Después, Error vs Solución | Tarjeta superior roja tachada (`✕ ERROR COMÚN`) con métricas negativas, píldora flotante `VS`, y tarjeta inferior iluminada (`✓ FÓRMULA OPTIMIZADA`) con métricas de retención. |
| `editorial_workflow_pipeline` | Arquitecturas de sistemas, flujos IA, pipelines | 3 nodos conectados con flechas (`01 Input` ➔ `02 KAI Director IA` con aura de iluminación ➔ `03 Video Master 4K`) y pie de nota técnica de privacidad/local. |
| `editorial_feature_checklist` | Requisitos técnicos, pasos previos, claves del éxito | 3 filas Bento satinadas con checks circulares SVG de verificación, titulares bold, micro-descripción y etiquetas de valor (`0€ / MES`, `AUTOMÁTICO`, `OFFLINE`). |
| `editorial_stat_benchmark` | Rendimiento, comparativa de velocidad o ahorro | Cifra monumental (96px) en gradiente temático (`12s`), píldora de tendencia verde neón (`▲ +890% MÁS RÁPIDO`), texto de contraste y barra de progreso. |
| `editorial_file_tree` | Estructura de carpetas, dónde colocar vídeos/archivos | Árbol de directorios macOS/VS Code (`assets/`, `inputs/`, `outputs/`) con fila destino resaltada con píldora de acción (`COLOCA AQUÍ TU VÍDEO`). |
| `editorial_prompt_diff` | Prompt Engineering, optimización de instrucciones LLM | Split view de prompt novato tachado con crítica de alucinación vs tokens de roles coloreados (`ROLE`, `HOOK`, `PACING`, `SCHEMA`) y métricas de precisión semántica. |
| `editorial_agent_matrix` | Orquestación multi-agente en paralelo (Swarm) | 3 tarjetas de agentes con avatars (Research, Scriptwriter, KAI Director con glow activo), badges de modelos (`DEEPSEEK-R1`, `SONNET 3.7`, `RTX 4090`) y latencias. |
| `editorial_pricing_roi` | Comparativa financiera de costes vs ahorro (ROI) | Tarjeta dual: Agencia/Freelance (1.850€/mes, esperas, límites) vs AetherCut Local (0€/mes, 12s, revisiones infinitas) con píldora verde de ahorro anual (22.200€). |
| `editorial_hardware_spec` | Telemetría de GPU, inferencia local y recursos | Monitor técnico estilo Apple/NVIDIA Studio con barra gráfica de VRAM usada (8.2/12 GB), velocidad (54.8 tokens/s), telemetría térmica y modo 100% offline. |
| `editorial_retention_graph` | Curva de retención de YouTube Shorts / Reels | Gráfica vectorial SVG con curva optimizada al 85% y 3 hitos clave (Hook 2s Zeigarnik, B-Roll, Micro-Pacing) frente a la línea punteada roja del video promedio que cae al 22%. |
| `editorial_search_mockup` | Tendencias de búsqueda, keywords y radar viral | Barra spotlight flotante con cursor pulsante y 3 filas de autocompletado con iconos de fuego, volúmenes de búsqueda mensuales (`148K / mes`) y etiquetas de CTR. |
| `editorial_full_canvas` | Pantalla completa vertical 9:16 para Shorts/Reels | Fondo de papel milimetrado/blueprint, cabecera de retención (`PASO 03/10`), titular dual contrastado, componente central interactivo (`canvas_type`) y zona inferior reservada para busto parlante. |

#### Temas Cromáticos Disponibles (`variant`):
- `editorial_cream` (por defecto): Fondo crema cálido (#FAF7F2), texto carbón (#111111) y acento rojo carmesí (#E11D48).
- `editorial_slate`: Modo oscuro técnico (#0D1117 / #161B22), bordes sutiles y acento azul cian neón (#38BDF8).
- `sunset_warm`: Gradiente atardecer cálido (#FFFDF9 / #1C1917) con acentos ámbar y terracota (#D97706).
- `sage_minimal`: Paleta minimalista orgánica (#F4F7F4) con acento verde bosque (#059669).

#### Ejemplos de Solicitud de Preview:
```bash
# 1. Preview de ingeniería de prompts con tokens de roles
curl "http://127.0.0.1:8000/api/v1/templates/preview?template=editorial_prompt_diff&variant=editorial_cream" \
  --output prompt_diff.png

# 2. Preview de orquestación multi-agente en modo oscuro
curl "http://127.0.0.1:8000/api/v1/templates/preview?template=editorial_agent_matrix&variant=editorial_slate" \
  --output agent_swarm.png

# 3. Preview de curva de retención viral
curl "http://127.0.0.1:8000/api/v1/templates/preview?template=editorial_retention_graph&variant=sunset_warm" \
  --output retention_graph.png

# 4. Preview de Lienzo Completo 9:16 con Curva de Retención incrustada
curl "http://127.0.0.1:8000/api/v1/templates/preview?template=editorial_full_canvas&canvas_type=retention_graph&step_number=04&total_steps=05&step_prefix=SECRETO&main_text=Multiplica%20tu&accent_text=retenci%C3%B3n%20media&variant=sunset_warm" \
  --output canvas_retention.png
```

---

## 🔔 5. Integración con Webhooks (Zapier, n8n, Make, Discord)

Cuando inicias un video indicando un `webhook_url`, AetherCut AI enviará automáticamente una solicitud HTTP POST al finalizar o ante cualquier eventualidad:

### Payload de Webhook Enviado:
```json
{
  "event": "video.completed",
  "task_id": "a1b2c3d4",
  "project_id": "a1b2c3d4",
  "status": "done",
  "title": "La revolución cuántica",
  "topic": "Física y Tecnología",
  "duration_sec": 84.5,
  "download_urls": {
    "master_video": "/media/a1b2c3d4_master.mp4",
    "thumbnail": "/media/a1b2c3d4_thumbnail.jpg",
    "subtitles_srt": "/api/v1/projects/a1b2c3d4/download/subtitles",
    "transcript": "/api/v1/projects/a1b2c3d4/download/transcript",
    "materials_zip": "/api/v1/projects/a1b2c3d4/materials/download"
  },
  "shorts": [
    {
      "filename": "short_a1b2c3d4_clip1.mp4",
      "url": "/outputs/short_a1b2c3d4_clip1.mp4",
      "size_mb": 18.4
    }
  ],
  "error": null,
  "timestamp": "2026-10-15T20:45:00Z"
}
```

---

## 💻 6. Ejemplos de Clientes en Código

### En Python (`requests`)
```python
import requests
import time

API_BASE = "http://127.0.0.1:8000/api/v1"
HEADERS = {"X-API-Key": "mi_clave_secreta"} # Opcional si está configurada

# 1. Crear video autónomo
payload = {
    "topic": "Los 5 mayores descubrimientos de telescopio James Webb",
    "duration_sec": 45,
    "aspect_ratio": "16:9",
}
res = requests.post(f"{API_BASE}/streamer/create", json=payload, headers=HEADERS).json()
task_id = res["data"]["task_id"]
print(f"Tarea iniciada: {task_id}")

# 2. Monitorear progreso
while True:
    status = requests.get(f"{API_BASE}/tasks/{task_id}", headers=HEADERS).json()["data"]
    print(f"[{status['step']}] {status['progress']}% — {status['message']}")
    if status["completed"]:
        print("¡Video terminado!")
        print("URL del video master:", status["result"].get("master_video_url"))
        break
    time.sleep(2)
```

### En Node.js (`fetch`)
```javascript
const API_BASE = "http://127.0.0.1:8000/api/v1";

async function sintetizarVoz(texto) {
  const resp = await fetch(`${API_BASE}/tts/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: texto,
      voice: "es-MX-JorgeNeural"
    })
  });
  const data = await resp.json();
  console.log("Audio URL:", data.data.url);
}

sintetizarVoz("Hola mundo, esta es la API de AetherCut AI.");
```
