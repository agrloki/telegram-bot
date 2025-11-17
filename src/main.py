from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Optional

from .bot import TelegramDigestBot
from .config import Settings, get_settings
from .digest import DigestService
from .openrouter_client import LLMClient, OllamaClient, OpenRouterClient
from .storage import MessageStorage
from .sync_service import SyncService


def build_bot(
    settings: Optional[Settings] = None,
    storage: Optional[MessageStorage] = None,
    model_override: Optional[str] = None,
    provider_override: Optional[str] = None,
) -> TelegramDigestBot:
    settings = settings or get_settings()
    storage = storage or MessageStorage(settings.database_path)
    provider = (provider_override or settings.llm_provider).lower()
    client: LLMClient

    if provider == "ollama":
        client = OllamaClient(
            base_url=settings.ollama_base_url,
            model=model_override or settings.ollama_model,
            timeout=settings.request_timeout,
        )
    elif provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY не задан, укажите его или переключитесь на Ollama."
            )
        client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=model_override or settings.openrouter_model,
            timeout=settings.request_timeout,
        )
    else:
        raise RuntimeError(
            f"Неизвестный LLM_PROVIDER='{provider}'. Допустимо: openrouter, ollama."
        )
    digest_service = DigestService(
        client=client,
        lookback_days=settings.digest_lookback_days,
        prompt_style=settings.prompt_style,
    )
    return TelegramDigestBot(settings, digest_service, storage)


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def cli() -> None:
    parser = argparse.ArgumentParser(description="Telegram digest bot")
    parser.add_argument(
        "command",
        choices=["digest", "force-send", "sync", "list-chats", "list-bot-chats", "clear-db"],
        help="Команда для выполнения",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Не отправлять сообщение в чат, а вывести в stdout",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Вывести отладочные логи взаимодействия с Telegram",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Переопределить модель LLM для текущего запуска",
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "ollama"],
        help="Временно выбрать провайдера LLM (openrouter/ollama)",
    )
    parser.add_argument(
        "--all-chats",
        action="store_true",
        help="(clear-db) Очистить все чаты, иначе только целевой",
    )
    parser.add_argument(
        "--reset-offset",
        action="store_true",
        help="(clear-db) Сбросить last_update_id после очистки",
    )
    args = parser.parse_args()

    configure_logging(debug=args.debug)
    settings = get_settings()
    storage = MessageStorage(settings.database_path)
    model_override = args.model
    provider_override = args.provider
    if args.command == "digest":
        bot = build_bot(
            settings=settings,
            storage=storage,
            model_override=model_override,
            provider_override=provider_override,
        )
        result = asyncio.run(bot.send_weekly_digest(dry_run=args.dry_run))
        if args.dry_run:
            print(result)
    elif args.command == "force-send":
        bot = build_bot(
            settings=settings,
            storage=storage,
            model_override=model_override,
            provider_override=provider_override,
        )
        result = asyncio.run(
            bot.send_weekly_digest(
                dry_run=args.dry_run,
                use_all_messages=True,
            )
        )
        if args.dry_run:
            print(result)
    elif args.command == "sync":
        service = SyncService(settings, storage)
        saved = asyncio.run(service.sync_updates())
        print(f"Синхронизировано {saved} сообщений")
    elif args.command == "list-chats":
        chats = storage.list_chats()
        if not chats:
            print("В базе нет чатов. Запустите sync, чтобы собрать сообщения.")
        else:
            print("Чаты, в которых есть сохранённые сообщения:")
            for chat in chats:
                title = chat.title
                if chat.username:
                    title += f" (@{chat.username})"
                print(
                    f"- ID: {chat.chat_id}, тип: {chat.chat_type}, "
                    f"последнее сообщение: {chat.last_message_ts} — {title}"
                )
    elif args.command == "list-bot-chats":
        # Проверяем, есть ли чаты в базе
        stored_chats = storage.list_chats()
        if not stored_chats:
            print("База данных пустая. Нет чатов для проверки.")
            print("\nДля работы команды 'list-bot-chats' необходимо:")
            print("  1. Убедиться, что бот добавлен в группы/каналы")
            print("  2. Запустить команду 'sync' для сбора сообщений из чатов")
            print("  3. Затем снова запустить 'list-bot-chats'")
            return
        
        service = SyncService(settings, storage)
        print("Проверка доступности чатов...")
        chats = asyncio.run(service.get_bot_chats())
        if not chats:
            print("Не удалось найти чаты, где бот является участником.")
            print("Возможно, бот был удален из всех чатов, или произошла ошибка при проверке.")
        else:
            print(f"\nНайдено {len(chats)} чатов, где бот является участником:\n")
            for chat in sorted(chats, key=lambda c: c.chat_id):
                title = chat.title
                if chat.username:
                    title += f" (@{chat.username})"
                print(f"- ID: {chat.chat_id}, тип: {chat.chat_type} — {title}")
    elif args.command == "clear-db":
        chat_id = None if args.all_chats else settings.target_chat_id
        if not args.all_chats and not chat_id:
            print("Ошибка: TARGET_CHAT_ID не задан. Используйте --all-chats для очистки всех чатов.")
            return
        removed = storage.clear_messages(
            chat_id=chat_id,
            reset_metadata=args.reset_offset,
        )
        scope = "все чаты" if args.all_chats else f"чат {chat_id}"
        print(f"Удалено {removed} сообщений ({scope}).")
        if args.reset_offset:
            print("Смещение last_update_id сброшено.")


if __name__ == "__main__":
    cli()

