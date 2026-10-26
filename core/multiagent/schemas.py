"""Definición de estructuras y datos compartidos del sistema multi-agente."""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AUDITING = "auditing"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AtomicTask(BaseModel):
    """Representa una tarea concreta asignada por el Arquitecto."""
    task_id: str
    title: str
    description: str
    target_files: List[str] = Field(default_factory=list)
    action_type: str = "create_or_modify"  # "create_or_modify", "test", "refactor"
    dependencies: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str = "implementer"  # "implementer", "architect"
    complexity: str = "light"  # "light" (GLM-5.3-flash) o "heavy" (GLM-5.3 Senior)
    assigned_model: str = "z-ai/glm-5.3-flash"
    attempt_count: int = 0
    max_attempts: int = 3
    
    # Código generado o propuesto
    proposed_code: Dict[str, str] = Field(default_factory=dict)  # filepath -> content
    
    # Auditoría y pruebas
    audit_notes: List[str] = Field(default_factory=list)
    test_results: List[Dict[str, Any]] = Field(default_factory=list)
    approved_by_auditor: bool = False
    error_feedback: Optional[str] = None


class ArchitecturePlan(BaseModel):
    """Plan maestro generado por GLM-5.3 (Arquitecto Líder)."""
    project_name: str
    summary: str
    architecture_overview: str
    components: List[Dict[str, str]] = Field(default_factory=list)
    tasks: List[AtomicTask] = Field(default_factory=list)
    suggested_tests: List[str] = Field(default_factory=list)


class AuditVerdict(BaseModel):
    """Veredicto emitido por Kimi-k3 (Auditor Independiente)."""
    approved: bool
    score: int = Field(ge=0, le=100)
    summary: str
    logic_errors_found: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    suggested_fixes: List[str] = Field(default_factory=list)
    run_tests_recommended: bool = True


class MultiAgentLogEntry(BaseModel):
    """Entrada individual de la bitácora de eventos del sistema multi-agente."""
    timestamp: float = Field(default_factory=time.time)
    agent: str  # "architect", "implementer", "auditor", "orchestrator"
    action: str
    details: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
