from typing import Any


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _ratio(short, long, periods):
    a, b = _f(short), _f(long)
    return min(10.0, a / max(b / periods, 1.0)) if b else 0.0


def momentum(token: dict[str, Any]) -> dict[str, float]:
    vol5_1 = _ratio(token.get("volume_5m"), token.get("volume_1h"), 12)
    vol1_6 = _ratio(token.get("volume_1h"), token.get("volume_6h"), 6)
    buyers5_1 = _ratio(token.get("buys_5m"), token.get("buys_1h"), 12)
    tx5_1 = _ratio(token.get("txns_5m"), token.get("txns_1h"), 12)
    score = 0.0
    for v, weight in ((vol5_1, 35), (vol1_6, 20), (buyers5_1, 25), (tx5_1, 20)):
        score += min(1.0, max(0.0, v - 0.8) / 2.2) * weight
    if _f(token.get("price_change_5m")) > 80 or _f(token.get("price_change_1h")) > 250:
        score *= 0.65
    return {
        "volume_acceleration_score": round(min(100, (vol5_1 / 3) * 60 + (vol1_6 / 3) * 40), 2),
        "buyer_acceleration_score": round(min(100, buyers5_1 / 3 * 100), 2),
        "transaction_acceleration_score": round(min(100, tx5_1 / 3 * 100), 2),
        "momentum_score": round(min(100, score), 2),
        "volume_acceleration_5m_vs_1h": round(vol5_1, 2),
        "volume_acceleration_1h_vs_6h": round(vol1_6, 2),
    }


def upside_asymmetry_score(token: dict[str, Any]) -> float:
    cap, liq, vol, age = _f(token.get("market_cap")), _f(token.get("liquidity_usd")), _f(token.get("volume_24h")), _f(token.get("age_hours"))
    m = momentum(token)["momentum_score"]
    score = 0.0
    if 50_000 <= cap <= 250_000:
        score += 34
    elif cap <= 500_000:
        score += 28
    elif cap <= 1_000_000:
        score += 20
    elif cap <= 1_500_000:
        score += 12
    if cap > 0:
        ratio = liq / cap
        if 0.08 <= ratio <= 0.8:
            score += 20
        elif ratio >= 0.04:
            score += 12
    if cap > 0:
        vratio = vol / cap
        if 0.3 <= vratio <= 8:
            score += 16
        elif vratio > 0.1:
            score += 8
    if 1 <= age <= 24:
        score += 12
    elif 24 < age <= 72:
        score += 6
    score += m * 0.18
    return round(min(100, score), 2)


def opportunity_score(token: dict[str, Any], flags: list[str]) -> float:
    cap, liq, vol = _f(token.get("market_cap")), _f(token.get("liquidity_usd")), _f(token.get("volume_24h"))
    m = momentum(token)
    asym = upside_asymmetry_score(token)
    score = asym * 0.38 + m["momentum_score"] * 0.30
    if cap and liq / cap >= 0.05:
        score += 10
    if vol >= 50_000:
        score += 7
    buys, sells = _f(token.get("buys_24h")), _f(token.get("sells_24h"))
    if buys and 0.35 <= sells / buys <= 2.5:
        score += 8
    pc1, pc24 = _f(token.get("price_change_1h")), _f(token.get("price_change_24h"))
    if 0 < pc1 < 60:
        score += 5
    if 0 < pc24 < 180:
        score += 5
    penalty = {"possible_pump": 14, "suspicious_volume": 14, "extreme_buy_imbalance": 10, "abnormal_price_spike": 10, "insufficient_history": 4}
    score -= sum(penalty.get(f, 3) for f in flags)
    return round(max(0, min(100, score)), 2)


def classification(token, opportunity, danger, settings, flags, unknown):
    critical = {"low_liquidity", "suspicious_volume", "mint_authority_enabled", "freeze_authority_enabled"}
    dangerous_unknown = {"mint_authority", "freeze_authority"}
    if (
        opportunity >= settings.min_score
        and danger <= 25
        and not (set(flags) & critical)
        and not (set(unknown) & dangerous_unknown)
    ):
        return "CANDIDATE"
    if opportunity >= 65 and danger <= 50:
        return "STRONG_WATCH"
    if opportunity >= 35:
        return "WATCH"
    return "REJECTED"
