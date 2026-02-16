from src.listener import IncomingMessage
from src.models import ApprovalDecision, TradeSignal
from src.state_store import SignalStateStore


def test_state_store_happy_path(tmp_path):
    db_path = tmp_path / "state.db"
    store = SignalStateStore(db_path=str(db_path))
    try:
        incoming = IncomingMessage(
            message_id=101,
            chat_id=55,
            text='{"pair":"BTC/USDT"}',
            media_path=None,
        )
        store.record_incoming(incoming)
        assert store.has_message(101) is True
        assert store.get_status(101) == "received"

        signal = TradeSignal(
            pair="BTC/USDT",
            direction="LONG",
            entry_zone=[100.0, 101.0],
            targets=[102.0],
            stop_loss=99.0,
            source_message_id=101,
        )
        store.mark_parsed(signal)
        assert store.get_status(101) == "parsed"

        decision = ApprovalDecision(approved=True, reason="ok", edited_signal=signal, tags=["approved"])
        store.mark_approved(101, decision)
        assert store.get_status(101) == "approved"

        store.mark_executed(101, {"status": "ok", "actions": []})
        assert store.get_status(101) == "executed"
    finally:
        store.close()


def test_state_store_parse_failed_and_rejected(tmp_path):
    db_path = tmp_path / "state.db"
    store = SignalStateStore(db_path=str(db_path))
    try:
        incoming = IncomingMessage(
            message_id=202,
            chat_id=66,
            text="bad signal",
            media_path=None,
        )
        store.record_incoming(incoming)
        store.mark_parse_failed(202, "invalid")
        assert store.get_status(202) == "parse_failed"

        rejected = ApprovalDecision(approved=False, reason="manual reject", tags=["rejected"])
        store.mark_rejected(202, rejected)
        assert store.get_status(202) == "rejected"
    finally:
        store.close()
