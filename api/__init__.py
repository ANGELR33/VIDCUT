"""AetherCut AI - Public API Package (v1).
Proporciona endpoints RESTful, SSE y Webhooks para que aplicaciones externas
(móviles, bots, Zapier, n8n, microservicios, scripts CLI) se comuniquen
e interactúen con todas las capacidades del estudio.
"""

from api.router import api_v1_router, init_api_state

__all__ = ["api_v1_router", "init_api_state"]
