import os
from storage import Store


def test_create_paper_trade_limits(tmp_path):
    db_path = str(tmp_path / "test_storage.db")
    store = Store(db_path)

    token_template = {
        "symbol": "TST",
        "name": "Test Token",
        "price_usd": 1.0,
        "market_cap": 100000,
        "liquidity_usd": 50000,
    }

    # create up to max_open_positions (default 3)
    addrs = [f"ADDR{i}" for i in range(3)]
    for a in addrs:
        token = dict(token_template)
        token["address"] = a
        created = store.create_paper_trade(a, token, reason="test")
        assert created is True

    # fourth should be rejected due to max_open_positions
    token = dict(token_template)
    token["address"] = "ADDR4"
    created = store.create_paper_trade("ADDR4", token, reason="test")
    assert created is False

    # duplicate create for existing address should be False
    dup = store.create_paper_trade(addrs[0], token, reason="test")
    assert dup is False
