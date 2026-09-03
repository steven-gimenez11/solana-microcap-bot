import base64
import logging
import struct
import requests

log = logging.getLogger(__name__)


class SolanaSecurity:
    """Best-effort public RPC checks. Unknown data is explicit, never treated as safe."""

    def __init__(self, rpc_url: str, timeout: float = 8):
        self.rpc_url = rpc_url
        self.timeout = timeout
        self.session = requests.Session()
        self._id = 0

    def _rpc(self, method, params):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        try:
            r = self.session.post(self.rpc_url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                raise RuntimeError(data["error"])
            return data.get("result")
        except Exception as exc:
            log.debug("Solana RPC %s failed: %s", method, exc)
            return None

    def inspect_mint(self, mint: str) -> dict:
        result = {
            "mint_authority": "UNKNOWN",
            "freeze_authority": "UNKNOWN",
            "token_supply": None,
            "top20_holders_pct": None,
            "security_unknown": [],
        }
        if not mint:
            result["security_unknown"] = ["mint_authority", "freeze_authority", "token_supply", "holder_concentration"]
            return result

        account = self._rpc("getAccountInfo", [mint, {"encoding": "base64"}])
        try:
            raw = base64.b64decode(account["value"]["data"][0]) if account and account.get("value") else b""
            if len(raw) >= 82:
                mint_auth_opt = struct.unpack_from("<I", raw, 0)[0]
                supply = struct.unpack_from("<Q", raw, 36)[0]
                decimals = raw[44]
                freeze_opt = struct.unpack_from("<I", raw, 46)[0]
                result["mint_authority"] = "ENABLED" if mint_auth_opt else "DISABLED"
                result["freeze_authority"] = "ENABLED" if freeze_opt else "DISABLED"
                result["token_supply"] = supply / (10 ** decimals) if decimals <= 18 else supply
            else:
                result["security_unknown"].extend(["mint_authority", "freeze_authority", "token_supply"])
        except Exception:
            result["security_unknown"].extend(["mint_authority", "freeze_authority", "token_supply"])

        largest = self._rpc("getTokenLargestAccounts", [mint])
        try:
            values = (largest or {}).get("value", [])
            total_supply = float(result["token_supply"] or 0)
            top_amount = sum(float(x.get("uiAmount") or 0) for x in values[:20])
            if total_supply > 0:
                result["top20_holders_pct"] = round(top_amount / total_supply * 100, 2)
            else:
                result["security_unknown"].append("holder_concentration")
        except Exception:
            result["security_unknown"].append("holder_concentration")

        result["security_unknown"] = sorted(set(result["security_unknown"]))
        return result

    @staticmethod
    def score(data: dict) -> float:
        score = 0.0
        if data.get("mint_authority") == "ENABLED":
            score += 30
        elif data.get("mint_authority") == "UNKNOWN":
            score += 6
        if data.get("freeze_authority") == "ENABLED":
            score += 30
        elif data.get("freeze_authority") == "UNKNOWN":
            score += 6
        top = data.get("top20_holders_pct")
        if top is None:
            score += 6
        elif top >= 90:
            score += 25
        elif top >= 75:
            score += 15
        elif top >= 60:
            score += 8
        return round(min(100, score), 2)
