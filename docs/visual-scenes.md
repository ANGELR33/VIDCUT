# VIDCUT — escenas explicativas animadas

Este cambio introduce una primera ruta para representar visualmente procesos y conceptos abstractos sin depender de APIs de generación de video.

## Tipos iniciales

- `automation`: persona/tarea frente a un sistema o robot.
- `comparison`: comparación gráfica animada.
- `cause_effect`: una causa conectada visualmente con una consecuencia.
- `concept`: mapa conceptual con nodos conectados.

Cada tipo usa una composición diferente: persona + robot para automatización, barras para comparación, nodos conectados para causa-efecto y mapa conceptual para ideas abstractas. El overlay es transparente para conservar el material original de fondo y se compone después del B-roll cuando coinciden en el tiempo.

## Flujo

1. El plan de edición puede incluir `visual_scenes`.
2. Gemini recibe instrucciones para seleccionar escenas solo cuando ayuden a entender una idea y asignar tiempos desde la narración.
3. `VideoRenderEngine` mapea los tiempos originales a la línea de tiempo después de los cortes.
4. `VisualSceneEngine` produce un MOV con transparencia mediante Pillow y FFmpeg.
5. El MOV se incorpora como overlay en el render final.

## Ejemplo de escena

```json
{
  "scene_id": "visual_1",
  "start_sec": 12.4,
  "end_sec": 16.8,
  "kind": "automation",
  "title": "De tarea manual a automatización",
  "label_a": "PERSONA",
  "label_b": "SISTEMA",
  "spoken_phrase": "La IA automatiza tareas repetitivas",
  "reasoning": "Hace visible el cambio de trabajo manual a proceso automático",
  "confidence": 0.88,
  "enabled": true
}
```

## Límites actuales

Esta es una primera versión procedural, no un sistema de animación avanzado. Las escenas tienen ilustraciones procedurales sencillas y composición editorial contenida; todavía no hay un catálogo amplio de personajes/objetos, editor visual para retocar cada escena, ni previsualización de escena dentro de la interfaz. Los fallos al generar una escena se registran como aviso y no deben bloquear el render completo.

## Verificación

Ejecutar las pruebas del proyecto con el entorno normal de desarrollo. La prueba de render requiere FFmpeg instalado. No marcar el cambio como validado hasta ejecutar las pruebas y comprobar un MP4 real.
