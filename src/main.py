import asyncio
import json
from pathlib import Path

from src.approvals import ApprovalService
from src.config import load_settings
from src.executor import ExchangeExecutor
from src.listener import IncomingMessage, create_client, register_channel_handler
from src.parser import SignalParser


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
    approvals.register_handlers()

    logs = Path("logs")
    logs.mkdir(parents=True, exist_ok=True)
    raw_log = logs / "raw_messages.jsonl"

    async def on_message(msg: IncomingMessage):
        with raw_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg.__dict__, ensure_ascii=True) + "\n")

        signal = await parser.parse_signal(msg.text, msg.media_path)
        if signal is None:
            return
        signal.source_message_id = msg.message_id

        decision = await approvals.request_approval(signal)
        if not decision.approved:
            await client.send_message(
                settings.approval_chat_id,
                f"Signal #{msg.message_id} rejected: {decision.reason}",
            )
            return

        result = await executor.execute(decision.edited_signal or signal)
        await client.send_message(settings.approval_chat_id, f"Execution result: {result}")

    register_channel_handler(client, settings, on_message)
    await client.start()
    try:
        await client.run_until_disconnected()
    finally:
        await executor.close()


if __name__ == "__main__":
    asyncio.run(run())
