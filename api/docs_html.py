"""Generador del portal interactivo de documentación para desarrolladores de AetherCut API."""

API_DOCS_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AetherCut AI — Developer API Portal & Integrations</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090b10;
      --card-bg: rgba(18, 22, 34, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #6366f1;
      --accent-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --code-bg: #0d1117;
      --success: #10b981;
      --method-get: #3b82f6;
      --method-post: #10b981;
      --method-put: #f59e0b;
      --method-delete: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      background-image: radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.12) 0%, transparent 40%),
                        radial-gradient(circle at 85% 75%, rgba(168, 85, 247, 0.1) 0%, transparent 45%);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      line-height: 1.6;
      padding-bottom: 80px;
    }
    .header {
      padding: 48px 24px 32px;
      text-align: center;
      max-width: 1100px;
      margin: 0 auto;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(99, 102, 241, 0.35);
      color: #c7d2fe;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 16px;
    }
    h1 {
      font-size: 2.8rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin-bottom: 12px;
      background: var(--accent-gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 1.15rem;
      max-width: 680px;
      margin: 0 auto 24px;
    }
    .quick-links {
      display: flex;
      justify-content: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px;
      border-radius: 10px;
      font-weight: 600;
      font-size: 0.95rem;
      text-decoration: none;
      transition: all 0.2s ease;
      cursor: pointer;
    }
    .btn-primary {
      background: var(--accent);
      color: white;
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
    }
    .btn-primary:hover {
      background: #4f46e5;
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.06);
      color: var(--text);
      border: 1px solid var(--card-border);
    }
    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.12);
      transform: translateY(-1px);
    }
    .container {
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 24px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 20px;
      margin-bottom: 36px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
      backdrop-filter: blur(12px);
    }
    .card h3 {
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .card p {
      color: var(--text-muted);
      font-size: 0.92rem;
      margin-bottom: 14px;
    }
    .endpoint-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px 20px;
      margin-bottom: 14px;
      backdrop-filter: blur(10px);
    }
    .endpoint-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }
    .method {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 6px;
      text-transform: uppercase;
      color: white;
    }
    .method-get { background: var(--method-get); }
    .method-post { background: var(--method-post); }
    .method-put { background: var(--method-put); }
    .method-delete { background: var(--method-delete); }
    .path {
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      font-weight: 600;
      color: #e2e8f0;
    }
    .desc {
      color: var(--text-muted);
      font-size: 0.9rem;
      margin-bottom: 12px;
    }
    .code-box {
      background: var(--code-bg);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 12px 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      overflow-x: auto;
      color: #38bdf8;
      position: relative;
    }
    .copy-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(255, 255, 255, 0.1);
      border: none;
      color: #94a3b8;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      cursor: pointer;
      transition: all 0.2s;
    }
    .copy-btn:hover {
      background: rgba(255, 255, 255, 0.2);
      color: white;
    }
    .section-title {
      font-size: 1.6rem;
      font-weight: 700;
      margin: 40px 0 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 8px;
      overflow-x: auto;
    }
    .tab-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 0.9rem;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .tab-btn.active {
      background: rgba(99, 102, 241, 0.2);
      color: #c7d2fe;
    }
  </style>
</head>
<body>

  <header class="header">
    <div class="badge">⚡ AetherCut AI Public API v1</div>
    <h1>Conecta Cualquier App</h1>
    <p class="subtitle">API RESTful unificada, Server-Sent Events (SSE) y Webhooks para integrar edición de video con IA, Shorts verticales, doblaje TTS y viralidad en tus propias aplicaciones, bots y flujos n8n/Zapier.</p>
    <div class="quick-links">
      <a href="/docs" target="_blank" class="btn btn-primary">📖 Swagger UI Interactivo</a>
      <a href="/redoc" target="_blank" class="btn btn-secondary">📑 ReDoc Especificación</a>
      <a href="/openapi.json" target="_blank" class="btn btn-secondary">📦 OpenAPI JSON</a>
    </div>
  </header>

  <main class="container">

    <div class="grid">
      <div class="card">
        <h3>🔑 Autenticación Flexible</h3>
        <p>Configura <code>AETHERCUT_API_KEY</code> en tu <code>.env</code> para proteger tu servidor o déjala vacía para acceso libre en tu red local.</p>
        <div class="code-box">X-API-Key: tu_clave_secreta<br>Authorization: Bearer tu_clave_secreta</div>
      </div>
      <div class="card">
        <h3>🌐 Webhooks Automáticos</h3>
        <p>Envía <code>webhook_url</code> al crear cualquier tarea y recibe un POST automático cuando el video termine o falle.</p>
        <div class="code-box">{"event": "video.completed", "download_urls": {...}}</div>
      </div>
      <div class="card">
        <h3>🔗 Ingesta por Archivo o URL</h3>
        <p>Sube archivos MP4/MOV locales o simplemente envía un enlace directo o de YouTube. AetherCut se encarga de todo.</p>
        <div class="code-box">POST /api/v1/videos/process-url<br>{"video_url": "https://..."}</div>
      </div>
    </div>

    <h2 class="section-title">🚀 Ejemplos Rápidos de Integración</h2>

    <div class="card" style="margin-bottom: 30px;">
      <div class="tabs">
        <button class="tab-btn active" onclick="showSnippet('curl')">cURL</button>
        <button class="tab-btn" onclick="showSnippet('python')">Python (requests)</button>
        <button class="tab-btn" onclick="showSnippet('node')">Node.js / JS (fetch)</button>
      </div>

      <div id="snippet-curl" class="code-box" style="white-space: pre;"># 1. Iniciar edición enviando URL de video y Webhook
