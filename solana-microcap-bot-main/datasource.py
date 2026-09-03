import logging
import time
from collections import OrderedDict
import requests

log = logging.getLogger(__name__)


class DexScreener:
    def __init__(self, base_url, timeout=10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path):
        for attempt in range(3):
            try:
                response = self.session.get(
                    self.base_url + path,
                    timeout=self.timeout,
                    headers={"User-Agent": "solana-microcap-bot/3.0"},
                )
                if response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                log.warning("DexScreener request failed: %s", exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return {}

    def _latest_profiles(self):
        data = self._get("/token-profiles/latest/v1")
        return data if isinstance(data, list) else data.get("profiles", [])

    def _latest_boosts(self):
        data = self._get("/token-boosts/latest/v1")
        return data if isinstance(data, list) else data.get("boosts", [])

    def fetch_token_pairs(self, mint, source="tracked"):
        data = self._get(f"/token-pairs/v1/solana/{mint}")
        found = data if isinstance(data, list) else data.get("pairs") or []
        out = []
        for pair in found:
            pair = dict(pair)
            existing = set(pair.get("_discovery_sources") or [])
            existing.add(source)
            pair["_discovery_sources"] = sorted(existing)
            out.append(pair)
        return out

    def fetch_solana_pairs(self, tracked_mints=None):
        discoveries = OrderedDict()
        for source, rows in (("profile", self._latest_profiles()), ("boost", self._latest_boosts())):
            for row in rows[:60]:
                if row.get("chainId") != "solana" or not row.get("tokenAddress"):
                    continue
                mint = row["tokenAddress"]
                discoveries.setdefault(mint, set()).add(source)
        for mint in tracked_mints or []:
            if mint:
                discoveries.setdefault(mint, set()).add("open_position")

        pairs = []
        for mint, sources in list(discoveries.items())[:70]:
            found = self.fetch_token_pairs(mint, source="discovery")
            for pair in found:
                pair["_discovery_sources"] = sorted(set(pair.get("_discovery_sources") or []) | sources)
                pairs.append(pair)
        return pairs
