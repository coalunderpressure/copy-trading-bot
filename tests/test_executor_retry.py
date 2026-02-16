import asyncio

from src.config import Settings
from src.executor import ExchangeExecutor


class _DummyExchange:
    async def close(self) -> None:
        return None


class _TestExecutor(ExchangeExecutor):
    def _build_exchange(self):
        return _DummyExchange()


def _settings() -> Settings:
    return Settings(
        telegram_api_id=1,
        telegram_api_hash="x",
        telegram_session_name="test",
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
        allowed_pairs={"BTC/USDT"},
        state_db_path=":memory:",
        executor_max_retries=2,
        executor_retry_delay_ms=0,
    )


def test_retry_succeeds_after_transient_failures():
    executor = _TestExecutor(settings=_settings())
    attempts = {"count": 0}

    async def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TimeoutError("temporary timeout")
        return "ok"

    result = asyncio.run(executor._call_with_retry("flaky", flaky))
    assert result == "ok"
    assert attempts["count"] == 3


def test_retry_exhausted_raises():
    executor = _TestExecutor(settings=_settings())
    attempts = {"count": 0}

    async def always_fails():
        attempts["count"] += 1
        raise TimeoutError("still failing")

    try:
        asyncio.run(executor._call_with_retry("always_fails", always_fails))
        assert False, "Expected TimeoutError"
    except TimeoutError:
        pass

    # max_retries=2 means total attempts=3
    assert attempts["count"] == 3


def test_non_retryable_raises_immediately():
    executor = _TestExecutor(settings=_settings())
    attempts = {"count": 0}

    async def bad_request():
        attempts["count"] += 1
        raise ValueError("invalid order params")

    try:
        asyncio.run(executor._call_with_retry("bad_request", bad_request))
        assert False, "Expected ValueError"
    except ValueError:
        pass

    assert attempts["count"] == 1
