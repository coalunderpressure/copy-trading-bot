import json
from typing import Optional

from jsonschema import ValidationError, validate

from src.models import TradeSignal

SIGNAL_SCHEMA = {
    "type": "object",
    "required": ["pair", "direction", "entry_zone", "targets", "stop_loss"],
    "properties": {
        "pair": {"type": "string", "minLength": 3},
        "direction": {"type": "string", "enum": ["LONG", "SHORT"]},
        "entry_zone": {"type": "array", "minItems": 1, "items": {"type": "number"}},
        "targets": {"type": "array", "minItems": 1, "items": {"type": "number"}},
        "stop_loss": {"type": "number"},
        "leverage": {"type": "integer", "minimum": 1, "maximum": 125},
        "margin_mode": {"type": "string", "enum": ["isolated", "cross"]},
        "order_type": {"type": "string", "enum": ["market", "limit"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


class SignalParser:
    def __init__(self, model_name: str):
        self.model_name = model_name

    async def parse_signal(self, text: str, image_path: Optional[str] = None) -> Optional[TradeSignal]:
        # Placeholder parser. Real LLM integration is a follow-up task.
        if not text.strip():
            return None

        maybe_json = self._extract_json(text)
        if maybe_json is None:
            return None

        try:
            data = json.loads(maybe_json)
            validate(instance=data, schema=SIGNAL_SCHEMA)
            return TradeSignal(
                pair=data["pair"],
                direction=data["direction"],
                entry_zone=[float(x) for x in data["entry_zone"]],
                targets=[float(x) for x in data["targets"]],
                stop_loss=float(data["stop_loss"]),
                leverage=int(data.get("leverage", 5)),
                margin_mode=data.get("margin_mode", "isolated"),
                order_type=data.get("order_type", "limit"),
                confidence=float(data.get("confidence", 0.0)),
                raw_text=text,
                media_path=image_path,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
            return None

    def _extract_json(self, text: str) -> Optional[str]:
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            return text
        return None
