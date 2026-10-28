---
name: narrative-motion
description: Diseña y revisa escenas explicativas de VIDCUT sincronizadas con la narración. Úsala cuando se trabaje en visual_scenes, motion graphics, escenas Remotion, ritmo visual, subtítulos palabra por palabra o calidad de exportación.
---

# Narrative Motion Director — VIDCUT

## Objetivo
Crear una secuencia visual que explique lo que dice el orador en el instante adecuado. No convertir el vídeo en una sucesión de tarjetas. Cada movimiento, revelación, cambio de plano gráfico y sonido debe servir a una frase o palabra concreta.

## Pipeline del proyecto
1. Lee la transcripción y conserva las marcas de tiempo reales. Usa `core/word_aligner.py` cuando se requiera alineación por palabra; no supongas que repartir el tiempo por longitud de texto equivale a sincronización real.
2. Selecciona pocos momentos de alto valor y genera `VisualScene` con `spoken_phrase` literal, `start_sec/end_sec`, `kind`, etiquetas y una explicación del propósito visual.
3. El director debe elegir una acción visual específica: revelar, conectar, comparar, acercar, construir, resaltar o transformar. Evita que todas las escenas usen el mismo patrón.
4. Para escenas completas, usa `remotion_studio/src/NarrativeScene.tsx` y la composición `NarrativeScene`. Usa Remotion para la animación determinista por frame; el puente `core/narrative_motion.py` llama al render y valida el archivo final.
5. En KAI Streamer, Remotion es el motor visual principal. Si no está disponible o falla, detén el render con un error explícito; no entregues silenciosamente el plano antiguo. `NARRATIVE_MOTION_REQUIRED=0` solo se usa para diagnóstico temporal con fallback.
6. Mantén el vídeo original y la voz como fuentes de verdad. Los diagramas conceptuales no son evidencia real; no inventes cifras, actores, ubicaciones ni resultados.
7. No cubras la cara ni la boca del orador. Cuando haya rostro detectado, prefiere bandas superior/inferior o una composición lateral. Evita textos largos, microtexto, neón excesivo y elementos que compitan con los subtítulos.

## Ritmo editorial
- Usa movimientos cortos con easing, entradas escalonadas y transiciones suaves.
- El cambio importante debe coincidir con el concepto mencionado, no simplemente con un intervalo fijo.
- Para procesos, revela nodos de izquierda a derecha; para comparaciones, establece ambos lados antes de resaltar la diferencia; para código, destaca la línea relacionada con la frase; para una cifra, cuenta solo hasta un valor respaldado por una fuente.
- Deja tiempo suficiente para leer. No cambies de escena a cada palabra: sincroniza las revelaciones semánticas con las palabras clave y los límites de frase.
- Mantén una paleta consistente por proyecto, con acento moderado y jerarquía tipográfica clara.

## Control de calidad obligatorio
- Valida esquema, tipo de escena, duración, dimensiones y tiempos finitos.
- Comprueba que el render existe, tiene tamaño razonable y duración cercana a la solicitada.
- Inspecciona un frame inicial, uno intermedio y uno final si el flujo de render lo permite.
- Revisa que no haya texto cortado, nodos fuera del lienzo, parpadeos, saltos de sincronización o fondos opacos no deseados.
- Si una prueba falla, corrige la causa y vuelve a ejecutar la prueba específica; no declares que pasó si no se ejecutó.

## Comandos de verificación
```bash
python -m unittest tests.test_visual_scene_engine tests.test_remotion_bridge -v
```

Para habilitar o deshabilitar el motor avanzado:
- `NARRATIVE_MOTION=1`: preferir Remotion cuando sus dependencias locales estén instaladas (valor por defecto).
- `NARRATIVE_MOTION=0`: usar únicamente el motor procedural Pillow/FFmpeg.
