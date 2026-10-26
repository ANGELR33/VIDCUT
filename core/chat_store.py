"""Persistencia local de conversaciones del Agente Copilot.

Guarda hasta MAX_CHATS conversaciones en storage/assistant_chats para que el
usuario pueda cerrar la app, recargar la página o volver días después y
encontrar sus chats. Al superar el límite se elimina el más antiguo.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings


class ChatStore:
    """Almacén de chats del asistente: un archivo JSON por conversación."""

    MAX_CHATS = 20
    MAX_MESSAGES = 80          # últimos mensajes conservados por chat
    MAX_MESSAGE_CHARS = 6000   # recorte de seguridad por mensaje

    def __init__(self):
        self.root = settings.STORAGE_DIR / "assistant_chats"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _make_title(text: str) -> str:
        clean = re.sub(r"\s+", " ", (text or "")).strip()
        if not clean:
            return "Chat sin título"
        return clean[:48] + ("…" if len(clean) > 48 else "")

    def _chat_path(self, chat_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "", chat_id)[:24]
        return self.root / f"{safe}.json"

    def save(self, chat_id: Optional[str], messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Crea o actualiza un chat con la lista completa de mensajes."""
        clean_messages: List[Dict[str, Any]] = []
        for msg in (messages or [])[-self.MAX_MESSAGES:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            content = str(msg.get("content") or "")[:self.MAX_MESSAGE_CHARS]
            clean_messages.append({"role": role, "content": content})

        first_user = next((m["content"] for m in clean_messages if m["role"] == "user"), "")
        existing = None
        if chat_id:
            existing = self.load(chat_id)

        now = self._now()
        document = {
            "id": chat_id or existing.get("id") if existing else chat_id,
            "title": existing.get("title") if existing else self._make_title(first_user),
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
            "messages": clean_messages,
        }
        if not document["id"]:
            import uuid
            document["id"] = uuid.uuid4().hex[:12]

        path = self._chat_path(document["id"])
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        self._evict_oldest()
        return document

    def load(self, chat_id: str) -> Optional[Dict[str, Any]]:
        path = self._chat_path(chat_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def delete(self, chat_id: str) -> bool:
        path = self._chat_path(chat_id)
        if path.exists():
            path.unlink(missing_ok=True)
            return True
        return False

    def list(self) -> List[Dict[str, Any]]:
        """Lista los chats guardados (más recientes primero), resumida."""
        chats: List[Dict[str, Any]] = []
        for path in self.root.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                chats.append({
                    "id": doc.get("id") or path.stem,
                    "title": doc.get("title") or "Chat sin título",
                    "updated_at": doc.get("updated_at") or "",
                    "messages_count": len(doc.get("messages") or []),
                })
            except (OSError, json.JSONDecodeError):
                continue
        chats.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
        return chats[:self.MAX_CHATS]

    def _evict_oldest(self) -> None:
        """Mantiene solo los MAX_CHATS chats más recientes."""
        paths = []
        for path in self.root.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                paths.append((doc.get("updated_at") or "", path))
            except (OSError, json.JSONDecodeError):
                paths.append(("", path))
        paths.sort(key=lambda item: item[0])
        for _, path in paths[:-self.MAX_CHATS]:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
