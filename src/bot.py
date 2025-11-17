from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from telegram import Bot

from .config import Settings
from .digest import DigestService, ThreadDiscussion, ThreadMessage
from .storage import MessageStorage, StoredMessage


def _chat_link_segment(chat_id: int) -> Optional[str]:
    chat_str = str(chat_id)
    if chat_str.startswith("-100"):
        return chat_str[4:]
    if chat_id > 0:
        return str(chat_id)
    return None


def build_message_link(chat_id: int, message_id: int) -> str:
    segment = _chat_link_segment(chat_id)
    if not segment:
        return f"(нет ссылки — чат {chat_id})"
    return f"https://t.me/c/{segment}/{message_id}"


def extract_text(message: Dict) -> Optional[str]:
    text = message.get("text")
    if isinstance(text, list):
        text = "".join(chunk.get("text", "") for chunk in text)
    if text:
        return text
    caption = message.get("caption")
    if isinstance(caption, list):
        caption = "".join(chunk.get("text", "") for chunk in caption)
    return caption


class TelegramDigestBot:
    def __init__(
        self,
        settings: Settings,
        digest_service: DigestService,
        storage: MessageStorage,
    ) -> None:
        self.settings = settings
        self.digest_service = digest_service
        self.storage = storage
        self.bot = Bot(token=settings.telegram_bot_token)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def send_weekly_digest(
        self, dry_run: bool = False, use_all_messages: bool = False
    ) -> str:
        """Отправляет дайджест. Если target_chat_id задан - для него, иначе для всех чатов."""
        if self.settings.target_chat_id:
            # Режим обратной совместимости
            result = await self.send_digest_for_chat(
                chat_id=self.settings.target_chat_id,
                dry_run=dry_run,
                use_all_messages=use_all_messages,
            )
            return result or "Нет сообщений для дайджеста"
        else:
            # Новый режим - для всех чатов
            results = await self.send_digests_for_all_chats(
                dry_run=dry_run,
                use_all_messages=use_all_messages,
            )
            if not results:
                return "Нет чатов для обработки"
            success_count = sum(1 for v in results.values() if v is not None)
            return f"Обработано {success_count} из {len(results)} чатов"

    async def send_digest_for_chat(
        self, chat_id: int, dry_run: bool = False, use_all_messages: bool = False
    ) -> Optional[str]:
        """Отправляет дайджест для конкретного чата."""
        threads = await self._collect_threads_for_chat(
            chat_id=chat_id, use_all_messages=use_all_messages
        )
        if not threads:
            self.logger.info("Нет обсуждений для чата %s", chat_id)
            return None

        self.logger.info("Собрано %s обсуждений для дайджеста (чат %s)", len(threads), chat_id)
        digest_text = await self.digest_service.build_digest(threads)

        if dry_run:
            print(f"\n=== Дайджест для чата {chat_id} ===\n{digest_text}\n")
            return digest_text

        await self.bot.send_message(
            chat_id=chat_id,
            text=digest_text,
            disable_web_page_preview=True,
        )
        self.logger.info("Дайджест отправлен в чат %s", chat_id)

        removed = self.storage.clear_messages(chat_id=chat_id)
        self.logger.info("Очищено %s сообщений из базы (чат %s)", removed, chat_id)
        return digest_text

    async def send_digests_for_all_chats(
        self, dry_run: bool = False, use_all_messages: bool = False
    ) -> Dict[int, Optional[str]]:
        """Отправляет дайджесты для всех чатов из базы."""
        chats = self.storage.list_chats()
        if not chats:
            self.logger.warning("В базе нет чатов для обработки")
            return {}

        results: Dict[int, Optional[str]] = {}
        for chat_info in chats:
            try:
                digest = await self.send_digest_for_chat(
                    chat_id=chat_info.chat_id,
                    dry_run=dry_run,
                    use_all_messages=use_all_messages,
                )
                results[chat_info.chat_id] = digest
            except Exception as e:
                self.logger.error(
                    "Ошибка при отправке дайджеста для чата %s: %s",
                    chat_info.chat_id,
                    e,
                    exc_info=True,
                )
                results[chat_info.chat_id] = None

        return results

    async def _collect_threads_for_chat(
        self, chat_id: int, use_all_messages: bool = False
    ) -> List[ThreadDiscussion]:
        """Собирает треды для конкретного чата."""
        if use_all_messages:
            since_ts = None
        else:
            since_ts = int(
                (
                    datetime.now(timezone.utc)
                    - timedelta(days=self.settings.digest_lookback_days)
                ).timestamp()
            )
        stored_messages = self.storage.load_messages(
            chat_id=chat_id,
            since_ts=since_ts,
            limit=self.settings.max_messages,
        )
        return self._group_threads(stored_messages, chat_id=chat_id)

    async def _collect_threads(
        self, use_all_messages: bool = False
    ) -> List[ThreadDiscussion]:
        """Устаревший метод для обратной совместимости."""
        if not self.settings.target_chat_id:
            raise ValueError("target_chat_id не задан, используйте send_digest_for_chat")
        return await self._collect_threads_for_chat(
            chat_id=self.settings.target_chat_id,
            use_all_messages=use_all_messages,
        )

    def _group_threads(
        self, raw_messages: List[StoredMessage], chat_id: Optional[int] = None
    ) -> List[ThreadDiscussion]:
        """Группирует сообщения в треды. chat_id используется для генерации ссылок."""
        if not raw_messages:
            return []

        # Используем chat_id из первого сообщения, если не передан явно
        if chat_id is None:
            chat_id = raw_messages[0].chat_id

        threads: Dict[int, Dict] = {}
        aggregations: Dict[int, List[ThreadMessage]] = defaultdict(list)

        for message in raw_messages:
            text = message.text
            message_id = message.message_id
            thread_key = message.thread_key
            if thread_key not in threads:
                topic_preview = text.split("\n", 1)[0][:120]
                threads[thread_key] = {
                    "topic": topic_preview or f"Обсуждение {thread_key}",
                    "link_message_id": message_id,
                }
            else:
                threads[thread_key]["link_message_id"] = min(
                    threads[thread_key]["link_message_id"], message_id
                )

            aggregations[thread_key].append(
                ThreadMessage(
                    message_id=message_id,
                    author=message.author,
                    text=text,
                    date=datetime.fromtimestamp(message.date, tz=timezone.utc),
                    link=build_message_link(chat_id, message_id),
                )
            )

        discussions: List[ThreadDiscussion] = []
        for key, meta in threads.items():
            messages = aggregations.get(key, [])
            if not messages:
                continue
            discussions.append(
                ThreadDiscussion(
                    topic=meta["topic"],
                    link=build_message_link(chat_id, meta["link_message_id"]),
                    messages=messages,
                )
            )
        discussions.sort(key=lambda d: d.messages[0].date)
        return discussions

