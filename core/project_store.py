"""Persistencia local de un proyecto de edición.

El render puede tardar, pero la decisión editorial no debe desaparecer cuando el
servidor se reinicia. Cada proyecto conserva el plan, las fuentes, los assets y
las versiones exportadas para poder revisarlo y volver a renderizarlo.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings
from core.models import VideoEditingPlan


class ProjectStore:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.root = settings.PROJECTS_DIR / project_id
        self.workdir = self.root / "work"
        self.manifest_path = self.root / "project.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.workdir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def read(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"No existe el proyecto {self.project_id}.")
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def write(self, document: Dict[str, Any]) -> Dict[str, Any]:
        document.setdefault("id", self.project_id)
        document["updated_at"] = self._now()
        temp = self.manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.manifest_path)
        return document

    def create(self, *, source_file: Path, original_name: str, options: Dict[str, Any]) -> Dict[str, Any]:
        now = self._now()
        return self.write({
            "id": self.project_id,
            "created_at": now,
            "source_file": str(source_file.resolve()),
            "original_name": original_name,
            "options": options,
            "status": "queued",
            "plan": None,
            "result": None,
            "preview_file": None,
        })

    def set_status(self, status: str, **extra: Any) -> Dict[str, Any]:
        doc = self.read()
        doc["status"] = status
        # Un estado nuevo que no sea error limpia el error anterior: si una
        # transmisión falló y luego se reanudó con éxito, project.json no debe
        # seguir mostrando el mensaje de error viejo junto a "done".
        if status != "error":
            doc.pop("error", None)
        doc.update(extra)
        return self.write(doc)

    def save_plan(self, plan: Any, **extra: Any) -> Dict[str, Any]:
        doc = self.read()
        if hasattr(plan, "model_dump"):
            doc["plan"] = plan.model_dump(mode="json")
        elif isinstance(plan, dict):
            doc["plan"] = plan
        else:
            doc["plan"] = getattr(plan, "to_dict", lambda: plan)()
        doc.update(extra)
        return self.write(doc)

    def load_plan(self) -> VideoEditingPlan:
        doc = self.read()
        if not doc.get("plan"):
            raise ValueError("El proyecto aún no tiene un plan de edición.")
        return VideoEditingPlan.model_validate(doc["plan"])

    def delete(self, include_source: bool = True, include_outputs: bool = True) -> Dict[str, Any]:
        """Elimina el proyecto y sus recursos asociados liberando espacio en disco."""
        import shutil
        freed_bytes = 0
        try:
            doc = self.read()
            if include_source:
                src = Path(doc.get("source_file") or "")
                if src.exists() and src.is_file():
                    freed_bytes += src.stat().st_size
                    src.unlink(missing_ok=True)
            if include_outputs:
                for out_file in settings.OUTPUTS_DIR.glob(f"{self.project_id}_*"):
                    if out_file.is_file():
                        freed_bytes += out_file.stat().st_size
                        out_file.unlink(missing_ok=True)
                for out_file in settings.OUTPUTS_DIR.glob(f"short_*_{self.project_id}_*"):
                    if out_file.is_file():
                        freed_bytes += out_file.stat().st_size
                        out_file.unlink(missing_ok=True)
        except Exception:
            pass

        if self.root.exists():
            for f in self.root.rglob("*"):
                if f.is_file():
                    freed_bytes += f.stat().st_size
            shutil.rmtree(self.root, ignore_errors=True)
        return {"freed_bytes": freed_bytes}


def editor_snapshot(plan: VideoEditingPlan) -> Dict[str, Any]:
    """Versión compacta y segura para actualizar el editor en el navegador."""
    return {
        "summary": plan.video_summary,
        "duration": plan.total_original_duration_sec,
        "cuts": [s.model_dump(mode="json") for s in plan.timeline if s.action != "KEEP"],
        "cards": [
            {
                "id": c.card_id, "start": c.start_sec, "end": c.end_sec,
                "duration": c.display_duration_sec, "headline": c.headline,
                "kind": c.kind, "claim": c.claim, "verdict": c.verdict,
                "stat_value": c.stat_value, "correction": c.correction,
                "corrected_value": c.corrected_value,
                "avatar_spoken_text": c.avatar_spoken_text,
                "avatar_enabled": getattr(c, "avatar_enabled", False),
                "note": c.note, "body": c.body, "position": c.screen_position,
                "enabled": c.enabled, "sources": [s.model_dump() for s in c.sources],
            }
            for c in plan.info_cards
        ],
        "brolls": [
            {
                "id": b.cue_id, "start": b.start_sec, "end": b.end_sec,
                "concept": b.concept, "status": b.download_status,
                "enabled": b.enabled,
            }
            for b in plan.b_rolls
        ],
        "shorts": [
            {
                "id": h.clip_id, "start": h.start_sec, "end": h.end_sec,
                "title": h.title, "hook": h.hook, "score": h.virality_score,
            }
            for h in plan.highlights
        ],
    }
