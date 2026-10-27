# Plan de edición autónoma (cuándo, dónde y cómo)

Basado en lo que hacen creadores conocidos y en lo que se ha medido. Se separa lo respaldado con datos de lo anecdótico.

## 1. Qué funciona (y qué tan firme es la evidencia)

| Práctica | Evidencia | Qué hace VidCut |
|---|---|---|
| Retiene la **información nueva**, no la velocidad de cortes (Mario Joos) | Argumento de editor, coherente con que MrBeast dijo en 2024 haber bajado el ritmo y subido las vistas | Tope de zooms por minuto y separación mínima; el ritmo se mide por contraste |
| Propuesta de valor en ~15 s, gancho en los primeros 3 s | Benchmarks de vidIQ: buenos ganchos retienen >65 % en el arranque, ≥60 % pasados 30 s | `hook_scorer` puntúa y recorta aperturas vacías; `editorial_qa` revisa el gancho |
| Subtítulos grandes, palabra resaltada, sincronizados (estilo Hormozi) | Cualitativo, ampliamente copiado; sin cifras públicas | Ya existe `highlight_words`; el director las usa como señal de énfasis |
| Zooms, SFX y B-Roll como énfasis | Cualitativo | `edit_director`: puntaje de énfasis, sin zoom sobre overlays, alternancia punch/slow, SFX con tope |
| Recorte vertical siguiendo a la persona (método AutoFlip) | Método publicado: detección de escenas, rostro/persona, estabilizado | Pendiente (Fase 2) con MediaPipe/OpenCV |
| Música que baja con la voz (ducking) y audio limpio | Práctica estándar de mezcla | `duck_windows` listo (datos); mezcla en Fase 2 |

Lo **no** respaldado y por tanto no se hardcodea: "un corte cada 1,3 s" (cifra de una fuente, ya matizada por el propio MrBeast) y "info nueva cada 10-15 s" (sin fuente). Quedan como parámetros ajustables.

## 2. Herramientas gratuitas y licencias (verificadas)

| Herramienta | Licencia | Decisión |
|---|---|---|
| Remotion | Gratis para individuos y equipos de hasta 3 personas, incluso comercial; desde 4 personas requiere licencia de pago | Opcional, solo si el equipo cumple el límite |
| Ultralytics YOLO | AGPL-3.0, o licencia Enterprise para uso comercial/cerrado | **Evitar**; usar MediaPipe/OpenCV |
| MediaPipe | Apache-2.0 (según su repositorio; no pude abrir la página, confírmalo) | Preferido para rostro/persona |
| DeepFilterNet | MIT/Apache, último release ago-2023 | Opcional para limpieza de voz |
| Freesound | Cada sonido tiene su licencia | Para monetizar, solo CC0 |
| YouTube Audio Library | Música y SFX con reglas de atribución por pista | Revisar la ficha de cada pista |

## 3. Fases

1. **Hecha — Director de edición** (`core/edit_director.py`, `EDIT_DIRECTOR=1`): zooms por mérito, SFX planificados, tramos estáticos marcados. Conectado al render con vuelta al comportamiento anterior si falla.
2. **Siguiente — Ejecución sonora**: mezclar el plan de SFX y el ducking en FFmpeg con biblioteca CC0; reencuadre vertical con seguimiento de rostro.
3. **Después — Bucle de aprendizaje**: leer YouTube Analytics (retención por segundo) y ajustar umbrales por canal.

## 4. Cómo saber si funciona

`run_report.md` ya registra conteos; el director agrega `zooms`, `per_minute`, `sfx`, `static_stretches`. La prueba real es comparar la curva de retención de videos con y sin director en tus propios videos. Los umbrales actuales (5 zooms/min, 4 s de separación, 12 s de tramo estático, 8 SFX/min) son puntos de partida sin calibrar.
