from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timezone
from typing import Dict, List, Optional

from telegram import Bot, Chat, Update

from .config import Settings
from .storage import MessageStorage, StoredMessage
from .bot import extract_text

logger = logging.getLogger(__name__)


@dataclass
class BotChatInfo:
    chat_id: int
    title: str
    chat_type: str
    username: Optional[str]
    first_seen_update_id: Optional[int] = None


class SyncService:
    def __init__(self, settings: Settings, storage: MessageStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.bot = Bot(token=settings.telegram_bot_token)

    async def sync_updates(self, limit_batches: Optional[int] = None) -> int:
        """
        Загружает новые апдейты через getUpdates и сохраняет сообщения в SQLite.
        Возвращает количество сохранённых сообщений.
        """

        last_update_id = self.storage.get_last_update_id()
        offset = last_update_id + 1 if last_update_id is not None else None
        total_saved = 0
        batches_processed = 0

        while True:
            updates: List[Update] = await self.bot.get_updates(
                offset=offset,
                timeout=30,
                allowed_updates=["message"],
            )
            if not updates:
                logger.info("Обновлений не поступило (offset=%s)", offset)
                break

            logger.info("Получено %s апдейтов (offset=%s)", len(updates), offset)

            records: List[StoredMessage] = []
            for update in updates:
                message = update.effective_message
                if not message:
                    logger.debug(
                        "Пропущен апдейт %s (нет сообщения)",
                        update.update_id,
                    )
                    continue
                text = extract_text(message.to_dict())
                if not text:
                    logger.debug(
                        "Пропущено сообщение без текста (chat_id=%s, message_id=%s)",
                        message.chat_id,
                        message.message_id,
                    )
                    continue
                logger.debug(
                    "Сообщение %s/%s: %s",
                    message.chat_id,
                    message.message_id,
                    text[:80],
                )
                records.append(
                    StoredMessage(
                        chat_id=message.chat_id,
                        message_id=message.message_id,
                        thread_key=_thread_key(message),
                        author=_format_author(message.from_user),
                        text=text,
                        date=int(message.date.replace(tzinfo=timezone.utc).timestamp()),
                        raw=message.to_dict(),
                    )
                )

            saved = self.storage.save_messages(records)
            total_saved += saved
            logger.info("Сохранено %s новых сообщений", saved)
            self.storage.set_last_update_id(updates[-1].update_id)
            offset = updates[-1].update_id + 1

            batches_processed += 1
            if limit_batches and batches_processed >= limit_batches:
                break

        return total_saved

    async def get_bot_chats(self) -> List[BotChatInfo]:
        """
        Получает список всех чатов, где бот является участником.
        Использует информацию из базы данных и проверяет доступность через getChat.
        """
        # Получаем уникальные chat_id из базы данных
        stored_chats = self.storage.list_chats()
        if not stored_chats:
            logger.info("База данных пустая. Нет чатов для проверки.")
            return []

        bot_chats: List[BotChatInfo] = []
        
        for stored_chat in stored_chats:
            try:
                # Проверяем доступность чата через getChat
                chat: Chat = await self.bot.get_chat(chat_id=stored_chat.chat_id)
                
                # Пропускаем личные чаты
                if chat.type == "private":
                    continue
                
                bot_chats.append(
                    BotChatInfo(
                        chat_id=chat.id,
                        title=chat.title or chat.username or f"Chat {chat.id}",
                        chat_type=chat.type,
                        username=chat.username,
                        first_seen_update_id=None,
                    )
                )
            except Exception as e:
                # Если getChat не удался, значит бот больше не имеет доступа к чату
                logger.debug(
                    "Бот не имеет доступа к чату %s (%s): %s",
                    stored_chat.chat_id,
                    stored_chat.title,
                    e,
                )
                continue

        return bot_chats


def _thread_key(message) -> int:
    if getattr(message, "message_thread_id", None):
        return message.message_thread_id
    if message.reply_to_message:
        return message.reply_to_message.message_id
    return message.message_id


def _format_author(user) -> str:
    if not user:
        return "Неизвестный участник"
    if user.username:
        return user.username
    full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip()
    return full_name or "Неизвестный участник"

