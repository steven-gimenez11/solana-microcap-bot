from typing import Any

def momentum(token: dict[str, Any]) -> dict[str, float]:
    """Calculate momentum and acceleration metrics (improved discovery)."""
    def ratio(short, long, periods):
        a, b = float(short or 0), float(long or 0)
        return round(min(10, a / max(b / periods, 1)) if b else 0, 2)
    
    return {
        "volume_acceleration": ratio(token.get("volume_5m"), token.get("volume_1h"), 12),
        "buyer_acceleration": ratio(token.get("buys_5m"), token.get("buys_1h"), 12),
        "transaction_acceleration": ratio(token.get("txns_5m"), token.get("txns_1h"), 12),
        "seller_pressure": 1 - ratio(token.get("sells_5m"), token.get("sells_1h"), 12) if token.get("sells_5m") else 0
    }

def opportunity_score(token: dict[str, Any], flags: list[str]) -> float:
    """Enhanced discovery and opportunity scoring."""
    cap, liq, vol = float(token.get("market_cap") or 0), float(token.get("liquidity_usd") or 0), float(token.get("volume_24h") or 0)
    score = 22 if 50000 <= cap <= 3000000 else 0
    
    if cap and liq / cap >= .05:
        score += 18
    if vol >= 50000:
        score += 14
    if 0 < float(token.get("price_change_1h") or 0) < 35:
        score += 8
    if 0 < float(token.get("price_change_24h") or 0) < 150:
        score += 8
    
    buys, sells = float(token.get("buys_24h") or 0), float(token.get("sells_24h") or 0)
    if buys and .35 <= sells / buys <= 2.5:
        score += 12
    
    m = momentum(token)
    score += min(8, max(0, m["volume_acceleration"] - 1) * 2)
    score += min(5, max(0, m["buyer_acceleration"] - 1))
    score += min(3, max(0, m["transaction_acceleration"] - 1))
    
    if 2 <= float(token.get("age_hours") or 0) <= 60:
        score += 5
    
    score -= sum(10 if f in {"possible_pump", "suspicious_volume", "extreme_buy_imbalance"} else 4 for f in flags)
    return round(max(0, min(100, score)), 2)

def classification(token, opportunity, danger, settings, flags, unknown):
    if opportunity >= settings.min_score and danger <= 25 and not (set(flags) & {"low_liquidity", "insufficient_history", "suspicious_volume"}) and not unknown:
        return "CANDIDATE"
    if opportunity >= 65 and danger <= 45:
        return "STRONG_WATCH"
    if opportunity >= 35:
        return "WATCH"
    return "REJECTED"
