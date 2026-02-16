import asyncio
from dataclasses import replace
from typing import Any, Dict, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.models import ApprovalDecision, TradeSignal


class BotApprovalService:
    def __init__(
        self,
        bot_token: str,
        approval_chat_id: Any,
        timeout_seconds: int = 180,
        max_leverage: int = 20,
        total_balance_usdt: float = 50.0,
    ):
        self.approval_chat_id = approval_chat_id
        self.timeout_seconds = timeout_seconds
        self.max_leverage = max_leverage
        self.total_balance_usdt = total_balance_usdt
        self.pending: Dict[int, asyncio.Future] = {}
        self.pending_signals: Dict[int, TradeSignal] = {}
        self.pending_sizes: Dict[int, float] = {}
        self._lock = asyncio.Lock()

        self.application = Application.builder().token(bot_token).build()
        self.application.add_handler(CallbackQueryHandler(self._on_button))
        self.application.add_handler(CommandHandler("approve", self._on_approve))
        self.application.add_handler(CommandHandler("reject", self._on_reject))
        self.application.add_handler(CommandHandler("edit", self._on_edit))
        self.application.add_handler(CommandHandler("size", self._on_size))

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

        await self.application.bot.send_message(
            chat_id=self.approval_chat_id,
            text=self._format_prompt(signal, signal_id),
            reply_markup=self._build_approval_keyboard(signal_id),
        )

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
                self.pending_sizes.pop(signal_id, None)

    async def _on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return
        chat_id = query.message.chat_id if query.message else None
        if chat_id is None or str(chat_id) != str(self.approval_chat_id):
            await query.answer()
            return

        parsed = self._parse_callback_data(query.data or "")
        if parsed is None:
            await query.answer("Unknown action")
            return
        signal_id, action, payload = parsed

        async with self._lock:
            future = self.pending.get(signal_id)
            signal = self.pending_signals.get(signal_id)
        if future is None or future.done():
            await query.answer("Signal no longer pending")
            return

        if action == "approve":
            sized = self._apply_selected_size(signal_id, signal)
            if sized is None:
                await query.answer("Select size first")
                return
            future.set_result(
                ApprovalDecision(
                    approved=True,
                    reason="approved by button",
                    edited_signal=sized,
                    tags=["approved", "button"],
                )
            )
            await query.answer("Approved")
            return

        if action == "reject":
            future.set_result(
                ApprovalDecision(approved=False, reason="rejected by button", tags=["rejected", "button"])
            )
            await query.answer("Rejected")
            return

        if action == "set_pct":
            size = self._pct_to_size(payload)
            if size is None:
                await query.answer("Invalid size")
                return
            async with self._lock:
                self.pending_sizes[signal_id] = size
            await query.answer(f"Size set: {size:.2f} USDT")
            return

        if action == "edit":
            if signal is None:
                await query.answer("Signal not found")
                return
            future.set_result(self.build_edit_decision(signal, payload))
            await query.answer("Approved with edit")
            return

        await query.answer("Unsupported action")

    async def _on_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._apply_command("/approve", context.args, update, context)

    async def _on_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._apply_command("/reject", context.args, update, context)

    async def _on_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._apply_command("/edit", context.args, update, context)

    async def _on_size(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id is None or str(chat_id) != str(self.approval_chat_id):
            return
        if len(context.args) < 2:
            return
        signal_id = self._parse_signal_id(context.args[0])
        if signal_id is None:
            return

        parsed = self._parse_size_token(context.args[1])
        if parsed is None:
            return

        async with self._lock:
            future = self.pending.get(signal_id)
        if future is None or future.done():
            return

        async with self._lock:
            self.pending_sizes[signal_id] = parsed
        await context.bot.send_message(
            chat_id=self.approval_chat_id,
            text=f"Size set for #{signal_id}: {parsed:.2f} USDT",
        )

    async def _apply_command(
        self,
        command: str,
        args: list[str],
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
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
            async with self._lock:
                signal = self.pending_signals.get(signal_id)
            if signal is None:
                return
            sized = self._apply_selected_size(signal_id, signal)
            if sized is None:
                await context.bot.send_message(
                    chat_id=self.approval_chat_id,
                    text=(
                        f"Signal #{signal_id}: choose size first.\n"
                        f"Use buttons or /size {signal_id} 20  (or /size {signal_id} 40%)"
                    ),
                )
                return
            future.set_result(
                ApprovalDecision(
                    approved=True,
                    reason="approved by user",
                    edited_signal=sized,
                    tags=["approved"],
                )
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
            f"Order: {signal.order_type}\n"
            f"Paper balance: {self.total_balance_usdt:.2f} USDT\n\n"
            "1) Select position size (buttons or /size)\n"
            "2) Approve / Reject\n\n"
            "Use inline buttons below, or fallback commands:\n"
            f"/approve {signal_id}\n"
            f"/reject {signal_id} <reason>\n"
            f"/size {signal_id} 20      (USDT)\n"
            f"/size {signal_id} 40%     (percent of paper balance)\n"
            f"/edit {signal_id} leverage=10 margin_mode=isolated order_type=limit stop_loss=12345\n"
        )

    def _build_approval_keyboard(self, signal_id: int) -> InlineKeyboardMarkup:
        pct25 = self.total_balance_usdt * 0.25
        pct50 = self.total_balance_usdt * 0.50
        pct100 = self.total_balance_usdt
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Approve", callback_data=f"sig:{signal_id}:approve"),
                    InlineKeyboardButton("Reject", callback_data=f"sig:{signal_id}:reject"),
                ],
                [
                    InlineKeyboardButton(
                        f"25% ({pct25:.2f}u)", callback_data=f"sig:{signal_id}:set_pct:25"
                    ),
                    InlineKeyboardButton(
                        f"50% ({pct50:.2f}u)", callback_data=f"sig:{signal_id}:set_pct:50"
                    ),
                    InlineKeyboardButton(
                        f"100% ({pct100:.2f}u)", callback_data=f"sig:{signal_id}:set_pct:100"
                    ),
                ],
                [
                    InlineKeyboardButton("Market", callback_data=f"sig:{signal_id}:edit:order_type=market"),
                    InlineKeyboardButton("5x", callback_data=f"sig:{signal_id}:edit:leverage=5"),
                    InlineKeyboardButton("10x", callback_data=f"sig:{signal_id}:edit:leverage=10"),
                ],
            ]
        )

    def _parse_callback_data(self, data: str) -> Optional[Tuple[int, str, str]]:
        # Format: sig:<signal_id>:<action>[:<payload>]
        parts = data.split(":", 3)
        if len(parts) < 3 or parts[0] != "sig":
            return None
        signal_id = self._parse_signal_id(parts[1])
        if signal_id is None:
            return None
        action = parts[2]
        payload = parts[3] if len(parts) == 4 else ""
        return signal_id, action, payload

    def _pct_to_size(self, value: str) -> Optional[float]:
        try:
            pct = float(value)
        except ValueError:
            return None
        if pct <= 0:
            return None
        return self.total_balance_usdt * (pct / 100.0)

    def _parse_size_token(self, token: str) -> Optional[float]:
        raw = token.strip()
        if not raw:
            return None
        if raw.endswith("%"):
            return self._pct_to_size(raw[:-1])
        try:
            usdt = float(raw)
        except ValueError:
            return None
        if usdt <= 0 or usdt > self.total_balance_usdt:
            return None
        return usdt

    def _apply_selected_size(self, signal_id: int, signal: Optional[TradeSignal]) -> Optional[TradeSignal]:
        if signal is None:
            return None
        size = self.pending_sizes.get(signal_id)
        if size is None:
            return None
        return replace(signal, position_size_usdt=float(size))

    def _parse_signal_id(self, value: str) -> Optional[int]:
        try:
            return int(value)
        except ValueError:
            return None
