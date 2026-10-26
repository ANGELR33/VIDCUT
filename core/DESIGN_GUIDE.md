# GUÍA DE DISEÑO OFICIAL: AETHERCUT STUDIO SIGNATURE PRO (2026)

Esta guía define los estándares inquebrantables de diseño, paleta, encuadres, física de movimiento y animación para todos los videos generados por el motor audiovisual de AetherCut AI.

---

## 1. PALETA DE COLORES & ATMÓSFERA STUDIO
* **Fondo Base**: `#08090d` (Negro mate espacial profundo, 100% sólido y limpio, SIN puntos, SIN cuadrículas ni efecto cuaderno).
* **Sombra Atmosférica Azul Noche**: `rgba(14, 28, 54, 0.30)` aplicada con desenfoque difuso orgánico de 160px en el tercio inferior izquierdo. Da profundidad pura sin estorbar.
* **Resplandor Blanco Cenital**: `rgba(255, 255, 255, 0.04)` difuso a 180px en el borde superior derecho para dar relieve de iluminación de estudio.
* **Obsidian Glass (Superficie de Tarjetas)**: Gradiente vertical `rgba(16, 21, 32, 0.90)` a `rgba(10, 14, 22, 0.95)` completamente uniforme y sólido.
* **Rim Light (Bisel de Cristal)**: Línea perimetral blanca ultra sutil `rgba(255, 255, 255, 0.22)` con esquinas redondeadas (radio: 16px - 22px).

### Acentos Cromáticos por Categoría
* **Cian Eléctrico (`#38bdf8`)**: Entradas sensoriales, datos auditados, conceptos clave y tecnología base.
* **Violeta Índigo (`#a855f7`)**: Capas de análisis, procesamiento abstracto, modelos de IA y síntesis.
* **Oro Ámbar Radiante (`#fbbf24`)**: Cifras récord, titular héroe ("PRO"), núcleo de pensamiento profundo y conclusiones críticas.
* **Verde Esmeralda (`#34d399`)**: Estados de confirmación, verificación y barras de activación positiva.

---

## 2. ENCUADRES & RETÍCULA CINEMATOGRÁFICA (SAFE ZONES - 1920x1080)
Para evitar cualquier colisión visual entre los gráficos explicativos y el presentador/avatar:

* **Zona Gráfica Principal (Tercio Izquierdo & Centro)**:
  * Coordenadas X: `80px` a `1300px`.
  * Aquí viven los diagramas de red, árboles de decisión, curvas de Bézier y titulares héroe.
* **Zona de Telemetría / HUD**:
  * Coordenadas X: `1340px` a `1820px` (cuando no hay PIP de avatar o cuando el presentador cede el protagonismo al dato).
* **Zona del Avatar / Streamer**:
  * PIP de esquina: `x = 1380px`, `y = 580px`, tamaño `420x420px` con bordes redondeados y sombra ambiental.
  * Margen de seguridad: mínimo `60px` de distancia entre cualquier elemento gráfico y el borde del recuadro del avatar.

---

## 3. FÍSICA DE MOVIMIENTO & ANIMACIÓN (MOTION GRAPHICS)
Las animaciones deben sentirse vivas, orgánicas y fluidas (estilo 3Blue1Brown + Manim + GSAP).

1. **Curvas de Bézier Cúbicas (Synaptic Flow)**:
   * Las líneas de interconexión nunca son rígidas. Se modelan con splines cúbicos suaves.
   * Los pulsos luminosos de datos viajan de nodo a nodo con una velocidad continua paramétrica (`pulse_progress = (t * speed + offset) % 1.0`).
2. **Respiración y Oscilación Armónica (Harmonic Breathing)**:
   * Los nodos y elementos centrales tienen una modulación senoidal sutil de ±5% en escala para transmitir vida biológica/tecnológica.
3. **Ensamble Escalonado (Staggered Assembly)**:
   * La tarjeta o contenedor entra primero (0.0s - 0.4s) con física elástica `ease_out_back`.
   * Los nodos y badges se despliegan en cascada con desfases de `80ms` a `120ms`.
   * El texto y las cifras entran con desvanecimiento de opacidad suave.
4. **Desarme Limpio (Clean Egress)**:
   * Salida rápida con aceleración cúbica (`ease_in_cubic`) y fade-out de 0.35s antes del corte de escena.

---

## 4. ASSET CANÓNICO
El archivo oficial de fondo pre-renderizado para todas las escenas de infografía y estudio está almacenado en:
`assets/aethercut_studio_matte_dark.jpg`
