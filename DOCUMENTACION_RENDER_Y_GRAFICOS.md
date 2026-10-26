# Directrices de Producción y Renderizado Audiovisual — AetherCut AI

Este documento actúa como registro de memoria técnica y directrices fijas para futuras mejoras, adiciones de elementos visuales (gráficos TanStack/Matplotlib, Bento HUD, B-Roll, Popups) y edición en la línea de tiempo.

---

## 1. Reglas Críticas del Motor de Renderizado (FFmpeg & Timeline)

### A. Prohibición de Truncado de Audio (`shortest=1`)
* **Problema resuelto:** En el filtergraph de composición (`core/scene_engine.py`), el uso de `:shortest=1` en filtros de overlay (avatar, fondo o capas visuales) provocaba que si una pista de video o loop terminaba antes que la voz hablada, FFmpeg truncaba abruptamente todo el archivo MP4 cortando hasta 2.5 segundos de audio ("mochar entre líneas / frases").
* **Regla obligatoria:** 
  - **NUNCA usar `shortest=1`** en overlays cuando el timeline dependa de la voz o de `-t {dur_str}`.
  - Usar siempre `eof_action=pass` en overlays de video y avatares.
  - La duración del video final debe estar estrictamente gobernada por la pista de voz Edge TTS (`tts_duration + 0.15s`) y el flag `-t {dur_str}`.

### B. Cadencia y Ritmo de Locución (Speech Normalizer & AI Director)
* **Pacing establecido:** **120 palabras por minuto** (~2.0 palabras por segundo).
* **Segmentación de oraciones:**
  - Máximo 14 palabras por segmento puntuado antes de forzar una pausa (coma o punto) en `utils/speech_normalizer.py`.
  - El narrador debe tener pausas para respirar y sonar elocuente y pausado, evitando monólogos apresurados.

---

## 2. Popups, Pastillas Dinámicas (Chips) y Elementos Reactivos

### A. Comportamiento en la Línea de Tiempo (No solo al inicio de la escena)
* **Objetivo:** Los elementos de apoyo visual (banderas, marcas, nombres de entidades, popups de datos) no deben limitarse a aparecer fijos en el segundo `0.0` o `0.5` de cada escena.
* **Sincronización contextual:**
  - Deben activarse de forma reactiva en el segundo exacto en que la voz pronuncia el concepto (utilizando los timestamps de `SentenceBoundary` obtenidos de Edge TTS).
  - Duración de popup: entrada rápida con fade/slide (`0.25s - 0.35s`), permanencia de 2.5 a 4.0 segundos mientras se explica la idea, y salida suave (`fade-out`).
  - Al desaparecer, la toma de video de fondo y la narración continúan con protagonismo completo y limpio.

---

## 3. Integración de Gráficos e Infografías (TanStack Charts 1.0 & Matplotlib)

### A. Ecosistema Gráfico
1. **Gráficos en Video (Backend Render):**
   - Implementado en `core/chart_generator.py` con Matplotlib (backend `Agg`) y PIL.
   - Genera barras comparativas (ej. "300M vs 6M"), medidores radiales/gauges ("99.8%", "2.4% PIB") y curvas de crecimiento en estética *Obsidian Glass / Neon Accent*.
2. **TanStack Charts 1.0 (Frontend Studio / Vista Interactiva):**
   - Compatible para visualización interactiva y dashboards de análisis dentro de la interfaz web (`web/`).
   - Permite al usuario editar parámetros de gráficos en tiempo real en la barra lateral antes de compilar y exportar el video definitivo.

### B. Criterios de Inclusión Automática
* Siempre que el guion o la evidencia cite porcentajes, proporciones, comparativas o datos financieros, el plan de dirección debe incluir el bloque `card` con métricas limpias (`stat`, `headline`, `body`) para renderizar el gráfico correspondiente.
