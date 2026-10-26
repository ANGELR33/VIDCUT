# 🎬 ESPECIFICACIÓN COMPLETA DE AETHERCUT AI PARA AGENTES EXTERNOS

Instrucciones: Pega todo este documento en el chat de tu Agente (ChatGPT, Claude, etc.) o adjúntale este archivo. Con esto el Agente no necesita navegar por internet ni descargar ningún archivo; ya tendrá la API completa en su contexto.

---

## 🌐 1. Conexión y Autenticación

- **URL Base:** `https://TU-URL-DE-CLOUDFLARE.trycloudflare.com/api/v1`
  *(Reemplaza `TU-URL-DE-CLOUDFLARE` por la que te muestra tu terminal al ejecutar `INICIAR_CON_TUNEL_PUBLICO.bat`, por ejemplo: `relative-goat-mls-impossible`)*
- **Header Opcional:** `X-API-Key: tu_clave_secreta` (solo si definiste `AETHERCUT_API_KEY` en tu `.env`)
- **Content-Type:** `application/json`

---

## 📋 2. Flujo de Trabajo que debe ejecutar el Agente

1. **Crear el Video**:
   - Para crear desde una idea/tema: `POST /streamer/create`
   - Para editar un video de YouTube o URL directa: `POST /videos/process-url`
   - Guarda el `task_id` que devuelve la respuesta.
2. **Consultar Avance**:
   - Realizar `GET /tasks/{task_id}` cada 5 segundos hasta que `completed: true`.
3. **Descargar los Resultados**:
   - Video Master: `GET /projects/{task_id}/download/master`
   - Shorts Verticales 9:16: `GET /clips/{task_id}` o `GET /projects/{task_id}/download/short`
   - Miniatura JPG: `GET /projects/{task_id}/download/thumbnail`
   - Subtítulos SRT: `GET /projects/{task_id}/download/subtitles`

---

## 📚 3. Catálogo Detallado de Endpoints

### 1. Iniciar Video Autónomo KAI
- **Endpoint:** `POST /api/v1/streamer/create`
- **Request Body (JSON):**
```json
{
  "topic": "La historia oculta de la inteligencia artificial",
  "style": "divulgacion",
  "duration_sec": 45,
  "aspect_ratio": "16:9",
  "card_theme": "dark",
  "voice": "es-MX-JorgeNeural",
  "visual_mode": "mixed",
  "webhook_url": "https://opcional-para-notificacion.com"
}
```
- **Response (HTTP 202):**
```json
{
  "success": true,
  "data": {
    "task_id": "a1b2c3d4",
    "project_id": "a1b2c3d4",
    "topic": "La historia oculta de la inteligencia artificial",
    "message": "Investigación y redacción de guion en curso."
  }
}
```

---

### 2. Procesar Video desde Enlace Web / YouTube
- **Endpoint:** `POST /api/v1/videos/process-url`
- **Request Body (JSON):**
```json
{
  "video_url": "https://www.youtube.com/watch?v=ejemplo",
  "title": "Mi Video Importado",
  "silence_threshold": 1.5,
  "enable_broll": true,
  "enable_captions": true,
  "enable_shorts": true,
  "enable_cards": true,
  "voice": "es-MX-JorgeNeural",
  "webhook_url": "https://opcional-para-notificacion.com"
}
```
- **Response (HTTP 202):**
```json
{
  "success": true,
  "data": {
    "task_id": "a1b2c3d4",
    "project_id": "a1b2c3d4",
    "status": "downloading"
  }
}
```

---

### 3. Consultar Estado y Progreso de la Tarea
- **Endpoint:** `GET /api/v1/tasks/{task_id}`
- **Response (HTTP 200):**
```json
{
  "success": true,
  "data": {
    "task_id": "a1b2c3d4",
    "step": "render",
    "progress": 78.5,
    "message": "Codificando video final...",
    "completed": false,
    "error": null,
    "result": null
  }
}
```
*(Cuando `completed` es `true`, el campo `result` contendrá las URLs y estadísticas).*

---

### 4. Descargar Artefactos Generados
- **Video Master Completo:** `GET /api/v1/projects/{project_id}/download/master`
- **Short Vertical 9:16:** `GET /api/v1/projects/{project_id}/download/short`
- **Miniatura JPG:** `GET /api/v1/projects/{project_id}/download/thumbnail`
- **Subtítulos SRT:** `GET /api/v1/projects/{project_id}/download/subtitles`
- **Transcripción JSON:** `GET /api/v1/projects/{project_id}/download/transcript`
- **Archivo ZIP con todos los materiales:** `GET /api/v1/projects/{project_id}/materials/download`

---

### 5. Listar y Extraer Clips / Shorts (9:16)
- **Listar Clips:** `GET /api/v1/clips/{project_id}`
- **Extraer Clip Específico:** `POST /api/v1/clips/{project_id}/extract`
  - **Body (JSON):**
  ```json
  {
    "start_sec": 10.0,
    "end_sec": 40.0,
    "title": "Momento Clave",
    "aspect_ratio": "9:16"
  }
  ```

---

### 6. Locución y Síntesis de Voz (TTS)
- **Listar Voces Disponibles:** `GET /api/v1/tts/voices`
- **Sintetizar Audio:** `POST /api/v1/tts/synthesize`
  - **Body (JSON):**
  ```json
  {
    "text": "Texto a narrar con la voz seleccionada.",
    "voice": "es-MX-JorgeNeural",
    "rate": "+0%",
    "pitch": "+0Hz"
  }
  ```

---

### 7. Radar de Tendencias Virales de YouTube
- **Consultar Tendencias:** `GET /api/v1/trends`
- **Replicar Tendencia en Video:** `POST /api/v1/trends/replicate`
  - **Body (JSON):**
  ```json
  {
    "topic": "Tema viral obtenido del radar",
    "duration_sec": 45,
    "style": "divulgacion"
  }
  ```

---

### 8. Diagnóstico de Salud
- **Endpoint:** `GET /api/v1/system/health`
- **Response (HTTP 200):**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "ffmpeg_available": true,
    "gpu_available": true,
    "storage_free_gb": 45.2,
    "active_tasks_count": 0
  }
}
```
