from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, events

from src.config import Settings


@dataclass
class IncomingMessage:
    message_id: int
    chat_id: int
    text: str
    media_path: Optional[str]


def create_client(settings: Settings) -> TelegramClient:
    return TelegramClient(
        settings.telegram_session_name,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )


def register_channel_handler(client: TelegramClient, settings: Settings, callback):
    downloads = Path("downloads")
    downloads.mkdir(parents=True, exist_ok=True)

    @client.on(events.NewMessage(chats=settings.telegram_channel_id))
    async def on_new_message(event):
        media_path = None
        if event.message.media:
            target = downloads / f"{event.message.id}"
            media_path = await event.message.download_media(file=target.as_posix())

        incoming = IncomingMessage(
            message_id=event.message.id,
            chat_id=event.chat_id or 0,
            text=event.raw_text or "",
            media_path=media_path,
        )
        await callback(incoming)

    return on_new_message
