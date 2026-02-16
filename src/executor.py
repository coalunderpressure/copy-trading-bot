from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt_async

from src.config import Settings
from src.models import TradeSignal


class ExchangeExecutor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.exchange_name = settings.exchange_name
        self.exchange = self._build_exchange()

    def _build_exchange(self):
        exchange_cls = getattr(ccxt_async, self.exchange_name, None)
        if exchange_cls is None:
            raise ValueError(f"Unsupported exchange: {self.exchange_name}")

        exchange = exchange_cls(
            {
                "apiKey": self.settings.exchange_api_key,
                "secret": self.settings.exchange_api_secret,
                "enableRateLimit": True,
            }
        )
        if self.settings.exchange_testnet and hasattr(exchange, "set_sandbox_mode"):
            exchange.set_sandbox_mode(True)
        return exchange

    async def execute(self, signal: TradeSignal) -> Dict[str, Any]:
        actions: List[Dict[str, Any]] = []
        try:
            self._validate_signal(signal)
            if self.settings.dry_run:
                actions.append(
                    {
                        "step": "dry_run",
                        "status": "ok",
                        "pair": signal.pair,
                        "order_type": signal.order_type,
                        "direction": signal.direction,
                        "targets": signal.targets,
                        "stop_loss": signal.stop_loss,
                    }
                )
                return {"status": "ok", "exchange": self.exchange_name, "actions": actions}

            await self.exchange.load_markets()
            await self._safe_set_leverage(signal, actions)
            await self._safe_set_margin_mode(signal, actions)

            side = "buy" if signal.direction == "LONG" else "sell"
            entry_price = self._entry_price(signal)
            amount = await self._calculate_amount(signal.pair, entry_price)
            order_type = "market" if signal.order_type == "market" else "limit"

            order = await self.exchange.create_order(
                symbol=signal.pair,
                type=order_type,
                side=side,
                amount=amount,
                price=None if order_type == "market" else entry_price,
                params={},
            )
            actions.append({"step": "entry", "status": "ok", "id": order.get("id")})

            await self._safe_create_stop_loss(signal, amount, actions)
            await self._safe_create_take_profits(signal, amount, actions)
            return {"status": "ok", "exchange": self.exchange_name, "actions": actions}
        except Exception as exc:
            actions.append({"step": "execute", "status": "error", "error": str(exc)})
            return {"status": "error", "exchange": self.exchange_name, "actions": actions}

    async def close(self) -> None:
        await self.exchange.close()

    async def _calculate_amount(self, symbol: str, entry_price: float) -> float:
        ticker = await self.exchange.fetch_ticker(symbol)
        reference_price = entry_price or float(ticker["last"])
        raw_amount = self.settings.fixed_position_usdt / reference_price
        return float(self.exchange.amount_to_precision(symbol, raw_amount))

    def _entry_price(self, signal: TradeSignal) -> float:
        if not signal.entry_zone:
            raise ValueError("Entry zone is empty")
        return float(sum(signal.entry_zone) / len(signal.entry_zone))

    def _validate_signal(self, signal: TradeSignal) -> None:
        if self.settings.allowed_pairs and signal.pair.upper() not in self.settings.allowed_pairs:
            raise ValueError(f"Pair not allowed by policy: {signal.pair}")

        if signal.leverage > self.settings.max_leverage:
            raise ValueError(
                f"Leverage {signal.leverage} exceeds max leverage policy {self.settings.max_leverage}"
            )

        entry = self._entry_price(signal)
        if signal.direction == "LONG" and signal.stop_loss >= entry:
            raise ValueError("Stop loss must be below entry for LONG signals")
        if signal.direction == "SHORT" and signal.stop_loss <= entry:
            raise ValueError("Stop loss must be above entry for SHORT signals")

    async def _safe_set_leverage(self, signal: TradeSignal, actions: List[Dict[str, Any]]) -> None:
        if not hasattr(self.exchange, "set_leverage"):
            actions.append({"step": "set_leverage", "status": "skipped"})
            return
        try:
            await self.exchange.set_leverage(signal.leverage, signal.pair)
            actions.append({"step": "set_leverage", "status": "ok", "value": signal.leverage})
        except Exception as exc:
            actions.append({"step": "set_leverage", "status": "error", "error": str(exc)})

    async def _safe_set_margin_mode(self, signal: TradeSignal, actions: List[Dict[str, Any]]) -> None:
        if not hasattr(self.exchange, "set_margin_mode"):
            actions.append({"step": "set_margin_mode", "status": "skipped"})
            return
        try:
            await self.exchange.set_margin_mode(signal.margin_mode, signal.pair)
            actions.append({"step": "set_margin_mode", "status": "ok", "value": signal.margin_mode})
        except Exception as exc:
            actions.append({"step": "set_margin_mode", "status": "error", "error": str(exc)})

    async def _safe_create_stop_loss(
        self, signal: TradeSignal, amount: float, actions: List[Dict[str, Any]]
    ) -> None:
        side = "sell" if signal.direction == "LONG" else "buy"
        params = {"reduceOnly": True, "stopPrice": signal.stop_loss}
        try:
            order = await self.exchange.create_order(
                symbol=signal.pair,
                type="stop_market",
                side=side,
                amount=amount,
                price=None,
                params=params,
            )
            actions.append({"step": "stop_loss", "status": "ok", "id": order.get("id")})
        except Exception as exc:
            actions.append({"step": "stop_loss", "status": "error", "error": str(exc)})

    async def _safe_create_take_profits(
        self, signal: TradeSignal, amount: float, actions: List[Dict[str, Any]]
    ) -> None:
        if not signal.targets:
            actions.append({"step": "take_profit", "status": "skipped"})
            return

        side = "sell" if signal.direction == "LONG" else "buy"
        split_amount = amount / len(signal.targets)
        for tp in signal.targets:
            try:
                order = await self.exchange.create_order(
                    symbol=signal.pair,
                    type="limit",
                    side=side,
                    amount=float(self.exchange.amount_to_precision(signal.pair, split_amount)),
                    price=tp,
                    params={"reduceOnly": True},
                )
                actions.append({"step": "take_profit", "status": "ok", "price": tp, "id": order.get("id")})
            except Exception as exc:
                actions.append({"step": "take_profit", "status": "error", "price": tp, "error": str(exc)})
