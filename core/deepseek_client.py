"""Cliente DeepSeek (API compatible con OpenAI) para razonamiento editorial.

Se usa para lo que DeepSeek hace mejor: generar/rankear ganchos, reparar cifras
sin respaldo y auditar el guion. Si falla o no hay saldo, el pipeline cae a
Gemini sin romper la producción.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import requests

from config.settings import settings
from core.llm import safe_log

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or getattr(settings, "DEEPSEEK_API_KEY", "") or "").strip()
        configured = (model or getattr(settings, "DEEPSEEK_MODEL", "") or "").strip()
        # deepseek-chat es el modelo estable para devolver JSON completo; flash puede
        # gastar todos los tokens en razonamiento y dejar "content" vacío.
        self.model = configured if configured and configured != "deepseek-flash" else "deepseek-chat"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _request(self, model: str, messages: list, temperature: float, max_tokens: int, deadline_sec: float) -> str:
        try:
            response = requests.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=(5, max(8.0, float(deadline_sec))),
            )
        except Exception as exc:
            raise RuntimeError(f"DeepSeek no responde: {exc}") from exc

        if response.status_code == 402:
            raise RuntimeError("DeepSeek sin saldo (payment required)")
        if response.status_code >= 400:
            raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:180]}")
        try:
            data = response.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            finish = choice.get("finish_reason")
            if not content:
                safe_log(
                    f"[DeepSeek] {model} devolvió content vacío "
                    f"(finish={finish}, reasoning={len(reasoning)} chars)"
                )
            return str(content or "").strip()
        except Exception as exc:
            raise RuntimeError(f"Respuesta DeepSeek inválida: {exc}") from exc

    def generate(
        self,
        prompt: str,
        json_mode: bool = True,
        deadline_sec: float = 25.0,
        temperature: float = 0.3,
        max_tokens: int = 3000,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY no configurada")

        system = "Eres un editor de contenido audiovisual. Devuelve solo JSON válido, sin markdown."
        messages = [
            {"role": "system", "content": system if json_mode else "Eres un editor audiovisual experto."},
            {"role": "user", "content": prompt},
        ]

        text = self._request(self.model, messages, temperature, max_tokens, deadline_sec)
        if not text and self.model != "deepseek-chat":
            # Reintento con el modelo estable sin razonamiento visible.
            text = self._request("deepseek-chat", messages, temperature, 3000, deadline_sec)
        if not text:
            raise RuntimeError("DeepSeek devolvió una respuesta vacía")

        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"```\s*$", "", text).strip()
        safe_log(f"[DeepSeek] {self.model} respondió ({len(text)} chars)")
        return text
