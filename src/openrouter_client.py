from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

import httpx


class OpenRouterError(RuntimeError):
    """Исключение при ошибке OpenRouter."""


class OllamaError(RuntimeError):
    """Исключение при ошибке Ollama."""


class LLMClient(Protocol):
    async def generate_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        ...


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/your-org/telegram-digest-bot",
            "X-Title": "Telegram Digest Bot",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        if response.status_code >= 400:
            raise OpenRouterError(
                f"OpenRouter error {response.status_code}: {response.text}"
            )
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise OpenRouterError("Unexpected OpenRouter response format") from exc


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
        if response.status_code >= 400:
            raise OllamaError(f"Ollama error {response.status_code}: {response.text}")
        data = response.json()
        try:
            return data["message"]["content"].strip()
        except KeyError as exc:
            raise OllamaError("Unexpected Ollama response format") from exc

