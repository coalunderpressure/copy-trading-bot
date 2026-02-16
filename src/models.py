from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TradeSignal:
    pair: str
    direction: str
    entry_zone: List[float]
    targets: List[float]
    stop_loss: float
    leverage: int = 5
    margin_mode: str = "isolated"
    order_type: str = "limit"
    confidence: float = 0.0
    source_message_id: Optional[int] = None
    raw_text: str = ""
    media_path: Optional[str] = None


@dataclass
class ApprovalDecision:
    approved: bool
    reason: str = ""
    edited_signal: Optional[TradeSignal] = None
    tags: List[str] = field(default_factory=list)
