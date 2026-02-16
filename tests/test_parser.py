import asyncio

from src.parser import SignalParser


def test_parse_valid_signal_json():
    parser = SignalParser(model_name="test-model")
    text = (
        '{"pair":"BTC/USDT","direction":"LONG","entry_zone":[100,101],'
        '"targets":[102,103],"stop_loss":99,"leverage":5,'
        '"margin_mode":"isolated","order_type":"limit","confidence":0.8}'
    )

    signal = asyncio.run(parser.parse_signal(text=text))
    assert signal is not None
    assert signal.pair == "BTC/USDT"
    assert signal.direction == "LONG"
    assert signal.stop_loss == 99


def test_parse_invalid_schema_returns_none():
    parser = SignalParser(model_name="test-model")
    text = (
        '{"pair":"BTC/USDT","direction":"UP","entry_zone":[100,101],'
        '"targets":[102,103],"stop_loss":99}'
    )

    signal = asyncio.run(parser.parse_signal(text=text))
    assert signal is None


def test_parse_non_json_returns_none():
    parser = SignalParser(model_name="test-model")
    signal = asyncio.run(parser.parse_signal(text="buy btc now"))
    assert signal is None
