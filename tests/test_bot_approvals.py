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


def test_build_approval_keyboard_contains_expected_actions():
    service = BotApprovalService(
        bot_token="123:abc",
        approval_chat_id=1,
    )
    keyboard = service._build_approval_keyboard(42)  # pylint: disable=protected-access
    callback_data = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert "sig:42:approve" in callback_data
    assert "sig:42:reject" in callback_data
    assert "sig:42:set_pct:25" in callback_data
    assert "sig:42:set_pct:50" in callback_data
    assert "sig:42:set_pct:100" in callback_data
    assert "sig:42:edit:order_type=market" in callback_data
    assert "sig:42:edit:leverage=5" in callback_data
    assert "sig:42:edit:leverage=10" in callback_data


def test_parse_callback_data():
    service = BotApprovalService(
        bot_token="123:abc",
        approval_chat_id=1,
    )
    parsed = service._parse_callback_data("sig:99:edit:leverage=10")  # pylint: disable=protected-access
    assert parsed == (99, "edit", "leverage=10")
    assert service._parse_callback_data("bad:data") is None  # pylint: disable=protected-access


def test_parse_size_token():
    service = BotApprovalService(
        bot_token="123:abc",
        approval_chat_id=1,
        total_balance_usdt=50.0,
    )
    assert service._parse_size_token("20") == 20.0  # pylint: disable=protected-access
    assert service._parse_size_token("40%") == 20.0  # pylint: disable=protected-access
    assert service._parse_size_token("0") is None  # pylint: disable=protected-access
    assert service._parse_size_token("200") is None  # pylint: disable=protected-access
