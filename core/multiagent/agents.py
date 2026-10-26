"""Agentes especializados del sistema de desarrollo multi-agente:
1. ArchitectAgent (GLM-5.3): Diseña arquitectura, descompone tareas, lidera integración.
2. ImplementerAgent (GLM-5.3-flash): Escribe código, componentes, endpoints y tests.
3. AuditorAgent (Kimi-k3): Audita lógica, detecta huecos, aprueba/rechaza y corre verificaciones.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.multiagent.models import (
    get_architect_model,
    get_implementer_model,
    get_auditor_model,
)
from core.multiagent.schemas import (
    ArchitecturePlan,
    AtomicTask,
    AuditVerdict,
    TaskStatus,
)


class ArchitectAgent:
    """GLM-5.3-flash: Delegador ágil del proyecto, planificador y creador de tareas."""

    def __init__(self):
        # Usamos flash como delegador ágil para máxima velocidad en crear el plan
        self.model = get_implementer_model()

    def create_architecture_plan(
        self,
        project_description: str,
        existing_context: Optional[str] = None,
        on_reasoning: Optional[Callable[[str], None]] = None,
    ) -> ArchitecturePlan:
        system_prompt = (
            "Eres el Arquitecto y Delegador Ágil del proyecto (modelo GLM-5.3-flash). "
            "Tu misión es descomponer el requerimiento en un plan de arquitectura limpio y delegar "
            "tareas atómicas concretas, precisas y ordenadas por dependencias para el equipo de desarrollo. "
            "Cada tarea debe tener: task_id, title, description, target_files (rutas relativas EXACTAS del proyecto), "
            "action_type ('create_or_modify' o 'test'), y dependencies (lista de task_id previos requeridos).\n"
            "ESTRUCTURA DE ARCHIVOS EXISTENTES EN ESTE PROYECTO:\n"
            "- web/templates/index.html (HTML principal de la interfaz)\n"
            "- web/static/css/style.css (CSS con el diseño, tema y estilos)\n"
            "- web/static/js/app.js (JavaScript del cliente, frontend y copilot)\n"
            "- server.py (Backend FastAPI)\n"
            "- core/ (Módulos de motor de video: streamer_pipeline.py, scene_engine.py, etc.)\n"
            "IMPORTANTE: Las rutas en target_files DEBEN ser relativas a la raíz del repositorio "
            "(ejemplo: 'web/static/css/style.css', 'web/templates/index.html'). NO inventes rutas genéricas como 'templates/base.html'.\n"
            "Respeta escrupulosamente los archivos y funciones existentes para NO TOCAR lo que ya sirve."
        )

        user_prompt = f"DESCRIPCIÓN DEL PROYECTO / REQUERIMIENTO:\n{project_description}\n\n"
        if existing_context:
            user_prompt += f"CONTEXTO Y ARCHIVOS EXISTENTES:\n{existing_context}\n\n"

        user_prompt += (
            "Responde estrictamente con la estructura JSON correspondiente a ArchitecturePlan:\n"
            "{\n"
            '  "project_name": "Nombre conciso",\n'
            '  "summary": "Resumen técnico de la solución",\n'
            '  "architecture_overview": "Explicación de módulos y flujo de datos",\n'
            '  "components": [{"name": "nombre", "purpose": "propósito"}],\n'
            '  "tasks": [\n'
            '      "task_id": "task_1",\n'
            '      "title": "Título de la tarea",\n'
            '      "description": "Detalle técnico de qué implementar",\n'
            '      "target_files": ["core/modulo.py"],\n'
            '      "action_type": "create_or_modify",\n'
            '      "complexity": "light",\n'
            '      "assigned_model": "z-ai/glm-5.3-flash",\n'
            '      "dependencies": []\n'
            '    }\n'
            '  ],\n'
            '  "suggested_tests": ["tests/test_modulo.py"]\n'
            "}\n"
            "REGLAS OBLIGATORIAS DE ARQUITECTURA:\n"
            "- EDICIÓN MODULAR Y ÁGIL (ESTILO ANTIGRAVITY / CURSOR): NUNCA pidas reescribir un archivo gigante entero (como app.js de 140KB o style.css de 58KB) en una sola tarea. En su lugar, delega extensiones modulares, parches o nuevos módulos específicos (ej: 'web/static/js/timeline.js', 'web/static/css/theme-dark-matte.css', 'core/web_card_renderer.py') o modificaciones puntuales de funciones.\n"
            "- Si la tarea es ligera (crear tests, helpers, templates, extensiones CSS, utilidades): asigna 'complexity': 'light' y 'assigned_model': 'z-ai/glm-5.3-flash' (la ejecutas tú mismo de forma ágil).\n"
            "- Si la tarea es pesada o compleja (arquitectura base, lógica de algoritmos, refactorización profunda, integración compleja): asigna 'complexity': 'heavy' y 'assigned_model': 'z-ai/glm-5.3' (para el Ingeniero Senior).\n"
            "IMPORTANTE: Sé conciso, no agregues texto fuera del JSON, mantén entre 2 y 5 tareas esenciales."
        )

        plan_dict = self.model.generate_json(system_prompt, user_prompt, max_tokens=8192, on_reasoning=on_reasoning)
        return ArchitecturePlan(**plan_dict)


class ImplementerAgent:
    """GLM-5.3 (Normal): Desarrollador Senior para tareas pesaditas, lógica compleja y reestructuración profunda."""

    def __init__(self):
        # GLM-5.3 normal asume la carga pesada de código
        self.senior_model = get_architect_model()
        # GLM-5.3-flash para tareas ligeras / repetitivas
        self.flash_model = get_implementer_model()
        self.model = self.senior_model

    def implement_task(
        self,
        task: AtomicTask,
        architecture_summary: str,
        context_files: Dict[str, str],
        error_feedback: Optional[str] = None,
        on_reasoning: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, str]:
        """Escribe el código concreto para cada target_file de la tarea usando el modelo asignado."""
        is_light = (task.complexity == "light") or ("flash" in (task.assigned_model or "").lower())
        active_model = self.flash_model if is_light else self.senior_model
        model_name = "GLM-5.3-flash (Desarrollador Ágil)" if is_light else "GLM-5.3 (Ingeniero Senior)"

        system_prompt = (
            f"Eres el desarrollador de software a cargo ({model_name}). "
            "Implementas código de forma precisa respetando la arquitectura y sin romper funciones existentes. "
            "REGLAS CRÍTICAS DE CÓDIGO:\n"
            "1. PROHIBIDO USAR PLACEHOLDERS O RESÚMENES como '/* entire css with ... */' o '...resto del código...'. Debes entregar el código COMPLETO y ejecutable.\n"
            "2. DEBES JUSTIFICAR TUS CAMBIOS: Si eliminas, limpias o reorganizas botones o elementos redundantes, asegúrate de que no rompa la funcionalidad y explica la lógica en los comentarios del código o en la justificación.\n"
            "3. Si se te proporciona retroalimentación de error o auditoría previa, corrige exactamente ese fallo."
        )

        files_context_str = "\n\n".join(
            [f"--- ARCHIVO: {fp} ---\n{content}" for fp, content in context_files.items()]
        )

        user_prompt = (
            f"ARQUITECTURA GENERAL:\n{architecture_summary}\n\n"
            f"TAREA ASIGNADA:\nID: {task.task_id} | Título: {task.title}\n"
            f"Descripción: {task.description}\n"
            f"Archivos objetivo: {task.target_files}\n\n"
        )
        if files_context_str:
            user_prompt += f"CÓDIGO DE CONTEXTO ACTUAL:\n{files_context_str}\n\n"
        if error_feedback:
            user_prompt += f"¡ATENCIÓN! CORRECCIÓN REQUERIDA (Auditoría previa falló):\n{error_feedback}\n\n"

        user_prompt += (
            "Responde estrictamente con un objeto JSON donde las claves sean los paths de target_files "
            "y los valores sean el código fuente COMPLETO del archivo (sin placeholders, con código real y funcional):\n"
            '{\n  "path/al/archivo.py": "codigo fuente completo..."\n}'
        )

        code_dict = active_model.generate_json(system_prompt, user_prompt, max_tokens=8192, on_reasoning=on_reasoning)
        # Si el modelo entregó código en bloque markdown puro sin envolver en JSON
        if "_raw_code_" in code_dict:
            raw_c = code_dict.pop("_raw_code_")
            primary_target = task.target_files[0] if task.target_files else "generated_file.txt"
            code_dict[primary_target] = raw_c
        return code_dict


class AuditorAgent:
    """Kimi-k3: Auditor Independiente de Calidad, QA y Lógica."""

    def __init__(self, mode: str = "analysis"):
        self.model = get_auditor_model()
        self.project_inventory: str = ""
        # "analysis" (Observador / Anotador de reporte final sin bloquear en caliente)
        # "admin" (Modo Administrador que da órdenes estrictas y rechaza en caliente)
        self.mode = mode

    def load_project_context(self, inventory_summary: str):
        """Carga en memoria del auditor el mapa completo de funcionalidades existentes para prevenir regresiones."""
        self.project_inventory = inventory_summary

    def audit_code(
        self,
        task: AtomicTask,
        proposed_code: Dict[str, str],
        project_context: str,
    ) -> AuditVerdict:
        """Inspecciona el código generado buscando incoherencias lógicas o fallas antes de ejecutar."""
        is_analysis_mode = (self.mode == "analysis")

        if is_analysis_mode:
            system_prompt = (
                "Eres el Auditor y Observador Técnico de Calidad (modelo Kimi-k3) en MODO ANÁLISIS / OBSERVADOR. "
                "Incorporas la metodología de ingeniería de Y Combinator (GStack de Garry Tan: Review, QA y Health). "
                "Tu labor en este modo es OBSERVAR, REGISTRAR y EVALUAR el trabajo del desarrollador sin bloquearlo inmediatamente: "
                "1. Evalúa la justificación técnica que dio el desarrollador sobre por qué modificó o reorganizó cada elemento. "
                "2. Aplica la rúbrica GStack: verificación de regresiones, trust boundaries, llamadas asíncronas y estabilidad. "
                "3. Si el código tiene sentido técnico y una justificación lógica coherente (incluso si moderniza la UI o limpia elementos redundantes), "
                "aprueba con score >= 85 y anota tus observaciones en el informe final para que el usuario humano tenga el veredicto definitivo. "
                "Solo rechaza si el código contiene errores de sintaxis fatales o llamadas que rompan el servidor por completo."
            )
        else:
            system_prompt = (
                "Eres el Auditor y Administrador de Calidad y Seguridad (modelo Kimi-k3) en MODO ADMINISTRADOR ESTRICTO. "
                "Operas con los estándares de ingeniería de software de Y Combinator (GStack: /review, /qa, /security). "
                "Tu misión es exigir máxima calidad y ASEGURAR QUE NO SE DESTRUYA O ELIMINE NINGUNA FUNCIONALIDAD EXISTENTE. "
                "Aplica los filtros de rigor GStack: "
                "- Regresiones: ¿mantiene todas las APIs, firmas y selectores DOM previos? "
                "- Seguridad e Inputs: ¿escapa entradas, previene inyecciones o variables no definidas? "
                "- Integridad: CERO placeholders o comentarios resumidos. El código debe ser completo. "
                "Si detectas fallas o riesgo para funciones existentes, rechaza en caliente con órdenes claras y diagnósticos accionables."
            )

        code_preview = "\n\n".join(
            [f"=== ARCHIVO: {path} ===\n{code}" for path, code in proposed_code.items()]
        )

        user_prompt = (
            f"MODO DE AUDITORÍA ACTIVO: {'MODO ANÁLISIS (Observar, registrar justificación y reportar)' if is_analysis_mode else 'MODO ADMINISTRADOR (Exigencia estricta y bloqueo)'}\n\n"
            f"MAPA DE FUNCIONALIDADES EXISTENTES DEL PROYECTO (¡PROTÉGELAS, NO LAS DESTRUYAS!):\n"
            f"{self.project_inventory or 'Proyecto en evolución activa.'}\n\n"
            f"CONTEXTO DE ESTE SPRINT / PLAN:\n{project_context}\n\n"
            f"TAREA A AUDITAR:\n{task.title} ({task.description})\n\n"
            f"CÓDIGO PROPUESTO:\n{code_preview}\n\n"
            "Emite tu veredicto estrictamente en formato JSON con la siguiente estructura:\n"
            "{\n"
            '  "approved": true o false,\n'
            '  "score": 0 a 100,\n'
            '  "summary": "Resumen conciso del veredicto y valoración de la justificación",\n'
            '  "logic_errors_found": ["error 1", "error 2"],\n'
            '  "missing_requirements": ["requisito no cumplido"],\n'
            '  "suggested_fixes": ["cómo corregirlo exactamente"],\n'
            '  "run_tests_recommended": true\n'
            "}"
        )

        verdict_dict = self.model.generate_json(system_prompt, user_prompt, max_tokens=2500)
        return AuditVerdict(**verdict_dict)

    @staticmethod
    def run_automated_syntax_check(filepath: Path) -> Dict[str, Any]:
        """Ejecuta py_compile sobre un archivo Python para validar sintaxis de manera 100% determinística."""
        if filepath.suffix != ".py":
            return {"passed": True, "output": "Archivo no-python (sintaxis ok)"}

        res = subprocess.run(
            [sys.executable, "-m", "py_compile", str(filepath)],
            capture_output=True,
            text=True,
        )
        return {
            "passed": res.returncode == 0,
            "stdout": res.stdout,
            "stderr": res.stderr,
        }