curl -X POST http://127.0.0.1:8000/api/v1/videos/process-url \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "silence_threshold": 1.5,
    "enable_broll": true,
    "enable_captions": true,
    "enable_shorts": true,
    "webhook_url": "https://mi-webhook.ejemplo.com/aethercut"
  }'

# 2. Consultar avance de tarea
curl http://127.0.0.1:8000/api/v1/tasks/{task_id}

# 3. Descargar video final editado
curl -O http://127.0.0.1:8000/api/v1/projects/{project_id}/download/master</div>

      <div id="snippet-python" class="code-box" style="white-space: pre; display: none;">import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Iniciar producción autónoma desde un tema
payload = {
    "topic": "La historia oculta de la inteligencia artificial",
    "duration_sec": 60,
    "aspect_ratio": "16:9",
    "webhook_url": "https://webhook.site/mi-endpoint"
}
res = requests.post(f"{BASE_URL}/streamer/create", json=payload).json()
task_id = res["data"]["task_id"]
print("Produciendo video:", task_id)

# Comprobar estado
status = requests.get(f"{BASE_URL}/tasks/{task_id}").json()
print("Progreso actual:", status["data"]["progress"], "%")</div>

      <div id="snippet-node" class="code-box" style="white-space: pre; display: none;">// Sintetizar voz neuronal con la API
const res = await fetch("http://127.0.0.1:8000/api/v1/tts/synthesize", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    text: "Bienvenidos a un nuevo video sobre tecnología y futuro.",
    voice: "es-MX-JorgeNeural"
  })
});
const data = await res.json();
console.log("Audio generado:", data.data.url);</div>
    </div>

    <h2 class="section-title">📚 Catálogo Principal de Endpoints v1</h2>

    <!-- Video Processing -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-post">POST</span>
        <span class="path">/api/v1/videos/process</span>
      </div>
      <div class="desc">Carga un archivo de video binario (Multipart) e inicia la edición con IA.</div>
      <div class="code-box">Form: video (file), silence_threshold (float), enable_broll (bool), enable_captions (bool), enable_shorts (bool), webhook_url (str)</div>
    </div>

    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-post">POST</span>
        <span class="path">/api/v1/videos/process-url</span>
      </div>
      <div class="desc">Descarga un video desde una URL remota (enlace directo o YouTube) e inicia el procesamiento.</div>
      <div class="code-box">JSON: {"video_url": "https://...", "silence_threshold": 1.5, "webhook_url": "https://..."}</div>
    </div>

    <!-- AI Streamer -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-post">POST</span>
        <span class="path">/api/v1/streamer/create</span>
      </div>
      <div class="desc">Produce un video completo con IA desde cero a partir de un tema o premisa.</div>
      <div class="code-box">JSON: {"topic": "Misterios del Cosmos", "style": "divulgacion", "duration_sec": 45, "voice": "es-MX-JorgeNeural"}</div>
    </div>

    <!-- Tasks -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/tasks/{task_id}</span>
      </div>
      <div class="desc">Obtiene el porcentaje de avance, etapa actual y enlaces de descarga del video.</div>
    </div>

    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/tasks/{task_id}/events</span>
      </div>
      <div class="desc">Transmisión de eventos en tiempo real mediante Server-Sent Events (SSE).</div>
    </div>

    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-post">POST</span>
        <span class="path">/api/v1/tasks/{task_id}/cancel</span>
      </div>
      <div class="desc">Cancela de inmediato la tarea en ejecución.</div>
    </div>

    <!-- Projects -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/projects</span>
      </div>
      <div class="desc">Lista proyectos con paginación (limit, offset), búsqueda y filtros por estado.</div>
    </div>

    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/projects/{project_id}/download/{asset_type}</span>
      </div>
      <div class="desc">Descarga directa de artefactos: master, short, subtitles, transcript, thumbnail o archivo por nombre.</div>
    </div>

    <!-- Shorts -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/clips/{project_id}</span>
      </div>
      <div class="desc">Lista todos los Shorts verticales 9:16 generados para el proyecto.</div>
    </div>

    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-post">POST</span>
        <span class="path">/api/v1/clips/{project_id}/extract</span>
      </div>
      <div class="desc">Extrae un clip vertical 9:16 personalizado (start_sec, end_sec, título).</div>
    </div>

    <!-- Voiceover & TTS -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/tts/voices</span>
      </div>
      <div class="desc">Lista las voces neuronales disponibles con acentos y muestras de audio.</div>
    </div>

    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-post">POST</span>
        <span class="path">/api/v1/tts/synthesize</span>
      </div>
      <div class="desc">Sintetiza texto a voz MP3 neuronal al instante.</div>
    </div>

    <!-- Trend Radar -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/trends</span>
      </div>
      <div class="desc">Obtiene videos y temas virales en tiempo real detectados por el Radar de YouTube.</div>
    </div>

    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-post">POST</span>
        <span class="path">/api/v1/trends/replicate</span>
      </div>
      <div class="desc">Un solo clic para replicar un tema viral en un nuevo video autónomo.</div>
    </div>

    <!-- System -->
    <div class="endpoint-card">
      <div class="endpoint-header">
        <span class="method method-get">GET</span>
        <span class="path">/api/v1/system/health</span>
      </div>
      <div class="desc">Verifica el estado de salud, FFmpeg, GPU y almacenamiento del servidor.</div>
    </div>

  </main>

  <script>
    function showSnippet(type) {
      document.querySelectorAll('.tabs .tab-btn').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('snippet-curl').style.display = (type === 'curl') ? 'block' : 'none';
      document.getElementById('snippet-python').style.display = (type === 'python') ? 'block' : 'none';
      document.getElementById('snippet-node').style.display = (type === 'node') ? 'block' : 'none';
    }
  </script>

</body>
</html>
"""
