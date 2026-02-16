import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.bot_approvals import BotApprovalService
from src.config import load_settings
from src.executor import ExchangeExecutor
from src.listener import IncomingMessage, create_client, register_channel_handler
from src.parser import SignalParser
from src.state_store import SignalStateStore


def _display_chat_label(chat_target: Any) -> str:
    if isinstance(chat_target, str):
        value = chat_target.strip()
        if not value:
            return "Configured chat"
        if value.lower() == "me":
            return "Saved Messages"
        if value.lstrip("-").isdigit():
            return "Configured private chat"
        return value if value.startswith("@") else f"@{value}"
    return "Configured private chat"


def _build_startup_message(settings, channel_label: str) -> str:
    started_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    mode_label = "Dry Run" if settings.dry_run else "Live Trading"
    approval_label = _display_chat_label(settings.approval_chat_id)
    return (
        "🟢 Copy Trading Bot is online\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Source: {channel_label}\n"
        f"💬 Approval: {approval_label}\n"
        f"🧪 Mode: {mode_label}\n"
        f"💵 Paper Balance: {settings.paper_total_balance_usdt:.2f} USDT\n"
        f"🏦 Exchange: {settings.exchange_name}\n"
        f"🕒 Started: {started_at_utc}"
    )


async def _resolve_channel_label(user_client, channel_target: Any) -> str:
    if isinstance(channel_target, str) and channel_target.lower() == "me":
        return "Saved Messages"
    try:
        entity = await user_client.get_entity(channel_target)
    except Exception:
        if isinstance(channel_target, str):
            return channel_target if channel_target.startswith("@") else f"@{channel_target}"
        return "Configured channel"

    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    title = getattr(entity, "title", None)
    if title:
        return title
    first_name = getattr(entity, "first_name", None)
    if first_name:
        return first_name
    return "Configured channel"


async def run() -> None:
    settings = load_settings()
    parser = SignalParser(model_name=settings.openai_model)
    user_client = create_client(settings)
    approvals = BotApprovalService(
        bot_token=settings.telegram_bot_token,
        approval_chat_id=settings.approval_chat_id,
        timeout_seconds=settings.approval_timeout_seconds,
        max_leverage=settings.max_leverage,
        total_balance_usdt=settings.paper_total_balance_usdt,
    )
    executor = ExchangeExecutor(settings=settings)
    state_store = SignalStateStore(db_path=settings.state_db_path)
    await approvals.start()

    logs = Path("logs")
    logs.mkdir(parents=True, exist_ok=True)
    raw_log = logs / "raw_messages.jsonl"

    async def on_message(msg: IncomingMessage):
        if state_store.has_message(msg.message_id):
            await approvals.send_message(f"Signal #{msg.message_id} ignored: already processed.")
            return

        state_store.record_incoming(msg)

        with raw_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg.__dict__, ensure_ascii=True) + "\n")

        signal = await parser.parse_signal(msg.text, msg.media_path)
        if signal is None:
            state_store.mark_parse_failed(msg.message_id, "invalid signal format")
            return
        signal.source_message_id = msg.message_id
        state_store.mark_parsed(signal)

        decision = await approvals.request_approval(signal)
        if not decision.approved:
            state_store.mark_rejected(msg.message_id, decision)
            await approvals.send_message(f"Signal #{msg.message_id} rejected: {decision.reason}")
            return

        state_store.mark_approved(msg.message_id, decision)
        result = await executor.execute(decision.edited_signal or signal)
        state_store.mark_executed(msg.message_id, result)
        await approvals.send_message(f"Execution result: {result}")

    register_channel_handler(user_client, settings, on_message)
    await user_client.start()
    try:
        channel_label = await _resolve_channel_label(user_client, settings.telegram_channel_id)
        await approvals.send_message(_build_startup_message(settings, channel_label))
        await user_client.run_until_disconnected()
    finally:
        await approvals.stop()
        await executor.close()
        state_store.close()


if __name__ == "__main__":
    asyncio.run(run())
