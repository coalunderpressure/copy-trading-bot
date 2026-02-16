from src.bot_approvals import BotApprovalService
from src.models import TradeSignal


def test_bot_build_edit_decision_updates_fields():
    service = BotApprovalService(
        bot_token="123:abc",
        approval_chat_id=1,
    )
    signal = TradeSignal(
        pair="BTC/USDT",
        direction="LONG",
        entry_zone=[100.0, 101.0],
        targets=[102.0],
        stop_loss=99.0,
    )

    decision = service.build_edit_decision(
        signal, "leverage=10 margin_mode=cross order_type=market stop_loss=98"
    )
    assert decision.approved is True
    assert decision.edited_signal is not None
    assert decision.edited_signal.leverage == 10
    assert decision.edited_signal.margin_mode == "cross"
    assert decision.edited_signal.order_type == "market"
    assert decision.edited_signal.stop_loss == 98.0
