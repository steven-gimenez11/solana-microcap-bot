import logging, time
import requests
log = logging.getLogger(__name__)
class DexScreener:
    def __init__(self, base_url, timeout=10): self.base_url, self.timeout = base_url.rstrip('/'), timeout
    def _get(self, path):
        for attempt in range(3):
            try:
                response = requests.get(self.base_url + path, timeout=self.timeout, headers={"User-Agent":"solana-microcap-bot/1.0"})
                if response.status_code == 429: time.sleep(2 ** attempt); continue
                response.raise_for_status(); return response.json()
            except (requests.RequestException, ValueError) as exc:
                log.warning("DexScreener request failed: %s", exc)
                if attempt < 2: time.sleep(2 ** attempt)
        return {}
    def fetch_solana_pairs(self):
        profile_response = self._get("/token-profiles/latest/v1")
        profiles = profile_response if isinstance(profile_response, list) else profile_response.get("profiles", [])
        pairs = []
        for profile in profiles[:30]:
            if profile.get("chainId") != "solana" or not profile.get("tokenAddress"): continue
            pair_response = self._get(f"/token-pairs/v1/solana/{profile['tokenAddress']}")
            pairs.extend(pair_response if isinstance(pair_response, list) else pair_response.get("pairs") or [])
        return pairs