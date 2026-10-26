---
name: live-edit
description: Edición en vivo de la interfaz de AetherCut Studio con visualización en tiempo real (hot-reload). Úsala SIEMPRE que el usuario pida cambiar algo visual o del comportamiento del frontend (CSS, HTML, JS en web/) o quiera ver los cambios al instante en la app abierta — p. ej. "cambia el color y que se vea ya", "edítalo en vivo", "quiero verlo en tiempo real", "actualiza la interfaz sin recargar".
---

# Edición en vivo de la interfaz (hot-reload)

AetherCut ya está cableado para mostrar tus ediciones en pantalla al instante.
El navegador recibe cada acción vía SSE (`GET /api/oc/events`, puente en
`core/opencode_engine.py` → `push_action` hace broadcast) y la ejecuta al momento,
sin esperar a que termine el turno.

## Flujo recomendado

### 1. Cambios persistentes (la fuente de verdad es el disco)
1. Localiza el archivo (`grep`/`glob` en `web/static/css/**`, `web/static/js/**`, `web/templates/**`).
   Lée­lo antes de editarlo.
2. Edítalo con `edit`/`write`.
3. Llama a la herramienta `live_reload` con el path relativo (ej: `web/static/css/theme/matte-dark.css`):
   - **.css** → hot-swap: el frontend re-vincula las hojas de estilo con cache-bust
     e inyecta el CSS nuevo SIN recargar. El usuario no pierde el chat ni el estado.
   - **.js / .html / plantillas Jinja** → avisa con toast y recarga la página (~2 s).
4. Avisa al usuario con `notify_user` resumiendo lo aplicado.

### 2. Prototipado instantáneo (sin tocar archivos)
- `ui_action` con `ren_mutate {selector, operation, styles}`: muta el DOM en vivo al instante.
  Ideal para iterar con el usuario ("¿así o más grande?").
- `ren_reset`: deshace las mutaciones.
- Cuando el usuario apruebe, persiste el cambio en el archivo real (paso 1) y llama `live_reload`.
  OJO: lo mutado por REN se pierde al recargar; solo el disco es persistente.

### 3. Cambios en Python (backend)
- Los `.py` NO se aplican en vivo: el servidor corre con `reload=False` (server.py, `__main__`).
  Tras editar, comprueba con `app_status` que no haya tareas activas (renders, investigaciones)
  y pide/propón reiniciar el servidor.

## Detalles técnicos
- La acción `edit_file` con path `.css` inyecta `css_code` en `<style id="agentLiveAppliedStyles">`
  y re-vincula `link[rel="stylesheet"]` con `?v=<timestamp>`.
- Estáticos servidos con `Cache-Control: no-store` (`NoCacheStaticFiles`, server.py) → el
  navegador siempre recoge la versión nueva del disco.
- Jinja usa `auto_reload=True` → las plantillas se re-renderizan en la siguiente petición,
  sin reiniciar el servidor.
- Deduplicación: cada acción lleva `uid` (se asigna en `push_action`); el frontend guarda un
  set de uids vistos para no ejecutar dos veces la misma acción (SSE + drenaje del turno).
- CSS con selectores que no existen no da error: simplemente no se ve. Verifica el selector.

## Verificación
- Si el usuario no ve el cambio: confirma que la app está abierta y actualizada (F5),
  que el path de `live_reload` es correcto y que el selector CSS existe en el DOM actual.
