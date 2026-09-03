"""
Paper trading executor with real position management simulation.
Handles entry rules, position tracking, and exit management (2x/5x/10x + moonbag).
"""
import json
from datetime import datetime, timezone
from typing import Optional

def now_iso():
    return datetime.now(timezone.utc).isoformat()

class PaperExecutor:
    """Simulates real position management with cash control and partial exits."""
    
    def __init__(self, store, settings):
        self.store = store
        self.settings = settings
        self.capital = settings.max_total_capital_usd
        self.cash = self.capital
        self.open_positions = []
    
    def open_from_candidate(self, token_address: str, entry_price: float, market_cap: float):
        """
        Automatically open paper position from CANDIDATE token.
        Respects: max 3 open positions, max $1 per position, cash control.
        """
        # Enforce constraints
        if len(self.open_positions) >= self.settings.max_open_positions:
            return {"status": "rejected", "reason": "max_positions_reached"}
        
        position_size = min(self.settings.max_position_usd, self.cash)
        if position_size <= 0:
            return {"status": "rejected", "reason": "insufficient_cash"}
        
        # Create position
        position = {
            "address": token_address,
            "entry_price": entry_price,
            "entry_market_cap": market_cap,
            "entry_at": now_iso(),
            "size_usd": position_size,
            "quantity": position_size / entry_price,
            "status": "open",
            "current_price": entry_price,
            "current_value": position_size,
            "return_pct": 0.0,
            "gain": 0.0,
            "exits": [],
            "reached_multiples": {
                "x2": False,
                "x5": False,
                "x10": False,
                "x20": False,
                "x50": False,
                "x100": False
            },
            "moonbag_enabled": self.settings.moonbag_enabled,
            "moonbag_quantity": 0.0
        }
        
        self.open_positions.append(position)
        self.cash -= position_size
        
        return {
            "status": "opened",
            "position": position,
            "cash_remaining": round(self.cash, 2)
        }
    
    def update_position(self, token_address: str, current_price: float):
        """Update position with current price and trigger exits."""
        for pos in self.open_positions:
            if pos["address"] == token_address and pos["status"] == "open":
                old_value = pos["current_value"]
                pos["current_price"] = current_price
                pos["current_value"] = pos["quantity"] * current_price
                pos["gain"] = pos["current_value"] - pos["size_usd"]
                pos["return_pct"] = round((pos["gain"] / pos["size_usd"]) * 100, 2) if pos["size_usd"] > 0 else 0
                
                # Update multiple tracking
                multiple = current_price / pos["entry_price"]
                if multiple >= 2 and not pos["reached_multiples"]["x2"]:
                    pos["reached_multiples"]["x2"] = True
                if multiple >= 5 and not pos["reached_multiples"]["x5"]:
                    pos["reached_multiples"]["x5"] = True
                if multiple >= 10 and not pos["reached_multiples"]["x10"]:
                    pos["reached_multiples"]["x10"] = True
                if multiple >= 20 and not pos["reached_multiples"]["x20"]:
                    pos["reached_multiples"]["x20"] = True
                if multiple >= 50 and not pos["reached_multiples"]["x50"]:
                    pos["reached_multiples"]["x50"] = True
                if multiple >= 100 and not pos["reached_multiples"]["x100"]:
                    pos["reached_multiples"]["x100"] = True
                
                # Check and execute partial exits
                self._check_exits(pos)
                return pos
        return None
    
    def _check_exits(self, position):
        """Execute partial exit rules: 2x/5x/10x + moonbag."""
        multiple = position["current_price"] / position["entry_price"]
        
        # Capital recovery at 2x
        if multiple >= 2 and not any(e["rule"] == "capital_recovery" for e in position["exits"]):
            exit_quantity = position["size_usd"] / position["current_price"]
            exit_value = exit_quantity * position["current_price"]
            self.cash += exit_value
            position["exits"].append({
                "rule": "capital_recovery",
                "price": position["current_price"],
                "quantity": exit_quantity,
                "value_usd": round(exit_value, 2),
                "exit_at": now_iso(),
                "multiple": round(multiple, 2)
            })
            position["quantity"] -= exit_quantity
        
        # 5x exit (if enabled and reached)
        if multiple >= 5 and not any(e["rule"] == "take_profit_5x" for e in position["exits"]):
            if position["quantity"] > 0:
                exit_quantity = position["quantity"] * 0.5
                exit_value = exit_quantity * position["current_price"]
                self.cash += exit_value
                position["exits"].append({
                    "rule": "take_profit_5x",
                    "price": position["current_price"],
                    "quantity": exit_quantity,
                    "value_usd": round(exit_value, 2),
                    "exit_at": now_iso(),
                    "multiple": round(multiple, 2)
                })
                position["quantity"] -= exit_quantity
        
        # 10x exit (if enabled and reached)
        if multiple >= 10 and not any(e["rule"] == "take_profit_10x" for e in position["exits"]):
            if position["quantity"] > 0:
                exit_quantity = position["quantity"] * 0.5
                exit_value = exit_quantity * position["current_price"]
                self.cash += exit_value
                position["exits"].append({
                    "rule": "take_profit_10x",
                    "price": position["current_price"],
                    "quantity": exit_quantity,
                    "value_usd": round(exit_value, 2),
                    "exit_at": now_iso(),
                    "multiple": round(multiple, 2)
                })
                position["quantity"] -= exit_quantity
        
        # Moonbag: keep remaining quantity
        if position["moonbag_enabled"] and position["quantity"] > 0:
            position["moonbag_quantity"] = position["quantity"]
    
    def get_portfolio_value(self):
        """Calculate total portfolio value (cash + open positions)."""
        positions_value = sum(p["current_value"] for p in self.open_positions if p["status"] == "open")
        return round(self.cash + positions_value, 2)
    
    def get_stats(self):
        """Get portfolio statistics."""
        open_count = len([p for p in self.open_positions if p["status"] == "open"])
        closed_count = len([p for p in self.open_positions if p["status"] == "closed"])
        
        all_returns = [p["return_pct"] for p in self.open_positions if p["current_value"] > 0]
        winners = sum(1 for p in self.open_positions if p["return_pct"] > 0)
        
        return {
            "capital_initial": round(self.capital, 2),
            "cash": round(self.cash, 2),
            "capital_invested": round(self.capital - self.cash, 2),
            "portfolio_value": self.get_portfolio_value(),
            "open_positions": open_count,
            "closed_positions": closed_count,
            "total_pnl": round(sum(p["gain"] for p in self.open_positions), 2),
            "roi_pct": round((self.get_portfolio_value() - self.capital) / self.capital * 100, 2) if self.capital > 0 else 0,
            "winners": winners,
            "avg_return": round(sum(all_returns) / len(all_returns), 2) if all_returns else 0
        }
