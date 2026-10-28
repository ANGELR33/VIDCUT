# VIDCUT — escenas explicativas animadas

Este cambio introduce una primera ruta para representar visualmente procesos y conceptos abstractos sin depender de APIs de generación de video.

## Tipos iniciales

- `automation`: persona/tarea frente a un sistema o robot.
- `comparison`: comparación gráfica animada.
- `cause_effect`: una causa conectada visualmente con una consecuencia.
- `concept`: mapa conceptual con nodos conectados.
- `timeline`: hitos sobre una línea temporal con marcador animado.
- `flow`: diagrama de proceso entre entrada y resultado.
- `network`: red compacta de relaciones entre elementos.
- `stat`: tratamiento editorial de una cifra textual extraída de la narración; no calcula ni inventa valores.
- `sequence`: tres etapas con indicador de paso activo.
- `route`: recorrido esquemático animado, no un mapa geográfico exacto.
- `layers`: tres capas apiladas para explicar la composición de un sistema.
- `title_card`: titular editorial de apertura/capítulo con jerarquía tipográfica y espacio negativo.
- `code_terminal`: ventana de código esquemático con una línea activa sincronizada con la animación; no afirma ser código real.
- `cyber_diagram`: diagrama de arquitectura con límite de confianza, nodos y señal animada.
- `pixel_team`: doce personajes pixel-art en tarjetas compactas para narraciones sobre equipos o agentes.

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

Esta es una biblioteca procedural ampliada, no un sistema de animación avanzado. Las escenas tienen ilustraciones procedurales sencillas y composición editorial contenida; todavía no hay un catálogo amplio de personajes/objetos, editor visual para retocar cada escena, ni previsualización de escena dentro de la interfaz. Los fallos al generar una escena se registran como aviso y no deben bloquear el render completo.

## Límites y validación defensiva

- Duración admitida por escena: de 1 a 15 segundos; los valores no finitos o no numéricos se rechazan.
- Frecuencia admitida por el motor: de 12 a 30 FPS.
- Resolución del overlay: de 320×240 a 3840×2160; los tamaños fuera de rango se rechazan antes de crear los fotogramas.
- La salida transparente debe ser MOV con códec compatible con alfa.
- Las etiquetas se recortan para respetar el ancho disponible; los datos inválidos de una escena se omiten y no deben interrumpir el render principal.
- La prueba de render cubre los 15 tipos de escena, incluidos los cuatro estilos editoriales nuevos.

## Verificación

Ejecutar las pruebas del proyecto con el entorno normal de desarrollo. La prueba de render requiere FFmpeg instalado. No marcar el cambio como validado hasta ejecutar las pruebas y comprobar un MP4 real.
