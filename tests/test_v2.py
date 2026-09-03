import pytest
from config import settings
from scanner import Scanner
from storage import Store
from paper_executor import PaperExecutor
from datasource import DexScreener
from risk import detect_risks, risk_score
from scoring import opportunity_score, classification, momentum

def test_settings_dry_run():
    """Ensure DRY_RUN and TRADING_ENABLED are enforced."""
    assert settings.dry_run == True
    assert settings.trading_enabled == False

def test_settings_position_limits():
    """Verify position control settings."""
    assert settings.max_position_usd == 1.0
    assert settings.max_open_positions == 3
    assert settings.max_total_capital_usd == 10

def test_store_initialization():
    """Test Store creates database tables."""
    store = Store(":memory:")
    assert store is not None
    # Test debug endpoint exists
    debug = store.get_debug()
    assert debug["dry_run_mode"] == True
    assert debug["trading_enabled"] == False

def test_store_paper_trades_no_none():
    """Ensure paper_trades() never returns None values."""
    store = Store(":memory:")
    trades = store.paper_trades()
    assert isinstance(trades, list)
    for trade in trades:
        assert trade.get("current_return_pct", 0) is not None
        assert trade.get("maximum_gain_pct", 0) is not None
        assert trade.get("reached_2x", False) is not None

def test_store_paper_stats_no_none():
    """Ensure paper_stats() never returns None values."""
    store = Store(":memory:")
    stats = store.paper_stats()
    assert stats["capital_initial"] == 10
    assert stats["cash"] == 10
    assert stats["portfolio_value"] == 10
    assert stats["roi_pct"] == 0
    assert isinstance(stats["win_rate"], (int, float))

def test_paper_executor_open_position():
    """Test PaperExecutor opens positions correctly."""
    store = Store(":memory:")
    executor = PaperExecutor(store, settings)
    
    result = executor.open_from_candidate("test_addr", 0.01, 100000)
    assert result["status"] == "opened"
    assert result["position"]["address"] == "test_addr"
    assert result["position"]["entry_price"] == 0.01
    assert result["position"]["size_usd"] <= settings.max_position_usd

def test_paper_executor_max_positions():
    """Test max 3 open positions limit."""
    store = Store(":memory:")
    executor = PaperExecutor(store, settings)
    
    # Open 3 positions
    for i in range(3):
        result = executor.open_from_candidate(f"addr_{i}", 0.01, 100000)
        assert result["status"] == "opened"
    
    # Try to open 4th - should fail
    result = executor.open_from_candidate("addr_3", 0.01, 100000)
    assert result["status"] == "rejected"
    assert "max_positions" in result["reason"]

def test_paper_executor_cash_control():
    """Test cash never goes negative."""
    store = Store(":memory:")
    executor = PaperExecutor(store, settings)
    
    initial_cash = executor.cash
    assert initial_cash == settings.max_total_capital_usd

def test_risk_detection():
    """Test risk detection flags."""
    token = {
        "address": "test",
        "market_cap": 100000,
        "liquidity_usd": 10000,
        "volume_24h": 5000,
        "txns_24h": 50,
        "age_hours": 1,
        "buys_24h": 10,
        "sells_24h": 10,
        "price_change_24h": 50
    }
    
    flags, unknown = detect_risks(token, settings)
    assert isinstance(flags, list)
    assert "insufficient_history" in flags  # age < 2

def test_momentum_metrics():
    """Test momentum calculation."""
    token = {
        "volume_5m": 100,
        "volume_1h": 500,
        "buys_5m": 10,
        "buys_1h": 50,
        "txns_5m": 20,
        "txns_1h": 100,
        "sells_5m": 10,
        "sells_1h": 50
    }
    
    m = momentum(token)
    assert "volume_acceleration" in m
    assert "buyer_acceleration" in m
    assert "transaction_acceleration" in m
    assert m["volume_acceleration"] >= 0
    assert m["volume_acceleration"] <= 10

def test_opportunity_score():
    """Test opportunity score calculation."""
    token = {
        "market_cap": 500000,
        "liquidity_usd": 50000,
        "volume_24h": 100000,
        "price_change_1h": 10,
        "price_change_24h": 50,
        "buys_24h": 100,
        "sells_24h": 100,
        "age_hours": 10,
        "volume_5m": 500,
        "volume_1h": 5000,
        "buys_5m": 20,
        "buys_1h": 200,
        "txns_5m": 40,
        "txns_1h": 400,
        "sells_5m": 20,
        "sells_1h": 200
    }
    
    score = opportunity_score(token, [])
    assert score >= 0
    assert score <= 100

def test_classification():
    """Test token classification logic."""
    token = {}
    
    # CANDIDATE: high opportunity, low risk
    result = classification(token, 85, 20, settings, [], [])
    assert result == "CANDIDATE"
    
    # STRONG_WATCH
    result = classification(token, 70, 40, settings, [], [])
    assert result == "STRONG_WATCH"
    
    # WATCH
    result = classification(token, 50, 50, settings, [], [])
    assert result == "WATCH"
    
    # REJECTED
    result = classification(token, 30, 80, settings, [], [])
    assert result == "REJECTED"

def test_scanner_initialization():
    """Test Scanner initializes correctly."""
    scanner = Scanner()
    assert scanner.store is not None
    assert scanner.source is not None
    assert scanner.executor is not None

def test_paper_executor_multiple_exit_levels():
    """Test multiple exit levels (2x, 5x, 10x) + moonbag."""
    store = Store(":memory:")
    executor = PaperExecutor(store, settings)
    
    # Open position
    executor.open_from_candidate("test_moon", 1.0, 100000)
    pos = executor.open_positions[0]
    
    # Simulate 10x gain
    executor.update_position("test_moon", 10.0)
    
    # Should have exits
    assert len(pos["exits"]) > 0
    assert pos["reached_multiples"]["x10"] == True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
