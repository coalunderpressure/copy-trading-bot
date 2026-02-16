import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import Settings
from src.executor import ExchangeExecutor
from src.models import TradeSignal
from src.parser import SignalParser


async def main() -> None:
    parser = SignalParser(model_name="smoke-test")
    text = (
        '{"pair":"BTC/USDT","direction":"LONG","entry_zone":[50000,50100],'
        '"targets":[50500,51000],"stop_loss":49500,"leverage":5,'
        '"margin_mode":"isolated","order_type":"limit","confidence":0.8}'
    )
    signal = await parser.parse_signal(text=text)
    if signal is None:
        raise RuntimeError("Smoke parse failed")

    settings = Settings(
        telegram_api_id=1,
        telegram_api_hash="x",
        telegram_bot_token="x:y",
        telegram_session_name="smoke",
        telegram_channel_id=1,
        approval_chat_id="me",
        approval_timeout_seconds=60,
        openai_api_key="x",
        openai_model="gpt-4o-mini",
        exchange_name="binance",
        exchange_api_key="x",
        exchange_api_secret="x",
        exchange_testnet=True,
        default_leverage=5,
        default_margin_mode="isolated",
        fixed_position_usdt=50.0,
        dry_run=True,
        max_leverage=20,
        allowed_pairs={"BTC/USDT", "ETH/USDT"},
        state_db_path="data/state.db",
        executor_max_retries=2,
        executor_retry_delay_ms=500,
    )
    executor = ExchangeExecutor(settings=settings)
    try:
        result = await executor.execute(signal)
        print(result)
    finally:
        await executor.close()


if __name__ == "__main__":
    asyncio.run(main())
