import asyncio
from dataclasses import replace
from typing import Any, Dict, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.models import ApprovalDecision, TradeSignal


class BotApprovalService:
    def __init__(
        self,
        bot_token: str,
        approval_chat_id: Any,
        timeout_seconds: int = 180,
        max_leverage: int = 20,
    ):
        self.approval_chat_id = approval_chat_id
        self.timeout_seconds = timeout_seconds
        self.max_leverage = max_leverage
        self.pending: Dict[int, asyncio.Future] = {}
        self.pending_signals: Dict[int, TradeSignal] = {}
        self._lock = asyncio.Lock()

        self.application = Application.builder().token(bot_token).build()
        self.application.add_handler(CommandHandler("approve", self._on_approve))
        self.application.add_handler(CommandHandler("reject", self._on_reject))
        self.application.add_handler(CommandHandler("edit", self._on_edit))

    async def start(self) -> None:
        await self.application.initialize()
        await self.application.start()
        if self.application.updater is None:
            raise RuntimeError("Telegram updater is not available")
        await self.application.updater.start_polling()

    async def stop(self) -> None:
        if self.application.updater is not None:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    async def send_message(self, text: str) -> None:
        await self.application.bot.send_message(chat_id=self.approval_chat_id, text=text)

    async def request_approval(self, signal: TradeSignal) -> ApprovalDecision:
        signal_id = signal.source_message_id or 0
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        async with self._lock:
            self.pending[signal_id] = future
            self.pending_signals[signal_id] = signal

        await self.send_message(self._format_prompt(signal, signal_id))

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

    async def _on_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._apply_command("/approve", context.args, update)

    async def _on_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._apply_command("/reject", context.args, update)

    async def _on_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._apply_command("/edit", context.args, update)

    async def _apply_command(
        self,
        command: str,
        args: list[str],
        update: Update,
    ) -> None:
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id is None or str(chat_id) != str(self.approval_chat_id):
            return
        signal_id = self._parse_signal_id(args[0] if args else "")
        if signal_id is None:
            return

        async with self._lock:
            future = self.pending.get(signal_id)
        if future is None or future.done():
            return

        if command == "/approve":
            future.set_result(
                ApprovalDecision(approved=True, reason="approved by user", tags=["approved"])
            )
            return

        if command == "/reject":
            reason = " ".join(args[1:]) if len(args) > 1 else "rejected by user"
            future.set_result(ApprovalDecision(approved=False, reason=reason, tags=["rejected"]))
            return

        if command == "/edit":
            edits = " ".join(args[1:]) if len(args) > 1 else ""
            async with self._lock:
                signal = self.pending_signals.get(signal_id)
            if signal is None:
                return
            future.set_result(self.build_edit_decision(signal, edits))

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
