import json
import os
import sqlite3
from datetime import datetime, timezone
from statistics import median
from config import settings


def now():
    return datetime.now(timezone.utc).isoformat()


def _r(v, n=4):
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return 0.0


class Store:
    def __init__(self, path):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS tokens (
                    address TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY, address TEXT, captured_at TEXT, data TEXT
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY, address TEXT, captured_at TEXT, data TEXT
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY, address TEXT, created_at TEXT, message TEXT
                );
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY, address TEXT, entry_price REAL, entry_market_cap REAL,
                    entry_at TEXT, data TEXT
                );
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def set_meta(self, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, json.dumps(value)))

    def get_meta(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def open_paper_count(self):
        return sum(t.get("status") == "OPEN" for t in self.paper_trades())

    def create_paper_trade(self, address, token, reason="candidate", amount_usd=None):
        amount = min(float(amount_usd or settings.max_position_usd), settings.max_position_usd)
        price = float(token.get("price_usd") or 0)
        if not address or price <= 0 or amount <= 0:
            return False
        portfolio = self.paper_stats()
        if portfolio["cash"] + 1e-9 < amount or portfolio["open_positions"] >= settings.max_open_positions:
            return False
        with self.connect() as db:
            rows = db.execute("SELECT data FROM paper_trades WHERE address=?", (address,)).fetchall()
            if any(json.loads(r[0]).get("status") == "OPEN" for r in rows):
                return False
            captured = now()
            units = amount / price
            trade = {
                "status": "OPEN", "address": address, "symbol": token.get("symbol", "UNKNOWN"),
                "amount_usd": amount, "entry_price": price, "entry_market_cap": token.get("market_cap", 0),
                "entry_at": captured, "entry_units": units, "remaining_units": units,
                "realized_proceeds": 0.0, "realized_pnl": 0.0, "current_price": price,
                "current_value": amount, "current_return_pct": 0.0, "multiple": 1.0,
                "highest_price": price, "lowest_price": price, "maximum_gain_pct": 0.0,
                "maximum_drawdown_pct": 0.0, "drawdown_from_peak_pct": 0.0,
                "why_entered": reason, "why_exited": None, "partial_exits": [], "samples": [],
                "horizon_returns": {}, "milestones": {}, "token": token,
            }
            db.execute(
                "INSERT INTO paper_trades(address,entry_price,entry_market_cap,entry_at,data) VALUES(?,?,?,?,?)",
                (address, price, token.get("market_cap", 0), captured, json.dumps(trade)),
            )
        return True

    def _partial_sell(self, trade, token, fraction_original, reason):
        price = float(token.get("price_usd") or 0)
        original_units = float(trade.get("entry_units") or 0)
        remaining = float(trade.get("remaining_units") or 0)
        units = min(remaining, original_units * fraction_original)
        if units <= 0 or price <= 0:
            return
        proceeds = units * price
        original_cost = units * float(trade.get("entry_price") or 0)
        trade["remaining_units"] = remaining - units
        trade["realized_proceeds"] = float(trade.get("realized_proceeds") or 0) + proceeds
        trade["realized_pnl"] = float(trade.get("realized_pnl") or 0) + (proceeds - original_cost)
        trade.setdefault("partial_exits", []).append({
            "timestamp": now(), "reason": reason, "price": price, "units": units,
            "proceeds_usd": round(proceeds, 6), "multiple": round(price / trade["entry_price"], 4),
        })

    def _close_trade(self, trade, token, reason):
        remaining = float(trade.get("remaining_units") or 0)
        if remaining > 0:
            fraction = remaining / max(float(trade.get("entry_units") or 1), 1e-18)
            self._partial_sell(trade, token, fraction, reason)
        trade["status"] = "CLOSED"
        trade["closed_at"] = now()
        trade["why_exited"] = reason
        trade["current_value"] = 0.0

    def update_paper_trade(self, address, token):
        with self.connect() as db:
            row = db.execute(
                "SELECT id,data FROM paper_trades WHERE address=? ORDER BY id DESC LIMIT 1", (address,)
            ).fetchone()
            if not row:
                return False
            trade = json.loads(row["data"])
            if trade.get("status") != "OPEN":
                return False
            price = float(token.get("price_usd") or 0)
            entry = float(trade.get("entry_price") or 0)
            if price <= 0 or entry <= 0:
                return False

            captured = now()
            multiple = price / entry
            trade["current_price"] = price
            trade["multiple"] = round(multiple, 4)
            trade["highest_price"] = max(float(trade.get("highest_price") or entry), price)
            trade["lowest_price"] = min(float(trade.get("lowest_price") or entry), price)
            trade["maximum_gain_pct"] = round((trade["highest_price"] / entry - 1) * 100, 2)
            trade["maximum_drawdown_pct"] = round((trade["lowest_price"] / entry - 1) * 100, 2)
            trade["drawdown_from_peak_pct"] = round((price / max(trade["highest_price"], 1e-18) - 1) * 100, 2)
            trade["current_return_pct"] = round((multiple - 1) * 100, 2)
            trade["token"] = token
            trade.setdefault("samples", []).append({
                "timestamp": captured, "price": price, "return_pct": trade["current_return_pct"],
                "market_cap": token.get("market_cap"), "risk_score": token.get("risk_score"),
                "opportunity_score": token.get("opportunity_score"),
            })
            if len(trade["samples"]) > 2000:
                trade["samples"] = trade["samples"][-2000:]

            elapsed = (datetime.fromisoformat(captured) - datetime.fromisoformat(trade["entry_at"])).total_seconds()
            for label, seconds in (("5m",300),("15m",900),("1h",3600),("6h",21600),("24h",86400),("48h",172800),("72h",259200)):
                if elapsed >= seconds and label not in trade.setdefault("horizon_returns", {}):
                    trade["horizon_returns"][label] = trade["current_return_pct"]

            for label, target in (("2x",2),("5x",5),("10x",10),("20x",20),("50x",50),("100x",100)):
                if multiple >= target and label not in trade.setdefault("milestones", {}):
                    trade["milestones"][label] = {"timestamp": captured, "hours": round(elapsed / 3600, 3)}

            reasons = {x.get("reason") for x in trade.get("partial_exits", [])}
            if multiple >= settings.capital_recovery_multiple and "capital_recovery_2x" not in reasons:
                self._partial_sell(trade, token, 0.50, "capital_recovery_2x")
            reasons = {x.get("reason") for x in trade.get("partial_exits", [])}
            if multiple >= settings.take_profit_1_multiple and "take_profit_5x" not in reasons:
                self._partial_sell(trade, token, 0.20, "take_profit_5x")
            reasons = {x.get("reason") for x in trade.get("partial_exits", [])}
            if multiple >= settings.take_profit_2_multiple and "take_profit_10x" not in reasons:
                self._partial_sell(trade, token, 0.15, "take_profit_10x")

            risk = float(token.get("risk_score") or 0)
            momentum = float((token.get("momentum") or {}).get("momentum_score") or 0)
            if risk >= 75:
                self._close_trade(trade, token, "risk_score_critical")
            elif trade["drawdown_from_peak_pct"] <= -60 and multiple >= 1.15:
                self._close_trade(trade, token, "major_drawdown_from_peak")
            elif elapsed >= 21600 and multiple < 0.55 and momentum < 20:
                self._close_trade(trade, token, "failed_momentum_after_6h")
            elif not settings.moonbag_enabled and multiple >= settings.take_profit_2_multiple:
                self._close_trade(trade, token, "take_profit_complete")

            trade["current_value"] = round(float(trade.get("remaining_units") or 0) * price, 6)
            db.execute("UPDATE paper_trades SET data=? WHERE id=?", (json.dumps(trade), row["id"]))
        return True

    def save(self, token):
        captured, address = now(), token["address"]
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO tokens VALUES (?, ?, ?)", (address, json.dumps(token), captured))
            db.execute("INSERT INTO snapshots(address,captured_at,data) VALUES(?,?,?)", (address, captured, json.dumps(token)))
            if token.get("classification") == "CANDIDATE":
                db.execute("INSERT INTO candidates(address,captured_at,data) VALUES(?,?,?)", (address, captured, json.dumps(token)))

        if token.get("classification") == "CANDIDATE":
            reason = (
                f"CANDIDATE opportunity={token.get('opportunity_score')} risk={token.get('risk_score')} "
                f"momentum={(token.get('momentum') or {}).get('momentum_score')} asymmetry={token.get('upside_asymmetry_score')}"
            )
            self.create_paper_trade(address, token, reason=reason)
        self.update_paper_trade(address, token)

    def latest(self, classification_name=None):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM tokens ORDER BY updated_at DESC").fetchall()
        items = [json.loads(row[0]) for row in rows]
        return [x for x in items if not classification_name or x.get("classification") == classification_name]

    def paper_trades(self):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM paper_trades ORDER BY entry_at DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def paper_stats(self):
        trades = self.paper_trades()
        open_trades = [x for x in trades if x.get("status") == "OPEN"]
        closed = [x for x in trades if x.get("status") == "CLOSED"]
        allocated = sum(float(x.get("amount_usd") or 0) for x in trades)
        realized = sum(float(x.get("realized_proceeds") or 0) for x in trades)
        invested = sum(float(x.get("current_value") or 0) for x in open_trades)
        initial = float(settings.paper_initial_capital_usd)
        cash = initial - allocated + realized
        portfolio_value = cash + invested
        pnl = portfolio_value - initial
        returns = [float(x.get("current_return_pct") or 0) for x in trades]
        max_gains = [float(x.get("maximum_gain_pct") or 0) for x in trades]
        drawdowns = [float(x.get("maximum_drawdown_pct") or 0) for x in trades]
        return {
            "capital_initial": _r(initial, 2), "cash": _r(cash, 4), "capital_invested": _r(invested, 4),
            "portfolio_value": _r(portfolio_value, 4), "total_pnl": _r(pnl, 4),
            "roi_pct": _r((pnl / initial * 100) if initial else 0, 2),
            "candidates": len(trades), "total_trades": len(trades), "open_positions": len(open_trades),
            "closed_positions": len(closed), "measured": len(returns),
            "win_rate": _r(sum(v > 0 for v in returns) / len(returns) * 100 if returns else 0, 2),
            "average_return": _r(sum(returns) / len(returns) if returns else 0, 2),
            "median_return": _r(median(returns) if returns else 0, 2),
            "maximum_gain": _r(max(max_gains, default=0), 2),
            "average_max_drawdown": _r(sum(drawdowns) / len(drawdowns) if drawdowns else 0, 2),
            "reached_2x": sum("2x" in x.get("milestones", {}) for x in trades),
            "reached_5x": sum("5x" in x.get("milestones", {}) for x in trades),
            "reached_10x": sum("10x" in x.get("milestones", {}) for x in trades),
            "reached_20x": sum("20x" in x.get("milestones", {}) for x in trades),
            "reached_50x": sum("50x" in x.get("milestones", {}) for x in trades),
            "reached_100x": sum("100x" in x.get("milestones", {}) for x in trades),
            "near_zero": sum(float(x.get("current_return_pct") or 0) <= -90 for x in trades),
        }

    def get_debug(self):
        return {
            "scanner_running": bool(self.get_meta("last_scan_timestamp")),
            "last_scan_timestamp": self.get_meta("last_scan_timestamp"),
            "scan_interval": settings.scan_interval,
            "total_scans": int(self.get_meta("total_scans", 0) or 0),
            "tokens_last_scan": int(self.get_meta("tokens_last_scan", 0) or 0),
            "database_path": self.path,
            "dry_run": settings.dry_run,
            "trading_enabled": settings.trading_enabled,
            "paper_executor_enabled": True,
            "open_paper_positions": self.open_paper_count(),
        }
