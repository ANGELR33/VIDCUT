import asyncio
import json
import re
from pathlib import Path
from typing import List, Callable, Optional, Dict, Any
from config.settings import settings
from core.models import VideoEditingPlan, BRollCue
from core.asset_providers import AssetProviderFactory, AssetProvider
from core.relevance_gate import RelevanceJudge, is_relevant
from core.run_log import log_count, log_event

# Apoyos que el propio planificador marcó con poca seguridad se omiten sin buscar.
MIN_CUE_CONFIDENCE = 0.5


def enrich_query(query: str, topic: str) -> str:
    """Añade el tema del video a consultas cortas para desambiguar ("mercury" -> "mercury planet").

    No toca consultas largas ni las que ya contienen alguna palabra del tema.
    """
    query = (query or "").strip()
    topic = (topic or "").strip()
    if not query or not topic:
        return query
    words = query.split()
    if len(words) > 4:
        return query
    topic_words = {w.lower() for w in re.findall(r"[a-zA-Z0-9áéíóúñ]{3,}", topic)}
    if not topic_words or any(w.lower() in topic_words for w in re.findall(r"[a-zA-Z0-9áéíóúñ]{3,}", query)):
        return query
    return f"{query} {topic}"


class AssetOrchestrator:
    """
    Orquestador concurrente multi-agente para la resolución, búsqueda y descarga
    en paralelo de todos los recursos visuales (B-Roll) requeridos en el plan de edición.

    Cada recurso descargado pasa por un filtro de relevancia visual: si no ilustra lo
    que dice el hablante se descarta y se prueba el siguiente proveedor. Si ninguno
    pasa, el apoyo se omite.
    """

    def __init__(self, target_dir: Optional[Path] = None,
                 relevance_judge: Optional[RelevanceJudge] = None,
                 llm: Any = None):
        self.target_dir = target_dir or settings.ASSETS_DIR
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self.providers: List[AssetProvider] = AssetProviderFactory.get_providers()
        self.judge = relevance_judge or RelevanceJudge(llm=llm)
        self.topic = ""
        self.decisions: List[Dict[str, Any]] = []

    def _log(self, cue: BRollCue, provider: str, outcome: str, score=None, reason: str = "") -> None:
        self.decisions.append({
            "cue_id": cue.cue_id, "concept": cue.concept, "query": cue.search_query_en,
            "spoken_phrase": cue.spoken_phrase, "provider": provider, "outcome": outcome,
            "score": score, "reason": reason,
        })
        log_count(f"broll_{outcome}")
        if outcome != "accepted":
            log_event("broll", f"{cue.cue_id} {outcome}: {reason or cue.concept}",
                      level="info", provider=provider, score=score)

    async def _resolve_single_cue(
        self,
        cue: BRollCue,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> BRollCue:
        """Intenta descargar un asset relevante iterando por la cadena de proveedores."""
        cue.download_status = "DOWNLOADING"
        if progress_callback:
            progress_callback("broll_downloading", {"cue_id": cue.cue_id, "concept": cue.concept})

        for provider in self.providers:
            name = provider.__class__.__name__
            try:
                local_path = await provider.search_and_download(cue, self.target_dir)
                if not (local_path and local_path.exists()):
                    continue

                score, reason = await self.judge.score(
                    local_path, cue.concept, phrase=cue.spoken_phrase, topic=self.topic
                )
                if not is_relevant(score, self.judge.threshold):
                    local_path.unlink(missing_ok=True)
                    self._log(cue, name, "rejected", score, reason)
                    if progress_callback:
                        progress_callback("broll_rejected", {
                            "cue_id": cue.cue_id, "concept": cue.concept,
                            "provider": name, "score": score, "reason": reason,
                        })
                    continue

                cue.local_file_path = str(local_path)
                cue.download_status = "COMPLETED"
                cue.relevance_score = score
                cue.relevance_note = reason or ("Sin evaluación visual" if score is None else "")
                self._log(cue, name, "accepted", score, reason)
                if progress_callback:
                    progress_callback("broll_completed", {
                        "cue_id": cue.cue_id,
                        "path": str(local_path),
                        "provider": name,
                        "score": score,
                    })
                return cue
            except Exception as e:
                print(f"[AssetOrchestrator] Error en {name} para {cue.cue_id}: {e}")

        cue.download_status = "FAILED"
        cue.relevance_note = cue.relevance_note or "Ningún proveedor ofreció un recurso relevante."
        self._log(cue, "-", "no_relevant_asset")
        if progress_callback:
            progress_callback("broll_failed", {"cue_id": cue.cue_id, "concept": cue.concept})
        return cue

    def _write_decisions(self) -> None:
        try:
            (self.target_dir / "broll_decisions.json").write_text(
                json.dumps(self.decisions, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    async def process_all_brolls(
        self,
        plan: VideoEditingPlan,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> VideoEditingPlan:
        """
        Ejecuta la descarga paralela y no bloqueante de todos los B-Rolls del plan.
        """
        if not plan.b_rolls:
            print("[AssetOrchestrator] No hay B-Rolls definidos en el plan de edición.")
            return plan

        self.topic = (getattr(plan, "topic_en", "") or "").strip()

        active: List[BRollCue] = []
        for cue in plan.b_rolls:
            if cue.confidence < MIN_CUE_CONFIDENCE:
                cue.enabled = False
                cue.download_status = "FAILED"
                cue.relevance_note = f"Omitido: el planificador tenía poca seguridad ({cue.confidence:.2f})."
                self._log(cue, "-", "skipped_low_confidence", None, cue.relevance_note)
                if progress_callback:
                    progress_callback("broll_failed", {"cue_id": cue.cue_id, "concept": cue.concept})
                continue
            cue.search_query_en = enrich_query(cue.search_query_en, self.topic)
            active.append(cue)

        print(f"[AssetOrchestrator] Iniciando descarga concurrente de {len(active)} B-Roll cues "
              f"({len(plan.b_rolls) - len(active)} omitidos por baja confianza)...")

        await asyncio.gather(*[self._resolve_single_cue(cue, progress_callback) for cue in active])

        completed_count = sum(1 for c in plan.b_rolls if c.download_status == "COMPLETED")
        print(f"[AssetOrchestrator] Proceso completado: {completed_count}/{len(plan.b_rolls)} assets listos.")
        self._write_decisions()
        return plan

    def run_sync(
        self,
        plan: VideoEditingPlan,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> VideoEditingPlan:
        """Wrapper síncrono conveniente para llamadas desde hilos de renderizado."""
        return asyncio.run(self.process_all_brolls(plan, progress_callback))
