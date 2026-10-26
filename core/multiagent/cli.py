"""Interfaz de línea de comandos (CLI) interactiva para el sistema multi-agente."""

import asyncio
import sys
from pathlib import Path

# Asegurar path raíz en sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.multiagent.orchestrator import MultiAgentOrchestrator


def print_banner():
    print("=" * 70)
    print("  🚀 AETHERCUT MULTI-AGENT DEV STUDIO")
    print("  • Arquitecto Líder:  GLM-5.3 (z-ai/glm-5.3)")
    print("  • Implementador:     GLM-5.3-flash (z-ai/glm-5.3-flash)")
    print("  • Auditor QA:        Kimi-k3 (moonshotai/kimi-k3)")
    print("=" * 70)


async def main():
    print_banner()

    if len(sys.argv) > 1:
        requirement = " ".join(sys.argv[1:])
    else:
        requirement = input("\n📝 Describe la aplicación, módulo o requerimiento a desarrollar:\n> ").strip()

    if not requirement:
        print("❌ Descripción vacía. Saliendo.")
        return

    orch = MultiAgentOrchestrator(workspace_root=BASE_DIR)

    def on_progress(msg: str, pct: float):
        print(f"[{pct:5.1f}%] {msg}")

    print("\nIniciando colaboración multi-agente...\n")
    result = await orch.execute_project(
        project_description=requirement,
        max_attempts_per_task=3,
        progress_cb=on_progress,
    )

    print("\n" + "=" * 70)
    print("🏁 RESULTADO FINAL DEL PROYECTO:")
    print(f"  • Proyecto:     {result['project_name']}")
    print(f"  • Tareas:       {result['completed_tasks']}/{result['total_tasks']} completadas")
    print(f"  • Éxito:        {result['success_rate']}")
    print("=" * 70)
    print("\nResumen del Informe:\n")
    print(result["report_markdown"][:600] + "...\n")


if __name__ == "__main__":
    asyncio.run(main())
