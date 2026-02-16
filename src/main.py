import asyncio
import json
from pathlib import Path

from src.approvals import ApprovalService
from src.config import load_settings
from src.executor import ExchangeExecutor
from src.listener import IncomingMessage, create_client, register_channel_handler
from src.parser import SignalParser
from src.state_store import SignalStateStore


async def run() -> None:
    settings = load_settings()
    parser = SignalParser(model_name=settings.openai_model)
    client = create_client(settings)
    approvals = ApprovalService(
        client=client,
        approval_chat_id=settings.approval_chat_id,
        timeout_seconds=settings.approval_timeout_seconds,
        max_leverage=settings.max_leverage,
    )
    executor = ExchangeExecutor(settings=settings)
    state_store = SignalStateStore(db_path=settings.state_db_path)
    approvals.register_handlers()

    logs = Path("logs")
    logs.mkdir(parents=True, exist_ok=True)
    raw_log = logs / "raw_messages.jsonl"

    async def on_message(msg: IncomingMessage):
        if state_store.has_message(msg.message_id):
            await client.send_message(
                settings.approval_chat_id,
                f"Signal #{msg.message_id} ignored: already processed.",
            )
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
            await client.send_message(
                settings.approval_chat_id,
                f"Signal #{msg.message_id} rejected: {decision.reason}",
            )
            return

        state_store.mark_approved(msg.message_id, decision)
        result = await executor.execute(decision.edited_signal or signal)
        state_store.mark_executed(msg.message_id, result)
        await client.send_message(settings.approval_chat_id, f"Execution result: {result}")

    register_channel_handler(client, settings, on_message)
    await client.start()
    try:
        await client.run_until_disconnected()
    finally:
        await executor.close()
        state_store.close()


if __name__ == "__main__":
    asyncio.run(run())
