from typing import Any

CRITICAL_FLAGS = {"low_liquidity", "insufficient_history", "extreme_buy_imbalance", "suspicious_volume"}

def detect_risks(token: dict[str, Any], settings: Any) -> tuple[list[str], list[str]]:
    flags, unknown = [], []
    liquidity, market_cap = float(token.get("liquidity_usd") or 0), float(token.get("market_cap") or 0)
    volume, tx, age = float(token.get("volume_24h") or 0), int(token.get("txns_24h") or 0), float(token.get("age_hours") or 0)
    buys, sells, change = int(token.get("buys_24h") or 0), int(token.get("sells_24h") or 0), float(token.get("price_change_24h") or 0)
    if liquidity < settings.min_liquidity_usd: flags.append("low_liquidity")
    if market_cap and liquidity / market_cap < .02: flags.append("thin_liquidity_vs_marketcap")
    if tx < 100: flags.append("low_transaction_count")
    if (buys >= 30 and sells == 0) or (buys > 0 and buys / max(sells, 1) >= 12): flags.append("extreme_buy_imbalance")
    if sells > 0 and sells / max(buys, 1) >= 12: flags.append("extreme_sell_imbalance")
    if volume > 0 and liquidity > 0 and volume / liquidity > 25: flags.append("suspicious_volume")
    if 0 < market_cap < settings.min_market_cap_usd * 1.25: flags.append("very_low_market_cap")
    if change >= 150: flags.extend(["abnormal_price_spike", "possible_pump"])
    if age < 2 or tx < 30: flags.append("insufficient_history")
    for field, label in (("mint_authority", "mint_authority"), ("freeze_authority", "freeze_authority"), ("top10_holders_pct", "holder_concentration"), ("lp_status", "lp_status"), ("insider_concentration", "insider_concentration")):
        if token.get(field) in (None, "", "UNKNOWN"): unknown.append(label)
    return sorted(set(flags)), sorted(set(unknown))

def risk_score(token: dict[str, Any], flags: list[str], unknown: list[str]) -> float:
    weights = {"low_liquidity":30,"thin_liquidity_vs_marketcap":18,"low_transaction_count":12,"extreme_buy_imbalance":24,"extreme_sell_imbalance":15,"suspicious_volume":25,"very_low_market_cap":10,"abnormal_price_spike":22,"possible_pump":18,"insufficient_history":20}
    return round(min(100, sum(weights.get(f, 8) for f in flags) + min(20, len(unknown) * 4)), 2)