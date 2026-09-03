"""Jupiter Swap API V2 executor.

The class is inert unless Settings.live_mode is true. The private key is read only from
an environment variable at runtime; it must never be committed to source control.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import requests

from config import settings

log = logging.getLogger(__name__)
SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = 1_000_000_000


class JupiterError(RuntimeError):
    pass


class JupiterExecutor:
    def __init__(self, cfg=settings, session=None):
        self.cfg = cfg
        self.session = session or requests.Session()
        self.enabled = bool(cfg.live_mode)
        self._keypair = None
        if self.enabled:
            if not cfg.jupiter_api_key:
                raise JupiterError("JUPITER_API_KEY is required for live mode")
            if not cfg.solana_private_key_b58:
                raise JupiterError("SOLANA_PRIVATE_KEY_B58 is required for live mode")
            try:
                import base58
                from solders.keypair import Keypair
                raw = base58.b58decode(cfg.solana_private_key_b58.strip())
                self._keypair = Keypair.from_bytes(raw) if len(raw) == 64 else Keypair.from_seed(raw) if len(raw) == 32 else None
                if self._keypair is None:
                    raise ValueError("expected a 32-byte seed or 64-byte secret key")
            except Exception as exc:
                raise JupiterError("Invalid SOLANA_PRIVATE_KEY_B58 or missing signing dependencies") from exc

    @property
    def wallet_address(self):
        return str(self._keypair.pubkey()) if self._keypair else None

    def _headers(self, json_body=False):
        h = {"x-api-key": self.cfg.jupiter_api_key, "User-Agent": "solana-microcap-bot/3.0"}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def _request(self, method, path, **kwargs):
        if not self.enabled:
            raise JupiterError("Live Jupiter executor is disabled")
        url = self.cfg.jupiter_api_url.rstrip("/") + path
        response = self.session.request(method, url, timeout=self.cfg.request_timeout, **kwargs)
        try:
            payload = response.json()
        except ValueError as exc:
            raise JupiterError(f"Jupiter returned non-JSON HTTP {response.status_code}") from exc
        if not response.ok:
            raise JupiterError(f"Jupiter HTTP {response.status_code}: {payload}")
        return payload

    def price_usd(self, mint):
        data = self._request("GET", "/price/v3", params={"ids": mint}, headers=self._headers())
        item = data.get(mint) or {}
        price = float(item.get("usdPrice") or 0)
        if price <= 0:
            raise JupiterError(f"No reliable Jupiter USD price for {mint}")
        return price

    def sol_balance(self):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [self.wallet_address, {"commitment": "confirmed"}]}
        r = self.session.post(self.cfg.solana_rpc_url, json=payload, timeout=self.cfg.request_timeout)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise JupiterError(f"RPC getBalance failed: {data['error']}")
        return int(data["result"]["value"]) / LAMPORTS_PER_SOL

    def quote_order(self, input_mint, output_mint, raw_amount):
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(int(raw_amount)),
            "taker": self.wallet_address,
        }
        order = self._request("GET", "/swap/v2/order", params=params, headers=self._headers())
        if order.get("errorCode") or not order.get("transaction"):
            raise JupiterError(f"Order is not executable: {order.get('errorMessage') or order.get('errorCode') or 'no transaction'}")
        impact = abs(float(order.get("priceImpact") or 0))
        # Jupiter V2 reports priceImpact as a percentage. Refuse unusually expensive routes.
        if impact > self.cfg.max_price_impact_pct:
            raise JupiterError(f"Price impact {impact:.4f}% exceeds cap {self.cfg.max_price_impact_pct}%")
        return order

    def _sign_transaction(self, transaction_b64):
        from solders.message import to_bytes_versioned
        from solders.signature import Signature
        from solders.transaction import VersionedTransaction
        tx = VersionedTransaction.from_bytes(base64.b64decode(transaction_b64))
        required = int(tx.message.header.num_required_signatures)
        signer_keys = list(tx.message.account_keys)[:required]
        wallet_pubkey = self._keypair.pubkey()
        try:
            signer_index = signer_keys.index(wallet_pubkey)
        except ValueError as exc:
            raise JupiterError("Wallet is not a required signer of Jupiter transaction") from exc
        signatures = list(tx.signatures)
        while len(signatures) < required:
            signatures.append(Signature.default())
        signatures[signer_index] = self._keypair.sign_message(to_bytes_versioned(tx.message))
        signed = VersionedTransaction.populate(tx.message, signatures)
        return base64.b64encode(bytes(signed)).decode("ascii")

    def execute_order(self, order):
        signed = self._sign_transaction(order["transaction"])
        body: dict[str, Any] = {"signedTransaction": signed, "requestId": order["requestId"]}
        if order.get("lastValidBlockHeight") is not None:
            body["lastValidBlockHeight"] = str(order["lastValidBlockHeight"])
        result = self._request("POST", "/swap/v2/execute", json=body, headers=self._headers(json_body=True))
        if result.get("status") != "Success" or int(result.get("code") or 0) != 0:
            raise JupiterError(f"Swap failed: {result.get('error') or result}")
        return result

    def buy_usd(self, output_mint, usd_amount):
        usd_amount = min(float(usd_amount), self.cfg.max_position_usd)
        if usd_amount <= 0:
            raise JupiterError("Buy amount must be positive")
        sol_price = self.price_usd(SOL_MINT)
        sol_amount = usd_amount / sol_price
        balance = self.sol_balance()
        if balance - sol_amount < self.cfg.min_sol_reserve:
            raise JupiterError(
                f"Insufficient SOL after gas reserve: balance={balance:.6f}, required trade={sol_amount:.6f}, reserve={self.cfg.min_sol_reserve:.6f}"
            )
        raw = max(1, int(sol_amount * LAMPORTS_PER_SOL))
        order = self.quote_order(SOL_MINT, output_mint, raw)
        result = self.execute_order(order)
        return {"order": order, "result": result, "usd_amount": usd_amount, "sol_price": sol_price}

    def sell_raw(self, input_mint, raw_amount):
        raw_amount = int(raw_amount)
        if raw_amount <= 0:
            raise JupiterError("Sell amount must be positive")
        order = self.quote_order(input_mint, SOL_MINT, raw_amount)
        result = self.execute_order(order)
        return {"order": order, "result": result}
