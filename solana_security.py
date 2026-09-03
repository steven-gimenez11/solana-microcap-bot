"""
Solana security layer: mint/freeze authorities, holder concentration, insider concentration.
DexScreener does not expose these metrics; mark as UNKNOWN explicitly.
"""
from typing import Dict, Any

def get_solana_security_info(token_address: str) -> Dict[str, Any]:
    """
    Fetch Solana-specific security metrics.
    Currently DexScreener API doesn't expose these; return UNKNOWN.
    In production, would call Solana RPC or on-chain indexer.
    """
    return {
        "mint_authority": "UNKNOWN",
        "mint_authority_burned": "UNKNOWN",
        "freeze_authority": "UNKNOWN",
        "freeze_authority_burned": "UNKNOWN",
        "top10_holders_pct": "UNKNOWN",
        "top50_holders_pct": "UNKNOWN",
        "insider_concentration": "UNKNOWN",
        "lp_status": "UNKNOWN",
        "is_upgradeable": "UNKNOWN",
        "source": "dexscreener_api"
    }

def security_score(security_info: Dict[str, Any]) -> float:
    """
    Calculate security score (0-100, higher = safer).
    Returns 50 (neutral) when data is UNKNOWN.
    """
    if all(v == "UNKNOWN" for v in security_info.values()):
        return 50.0  # Unknown = neutral, not positive
    
    score = 50
    # Mint authority burned = +20
    if security_info.get("mint_authority_burned") == True:
        score += 20
    elif security_info.get("mint_authority_burned") == False:
        score -= 15
    
    # Freeze authority burned = +15
    if security_info.get("freeze_authority_burned") == True:
        score += 15
    elif security_info.get("freeze_authority_burned") == False:
        score -= 10
    
    # Top 10 holders
    try:
        top10 = float(security_info.get("top10_holders_pct", "UNKNOWN"))
        if 0 <= top10 <= 30:
            score += 10
        elif 30 < top10 <= 50:
            score -= 5
        else:
            score -= 15
    except (TypeError, ValueError):
        pass
    
    return round(max(0, min(100, score)), 2)
