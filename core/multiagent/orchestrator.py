"""Orquestador Central del Sistema Multi-Agente:
- Coordina el flujo de trabajo entre GLM-5.3, GLM-5.3-flash y Kimi-k3.
- Ejecuta las tareas respetando dependencias.
- Maneja el ciclo de reintentos con auditoría automática.
- Genera informes de progreso y resultados.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.multiagent.agents import ArchitectAgent, ImplementerAgent, AuditorAgent
from core.multiagent.logger import MultiAgentLogger
from core.multiagent.schemas import (
    ArchitecturePlan,
    AtomicTask,
    AuditVerdict,
    TaskStatus,
)


class MultiAgentOrchestrator:
    """Orquestador central que lidera el ciclo autónomo de desarrollo."""

    def __init__(self, workspace_root: Optional[Path] = None, audit_mode: str = "analysis"):
        self.root = workspace_root or Path(".")
        self.logger = MultiAgentLogger(self.root / "storage/multiagent_logs")
        self.audit_mode = audit_mode
        self.architect = ArchitectAgent()
        self.implementer = ImplementerAgent()
        self.auditor = AuditorAgent(mode=audit_mode)

        self.current_plan: Optional[ArchitecturePlan] = None
        self.is_running = False

    def _read_file_safe(self, rel_path: str) -> str:
        p = self.root / rel_path
        if p.exists() and p.is_file():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""

    def _write_file_safe(self, rel_path: str, content: str):
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    async def execute_project(
        self,
        project_description: str,
        max_attempts_per_task: int = 3,
        progress_cb: Optional[Callable[[str, float, Optional[Dict[str, Any]]], None]] = None,
    ) -> Dict[str, Any]:
        """Ejecuta el ciclo de desarrollo completo de principio a fin."""
        self.is_running = True
        self.logger.log(
            "orchestrator",
            "INIT_PROJECT",
            f"Iniciando proyecto: {project_description[:100]}...",
            {"description": project_description},
        )

        def report(msg: str, pct: float, extra: Optional[Dict[str, Any]] = None):
            if progress_cb:
                try:
                    progress_cb(msg, pct, extra)
                except TypeError:
                    progress_cb(msg, pct)

        # FASE 1: Planificación y Delegación Ágil (GLM-5.3-flash)
        report(
            "⚡ GLM-5.3-flash (Delegador): Descomponiendo requerimiento y delegando tareas...",
            10.0,
            {
                "agent": "planner",
                "model": "z-ai/glm-5.3-flash",
                "action": "Planificando y delegando tareas atómicas",
                "reasoning": "Analizando dependencias de archivos, aislando componentes y preparando tareas para el Ingeniero Senior...",
            },
        )
        self.logger.log("planner", "START_PLANNING", "Planificando arquitectura y delegando tareas")

        def on_arch_reasoning(live_text: str):
            report(
                "⚡ GLM-5.3-flash: Descomponiendo y delegando tareas en vivo...",
                12.0,
                {
                    "agent": "planner",
                    "model": "z-ai/glm-5.3-flash",
                    "action": "Descomponiendo requerimiento en tareas atómicas",
                    "reasoning": live_text,
                },
            )

        try:
            plan = await asyncio.to_thread(
                self.architect.create_architecture_plan,
                project_description=project_description,
                on_reasoning=on_arch_reasoning,
            )
            self.current_plan = plan
            arch_reasoning = getattr(self.architect.model, "last_reasoning", "") or "Plan y delegación generados con éxito."
            self.logger.log(
                "planner",
                "PLAN_CREATED",
                f"Plan creado con éxito: {len(plan.tasks)} tareas delegadas.",
                {"plan_summary": plan.summary, "tasks_count": len(plan.tasks)},
            )
            report(
                f"⚡ GLM-5.3-flash: {len(plan.tasks)} tareas delegadas para GLM-5.3",
                18.0,
                {
                    "agent": "planner",
                    "model": "z-ai/glm-5.3-flash",
                    "action": f"Plan creado: {plan.project_name}",
                    "reasoning": arch_reasoning,
                    "plan": plan.model_dump(),
                },
            )
        except Exception as exc:
            self.logger.log("planner", "PLAN_ERROR", f"Error en fase de delegación: {exc}")
            self.is_running = False
            raise RuntimeError(f"Fallo al generar plan de arquitectura: {exc}")

        # FASE 1.5: Inducción de Contexto al Auditor (Kimi-k3 se empapa del proyecto existente)
        report(
            "🔍 Kimi-k3: Escaneando funcionalidades existentes del proyecto para prevenir daños...",
            19.0,
            {
                "agent": "auditor",
                "model": "moonshotai/kimi-k3",
                "action": "Indexando funcionalidades para QA y preservación",
                "reasoning": "Leyendo árbol del proyecto, identificando módulos de video, streaming, audio, render y web...",
            },
        )
        # Construir inventario de funcionalidades clave del proyecto
        key_modules = [
            "core/streamer_pipeline.py",
            "core/scene_engine.py",
            "core/render_engine.py",
            "core/avatar_narrator.py",
            "core/subtitle_generator.py",
            "core/fact_checker.py",
            "core/card_renderer.py",
            "server.py",
        ]
        inventory_items = []
        for km in key_modules:
            p_km = self.root / km
            if p_km.exists():
                size_kb = p_km.stat().st_size / 1024
                inventory_items.append(f"- {km} (~{size_kb:.1f} KB): Módulo crítico del motor.")
        inventory_text = (
            "COMPONENTES ACTIVOS EN EL PROYECTO (PROHIBIDO ROMPER):\n"
            + "\n".join(inventory_items)
            + "\nREGLA ESTRICTA: Cualquier cambio debe ser compatible hacia atrás. Mantener todas las firmas públicas y APIs existentes."
        )
        self.auditor.load_project_context(inventory_text)
        self.logger.log("auditor", "CONTEXT_LOADED", "Kimi-k3 memorizó el mapa del proyecto.", {"inventory": inventory_items})

        # FASE 2: Ejecución Colaborativa de Tareas (Flash y Senior según complejidad)
        total_tasks = len(plan.tasks)
        completed_tasks = 0

        for idx, task in enumerate(plan.tasks):
            task.max_attempts = max_attempts_per_task
            task.status = TaskStatus.IN_PROGRESS
            progress_base = 20.0 + (float(idx) / max(1, total_tasks)) * 70.0

            is_light = (task.complexity == "light") or ("flash" in (task.assigned_model or "").lower())
            worker_icon = "⚡" if is_light else "🏛️"
            worker_name = "GLM-5.3-flash (Ágil)" if is_light else "GLM-5.3 (Senior)"
            worker_model = "z-ai/glm-5.3-flash" if is_light else "z-ai/glm-5.3"
            worker_role = "tarea ligera / soporte" if is_light else "tarea pesada"

            report(
                f"{worker_icon} {worker_name}: Ejecutando {worker_role} [{task.task_id}] {task.title}...",
                progress_base,
                {
                    "agent": "implementer",
                    "model": worker_model,
                    "action": f"Ejecutando {worker_role}: {task.title}",
                    "reasoning": f"Construyendo lógica y componentes en archivos: {', '.join(task.target_files)}",
                    "task_id": task.task_id,
                },
            )
            self.logger.log(
                "implementer",
                "START_TASK",
                f"Iniciando {worker_role} {task.task_id}: {task.title} con {worker_name}",
                {"target_files": task.target_files, "complexity": task.complexity, "model": worker_model},
            )

            # Contexto previo de los archivos objetivo si ya existen
            existing_ctx = {}
            for tf in task.target_files:
                tf_content = self._read_file_safe(tf)
                if tf_content:
                    existing_ctx[tf] = tf_content
                    fsize = len(tf_content.encode("utf-8"))
                    report(
                        f"📖 Leyendo: {tf} ({fsize} bytes)...",
                        progress_base + 1.0,
                        {
                            "agent": "implementer",
                            "model": worker_model,
                            "action": f"📖 Leyendo archivo: {tf}",
                            "file_op": {"type": "read", "file": tf, "bytes": fsize},
                            "reasoning": f"Analizando estructura previa de {tf} para preservar lo que ya sirve...",
                        },
                    )

            # Ciclo de Implementación -> Auditoría -> Reintento
            error_feedback = None
            task_passed = False

            while task.attempt_count < task.max_attempts and not task_passed:
                task.attempt_count += 1
                try:
                    def on_impl_reasoning(live_text: str):
                        report(
                            f"{worker_icon} {worker_name}: Razonando código para [{task.task_id}]...",
                            progress_base + 2.0,
                            {
                                "agent": "implementer",
                                "model": worker_model,
                                "action": f"Razonando implementación de {task.task_id}",
                                "reasoning": live_text,
                            },
                        )

                    # 1. El modelo asignado (Flash o Senior) genera el código
                    code_map = await asyncio.to_thread(
                        self.implementer.implement_task,
                        task=task,
                        architecture_summary=plan.architecture_overview,
                        context_files=existing_ctx,
                        error_feedback=error_feedback,
                        on_reasoning=on_impl_reasoning,
                    )
                    task.proposed_code = code_map
                    impl_reasoning = getattr(
                        self.implementer.flash_model if is_light else self.implementer.senior_model,
                        "last_reasoning",
                        ""
                    ) or "Código generado de acuerdo a especificaciones."

                    report(
                        f"{worker_icon} {worker_name}: Código completado para [{task.task_id}]",
                        progress_base + 4.0,
                        {
                            "agent": "implementer",
                            "model": worker_model,
                            "action": f"Código completado para {list(code_map.keys())}",
                            "reasoning": impl_reasoning,
                            "files_changed": list(code_map.keys()),
                        },
                    )

                    # 2. Auditor Kimi-k3 examina el código
                    report(
                        f"🔍 Kimi-k3: Auditando calidad y lógica de [{task.task_id}]...",
                        progress_base + 6.0,
                        {
                            "agent": "auditor",
                            "model": "moonshotai/kimi-k3",
                            "action": f"Auditando {task.task_id} (Intento {task.attempt_count})",
                            "reasoning": "Analizando lógica, riesgos de regresión, integridad de funciones previas y pruebas...",
                        },
                    )
                    self.logger.log("auditor", "AUDITING_CODE", f"Inspeccionando {list(code_map.keys())}")

                    verdict = await asyncio.to_thread(
                        self.auditor.audit_code,
                        task=task,
                        proposed_code=code_map,
                        project_context=plan.summary,
                    )
                    task.audit_notes.append(f"Intento {task.attempt_count}: Score={verdict.score} - {verdict.summary}")
                    audit_reasoning = getattr(self.auditor.model, "last_reasoning", "") or verdict.summary

                    # 3. Verificación de sintaxis automatizada determinística
                    syntax_errors = []
                    # Respaldar archivos existentes por si la auditoría falla
                    backups = {}
                    for tf_path in code_map.keys():
                        t_path = self.root / tf_path
                        if t_path.exists():
                            backups[tf_path] = t_path.read_text(encoding="utf-8")
                        else:
                            backups[tf_path] = None

                    # Escribir código propuesto en disco y verificar sintaxis
                    for tf_path, tf_code in code_map.items():
                        tmp_target = self.root / tf_path
                        tmp_target.parent.mkdir(parents=True, exist_ok=True)
                        tmp_target.write_text(tf_code, encoding="utf-8")
                        fsize = len(tf_code.encode("utf-8"))
                        report(
                            f"✍️ Escribiendo en disco: {tf_path} ({fsize} bytes)...",
                            progress_base + 5.0,
                            {
                                "agent": "implementer",
                                "model": worker_model,
                                "action": f"✍️ Modificando archivo: {tf_path}",
                                "file_op": {"type": "write", "file": tf_path, "bytes": fsize},
                                "reasoning": f"Consolidando cambios directamente en {tf_path}...",
                            },
                        )
                        s_check = self.auditor.run_automated_syntax_check(tmp_target)
                        if not s_check["passed"]:
                            syntax_errors.append(f"{tf_path}: {s_check['stderr']}")

                    # En Modo Análisis, si la sintaxis pasa y no hay error fatal, se preserva el trabajo para que el usuario decida al final
                    is_analysis_mode = (getattr(self.auditor, "mode", "analysis") == "analysis")
                    approved_or_accepted = (verdict.approved or (is_analysis_mode and not syntax_errors))

                    if approved_or_accepted and not syntax_errors:
                        task.status = TaskStatus.PASSED
                        task.approved_by_auditor = verdict.approved
                        task_passed = True
                        approval_note = "Aprobado" if verdict.approved else "Aceptado en Modo Análisis (Observación sin bloqueo)"
                        self.logger.log(
                            "auditor",
                            "TASK_APPROVED",
                            f"Tarea {task.task_id} {approval_note} (Score {verdict.score}/100). Archivos guardados en disco.",
                            {"score": verdict.score, "summary": verdict.summary, "files": list(code_map.keys()), "mode": self.auditor.mode},
                        )
                        report(
                            f"✅ {approval_note}: [{task.task_id}] (Score {verdict.score}/100)",
                            progress_base + 8.0,
                            {
                                "agent": "auditor",
                                "model": "moonshotai/kimi-k3",
                                "action": f"{approval_note} - Score {verdict.score}/100",
                                "reasoning": f"Evaluación de Kimi-k3 ({'Modo Análisis' if is_analysis_mode else 'Modo Administrador'}): {verdict.summary}",
                            },
                        )
                    else:
                        # Falló: revertir cambios a los archivos para no dañar el proyecto
                        for tf_path, original_content in backups.items():
                            t_path = self.root / tf_path
                            if original_content is not None:
                                t_path.write_text(original_content, encoding="utf-8")
                            elif t_path.exists():
                                t_path.unlink()

                        issues = verdict.logic_errors_found + verdict.missing_requirements + syntax_errors
                        error_feedback = (
                            f"[FEEDBACK EN CALIENTE DE KIMI-K3 (QA) A {worker_name}]:\n"
                            + "Oye, se detectaron estos problemas o posibles afectaciones al proyecto existente:\n- "
                            + "\n- ".join(issues)
                            + f"\nSugerencias de Kimi-k3:\n- "
                            + "\n- ".join(verdict.suggested_fixes or ["Corrige los fallos puntuales sin alterar lo demás."])
                            + "\nPor favor corrige únicamente este punto en el siguiente intento sin borrar ni reiniciar todo."
                        )
                        report(
                            f"💬 Kimi-k3 ➔ {worker_name}: Feedback en caliente emitido ({len(issues)} observación(es))",
                            progress_base + 7.0,
                            {
                                "agent": "auditor",
                                "model": "moonshotai/kimi-k3",
                                "action": f"Feedback en caliente para {worker_name}",
                                "reasoning": f"Kimi-k3 le pide a {worker_name} corregir en la marcha: {verdict.summary}",
                                "feedback": error_feedback,
                            },
                        )
                        self.logger.log(
                            "auditor",
                            "TASK_FEEDBACK_DISPATCHED",
                            f"Kimi-k3 envió corrección en caliente a {worker_name} para {task.task_id}: {verdict.summary}",
                            {"issues": issues, "suggested_fixes": verdict.suggested_fixes},
                        )

                except Exception as task_exc:
                    error_feedback = f"Excepción durante ejecución: {task_exc}"
                    self.logger.log("orchestrator", "TASK_EXCEPTION", error_feedback)

            if task_passed:
                completed_tasks += 1
            else:
                task.status = TaskStatus.FAILED
                self.logger.log("orchestrator", "TASK_FAILED_FINAL", f"Tarea {task.task_id} no superó el límite de intentos.")

        # FASE 3: Reporte Final y Conclusión
        report("📋 Generando informe final de desarrollo...", 95.0)
        report_md = self.logger.export_markdown_report(f"Informe de Desarrollo: {plan.project_name}")

        self.is_running = False
        if completed_tasks > 0:
            report(f"✅ Desarrollo completado: {completed_tasks}/{total_tasks} tarea(s) aprobada(s) y aplicadas al proyecto.", 100.0)
        else:
            report(f"⚠️ Proceso finalizado sin cambios aplicados ({completed_tasks}/{total_tasks} aprobadas). Revisa los registros.", 100.0)

        return {
            "project_name": plan.project_name,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "success_rate": f"{(completed_tasks / max(1, total_tasks)) * 100:.1f}%",
            "report_path": str(self.logger.session_file),
            "report_markdown": report_md,
            "tasks": [t.model_dump() for t in plan.tasks],
        }
