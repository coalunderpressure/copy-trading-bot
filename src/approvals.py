import asyncio
from dataclasses import replace
from typing import Any, Dict, Optional

from telethon import events
from telethon.client.telegramclient import TelegramClient

from src.models import ApprovalDecision, TradeSignal


class ApprovalService:
    def __init__(
        self,
        client: TelegramClient,
        approval_chat_id: str,
        timeout_seconds: int = 180,
        max_leverage: int = 20,
    ):
        self.client = client
        self.approval_chat_id = approval_chat_id
        self.timeout_seconds = timeout_seconds
        self.max_leverage = max_leverage
        self.pending: Dict[int, asyncio.Future] = {}
        self.pending_signals: Dict[int, TradeSignal] = {}
        self.pending_chats: Dict[int, Any] = {}
        self._lock = asyncio.Lock()

    def register_handlers(self) -> None:
        @self.client.on(events.NewMessage())
        async def on_approval_command(event):
            text = (event.raw_text or "").strip()
            if not text.startswith("/"):
                return
            await self._handle_command(text, event.chat_id)

    async def request_approval(self, signal: TradeSignal, approval_chat_id: Optional[Any] = None) -> ApprovalDecision:
        signal_id = signal.source_message_id or 0
        target_chat = approval_chat_id if approval_chat_id is not None else self.approval_chat_id
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        async with self._lock:
            self.pending[signal_id] = future
            self.pending_signals[signal_id] = signal
            self.pending_chats[signal_id] = target_chat

        await self.client.send_message(target_chat, self._format_prompt(signal, signal_id))

        try:
            decision: ApprovalDecision = await asyncio.wait_for(future, timeout=self.timeout_seconds)
            return decision
        except asyncio.TimeoutError:
            return ApprovalDecision(
                approved=False,
                reason=f"Approval timed out after {self.timeout_seconds}s",
                edited_signal=signal,
                tags=["timeout"],
            )
        finally:
            async with self._lock:
                self.pending.pop(signal_id, None)
                self.pending_signals.pop(signal_id, None)
                self.pending_chats.pop(signal_id, None)

    async def _handle_command(self, text: str, event_chat_id: Optional[int]) -> None:
        parts = text.split()
        command = parts[0].lower()
        signal_id = self._parse_signal_id(parts[1] if len(parts) > 1 else "")
        if signal_id is None:
            return

        async with self._lock:
            future = self.pending.get(signal_id)
            expected_chat = self.pending_chats.get(signal_id)
        if future is None or future.done():
            return
        if expected_chat is not None and event_chat_id is not None and str(event_chat_id) != str(expected_chat):
            return

        if command == "/approve":
            future.set_result(
                ApprovalDecision(approved=True, reason="approved by user", tags=["approved"])
            )
            return

        if command == "/reject":
            reason = " ".join(parts[2:]) if len(parts) > 2 else "rejected by user"
            future.set_result(ApprovalDecision(approved=False, reason=reason, tags=["rejected"]))
            return

        if command == "/edit":
            edits = " ".join(parts[2:]) if len(parts) > 2 else ""
            async with self._lock:
                signal = self.pending_signals.get(signal_id)
            if signal is None:
                return
            future.set_result(self.build_edit_decision(signal, edits))
            return

    def build_edit_decision(self, signal: TradeSignal, edits_text: str) -> ApprovalDecision:
        updates = {}
        for token in edits_text.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "leverage":
                parsed = int(value)
                updates["leverage"] = max(1, min(self.max_leverage, parsed))
            elif key == "margin_mode" and value in {"isolated", "cross"}:
                updates["margin_mode"] = value
            elif key == "order_type" and value in {"market", "limit"}:
                updates["order_type"] = value
            elif key == "stop_loss":
                updates["stop_loss"] = float(value)

        edited_signal = replace(signal, **updates) if updates else signal
        return ApprovalDecision(
            approved=True,
            reason="approved with edits",
            edited_signal=edited_signal,
            tags=["approved", "edited"],
        )

    def _format_prompt(self, signal: TradeSignal, signal_id: int) -> str:
        return (
            f"Signal #{signal_id}\n"
            f"Pair: {signal.pair}\n"
            f"Direction: {signal.direction}\n"
            f"Entry: {signal.entry_zone}\n"
            f"Targets: {signal.targets}\n"
            f"SL: {signal.stop_loss}\n"
            f"Leverage: {signal.leverage}x\n"
            f"Margin: {signal.margin_mode}\n"
            f"Order: {signal.order_type}\n\n"
            "Commands:\n"
            f"/approve {signal_id}\n"
            f"/reject {signal_id} <reason>\n"
            f"/edit {signal_id} leverage=10 margin_mode=isolated order_type=limit stop_loss=12345\n"
        )

    def _parse_signal_id(self, value: str) -> Optional[int]:
        try:
            return int(value)
        except ValueError:
            return None
