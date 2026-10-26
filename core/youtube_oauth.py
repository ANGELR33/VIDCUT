"""Publicación directa en YouTube (OAuth 2.0 + Data API v3).

Flujo de código de autorización con PKCE (el client_secret es opcional),
subida resumable con progreso y asignación de miniatura personalizada.

Soporta VARIOS canales: cada cuenta conectada se guarda en
storage/youtube_accounts.json con una etiqueta, palabras clave y un tipo
(short / video / cualquiera) que permiten elegir el canal de forma inteligente.
El token antiguo (storage/youtube_token.json) se migra solo.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from config.settings import settings
from core.llm import safe_log

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
CHANNEL_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"
UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMBNAIL_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    # Permite gestionar (hacer privados/cancelar/eliminar) los videos propios.
    "https://www.googleapis.com/auth/youtube",
]

UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB por petición del protocolo resumable
SHORTS_MAX_SECONDS = 180  # YouTube clasifica como Short vertical/cuadrado hasta 3 min

ACCOUNT_KINDS = ("any", "short", "video")


def _token_path() -> Path:
    """Ruta del token heredado (un solo canal); solo se usa para migrar."""
    return settings.STORAGE_DIR / "youtube_token.json"


def _accounts_path() -> Path:
    return settings.STORAGE_DIR / "youtube_accounts.json"


def _pending_path() -> Path:
    return settings.STORAGE_DIR / "youtube_oauth_pending.json"


def is_configured() -> bool:
    return bool(settings.YOUTUBE_CLIENT_ID)


def redirect_uri() -> str:
    return f"http://localhost:{settings.YOUTUBE_REDIRECT_PORT}/api/publish/youtube/callback"


# ---------------------------------------------------------------------------
# Multi-proyecto: descubrir pares de credenciales del .env
# ---------------------------------------------------------------------------

def _discover_clients() -> List[Dict[str, str]]:
    """Lee todos los pares YOUTUBE_CLIENT_ID[_N] / YOUTUBE_CLIENT_SECRET[_N].

    Devuelve una lista de dicts {client_id, client_secret, slot} donde
    slot es "" para el par principal y "_2", "_3"... para los adicionales.
    """
    import os
    clients: List[Dict[str, str]] = []
    # Par principal (sin sufijo)
    cid = (getattr(settings, "YOUTUBE_CLIENT_ID", None) or "").strip()
    sec = (getattr(settings, "YOUTUBE_CLIENT_SECRET", None) or "").strip()
    if cid:
        clients.append({"client_id": cid, "client_secret": sec, "slot": ""})
    # Pares numerados (_2, _3 ... _9)
    for n in range(2, 10):
        slot = f"_{n}"
        cid_n = (os.environ.get(f"YOUTUBE_CLIENT_ID{slot}") or getattr(settings, f"YOUTUBE_CLIENT_ID{slot}", None) or "").strip()
        sec_n = (os.environ.get(f"YOUTUBE_CLIENT_SECRET{slot}") or getattr(settings, f"YOUTUBE_CLIENT_SECRET{slot}", None) or "").strip()
        if cid_n:
            clients.append({"client_id": cid_n, "client_secret": sec_n, "slot": slot})
    return clients


def _client_for_account(account: Dict[str, Any]) -> Dict[str, str]:
    """Devuelve el par {client_id, client_secret} asociado a una cuenta.

    Si la cuenta tiene su propio client_id guardado (multi-proyecto), lo usa.
    Si no, vuelve al par principal del .env.
    """
    stored_cid = (account.get("client_id") or "").strip()
    stored_sec = (account.get("client_secret") or "").strip()
    if stored_cid:
        return {"client_id": stored_cid, "client_secret": stored_sec}
    # Fallback al par principal
    return {
        "client_id": (getattr(settings, "YOUTUBE_CLIENT_ID", None) or "").strip(),
        "client_secret": (getattr(settings, "YOUTUBE_CLIENT_SECRET", None) or "").strip(),
    }


class YouTubeAuthError(RuntimeError):
    pass


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Almacén de cuentas (multi-canal)
# ---------------------------------------------------------------------------

def _fetch_channel(access_token: str) -> Optional[Dict[str, Any]]:
    response = requests.get(
        CHANNEL_ENDPOINT,
        params={"part": "snippet,statistics", "mine": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if response.status_code != 200:
        safe_log(f"[YouTube] Canal no disponible ({response.status_code}): {response.text[:160]}")
        return None
    items = response.json().get("items") or []
    if not items:
        return None
    snippet = items[0].get("snippet", {})
    stats = items[0].get("statistics", {})
    return {
        "channel_id": items[0].get("id", ""),
        "title": snippet.get("title", ""),
        "thumbnail": (snippet.get("thumbnails", {}).get("default", {}) or {}).get("url", ""),
        "subscribers": stats.get("subscriberCount", "0"),
    }


def _load_accounts() -> List[Dict[str, Any]]:
    path = _accounts_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return []

    # Migración del token de un solo canal
    legacy = _token_path()
    if legacy.exists():
        try:
            session = json.loads(legacy.read_text(encoding="utf-8"))
            if session.get("refresh_token"):
                account = {
                    "channel_id": "legacy",
                    "title": "Canal conectado",
                    "thumbnail": "",
                    "subscribers": "0",
                    "tag": "",
                    "keywords": [],
                    "kind": "any",
                    "refresh_token": session["refresh_token"],
                    "access_token": session.get("access_token", ""),
                    "expires_at": session.get("expires_at", 0),
                    "connected_at": session.get("connected_at", time.time()),
                }
                accounts = [account]
                _save_json(path, accounts)
                try:
                    info = _fetch_channel(_valid_access_token("legacy"))
                    if info and info.get("channel_id"):
                        accounts = _load_accounts()
                        accounts[0].update(info)
                        _save_json(path, accounts)
                except Exception as exc:
                    safe_log(f"[YouTube] No se pudo completar la migración del canal: {exc}")
                return _load_accounts()
        except (OSError, json.JSONDecodeError):
            pass
    return []


def _save_accounts(accounts: List[Dict[str, Any]]) -> None:
    _save_json(_accounts_path(), accounts)


def _find_account(channel_id: Optional[str]) -> Dict[str, Any]:
    accounts = _load_accounts()
    if not accounts:
        raise YouTubeAuthError("No hay ningún canal de YouTube conectado.")
    if not channel_id:
        return accounts[0]
    for account in accounts:
        if account.get("channel_id") == channel_id:
            return account
    raise YouTubeAuthError("El canal de YouTube seleccionado ya no está conectado.")


def _public(account: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "channel_id": account.get("channel_id", ""),
        "title": account.get("title", ""),
        "thumbnail": account.get("thumbnail", ""),
        "subscribers": account.get("subscribers", "0"),
        "tag": account.get("tag", ""),
        "keywords": account.get("keywords", []),
        "kind": account.get("kind", "any"),
    }


def list_accounts() -> List[Dict[str, Any]]:
    """Canales conectados, sin tokens."""
    return [_public(a) for a in _load_accounts()]


def update_account(channel_id: str, tag: Optional[str] = None,
                   keywords: Optional[List[str]] = None, kind: Optional[str] = None) -> Dict[str, Any]:
    accounts = _load_accounts()
    for account in accounts:
        if account.get("channel_id") == channel_id:
            if tag is not None:
                account["tag"] = tag.strip()[:40]
            if keywords is not None:
                account["keywords"] = [k.strip()[:40] for k in keywords if k and k.strip()][:30]
            if kind is not None and kind in ACCOUNT_KINDS:
                account["kind"] = kind
            _save_accounts(accounts)
            return _public(account)
    raise YouTubeAuthError("Canal no encontrado.")


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def begin_authorization(client_slot: str = "") -> Dict[str, str]:
    """Genera la URL de consentimiento de Google con PKCE.

    client_slot: identificador del par de credenciales a usar.
      ""  → par principal (Canal 1)
      "_2" → YOUTUBE_CLIENT_ID_2 / YOUTUBE_CLIENT_SECRET_2 (Canal 2), etc.
    """
    clients = _discover_clients()
    if not clients:
        raise YouTubeAuthError("YOUTUBE_CLIENT_ID no está configurado en .env")
    # Buscar el slot pedido; si no existe, usar el primero disponible
    matched = next((c for c in clients if c["slot"] == client_slot), None) or clients[0]
    client_id = matched["client_id"]
    client_secret = matched["client_secret"]

    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b="=").decode()
    state = secrets.token_urlsafe(24)
    _save_json(_pending_path(), {
        "state": state,
        "verifier": verifier,
        "client_id": client_id,
        "client_secret": client_secret,
        "created_at": time.time(),
    })

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent select_account",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    from urllib.parse import urlencode
    return {
        "auth_url": f"{AUTH_ENDPOINT}?{urlencode(params)}",
        "state": state,
        "client_slot": matched["slot"],
    }


def complete_authorization(code: str, state: str) -> Dict[str, Any]:
    """Intercambia el código por tokens y guarda (o actualiza) el canal.

    Usa las credenciales del cliente guardadas en el pending (multi-proyecto).
    """
    pending = json.loads(_pending_path().read_text(encoding="utf-8"))
    if not pending or pending.get("state") != state:
        raise YouTubeAuthError("Estado OAuth no válido: reinicia la conexión desde el estudio de publicación.")
    verifier = pending["verifier"]
    # Credenciales del cliente usadas en este flujo (pueden ser del Canal 2, etc.)
    p_client_id = pending.get("client_id") or (getattr(settings, "YOUTUBE_CLIENT_ID", None) or "").strip()
    p_client_secret = pending.get("client_secret") or (getattr(settings, "YOUTUBE_CLIENT_SECRET", None) or "").strip()
    _pending_path().unlink(missing_ok=True)

    data: Dict[str, str] = {
        "code": code,
        "client_id": p_client_id,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    }
    if p_client_secret:
        data["client_secret"] = p_client_secret
    response = requests.post(TOKEN_ENDPOINT, data=data, timeout=30)
    if response.status_code != 200:
        raise YouTubeAuthError(f"Google rechazó el intercambio de código ({response.status_code}): {response.text[:300]}")
    tokens = response.json()
    if not tokens.get("refresh_token"):
        raise YouTubeAuthError("Google no devolvió refresh_token. Revoca el acceso en myaccount.google.com/permissions e inténtalo de nuevo.")

    access_token = tokens.get("access_token", "")
    info = _fetch_channel(access_token) or {}
    channel_id = info.get("channel_id") or f"canal_{secrets.token_hex(3)}"

    accounts = _load_accounts()
    # Si solo existe el canal heredado "legacy", pasa a ser este canal real conservando su etiqueta.
    if channel_id != "legacy" and len(accounts) == 1 and accounts[0].get("channel_id") == "legacy" \
            and not any(a.get("channel_id") == channel_id for a in accounts):
        accounts[0]["channel_id"] = channel_id

    existing = next((a for a in accounts if a.get("channel_id") == channel_id), None)
    session = existing or {"tag": "", "keywords": [], "kind": "any"}
    session.update({
        "channel_id": channel_id,
        "title": info.get("title", session.get("title", "")),
        "thumbnail": info.get("thumbnail", session.get("thumbnail", "")),
        "subscribers": info.get("subscribers", session.get("subscribers", "0")),
        "refresh_token": tokens["refresh_token"],
        "access_token": access_token,
        "expires_at": time.time() + int(tokens.get("expires_in", 3600)),
        "connected_at": time.time(),
        # Guardar credenciales del cliente para renovar tokens sin depender del .env global
        "client_id": p_client_id,
        "client_secret": p_client_secret,
    })
    if not existing:
        accounts.append(session)
    _save_accounts(accounts)
    return _public(session)


def disconnect(channel_id: Optional[str] = None) -> None:
    """Desconecta un canal (o todos si no se indica)."""
    if channel_id:
        remaining = [a for a in _load_accounts() if a.get("channel_id") != channel_id]
        _save_accounts(remaining)
        if not remaining:
            _token_path().unlink(missing_ok=True)
        return
    _save_accounts([])
    _token_path().unlink(missing_ok=True)


def is_connected() -> bool:
    return bool(_load_accounts())


def _valid_access_token(channel_id: Optional[str] = None) -> str:
    accounts = _load_accounts() if channel_id != "legacy" else None
    if accounts is None:
        # Durante la migración se lee directamente el archivo heredado
        stored = json.loads(_accounts_path().read_text(encoding="utf-8"))
        accounts = stored
    if not accounts:
        raise YouTubeAuthError("No hay ningún canal de YouTube conectado.")
    session = accounts[0]
    if channel_id:
        session = next((a for a in accounts if a.get("channel_id") == channel_id), None)
        if session is None:
            raise YouTubeAuthError("El canal de YouTube seleccionado ya no está conectado.")

    if time.time() < float(session.get("expires_at", 0)) - 60 and session.get("access_token"):
        return session["access_token"]
    # Usar las credenciales del cliente de ESTA cuenta (multi-proyecto)
    creds = _client_for_account(session)
    data: Dict[str, str] = {
        "refresh_token": session["refresh_token"],
        "client_id": creds["client_id"],
        "grant_type": "refresh_token",
    }
    if creds["client_secret"]:
        data["client_secret"] = creds["client_secret"]
    response = requests.post(TOKEN_ENDPOINT, data=data, timeout=30)
    if response.status_code != 200:
        raise YouTubeAuthError(f"No se pudo renovar el token de YouTube ({response.status_code}): {response.text[:300]}")
    refreshed = response.json()
    session["access_token"] = refreshed.get("access_token", "")
    session["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
    _save_accounts(accounts)
    return session["access_token"]


def get_channel_info(channel_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Datos del canal indicado (o el primero conectado)."""
    if not is_connected():
        return None
    try:
        account = _find_account(channel_id)
        return _public(account)
    except Exception as exc:
        safe_log(f"[YouTube] Error leyendo canal: {exc}")
        return None


