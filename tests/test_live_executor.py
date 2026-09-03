from dataclasses import replace

from config import settings
from execution.live_executor import LiveTradingEngine
from storage import Store


class FakeJupiter:
    wallet_address = "FakeWallet111"
    def __init__(self):
        self.buys = []
        self.sells = []
    def buy_usd(self, mint, amount):
        self.buys.append((mint, amount))
        return {"usd_amount": amount, "order": {"router": "test"}, "result": {"status": "Success", "code": 0, "signature": "buytx", "outputAmountResult": "1000000"}}
    def sell_raw(self, mint, raw):
        self.sells.append((mint, raw))
        return {"order": {"router": "test"}, "result": {"status": "Success", "code": 0, "signature": f"sell{len(self.sells)}", "outputAmountResult": "1000"}}


def live_cfg():
    return replace(settings, dry_run=False, trading_enabled=True, live_trading_ack="I_ACCEPT_REAL_LOSS_RISK", live_min_asymmetry_score=70, live_min_momentum_score=55)


def token(price=0.001, classification="CANDIDATE"):
    return {
        "address": "Mint111111111111111111111111111111111111111",
        "symbol": "TEST", "classification": classification, "price_usd": price,
        "market_cap": 100000, "liquidity_usd": 50000, "volume_24h": 100000,
        "opportunity_score": 90, "risk_score": 10, "risk_flags": [],
        "upside_asymmetry_score": 85, "momentum": {"momentum_score": 80},
    }


def test_candidate_buys_and_no_duplicate(tmp_path):
    store = Store(str(tmp_path / "db.sqlite")); j = FakeJupiter(); e = LiveTradingEngine(store, live_cfg(), j)
    e.on_token(token())
    e.on_token(token())
    assert len(j.buys) == 1
    assert store.open_live_count() == 1


def test_partial_exits_keep_moonbag(tmp_path):
    store = Store(str(tmp_path / "db.sqlite")); j = FakeJupiter(); e = LiveTradingEngine(store, live_cfg(), j)
    e.on_token(token())
    e.on_token(token(0.002))
    e.on_token(token(0.005))
    e.on_token(token(0.010))
    trade = store.get_open_live_trade(token()["address"])
    assert len(j.sells) == 3
    assert trade["remaining_raw_amount"] == 150000
    assert [x["reason"] for x in trade["partial_exits"]] == ["capital_recovery_2x", "take_profit_5x", "take_profit_10x"]


def test_rejects_non_candidate(tmp_path):
    store = Store(str(tmp_path / "db.sqlite")); j = FakeJupiter(); e = LiveTradingEngine(store, live_cfg(), j)
    e.on_token(token(classification="STRONG_WATCH"))
    assert not j.buys
