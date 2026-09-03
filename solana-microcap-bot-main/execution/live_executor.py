from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import settings
from execution.jupiter_executor import JupiterExecutor, JupiterError

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


class LiveTradingEngine:
    """Hard-gated real-money execution engine.

    It only reacts to tokens that already passed the scanner's CANDIDATE classification,
    applies a second live gate, then uses at most MAX_POSITION_USD per new position.
    """
    CRITICAL_FLAGS = {
        "low_liquidity", "suspicious_volume", "mint_authority_enabled",
        "freeze_authority_enabled", "possible_pump", "extreme_sell_imbalance",
    }

    def __init__(self, store, cfg=settings, jupiter=None):
        self.store = store
        self.cfg = cfg
        self.enabled = bool(cfg.live_mode)
        self.jupiter = jupiter if jupiter is not None else (JupiterExecutor(cfg) if self.enabled else None)

    def status(self):
        return {
            "enabled": self.enabled,
            "wallet": self.jupiter.wallet_address if self.jupiter else None,
            "max_position_usd": self.cfg.max_position_usd,
            "max_open_positions": self.cfg.max_open_positions,
            "max_total_capital_usd": self.cfg.max_total_capital_usd,
        }

    def _eligible(self, token):
        if not self.enabled or token.get("classification") != "CANDIDATE":
            return False, "not_live_candidate"
        if float(token.get("opportunity_score") or 0) < self.cfg.min_score:
            return False, "opportunity_below_threshold"
        if float(token.get("risk_score") or 100) > self.cfg.max_candidate_risk:
            return False, "risk_above_threshold"
        if set(token.get("risk_flags") or []) & self.CRITICAL_FLAGS:
            return False, "critical_risk_flag"
        if float(token.get("upside_asymmetry_score") or 0) < self.cfg.live_min_asymmetry_score:
            return False, "asymmetry_below_live_threshold"
        if float((token.get("momentum") or {}).get("momentum_score") or 0) < self.cfg.live_min_momentum_score:
            return False, "momentum_below_live_threshold"
        if float(token.get("liquidity_usd") or 0) < self.cfg.min_liquidity_usd:
            return False, "liquidity_below_threshold"
        return True, "eligible"

    def on_token(self, token):
        if not self.enabled:
            return
        address = token.get("address")
        if not address:
            return
        existing = self.store.get_open_live_trade(address)
        if existing:
            self._manage(existing, token)
            return
        eligible, reason = self._eligible(token)
        if not eligible:
            return
        if self.store.open_live_count() >= self.cfg.max_open_positions:
            return
        if self.store.live_recently_traded(address, self.cfg.live_entry_cooldown_hours):
            return
        self._buy(token)

    def _buy(self, token):
        address = token["address"]
        reason = (
            f"CANDIDATE opp={token.get('opportunity_score')} risk={token.get('risk_score')} "
            f"momentum={(token.get('momentum') or {}).get('momentum_score')} asym={token.get('upside_asymmetry_score')}"
        )
        try:
            execution = self.jupiter.buy_usd(address, self.cfg.max_position_usd)
            result = execution["result"]
            raw_out = int(result.get("outputAmountResult") or result.get("totalOutputAmount") or 0)
            if raw_out <= 0:
                raise JupiterError("Swap succeeded but output amount was unavailable")
            self.store.create_live_trade(token, execution, raw_out, reason)
            log.warning("LIVE BUY %s $%.2f tx=%s", token.get("symbol"), self.cfg.max_position_usd, result.get("signature"))
        except Exception as exc:
            self.store.add_live_event(address, "BUY_FAILED", str(exc))
            log.exception("live buy failed for %s", address)

    def _sell_fraction(self, trade, token, fraction_original, reason):
        original = int(trade.get("entry_raw_amount") or 0)
        remaining = int(trade.get("remaining_raw_amount") or 0)
        raw = min(remaining, max(1, int(original * fraction_original)))
        if raw <= 0:
            return False
        try:
            execution = self.jupiter.sell_raw(trade["address"], raw)
            self.store.record_live_sale(trade["id"], token, raw, execution, reason)
            log.warning("LIVE SELL %s fraction=%s reason=%s tx=%s", trade.get("symbol"), fraction_original, reason, execution["result"].get("signature"))
            return True
        except Exception as exc:
            self.store.add_live_event(trade["address"], "SELL_FAILED", f"{reason}: {exc}")
            log.exception("live sell failed for %s", trade["address"])
            return False

    def _manage(self, trade, token):
        entry = float(trade.get("entry_price") or 0)
        current = float(token.get("price_usd") or 0)
        if entry <= 0 or current <= 0:
            return
        multiple = current / entry
        peak = max(float(trade.get("highest_price") or entry), current)
        drawdown_peak = (current / peak - 1) * 100
        self.store.mark_live_price(trade["id"], token, current, peak, multiple, drawdown_peak)
        trade = self.store.get_live_trade_by_id(trade["id"]) or trade
        reasons = {x.get("reason") for x in trade.get("partial_exits", [])}

        if multiple >= self.cfg.capital_recovery_multiple and "capital_recovery_2x" not in reasons:
            self._sell_fraction(trade, token, 0.50, "capital_recovery_2x")
            trade = self.store.get_live_trade_by_id(trade["id"]) or trade
        reasons = {x.get("reason") for x in trade.get("partial_exits", [])}
        if multiple >= self.cfg.take_profit_1_multiple and "take_profit_5x" not in reasons:
            self._sell_fraction(trade, token, 0.20, "take_profit_5x")
            trade = self.store.get_live_trade_by_id(trade["id"]) or trade
        reasons = {x.get("reason") for x in trade.get("partial_exits", [])}
        if multiple >= self.cfg.take_profit_2_multiple and "take_profit_10x" not in reasons:
            self._sell_fraction(trade, token, 0.15, "take_profit_10x")
            trade = self.store.get_live_trade_by_id(trade["id"]) or trade

        risk = float(token.get("risk_score") or 0)
        momentum = float((token.get("momentum") or {}).get("momentum_score") or 0)
        reason = None
        if risk >= 75:
            reason = "risk_score_critical"
        elif set(token.get("risk_flags") or []) & {"freeze_authority_enabled", "mint_authority_enabled", "extreme_sell_imbalance"}:
            reason = "critical_risk_flag_after_entry"
        elif drawdown_peak <= -60 and multiple >= 1.15:
            reason = "major_drawdown_from_peak"
        else:
            try:
                entered = datetime.fromisoformat(trade["entry_at"])
                age = (datetime.now(timezone.utc) - entered).total_seconds()
                if age >= 21600 and multiple < 0.55 and momentum < 20:
                    reason = "failed_momentum_after_6h"
            except Exception:
                pass
        if reason:
            remaining = int((self.store.get_live_trade_by_id(trade["id"]) or trade).get("remaining_raw_amount") or 0)
            if remaining > 0:
                self._sell_fraction(self.store.get_live_trade_by_id(trade["id"]) or trade, token, remaining / max(int(trade.get("entry_raw_amount") or 1), 1), reason)
