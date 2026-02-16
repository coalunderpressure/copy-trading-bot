import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Settings:
    telegram_api_id: int
    telegram_api_hash: str
    telegram_bot_token: str
    telegram_session_name: str
    telegram_channel_id: int
    approval_chat_id: str
    approval_timeout_seconds: int
    openai_api_key: str
    openai_model: str
    exchange_name: str
    exchange_api_key: str
    exchange_api_secret: str
    exchange_testnet: bool
    default_leverage: int
    default_margin_mode: str
    fixed_position_usdt: float
    dry_run: bool
    max_leverage: int
    allowed_pairs: Optional[set[str]]
    state_db_path: str
    executor_max_retries: int
    executor_retry_delay_ms: int


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {key}")
    return value


def load_settings() -> Settings:
    load_dotenv()
    allowed_pairs_raw = os.getenv("ALLOWED_PAIRS", "").strip()
    allowed_pairs = None
    if allowed_pairs_raw:
        allowed_pairs = {item.strip().upper() for item in allowed_pairs_raw.split(",") if item.strip()}

    return Settings(
        telegram_api_id=int(_require("TELEGRAM_API_ID")),
        telegram_api_hash=_require("TELEGRAM_API_HASH"),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_session_name=os.getenv("TELEGRAM_SESSION_NAME", "copy_trading_userbot"),
        telegram_channel_id=int(_require("TELEGRAM_CHANNEL_ID")),
        approval_chat_id=os.getenv("APPROVAL_CHAT_ID", "me"),
        approval_timeout_seconds=int(os.getenv("APPROVAL_TIMEOUT_SECONDS", "180")),
        openai_api_key=_require("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        exchange_name=os.getenv("EXCHANGE_NAME", "binance"),
        exchange_api_key=_require("EXCHANGE_API_KEY"),
        exchange_api_secret=_require("EXCHANGE_API_SECRET"),
        exchange_testnet=os.getenv("EXCHANGE_TESTNET", "true").lower() == "true",
        default_leverage=int(os.getenv("DEFAULT_LEVERAGE", "5")),
        default_margin_mode=os.getenv("DEFAULT_MARGIN_MODE", "isolated"),
        fixed_position_usdt=float(os.getenv("FIXED_POSITION_USDT", "50")),
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
        max_leverage=int(os.getenv("MAX_LEVERAGE", "20")),
        allowed_pairs=allowed_pairs,
        state_db_path=os.getenv("STATE_DB_PATH", "data/state.db"),
        executor_max_retries=int(os.getenv("EXECUTOR_MAX_RETRIES", "2")),
        executor_retry_delay_ms=int(os.getenv("EXECUTOR_RETRY_DELAY_MS", "500")),
    )
