import time
from pathlib import Path
from threading import Event
from typing import Callable, Optional

from google.genai import types

from config.settings import settings
from cancellation import CancellationRequested
from core.llm import GeminiAPIError, LLMClient, safe_log
from core.models import VideoEditingPlan
from core.prompt_templates import build_editor_prompt
from utils.json_validator import JSONValidator, JSONParsingError

__all__ = ["GeminiVideoAnalyzer", "safe_log"]


class GeminiVideoAnalyzer:
    """
    Sube el video a la File API de Gemini y obtiene el plan de edición estructurado (JSON validado).
    Usa LLMClient: reintentos con espera y modelos de respaldo ante 503/429.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None,
                 llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient(api_key=api_key, primary_model=model_name)
        self.client = None

    def _upload_and_wait(self, file_path: Path, client,
                         progress: Optional[Callable[[str], None]] = None,
                         project_label: str = "", cancel_event: Optional[Event] = None):
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo de video no existe en: {file_path}")

        say = progress or (lambda _m: None)
        safe_log(f"[GeminiAnalyzer] Subiendo {file_path.name}...")
        say(f"Subiendo el video a Gemini ({project_label})...")
        uploaded = client.files.upload(file=str(file_path))
        try:
            waited = 0
            while uploaded.state == types.FileState.PROCESSING:
                if cancel_event is not None and cancel_event.is_set():
                    raise CancellationRequested()
                time.sleep(4)
                waited += 4
                say(f"{project_label}: Gemini está preparando el archivo ({waited} s).")
                uploaded = client.files.get(name=uploaded.name)
                if waited > 300:
                    raise TimeoutError("Gemini tardó más de 5 minutos preparando el archivo.")

            if uploaded.state == types.FileState.FAILED:
                raise RuntimeError(f"Gemini no pudo procesar el video: {uploaded.error}")
            safe_log(f"[GeminiAnalyzer] Video listo ({uploaded.state}).")
            return uploaded
        except Exception:
            try:
                client.files.delete(name=uploaded.name)
            except Exception as cleanup_exc:
                safe_log(f"[GeminiAnalyzer] No se pudo borrar el archivo fallido de {project_label}: {cleanup_exc}")
            raise

    def analyze_video(
        self,
        video_path: Path,
        silence_threshold: Optional[float] = None,
        max_cards: int = 8,
        progress: Optional[Callable[[str], None]] = None,
        transcript: str = None,
        cancel_event: Optional[Event] = None,
    ) -> VideoEditingPlan:
        threshold = silence_threshold or settings.MAX_SILENCE_DURATION_SEC
        prompt = build_editor_prompt(silence_threshold=threshold, max_cards=max_cards, transcript=transcript)
        api_keys = self.llm.ordered_api_keys()
        last_error = None

        for index, api_key in enumerate(api_keys, start=1):
            if cancel_event is not None and cancel_event.is_set():
                raise CancellationRequested()
            project_label = f"Proyecto {index} de {len(api_keys)}"
            client = None
            uploaded = None
            try:
                client = self.llm.client_for_key(api_key)
                uploaded = self._upload_and_wait(video_path, client, progress, project_label, cancel_event)
                if progress:
                    progress(f"{project_label}: archivo listo. Enviando el análisis con {self.llm.models[0]}.")

                raw = self.llm.generate(
                    [uploaded, prompt], json_mode=True, progress=progress, client=client,
                    cancel_event=cancel_event, purpose="plan_edicion",
                    # Probar el modelo principal de este proyecto; si está saturado (503),
                    # saltar de inmediato al siguiente proyecto sin perder minutos probando modelos viejos.
                    max_models=1,
                )
                safe_log(f"[GeminiAnalyzer] Respuesta recibida de {self.llm.last_model_used}. Validando JSON...")
                plan = JSONValidator.validate_editing_plan(raw)
                safe_log(
                    f"[GeminiAnalyzer] Plan: {len(plan.timeline)} segmentos, {len(plan.b_rolls)} B-Rolls, "
                    f"{len(plan.info_cards)} datos a verificar, {len(plan.highlights)} clips cortos."
                )
                return plan
            except JSONParsingError as exc:
                safe_log(f"[GeminiAnalyzer] JSON inválido de Gemini: {exc}")
                raise
            except Exception as exc:
                if isinstance(exc, CancellationRequested):
                    raise
                if cancel_event is not None and cancel_event.is_set():
                    raise CancellationRequested() from exc
                status = getattr(exc, "status", None) or self.llm._status_of(exc)
                if status not in self.llm.PROJECT_FAILOVER_STATUSES:
                    raise
                last_error = exc if isinstance(exc, GeminiAPIError) else GeminiAPIError(status, str(exc))
                safe_log(f"[GeminiAnalyzer] {project_label} falló con HTTP {status}; rotando inmediatamente al siguiente proyecto.")
                if progress and index < len(api_keys):
                    progress(
                        f"{project_label} ocupado en Google (HTTP {status}). "
                        f"Rotando al Proyecto {index + 1} de {len(api_keys)}..."
                    )
            finally:
                if uploaded and client:
                    try:
                        client.files.delete(name=uploaded.name)
                    except Exception as exc:
                        safe_log(f"[GeminiAnalyzer] No se pudo borrar el archivo remoto de {project_label}: {exc}")

        # Si los servidores de video de Gemini están saturados pero tenemos transcripción de audio:
        if transcript:
            safe_log("[GeminiAnalyzer] Servidores de video de Gemini saturados (503). Continuando análisis con transcripción de audio...")
            if progress:
                progress("Servidores de video de Google en alta demanda temporal; completando análisis con transcripción de audio...")
            for index, api_key in enumerate(api_keys, start=1):
                try:
                    client = self.llm.client_for_key(api_key)
                    raw = self.llm.generate(
                        [prompt], json_mode=True, progress=progress, client=client,
                        cancel_event=cancel_event, max_models=1, purpose="plan_edicion_transcripcion",
                    )
                    safe_log(f"[GeminiAnalyzer] Plan generado exitosamente con transcripción usando {self.llm.last_model_used}.")
                    return JSONValidator.validate_editing_plan(raw)
                except Exception as exc:
                    safe_log(f"[GeminiAnalyzer] Análisis con transcripción en proyecto {index} falló: {exc}")
                    continue

        if isinstance(last_error, GeminiAPIError):
            raise RuntimeError(
                f"Gemini no pudo analizar el video con ninguno de los {len(api_keys)} proyectos configurados. "
                f"Último estado HTTP: {last_error.status}. Revisa las cuotas y permisos de los proyectos."
            ) from last_error
        raise RuntimeError(f"Gemini no pudo analizar el video con los {len(api_keys)} proyectos configurados.") from last_error
