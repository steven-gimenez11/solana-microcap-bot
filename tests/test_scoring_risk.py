from types import SimpleNamespace
from risk import detect_risks, risk_score
from scoring import opportunity_score, momentum, upside_asymmetry_score, classification

settings = SimpleNamespace(min_liquidity_usd=25000, min_market_cap_usd=50000, min_score=80)


def test_risk_flags_dangerous_imbalance_and_spike():
    token = {"liquidity_usd":10000,"market_cap":100000,"volume_24h":3000000,"txns_24h":10,"age_hours":1,"buys_24h":100,"sells_24h":1,"price_change_24h":500}
    flags, unknown = detect_risks(token, settings)
    assert "low_liquidity" in flags and "possible_pump" in flags and risk_score(token, flags, unknown) >= 25


def test_opportunity_does_not_reward_vertical_price_alone():
    token = {"market_cap":100000,"liquidity_usd":30000,"volume_24h":60000,"price_change_1h":500,"price_change_24h":800,"buys_24h":100,"sells_24h":1,"age_hours":4,"volume_5m":1,"volume_1h":100,"volume_6h":600,"buys_5m":1,"buys_1h":100,"txns_5m":2,"txns_1h":150}
    assert opportunity_score(token, ["possible_pump","abnormal_price_spike","extreme_buy_imbalance"]) < 60


def test_momentum_and_asymmetry_reward_early_acceleration():
    token = {"market_cap":120000,"liquidity_usd":30000,"volume_24h":150000,"age_hours":5,"volume_5m":20000,"volume_1h":40000,"volume_6h":100000,"buys_5m":120,"buys_1h":200,"txns_5m":180,"txns_1h":300,"price_change_5m":10,"price_change_1h":25}
    assert momentum(token)["momentum_score"] > 50
    assert upside_asymmetry_score(token) > 60


def test_unknown_holder_data_alone_does_not_block_candidate():
    token = {}
    assert classification(token, 90, 20, settings, [], ["holder_concentration"]) == "CANDIDATE"
    assert classification(token, 90, 20, settings, [], ["mint_authority"]) != "CANDIDATE"
