from types import SimpleNamespace
from risk import detect_risks, risk_score
from scoring import opportunity_score
settings = SimpleNamespace(min_liquidity_usd=25000, min_market_cap_usd=50000)
def test_risk_flags_dangerous_imbalance_and_spike():
    token = {"liquidity_usd":10000,"market_cap":100000,"volume_24h":3000000,"txns_24h":10,"age_hours":1,"buys_24h":100,"sells_24h":1,"price_change_24h":500}
    flags, unknown = detect_risks(token, settings)
    assert "low_liquidity" in flags and "possible_pump" in flags and risk_score(token, flags, unknown) >= 25
def test_opportunity_does_not_reward_vertical_price_alone():
    token = {"market_cap":100000,"liquidity_usd":30000,"volume_24h":60000,"price_change_1h":500,"price_change_24h":800,"buys_24h":100,"sells_24h":1,"age_hours":4,"volume_5m":1,"volume_1h":100}
    assert opportunity_score(token, ["possible_pump","abnormal_price_spike","extreme_buy_imbalance"]) < 60