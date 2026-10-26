"""Sistema de registro estructurado y persistencia de eventos para el equipo multi-agente."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.multiagent.schemas import MultiAgentLogEntry, TaskStatus


class MultiAgentLogger:
    """Registra en memoria y en disco (JSON / Markdown) las decisiones, diffs y resultados de pruebas."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path("storage/multiagent_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = f"session_{int(time.time())}"
        self.session_file = self.log_dir / f"{self.session_id}.jsonl"
        self.entries: List[MultiAgentLogEntry] = []

    def log(self, agent: str, action: str, details: str, metadata: Optional[Dict[str, Any]] = None) -> MultiAgentLogEntry:
        entry = MultiAgentLogEntry(
            timestamp=time.time(),
            agent=agent,
            action=action,
            details=details,
            metadata=metadata or {},
        )
        self.entries.append(entry)
        
        # Escribir en archivo JSONL para streaming y persistencia inmediata
        try:
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception:
            pass
        return entry

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self.entries[-limit:]]

    def export_markdown_report(self, title: str = "Informe de Sesión Multi-Agente") -> str:
        """Genera un informe completo en Markdown con resumen de arquitectura, decisiones y tests."""
        lines = [
            f"# {title}",
            f"**Sesión:** `{self.session_id}` | **Eventos registrados:** {len(self.entries)}",
            "",
            "## Registro Cronológico de Colaboración",
            "| Tiempo | Agente | Acción | Resumen |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for e in self.entries:
            t_str = time.strftime("%H:%M:%S", time.localtime(e.timestamp))
            agent_badge = {
                "architect": "🏛️ Arquitecto (GLM-5.3)",
                "implementer": "⚡ Implementador (GLM-5.3-flash)",
                "auditor": "🔍 Auditor (Kimi-k3)",
                "orchestrator": "🎯 Orquestador Central",
            }.get(e.agent, e.agent)
            
            clean_det = e.details.replace("\n", " ")[:90] + ("..." if len(e.details) > 90 else "")
            lines.append(f"| `{t_str}` | {agent_badge} | **{e.action}** | {clean_det} |")

        report_md = "\n".join(lines)
        report_path = self.log_dir / f"{self.session_id}_report.md"
        report_path.write_text(report_md, encoding="utf-8")
        return report_md
