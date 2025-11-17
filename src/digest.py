from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Sequence

from .openrouter_client import LLMClient
from .prompts import get_system_prompt


@dataclass
class ThreadMessage:
    message_id: int
    author: str
    text: str
    date: datetime
    link: str


@dataclass
class ThreadDiscussion:
    topic: str
    link: str
    messages: List[ThreadMessage]


def _trim_text(text: str, limit: int = 400) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


class DigestService:
    def __init__(
        self,
        client: LLMClient,
        lookback_days: int,
        prompt_style: str = "default",
    ) -> None:
        self._client = client
        self._lookback_days = lookback_days
        self._prompt_style = prompt_style.lower()

    async def build_digest(self, threads: Sequence[ThreadDiscussion]) -> str:
        if not threads:
            return "За последнюю неделю в чате не было новых сообщений."
        messages = self._build_prompt_messages(threads)
        return await self._client.generate_completion(messages)

    def _build_prompt_messages(
        self, threads: Sequence[ThreadDiscussion]
    ) -> List[dict]:
        serialized_threads = "\n\n".join(
            self._serialize_thread(thread) for thread in threads
        )
        user_prompt = (
            f"Ниже приводятся обсуждения за последние {self._lookback_days} дней. "
            "Составь ёмкий дайджест на русском языке. "
            "Для каждой темы укажи 1-2 ключевые мысли и ссылку на начало обсуждения. "
            "Ответ верни в Markdown-формате со списком."
        )
        system_prompt = get_system_prompt(self._prompt_style)

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": f"{user_prompt}\n\n{serialized_threads}",
            },
        ]

    def _serialize_thread(self, thread: ThreadDiscussion) -> str:
        lines = [
            f"Тема: {thread.topic}",
            f"Ссылка: {thread.link}",
            "Сообщения:",
        ]
        for msg in thread.messages[:10]:
            lines.append(
                f"- [{msg.date.isoformat()}] {msg.author}: {_trim_text(msg.text)}"
            )
        return "\n".join(lines)

