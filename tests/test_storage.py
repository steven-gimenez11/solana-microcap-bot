from storage import Store


def token(address, price=1.0, classification="CANDIDATE", risk=10, opportunity=90, momentum=70):
    return {
        "address": address, "symbol": address, "name": "Test Token", "price_usd": price,
        "market_cap": 100000, "liquidity_usd": 50000, "volume_24h": 100000,
        "classification": classification, "risk_score": risk, "opportunity_score": opportunity,
        "momentum": {"momentum_score": momentum}, "upside_asymmetry_score": 85,
    }


def test_portfolio_never_none(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    p = store.paper_stats()
    assert p["capital_initial"] == 10
    assert p["cash"] == 10
    assert p["portfolio_value"] == 10
    assert p["total_pnl"] == 0
    assert p["roi_pct"] == 0


def test_create_paper_trade_limits_and_duplicate(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    for i in range(3):
        assert store.create_paper_trade(f"ADDR{i}", token(f"ADDR{i}"), reason="test") is True
    assert store.create_paper_trade("ADDR4", token("ADDR4"), reason="test") is False
    assert store.create_paper_trade("ADDR0", token("ADDR0"), reason="test") is False
    assert store.paper_stats()["open_positions"] == 3
    assert store.paper_stats()["cash"] == 7


def test_candidate_save_opens_trade_and_partial_exits(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    t = token("MOON", price=1.0)
    store.save(t)
    trades = store.paper_trades()
    assert len(trades) == 1
    assert trades[0]["status"] == "OPEN"

    t2 = token("MOON", price=2.0)
    store.save(t2)
    tr = store.paper_trades()[0]
    assert "2x" in tr["milestones"]
    assert any(x["reason"] == "capital_recovery_2x" for x in tr["partial_exits"])
    assert tr["remaining_units"] < tr["entry_units"]

    store.save(token("MOON", price=5.0))
    store.save(token("MOON", price=10.0))
    tr = store.paper_trades()[0]
    reasons = {x["reason"] for x in tr["partial_exits"]}
    assert {"capital_recovery_2x", "take_profit_5x", "take_profit_10x"}.issubset(reasons)
    assert "10x" in tr["milestones"]


def test_risk_exit_closes_remaining(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    store.save(token("BAD", price=1.0))
    store.save(token("BAD", price=0.8, risk=80))
    tr = store.paper_trades()[0]
    assert tr["status"] == "CLOSED"
    assert tr["why_exited"] == "risk_score_critical"
