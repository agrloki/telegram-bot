from __future__ import annotations

import functools
import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()


class Settings(BaseModel):
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    target_chat_id: Optional[int] = Field(None, alias="TARGET_CHAT_ID")
    database_path: str = Field("messages.db", alias="DATABASE_PATH")
    llm_provider: str = Field("openrouter", alias="LLM_PROVIDER")
    openrouter_api_key: Optional[str] = Field(None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="openrouter/anthropic/claude-3.5-sonnet",
        alias="OPENROUTER_MODEL",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="llama3", alias="OLLAMA_MODEL")
    digest_lookback_days: int = Field(7, alias="DIGEST_LOOKBACK_DAYS")
    max_messages: int = Field(400, alias="MAX_MESSAGES")
    request_timeout: int = Field(60, alias="REQUEST_TIMEOUT")
    prompt_style: str = Field("default", alias="PROMPT_STYLE")


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings.model_validate(dict(os.environ))
    except ValidationError as exc:  # pragma: no cover - user feedback
        missing = ", ".join(err["loc"][0] for err in exc.errors())
        raise RuntimeError(
            f"Некорректные переменные окружения. Заполните: {missing}"
        ) from exc


def override_settings(**kwargs: Optional[str]) -> Settings:
    """
    Утилита для тестов: заменяет настройки и сбрасывает кэш.
    """

    get_settings.cache_clear()
    env = dict(os.environ)
    env.update({k: str(v) for k, v in kwargs.items() if v is not None})
    return Settings.model_validate(env)

