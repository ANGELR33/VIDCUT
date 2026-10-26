# 🎵 Biblioteca de Audio de YouTube (YouTube Audio Library)

Esta carpeta integra **música de fondo (BGM)** y **efectos de sonido (SFX)** 100% libres de derechos y reclamos de Content ID procedentes de la **Biblioteca de audio de YouTube Studio**.

## 📁 Estructura de Carpetas

```text
assets/audio/youtube_library/
├── bgm/
│   ├── cinematic/   -> Pistas orquestales, bandas sonoras, trailers, documentales épicos
│   ├── tension/     -> Tensión, noticias de última hora, misterio, suspense
│   ├── upbeat/      -> Ritmo enérgico, tecnología, divulgación dinámica, motivación
│   ├── ambient/     -> Fondos tranquilos, reflexivos, paisajes sonoros sutiles
│   └── lofi/        -> Beats lo-fi relajantes para explicaciones pausadas
└── sfx/
    ├── transitions/ -> Whooshes, swooshes, barridos de transición
    ├── impacts/     -> Booms cinematográficos, sub-bass drops, golpes secos
    ├── alerts/      -> Beeps de notificación, breaking news stingers, alertas
    ├── chimes/      -> Campanadas de acierto, dings, confirmación
    └── ui/          -> Clics, pops elásticos, papel, resaltadores
```

## 🚀 Cómo agregar tus canciones favoritas de YouTube Studio

1. Abre tu navegador e ingresa a [YouTube Studio](https://studio.youtube.com).
2. En el menú lateral izquierdo, haz clic en **Biblioteca de audio** (`Audio Library`).
3. Filtra por:
   - **Género**: Cinemático, Ambiental, Hip-Hop, etc.
   - **Estado de ánimo (Mood)**: Dramático, Inspirador, Oscuro, Alegre, etc.
   - **Efectos de sonido**: Transiciones, Impactos, Dibujos animados, Foley, etc.
4. Haz clic en **Descargar** (obtendrás un archivo `.mp3`).
5. Copia o mueve el archivo `.mp3` descargado dentro de la subcarpeta correspondiente (ejemplo: `bgm/cinematic/` o `sfx/transitions/`).
6. **¡Listo!** El motor de KAI detectará automáticamente los nuevos audios y los usará con compresión sidechain inteligente bajo la voz.

## 🛡️ Ventajas Legales y de Monetización
- **100% Seguro para Monetizar**: Pistas autorizadas oficialmente por YouTube.
- **Cero Content ID Claims**: Sin riesgo de desmonetización ni silenciamiento de videos.
- **Sidechain Ducking Automático**: KAI reduce la música suavemente (-12 a -14 dB) mientras habla la voz y la eleva en silencios reflexivos.
