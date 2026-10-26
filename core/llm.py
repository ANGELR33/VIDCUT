import re
import sys
import time
from typing import Any, Callable, List, Optional

from google import genai
from google.genai import types

from config.settings import settings
from cancellation import CancellationRequested
from core.run_log import log_llm

# El orden se ha comprobado contra los proyectos configurados. Empezamos por el
# modelo que respondió y conservamos los demás para recuperarnos de una caída.
# 3.8 agotó el tiempo incluso con una consulta mínima durante la comprobación
# del 2026-10-05. Se excluye del camino crítico para no atascar cada proyecto.
FALLBACK_MODELS = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-latest"]


def safe_log(msg: str) -> None:
    """Imprime sin romper la consola de Windows con emojis u otros caracteres Unicode."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


import itertools
import threading

class LLMClient:
    """
    Cliente de Gemini con reintentos con espera, cadena de modelos de respaldo,
    y rotación entre claves para repartir solicitudes. Las claves no eliminan
    cuotas: Gemini las aplica por proyecto.
    """
    # Una petición multimodal sana responde antes de este límite. Si el modelo
    # queda en espera, se intenta 3.7 y luego otro proyecto en lugar de mostrar
    # una edición aparentemente congelada durante varios minutos.
    RESPONSE_TIMEOUT_MS = 65_000
    UPLOAD_TIMEOUT_MS = 180_000
    REQUEST_DEADLINE_SEC = 120
    PROJECT_FAILOVER_STATUSES = {401, 403, 408, 429, 500, 502, 503, 504}
    _key_cycles = {}
    _key_lock = threading.Lock()

    def __init__(self, api_key: Optional[str] = None, primary_model: Optional[str] = None):
        raw_keys = api_key or settings.GEMINI_API_KEY
        if not raw_keys or raw_keys == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY no configurada. Defínela en el archivo .env")
        
        # Split by comma for multiple keys
        self.api_keys = list(dict.fromkeys(k.strip() for k in raw_keys.split(",") if k.strip()))
        
        self._pool_id = tuple(self.api_keys)
        with LLMClient._key_lock:
            if self._pool_id not in LLMClient._key_cycles:
                LLMClient._key_cycles[self._pool_id] = itertools.cycle(self.api_keys)
        
        # We don't initialize a single client, we will initialize it per request 
        # or grab the next one to distribute the load.
        
        primary = primary_model or settings.GEMINI_MODEL or "gemini-flash-lite-latest"
        if "2.5" in primary or "3.8" in primary:
            primary = "gemini-flash-lite-latest"
        self.models: List[str] = [primary] + [m for m in FALLBACK_MODELS if m != primary]
        self.last_model_used: Optional[str] = None
        self._active_client = None
        self._active_api_key: Optional[str] = None
        
    def _get_next_client(self, timeout_ms: int):
        with LLMClient._key_lock:
            next_key = next(LLMClient._key_cycles[self._pool_id])
        self._active_api_key = next_key
        return genai.Client(api_key=next_key, http_options=types.HttpOptions(timeout=timeout_ms))

    def ordered_api_keys(self) -> List[str]:
        """Return the configured projects starting from the next round-robin key."""
        with LLMClient._key_lock:
            first = next(LLMClient._key_cycles[self._pool_id])
        start = self.api_keys.index(first)
        return self.api_keys[start:] + self.api_keys[:start]

    def client_for_key(self, api_key: str):
        """Create a client explicitly bound to one project's API key."""
        self._active_api_key = api_key
        self._active_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=self.UPLOAD_TIMEOUT_MS),
        )
        return self._active_client

    def _client_with_timeout(self, client, timeout_ms: int):
        """Keep the upload's project identity when a request references its file."""
        if client is None:
            return self._get_next_client(timeout_ms)
        api_key = self._active_api_key or getattr(client, "api_key", None)
        if api_key:
            return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))
        # SDK clients may not expose their key; retain the original client rather
        # than silently switching projects for a file uploaded through it.
        return client
        
    @property
    def client(self):
        self._active_client = self._get_next_client(self.UPLOAD_TIMEOUT_MS)
        return self._active_client

    @staticmethod
    def _status_of(exc: Exception) -> Optional[int]:
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if isinstance(code, int):
            return code
        text = str(exc)
        match = re.search(r"(?:^|HTTP\s+|code['\"]?\s*[:=]\s*)(504|503|502|500|429|408|404|403|401|400)\b", text, re.I)
        if match:
            return int(match.group(1))
        markers = {
            "RESOURCE_EXHAUSTED": 429,
            "PERMISSION_DENIED": 403,
            "UNAUTHENTICATED": 401,
            "UNAVAILABLE": 503,
        }
        for marker, status in markers.items():
            if marker in text.upper():
                return status
        return None

    def generate(self, contents: Any, json_mode: bool = False, attempts_per_model: int = 1,
                 use_search: bool = False, progress: Optional[Callable[[str], None]] = None,
                 client=None, cancel_event=None, max_models: Optional[int] = None,
                 deadline_sec: Optional[float] = None, thinking_budget: Optional[int] = None,
                 purpose: str = "") -> str:
        def report(message: str) -> None:
            if callable(progress):
                try:
                    progress(message)
                except Exception as exc:
                    safe_log(f"[LLM] No se pudo actualizar el progreso: {exc}")

        config_kwargs: dict = {
            "response_mime_type": "application/json" if json_mode else None,
            "tools": [{"google_search": {}}] if use_search else None,
        }
        if json_mode:
            # Decisiones editoriales reproducibles: sin temperatura alta el mismo video
            # daba planes distintos en cada ejecución.
            config_kwargs["temperature"] = 0.2
        if thinking_budget is not None:
            try:
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
            except Exception as _e:
                safe_log(f"[LLM] Aviso: thinking_config no admitido en entorno actual: {_e}")
        config = types.GenerateContentConfig(**config_kwargs)
        last_exc: Optional[Exception] = None
        req_deadline = deadline_sec if deadline_sec is not None else self.REQUEST_DEADLINE_SEC
        deadline = time.monotonic() + req_deadline

        models = self.models[:max_models] if max_models else self.models

        # Si se pasó un cliente específico (ej. upload multimodal vinculado a un proyecto concreto),
        # probar únicamente con ese cliente en los modelos permitidos.
        # Si NO se pasó cliente específico, rotar a través de las claves disponibles de Gemini.
        clients_to_try = [client] if client is not None else [self.client_for_key(k) for k in self.ordered_api_keys()]

        for active_client in clients_to_try:
            for model in models:
                for attempt in range(1, attempts_per_model + 1):
                    if cancel_event is not None and cancel_event.is_set():
                        raise CancellationRequested()
                    remaining = deadline - time.monotonic()
                    if remaining <= 2.0:
                        break
                    call_started = time.monotonic()
                    try:
                        report(f"Enviando solicitud a Gemini ({model}, intento {attempt}/{attempts_per_model}).")
                        timeout_val = max(25_000, min(self.RESPONSE_TIMEOUT_MS, int(remaining * 1000)))
                        request_client = self._client_with_timeout(
                            active_client, timeout_val)
                        response = request_client.models.generate_content(model=model, contents=contents, config=config)
                        text = response.text
                        if not text:
                            raise ValueError("respuesta vacía")
                        self.last_model_used = model
                        usage = getattr(response, "usage_metadata", None)
                        log_llm("gemini", model, purpose,
                                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
                                latency_sec=time.monotonic() - call_started)
                        return text
                    except Exception as exc:
                        if isinstance(exc, CancellationRequested):
                            raise
                        if cancel_event is not None and cancel_event.is_set():
                            raise CancellationRequested() from exc
                        last_exc = exc
                        status = self._status_of(exc)
                        log_llm("gemini", model, purpose, latency_sec=time.monotonic() - call_started,
                                ok=False, error=f"HTTP {status or 'n/d'}: {str(exc)[:150]}")
                        safe_log(f"[LLM] {model} intento {attempt}/{attempts_per_model} falló ({status or 'error'}): {str(exc)[:110]}")
                        if status in (404, 400):
                            report(f"Gemini rechazó {model}; probando el siguiente modelo disponible.")
                            break  # el modelo no existe o la petición es inválida para este modelo
                        if status in (401, 403, 429, 500, 502, 503, 504):
                            # Rotar de inmediato a la siguiente clave/proyecto de Gemini
                            break
                        delay = min(2 * attempt, 3)
                        time.sleep(delay)

        # Si todas las claves/modelos de Gemini fallaron o se saturaron, recurrir a NVIDIA como respaldo
        # (siempre que el prompt sea de texto)
        if isinstance(contents, (str, list)) and getattr(settings, "NVIDIA_API_KEY", None):
            # Extraer prompt textual
            text_prompt = ""
            if isinstance(contents, str):
                text_prompt = contents
            elif isinstance(contents, list):
                text_parts = [c for c in contents if isinstance(c, str)]
                if text_parts:
                    text_prompt = "\n\n".join(text_parts)

            if text_prompt:
                report("Gemini saturado o con cuota agotada. Activando respaldo de alta velocidad NVIDIA...")
                safe_log(f"[LLM] Fallback automático a API de NVIDIA...")
                try:
                    nv_res = self._generate_with_nvidia(text_prompt, json_mode=json_mode, report=report)
                    if nv_res:
                        return nv_res
                except Exception as nv_exc:
                    safe_log(f"[LLM] Error en fallback de NVIDIA: {nv_exc}")

        status = self._status_of(last_exc) if last_exc else None
        if status is not None:
            raise GeminiAPIError(status, str(last_exc)) from last_exc
        raise RuntimeError(f"Ningún proveedor de IA (Gemini ni NVIDIA) respondió. Último error: {last_exc}")

    def _generate_with_nvidia(self, prompt: str, json_mode: bool = False, report: Optional[Callable[[str], None]] = None) -> str:
        """Generador de respaldo usando NVIDIA AI Foundations (OpenAI compatible)."""
        from openai import OpenAI
        api_key = getattr(settings, "NVIDIA_API_KEY", "")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY no configurada")

        candidate_models = [
            getattr(settings, "NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"),
            "nvidia/nemotron-3.5-lightning-30b-a3b",
            "meta/llama-3.2-11b-vision-instruct",
        ]
        # Quitar duplicados conservando orden
        models = list(dict.fromkeys(candidate_models))

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            timeout=45.0,
        )

        system_instruction = (
            "Eres un asistente de producción, diseño visual y redacción audiovisual de élite. "
            "Responde estrictamente con la información solicitada."
        )
        if json_mode:
            system_instruction += " DEBES RESPONDER EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO. Sin explicaciones previas ni posteriores, sin bloques markdown innecesarios."

        last_error = None
        for m in models:
            try:
                if report:
                    model_display = "Nemotron" if "nemotron" in m.lower() else ("Llama" if "llama" in m.lower() else m)
                    report(f"Razonando con {model_display} ({m})...")
                safe_log(f"[LLM] Enviando petición a NVIDIA model={m}...")
                create_kwargs = {
                    "model": m,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.4,
                    "max_tokens": 12000,
                }
                if "nemotron" in m.lower():
                    create_kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": not json_mode}}
                elif "kimi" in m.lower():
                    create_kwargs["temperature"] = 0.7

                nv_started = time.monotonic()
                response = client.chat.completions.create(**create_kwargs)
                msg = response.choices[0].message
                content_text = (msg.content or "").strip()
                reasoning_text = (getattr(msg, "reasoning_content", "") or "").strip()
                text = content_text or reasoning_text
                nv_usage = getattr(response, "usage", None)
                log_llm("nvidia", m, "respaldo", fallback=True, ok=bool(text),
                        input_tokens=int(getattr(nv_usage, "prompt_tokens", 0) or 0),
                        output_tokens=int(getattr(nv_usage, "completion_tokens", 0) or 0),
                        latency_sec=time.monotonic() - nv_started)
                if text:
                    self.last_model_used = f"nvidia:{m}"
                    safe_log(f"[LLM] Respuesta exitosa obtenida desde NVIDIA ({m}).")
                    return text
            except Exception as exc:
                last_error = exc
                safe_log(f"[LLM] NVIDIA model={m} falló: {exc}")
                continue

        raise RuntimeError(f"Ningún modelo de NVIDIA respondió: {last_error}")


class GeminiAPIError(RuntimeError):
    """API failure retaining its HTTP status for safe project failover."""

    def __init__(self, status: int, detail: str):
        self.status = status
        # Do not include request details that might contain file URIs or credentials.
        labels = {
            401: "la clave no fue aceptada",
            403: "el proyecto no tiene permiso para esta operación",
            429: "se alcanzó la cuota temporal de este proyecto",
            500: "Gemini devolvió un error interno",
            502: "Gemini devolvió un error de puerta de enlace",
            503: "el modelo está temporalmente saturado",
            504: "Gemini agotó el tiempo de respuesta",
        }
        super().__init__(labels.get(status, f"Gemini respondió HTTP {status}"))
