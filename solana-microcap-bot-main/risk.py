from typing import Any


def detect_risks(token: dict[str, Any], settings: Any) -> tuple[list[str], list[str]]:
    flags, unknown = [], []
    liquidity, market_cap = float(token.get("liquidity_usd") or 0), float(token.get("market_cap") or 0)
    volume, tx, age = float(token.get("volume_24h") or 0), int(token.get("txns_24h") or 0), float(token.get("age_hours") or 0)
    buys, sells, change = int(token.get("buys_24h") or 0), int(token.get("sells_24h") or 0), float(token.get("price_change_24h") or 0)
    if liquidity < settings.min_liquidity_usd: flags.append("low_liquidity")
    if market_cap and liquidity / market_cap < .03: flags.append("thin_liquidity_vs_marketcap")
    if tx < 100: flags.append("low_transaction_count")
    if (buys >= 30 and sells == 0) or (buys > 0 and buys / max(sells, 1) >= 12): flags.append("extreme_buy_imbalance")
    if sells > 0 and sells / max(buys, 1) >= 8: flags.append("extreme_sell_imbalance")
    if volume > 0 and liquidity > 0 and volume / liquidity > 25: flags.append("suspicious_volume")
    if 0 < market_cap < settings.min_market_cap_usd * 1.25: flags.append("very_low_market_cap")
    if change >= 180 or float(token.get("price_change_1h") or 0) >= 120: flags.extend(["abnormal_price_spike", "possible_pump"])
    if age < 1 or tx < 30: flags.append("insufficient_history")
    if token.get("mint_authority") == "ENABLED": flags.append("mint_authority_enabled")
    if token.get("freeze_authority") == "ENABLED": flags.append("freeze_authority_enabled")
    top = token.get("top20_holders_pct")
    if top is not None and float(top) >= 90: flags.append("extreme_holder_concentration")
    for field, label in (("mint_authority", "mint_authority"), ("freeze_authority", "freeze_authority"), ("top20_holders_pct", "holder_concentration")):
        if token.get(field) in (None, "", "UNKNOWN"): unknown.append(label)
    unknown.extend(token.get("security_unknown") or [])
    return sorted(set(flags)), sorted(set(unknown))


def risk_score(token: dict[str, Any], flags: list[str], unknown: list[str]) -> float:
    weights = {
        "low_liquidity": 35, "thin_liquidity_vs_marketcap": 18, "low_transaction_count": 10,
        "extreme_buy_imbalance": 20, "extreme_sell_imbalance": 18, "suspicious_volume": 24,
        "very_low_market_cap": 8, "abnormal_price_spike": 18, "possible_pump": 18,
        "insufficient_history": 12, "mint_authority_enabled": 35, "freeze_authority_enabled": 35,
        "extreme_holder_concentration": 25,
    }
    score = sum(weights.get(f, 7) for f in flags)
    for u in set(unknown):
        score += 5 if u in {"mint_authority", "freeze_authority"} else 2
    security_score = float(token.get("security_score") or 0)
    score += security_score * 0.25
    return round(min(100, score), 2)