# ---------------------------------------------------------------------------
# Formato (Short / Video) y elección inteligente de canal
# ---------------------------------------------------------------------------

def detect_format(video_path: Path) -> Dict[str, Any]:
    """Determina si el archivo lo tratará YouTube como Short o como video largo.

    Es Short si es vertical o cuadrado y dura como máximo 3 minutos.
    """
    width = height = 0
    duration = 0.0
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", str(video_path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        duration = float((data.get("format") or {}).get("duration") or 0)
    except Exception as exc:
        safe_log(f"[YouTube] No se pudo analizar el formato del video: {exc}")
    vertical_or_square = bool(width and height and height >= width)
    is_short = vertical_or_square and 0 < duration <= SHORTS_MAX_SECONDS
    return {
        "format": "short" if is_short else "video",
        "width": width,
        "height": height,
        "duration": round(duration, 1),
        "ratio": "9:16" if (width and height and height > width) else ("1:1" if width == height and width else "16:9"),
    }


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def suggest_account(title: str, description: str, tags: List[str], fmt: str) -> Dict[str, Any]:
    """Elige el canal segun etiqueta, palabras clave y tipo (short/video).

    En caso de empate de puntuacion, distribuye entre los canales empatados
    de forma aleatoria para que todos reciban contenido equitativamente.
    """
    accounts = _load_accounts()
    if not accounts:
        return {"channel_id": "", "reason": "", "scores": {}}
    haystack = _norm(" ".join([title or "", description or "", " ".join(tags or [])]))
    words = set(re.findall(r"[a-z0-9]{3,}", haystack))

    scores: Dict[str, float] = {}
    notes: Dict[str, List[str]] = {}
    for account in accounts:
        cid = account.get("channel_id", "")
        score = 0.0
        why: List[str] = []
        terms = list(account.get("keywords") or [])
        if account.get("tag"):
            terms.append(account["tag"])
        for term in terms:
            t = _norm(term).strip()
            if not t:
                continue
            # Coincidencia exacta de frase completa
            if " " in t and t in haystack:
                score += 2.0
                why.append(term)
                continue
            # Coincidencia de cada palabra individual en el termino
            # (permite que 'inteligencia artificial' coincida si 'inteligencia' o 'artificial' aparecen)
            term_words = [w for w in re.findall(r"[a-z0-9]{3,}", t)]
            matched_any = False
            for tw in term_words:
                if tw in words or (len(tw) >= 5 and any(w.startswith(tw[:5]) for w in words if len(w) >= 5)):
                    matched_any = True
                    break
            if matched_any:
                score += 2.0
                why.append(term)
        kind = account.get("kind", "any")
        if kind == fmt:
            score += 3.0
            why.append("formato " + ("Short" if fmt == "short" else "video largo"))
        elif kind in ("short", "video") and kind != fmt:
            score -= 3.0
        scores[cid] = score
        notes[cid] = why

    top_score = max(scores.values(), default=0)
    # Si hay empate exacto, distribuir aleatoriamente entre los empatados
    tied = [a for a in accounts if abs(scores.get(a.get("channel_id", ""), 0) - top_score) < 0.01]
    best = random.choice(tied) if len(tied) > 1 else tied[0]
    best_id = best.get("channel_id", "")
    reason = ", ".join(notes.get(best_id, []))
    return {
        "channel_id": best_id,
        "reason": f"Coincide con: {reason}" if reason else "Canal principal (distribucion aleatoria)",
        "scores": scores,
    }


