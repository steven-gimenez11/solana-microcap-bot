import logging, time
from datetime import datetime, timezone
from config import settings
from datasource import DexScreener
from risk import detect_risks, risk_score
from scoring import classification, momentum, opportunity_score
from storage import Store
log = logging.getLogger(__name__)
def _num(value):
    try: return float(value or 0)
    except (TypeError, ValueError): return 0
def normalize(pair):
    tx = {k: pair.get("txns", {}).get(k, {}) for k in ("m5", "h1", "h24")}; created = pair.get("pairCreatedAt")
    age = max(0, (datetime.now(timezone.utc).timestamp() * 1000 - created) / 3600000) if created else 9999
    def count(window, side): return int(tx[window].get(side, 0) or 0)
    return {"address":pair.get("baseToken", {}).get("address", ""), "name":pair.get("baseToken", {}).get("name", "UNKNOWN"), "symbol":pair.get("baseToken", {}).get("symbol", "UNKNOWN"), "pair_address":pair.get("pairAddress", "UNKNOWN"), "dex":pair.get("dexId", "UNKNOWN"), "pair_created_at":created, "age_hours":round(age, 2), "price_usd":_num(pair.get("priceUsd")), "market_cap":_num(pair.get("marketCap") or pair.get("fdv")), "fdv":_num(pair.get("fdv")), "liquidity_usd":_num(pair.get("liquidity", {}).get("usd")), "volume_5m":_num(pair.get("volume", {}).get("m5")), "volume_1h":_num(pair.get("volume", {}).get("h1")), "volume_6h":_num(pair.get("volume", {}).get("h6")), "volume_24h":_num(pair.get("volume", {}).get("h24")), "buys_5m":count("m5","buys"), "sells_5m":count("m5","sells"), "buys_1h":count("h1","buys"), "sells_1h":count("h1","sells"), "buys_24h":count("h24","buys"), "sells_24h":count("h24","sells"), "txns_5m":count("m5","buys")+count("m5","sells"), "txns_1h":count("h1","buys")+count("h1","sells"), "txns_24h":count("h24","buys")+count("h24","sells"), "price_change_5m":_num(pair.get("priceChange", {}).get("m5")), "price_change_1h":_num(pair.get("priceChange", {}).get("h1")), "price_change_6h":_num(pair.get("priceChange", {}).get("h6")), "price_change_24h":_num(pair.get("priceChange", {}).get("h24")), "dexscreener_url":f"https://dexscreener.com/solana/{pair.get('pairAddress', '')}"}
class Scanner:
    def __init__(self, store=None, source=None): self.store, self.source = store or Store(settings.database_path), source or DexScreener(settings.api_url, settings.request_timeout)
    def scan(self):
        try: pairs = self.source.fetch_solana_pairs()
        except Exception: log.exception("Unexpected datasource failure"); return {"scanned":0,"accepted":0,"rejected":0}
        counts, seen = {"scanned":0,"accepted":0,"rejected":0}, set()
        for pair in pairs:
            token = normalize(pair)
            if not token["address"] or token["address"] in seen: continue
            seen.add(token["address"]); counts["scanned"] += 1
            eligible = settings.min_market_cap_usd <= token["market_cap"] <= settings.max_market_cap_usd and token["liquidity_usd"] >= settings.min_liquidity_usd and token["volume_24h"] >= settings.min_volume_24h_usd and token["age_hours"] <= settings.max_pair_age_hours
            if not eligible: token["classification"] = "REJECTED"; counts["rejected"] += 1
            else:
                flags, unknown = detect_risks(token, settings); token.update(risk_flags=flags, unknown_safety=unknown, opportunity_score=opportunity_score(token, flags), risk_score=risk_score(token, flags, unknown)); token["momentum"] = momentum(token); token["classification"] = classification(token, token["opportunity_score"], token["risk_score"], settings, flags, unknown); counts["accepted"] += 1
            self.store.save(token)
        return counts
    def run_forever(self):
        while True: self.scan(); time.sleep(max(10, settings.scan_interval))