# Opciones de calidad, derechos y tecnologías opcionales

Todo está pensado para no romper nada: lo opcional viene apagado y, si falla, el sistema vuelve al comportamiento anterior.

| Variable | Valores | Qué hace |
|---|---|---|
| `LICENSE_POLICY` | `permissive` (defecto), `balanced`, `strict` | Qué B-Roll se rechaza por derechos. `permissive` solo registra y avisa. |
| `SOURCE_TRUST_STRICT` | `1` (defecto) / `0` | Un dato o corrección exige fuente oficial o dos independientes. |
| `FILLER_CUT` | `1` (defecto) / `0` | Corta muletillas y tartamudeos (máx. 6% del video). |
| `RELEVANCE_THRESHOLD` | `6` (defecto) | Puntaje mínimo (0-10) de relevancia visual del B-Roll. |
| `ALIGNER` | `off` (defecto) / `whisperx` | Afina los tiempos por palabra con alineación forzada. |
| `SEMANTIC_LIBRARY` | `0` (defecto) / `1` | Busca en `assets/broll` por significado (CLIP) y no por el nombre del archivo. |
| `VISUAL_DEDUPE` | `0` (defecto) / `1` | Evita repetir imágenes casi idénticas en un mismo video. |

## Control de derechos

Cada B-Roll queda clasificado como `cleared` (propio o dominio público), `attribution_required` (hay que citar),
`review` (uso editorial o de empresa) o `risky` (sin licencia clara o clip de YouTube). En cada proyecto se generan
en `assets/`:

- `rights_report.md` y `rights_report.json`: qué revisar antes de publicar.
- `credits.txt`: créditos listos para pegar en la descripción del video.

Es una ayuda para tu revisión, no asesoría legal. Para un canal monetizado usa `balanced` o `strict`.

## Cosas que no pude verificar con modelos reales

El código de WhisperX y CLIP se probó con modelos simulados, no con los reales. Antes de confiar en ellos:

1. Activa **una** opción a la vez en un video corto.
2. Revisa `run_events.jsonl`: el afinado indica `adoptado` o `descartado` y por qué.
3. Calibra `SEMANTIC_MIN_SCORE` y `DEDUPE_THRESHOLD` con tu propia biblioteca; los valores por defecto son orientativos.

## Animaciones de representación

Las frases con datos reciben una animación generada: cifra que cuenta (`counter`), barras comparativas
(`compare`) o pasos numerados (`steps`). Sin datos en la frase se genera una tarjeta del concepto.
Solo se anima lo que está escrito en la frase; nunca se inventan cifras.

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `ANIMATE_DATA` | 1 | Anima las frases con datos antes de buscar imagen real |
| `MOTION_FALLBACK` | 1 | Genera tarjeta de concepto si no hay imagen relevante |
| `REMOTION` | 0 | Usa Remotion en lugar del dibujo interno |

### Remotion (opcional, sin verificar)

El proyecto está en `remotion/` (composiciones `counter`, `compare` y `steps`). **No se pudo instalar ni
renderizar en el entorno donde se escribió**, por lo que su código no está probado. Para usarlo:

```bash
cd remotion && npm install
export REMOTION=1
# Si Remotion no descarga su propio Chrome: export REMOTION_BROWSER=/ruta/a/chromium
node render.mjs --spec ejemplo.json --out prueba.mp4   # prueba aislada
```

Ejemplo de `ejemplo.json`: `{"composition":"counter","props":{"title":"Inflación","durationSec":4,"palette":{"c1":"#141a3a","c2":"#2b3a8f","accent":"#ffc857"},"value":300,"prefix":"","suffix":"%","decimals":0}}`

Si falla, el sistema usa el renderizador interno automáticamente. Licencia: gratis para individuos y
equipos de hasta 3 personas; con 4 o más hay que pagar la licencia de empresa.
