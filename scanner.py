import logging, time
from datetime import datetime, timezone
from config import settings
from datasource import DexScreener
from risk import detect_risks, risk_score
from scoring import classification, momentum, opportunity_score
from storage import Store
from paper_executor import PaperExecutor

log = logging.getLogger(__name__)

def _num(value):
    try: return float(value or 0)
    except (TypeError, ValueError): return 0

def normalize(pair):
    tx = {k: pair.get("txns", {}).get(k, {}) for k in ("m5", "h1", "h24")}
    created = pair.get("pairCreatedAt")
    age = max(0, (datetime.now(timezone.utc).timestamp() * 1000 - created) / 3600000) if created else 9999
    
    def count(window, side): 
        return int(tx[window].get(side, 0) or 0)
    
    base_token = pair.get("baseToken", {})
    return {
        "address": base_token.get("address", ""),
        "name": base_token.get("name", "UNKNOWN"),
        "symbol": base_token.get("symbol", "UNKNOWN"),
        "pair_address": pair.get("pairAddress", ""),
        "price_usd": _num(pair.get("priceUsd")),
        "market_cap": _num(pair.get("marketCap")),
        "liquidity_usd": _num(pair.get("liquidity", {}).get("usd")),
        "volume_24h": _num(pair.get("volume", {}).get("h24")),
        "volume_1h": _num(pair.get("volume", {}).get("h1")),
        "volume_5m": _num(pair.get("volume", {}).get("m5")),
        "price_change_24h": _num(pair.get("priceChange", {}).get("h24")),
        "price_change_1h": _num(pair.get("priceChange", {}).get("h1")),
        "price_change_5m": _num(pair.get("priceChange", {}).get("m5")),
        "buys_24h": count("h24", "buys"),
        "sells_24h": count("h24", "sells"),
        "buys_1h": count("h1", "buys"),
        "sells_1h": count("h1", "sells"),
        "buys_5m": count("m5", "buys"),
        "sells_5m": count("m5", "sells"),
        "txns_24h": count("h24", "buys") + count("h24", "sells"),
        "txns_1h": count("h1", "buys") + count("h1", "sells"),
        "txns_5m": count("m5", "buys") + count("m5", "sells"),
        "age_hours": age,
        "mint_authority": "UNKNOWN",
        "freeze_authority": "UNKNOWN",
        "top10_holders_pct": "UNKNOWN",
        "lp_status": "UNKNOWN",
        "insider_concentration": "UNKNOWN"
    }

class Scanner:
    def __init__(self, store=None, source=None, executor=None):
        self.store = store or Store(settings.database_path)
        self.source = source or DexScreener(settings.api_url, settings.request_timeout)
        self.executor = executor or PaperExecutor(self.store, settings)
    
    def scan(self):
        try:
            pairs = self.source.fetch_solana_pairs()
        except Exception:
            log.exception("Unexpected datasource failure")
            return {"scanned": 0, "accepted": 0, "rejected": 0}
        
        counts, seen = {"scanned": 0, "accepted": 0, "rejected": 0}, set()
        
        for pair in pairs:
            token = normalize(pair)
            if not token["address"] or token["address"] in seen:
                continue
            
            seen.add(token["address"])
            counts["scanned"] += 1
            
            # Check eligibility
            eligible = (
                settings.min_market_cap_usd <= token["market_cap"] <= settings.max_market_cap_usd and
                token["liquidity_usd"] >= settings.min_liquidity_usd and
                token["volume_24h"] >= settings.min_volume_24h_usd and
                token["age_hours"] <= settings.max_pair_age_hours
            )
            
            if not eligible:
                token["classification"] = "REJECTED"
                counts["rejected"] += 1
            else:
                # Calculate scores
                flags, unknown = detect_risks(token, settings)
                opp_score = opportunity_score(token, flags)
                risk = risk_score(token, flags, unknown)
                token_class = classification(token, opp_score, risk, settings, flags, unknown)
                
                token.update(
                    risk_flags=flags,
                    unknown_safety=unknown,
                    opportunity_score=opp_score,
                    risk_score=risk,
                    classification=token_class,
                    momentum_metrics=momentum(token)
                )
                
                counts["accepted"] += 1
                
                # Auto-open CANDIDATE positions
                if token_class == "CANDIDATE":
                    result = self.executor.open_from_candidate(
                        token["address"],
                        token["price_usd"],
                        token["market_cap"]
                    )
                    token["paper_trade"] = result
            
            self.store.save(token)
        
        return counts
    
    def run_forever(self):
        while True:
            self.scan()
            time.sleep(max(10, settings.scan_interval))
