# Informe Forense y Veredicto: Arquitectura de Edición Audiovisual y Eliminación de Patrones de «IA Genérica»

**Fecha:** 24 de Octubre de 2026  
**Proyecto analizado:** `5e55c0ac` (*La Crisis de los Misiles en Cuba*) y `1e6632fe` (*El Estrecho de Malaca*)  
**Estado:** Veredicto Emitido — Aprobado para Plan de Remediación  

---

## 1. Resumen Ejecutivo

Tras el análisis de los últimos masters audiovisuales generados y la revisión directa del código fuente, se confirma con total precisión la causa de las fallas señaladas por el usuario:
1. **Metraje y clips de mala calidad:** Presencia de clips con marcas de agua gigantescas de terceros (`www.PeriscopeFilm.com`, `wildfilmsindia`), timecodes quemados y reescalado digital excesivo de archivos antiguos 4:3 a 9:16 vertical.
2. **Etiquetas toscas, redundantes y congeladas:** Elementos gráficos («32 HORAS») con diseño de «pegatina» que permanecen congelados durante 12 a 14 segundos consecutivos por un error en el cálculo de duración de FFmpeg, superponiendo hasta tres capas independientes que repiten el mismo dato.
3. **Ausencia de una línea de tiempo real:** Inexistencia de alineación temporal basada en el audio fonético. La duración del texto se estimaba dividiendo artificialmente el tiempo entre el número de letras, provocando que los bloques de texto queden estáticos 10 segundos en vez de seguir el ritmo palabra por palabra de un editor humano.

---

## 2. Investigación Detallada de Causas Raíz

### Hallazgo A: Metraje de Mala Calidad y Marcas de Agua Ajenas
* **Archivos afectados:** `core/asset_providers.py` (L600-L770)
* **Causa técnica:**
  * La clase `YouTubeReactionAssetProvider` realizaba búsquedas con scoring permisivo (`score += 2` por palabras como *documentary* o *report*), sin lista negra de canales de archivo público masivo.
  * Agregadores históricos populares como *Periscope Film* suben material de archivo con un banner inferior permanente (`#: XD31251 00:00:11 www.PeriscopeFilm.com`).
  * No existía validación de resolución mínima de video (permitiendo clips de 480p o 360p) ni verificación de barras negras laterales (pillarboxing). Al aplicar un recorte vertical de 9:16 sobre metraje original 4:3, el zoom digital aumentaba más del 250%, pixelando severamente la imagen.

---

### Hallazgo B: Etiquetas Estáticas Congeladas («32 HORAS») y Aspecto Amateur
* **Archivos afectados:** `core/scene_engine.py` (L2387-L2434)
* **Causa técnica del tiempo congelado:**
  En las líneas 2400 y 2421, la fórmula para calcular el instante final (`b_end` y `s_end`) de las insignias y métricas era:
  ```python
  b_end = min(duration - 0.3, max(b_st + 3.2, duration - 0.4))
  ```
  En una escena típica de 14 segundos:
  * `duration - 0.4` = **13.6 segundos**.
  * `max(b_st + 3.2, 13.6)` = **13.6 segundos**.
  * El elemento entraba al segundo 1.0 y **se quedaba clavado 12.6 segundos seguidos** hasta el final de la escena.
* **Causa técnica de la redundancia visual:**
  El AI Director y el motor de escenas generaban tres componentes superpuestos sin coordinación espacial ni semántica:
  1. *Motion Badges:* Pastilla superior con el texto `32 HORAS`.
  2. *Motion Stat:* Bloque central con el texto `32 H MARGEN ANTES DEL FIN`.
  3. *Lower Third / InfoCard:* Recuadro inferior con `ESTADOS UNIDOS 1962 / 1,962 / TREUBENTA Y DOS HORAS...`.
  El resultado era una pantalla saturada de tres elementos repitiendo exactamente la misma información.

---

### Hallazgo C: Falta de Línea de Tiempo y Sincronización Palabra por Palabra
* **Archivos afectados:** `core/scene_engine.py` (L3687-L3712) y `core/transcriber.py` (L25-L60)
* **Causa técnica:**
  * Al emplear locuciones de Speechify (`speechify:alejandro`), el sintetizador entrega el audio en MP3 sin marcas de tiempo a nivel de palabra.
  * Como alternativa, `SceneEngine._generate_scene_subtitles` implementaba un cálculo rudimentario:
    ```python
    chunk_weight = len(chunk) / total_chars
    chunk_dur = max(0.7, active_speech_time * chunk_weight)
    ```
  * Cuando la escena incorporaba un *soundbite* de archivo (por ejemplo, 5.8 segundos del discurso histórico de JFK), la locución se pausaba, pero el algoritmo matemático distribuía el texto sobre toda la duración de la escena, desfasando por completo el audio y dejando párrafos estáticos durante 10 segundos.
  * **Recurso infrautilizado:** La biblioteca `faster-whisper` ya se encuentra instalada en el entorno y dispone de `word_timestamps=True`, pero no estaba conectada para alimentar la línea de tiempo de `SceneEngine`.

---

## 3. Veredicto y Principios de Remediación

| Defecto Observado | Diagnóstico Técnico | Veredicto de Corrección |
| :--- | :--- | :--- |
| **Metraje borroso con timecodes** | Ingesta no filtrada de agregadores con marcas y baja resolución | Filtrado estricto de canales vetados + resolución mínima 1080p/720p limpia + prioridad a fotos editoriales HD con *Ken Burns* |
| **Etiqueta «32 HORAS» congelada 13s** | Fórmula `max(b_st + 3.2, duration - 0.4)` mantiene el elemento activo hasta el final | Limitar duración a **2.2s - 2.8s** como máximo con animación de entrada (0.2s) y salida (0.3s) |
| **3 elementos duplicados a la vez** | Insignias + Stat + Card generados simultáneamente | **Regla estricta:** Máximo 1 elemento gráfico de acento a la vez. Cero redundancias. |
| **Texto estático en bloques de 10s** | Ausencia de análisis fonético del audio sintetizado | Integrar `faster-whisper` con `word_timestamps=True` para generar subtítulos dinámicos palabra por palabra |

---

## 4. Plan de Acción Técnico Paso a Paso

1. **Implementar Línea de Tiempo Fonética con `faster-whisper`:**
   * En `core/scene_engine.py`, al finalizar la síntesis de `voice.mp3` de cada escena, transcribir el audio con `faster_whisper.WhisperModel` configurado con `word_timestamps=True`.
   * Generar subtítulos estilo viral Alex Hormozi (ráfagas de 1 a 3 palabras sincronizadas al milisegundo con la voz del locutor).

2. **Corregir Duración y Disparo de Gráficos:**
   * Sustituir el cálculo de `b_end` y `s_end` para que las insignias y métricas duren entre **2.2s y 2.8s**.
   * Suprimir capas redundantes: si existe una métrica destacada, ocultar insignias y tarjetas duplicadas.

3. **Blindaje de Calidad de Clips:**
   * En `core/asset_providers.py`, añadir lista negra de canales con marcas (`periscopefilm`, `archive`, `getty`, `stock`, etc.).
   * Validar resolución y formato evitando clips en 4:3 con barras negras o aspecto borroso.