def prepare_shorts_metadata(title: str, description: str, tags: List[str]) -> Dict[str, Any]:
    """Marca el contenido como Short garantizando #Shorts en titulo Y descripcion.

    YouTube usa #Shorts en el titulo o descripcion para clasificar el video.
    Agregar en ambos lugares maximiza la deteccion automatica.
    """
    # --- Titulo: agregar #Shorts al final si no esta ya ---
    t = (title or "").strip()
    if "#shorts" not in t.lower():
        # Limitar titulo a 95 chars para dejar espacio al tag
        if len(t) > 90:
            t = t[:90].rstrip()
        t = f"{t} #Shorts"

    # --- Descripcion: agregar #Shorts en bloque al final ---
    desc = (description or "").strip()
    if "#shorts" not in desc.lower():
        desc = f"{desc}\n\n#Shorts".strip()

    # --- Tags: incluir 'Shorts' ---
    tag_list = list(tags or [])
    if not any(tw.lower().lstrip("#") == "shorts" for tw in tag_list):
        tag_list.insert(0, "Shorts")

    return {"title": t, "description": desc, "tags": tag_list}


# ---------------------------------------------------------------------------
# Subida
# ---------------------------------------------------------------------------

def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: List[str],
    privacy: str = "public",
    *,
    category_id: str = "27",
    made_for_kids: bool = False,
    notify_subscribers: bool = True,
    channel_id: Optional[str] = None,
    publish_at: Optional[str] = None,
    progress: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """Sube el video con el protocolo resumable de YouTube.

    Devuelve {"video_id", "video_url"}. progress recibe (0..1, mensaje).
    """
    access_token = _valid_access_token(channel_id)
    report = progress or (lambda frac, msg: None)
    total = video_path.stat().st_size

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": (description or "")[:5000],
            "tags": [t[:100] for t in tags][:30],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy if privacy in ("public", "unlisted", "private") else "public",
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }
    if publish_at:
        # Programado: YouTube exige 'private' + publishAt y lo publica solo a esa hora.
        metadata["status"]["privacyStatus"] = "private"
        metadata["status"]["publishAt"] = publish_at

    report(0.02, "Iniciando sesión de subida en YouTube...")
    session_response = requests.post(
        f"{UPLOAD_ENDPOINT}?uploadType=resumable&part=snippet,status"
        f"{'&notifySubscribers=false' if not notify_subscribers else ''}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(total),
            "X-Upload-Content-Type": "video/mp4",
        },
        data=json.dumps(metadata),
        timeout=60,
    )
    if session_response.status_code not in (200, 201):
        raise YouTubeAuthError(f"YouTube rechazó la subida ({session_response.status_code}): {session_response.text[:300]}")
    session_uri = session_response.headers.get("Location")
    if not session_uri:
        raise YouTubeAuthError("YouTube no devolvió la URL de sesión resumable.")

    report(0.05, f"Subiendo video ({total / 1024 / 1024:.1f} MB)...")
    with video_path.open("rb") as handle:
        offset = 0
        while offset < total:
            chunk = handle.read(UPLOAD_CHUNK_SIZE)
            chunk_end = offset + len(chunk) - 1
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{chunk_end}/{total}",
            }
            put = requests.put(
                session_uri, data=chunk, headers=headers, timeout=600, allow_redirects=False
            )
            # 308 = "Resume Incomplete": respuesta normal a un trozo intermedio.
            if put.status_code not in (200, 201, 202, 308):
                raise YouTubeAuthError(f"Fallo durante la subida ({put.status_code}): {put.text[:300]}")
            if put.status_code == 308:
                confirmed = put.headers.get("Range", "")
                if confirmed.startswith("bytes=0-"):
                    next_offset = int(confirmed.split("-")[1]) + 1
                else:
                    next_offset = chunk_end + 1
                if next_offset != chunk_end + 1:
                    handle.seek(next_offset)
                offset = next_offset
            else:
                offset = chunk_end + 1
            report(0.05 + 0.9 * (offset / total), f"Subiendo video... {offset / total * 100:.0f}%")
            if put.status_code in (200, 201):
                video = put.json()
                video_id = video.get("id", "")
                report(1.0, "Video recibido por YouTube.")
                return {"video_id": video_id, "video_url": f"https://youtu.be/{video_id}"}

    raise YouTubeAuthError("La subida terminó sin confirmación de YouTube.")


def set_thumbnail(video_id: str, thumbnail_path: Path, channel_id: Optional[str] = None) -> bool:
    """Asigna la miniatura personalizada (requiere canal verificado)."""
    if not video_id or not thumbnail_path.exists():
        return False
    try:
        access_token = _valid_access_token(channel_id)
        with thumbnail_path.open("rb") as handle:
            response = requests.post(
                f"{THUMBNAIL_ENDPOINT}?videoId={video_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                files={"media": (thumbnail_path.name, handle, "image/jpeg")},
                timeout=120,
            )
        if response.status_code in (200, 201):
            return True
        safe_log(f"[YouTube] Miniatura personalizada rechazada ({response.status_code}): {response.text[:200]}")
        return False
    except Exception as exc:
        safe_log(f"[YouTube] Error subiendo miniatura: {exc}")
        return False
