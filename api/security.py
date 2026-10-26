"""Seguridad y Autenticación para la API Externa de AetherCut AI.

Permite proteger los endpoints de la API con API Key si está configurada en .env
(variable AETHERCUT_API_KEY).
Soporta de forma flexible:
  - Header: X-API-Key: <clave>
  - Header: Authorization: Bearer <clave> (o Authorization: <clave>)
  - Header: api-key: <clave> / apikey: <clave>
  - Query param: ?api_key=<clave> / ?key=<clave> / ?token=<clave>

Si AETHERCUT_API_KEY no está definida o está vacía, la API opera en modo abierto
local (ideal para desktop o LAN privada sin autenticación obligatoria).
"""

from typing import Optional
from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from config.settings import settings
from core.llm import safe_log

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


async def verify_api_key(
    request: Request,
    header_key: Optional[str] = Security(api_key_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> bool:
    """Valida la clave de la API si AETHERCUT_API_KEY está configurada en settings."""
    configured_key = getattr(settings, "AETHERCUT_API_KEY", "").strip()
    
    # Si no se configuró clave en el servidor, permitimos acceso libre
    if not configured_key:
        return True

    # 1. Verificar X-API-Key
    if header_key and header_key.strip() == configured_key:
        return True

    # 2. Verificar Authorization: Bearer <token>
    if bearer_creds and bearer_creds.credentials.strip() == configured_key:
        return True

    # 3. Inspeccionar encabezados flexibles (case-insensitive)
    for h in ["x-api-key", "api-key", "apikey", "authorization"]:
        val = request.headers.get(h, "").strip()
        if not val:
            continue
        if val.lower().startswith("bearer "):
            val = val[7:].strip()
        if val == configured_key:
            return True

    # 4. Inspeccionar Query Params opcionales (?api_key=... o ?key=...)
    for q in ["api_key", "key", "token"]:
        val = request.query_params.get(q, "").strip()
        if val and val == configured_key:
            return True

    safe_log(f"[Security] Petición rechazada en {request.url.path}: Credenciales no coinciden con AETHERCUT_API_KEY")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado. Provee una API Key válida mediante el header 'X-API-Key' o 'Authorization: Bearer <token>'.",
        headers={"WWW-Authenticate": "Bearer"},
    )
