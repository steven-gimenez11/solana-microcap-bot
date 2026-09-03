import json, os, sqlite3
from statistics import median
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, path):
        self.path = path
        directory = os.path.dirname(path)
        if directory: os.makedirs(directory, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS tokens (address TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshots (address TEXT, captured_at TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS candidates (address TEXT, captured_at TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE,
                    entry_price REAL,
                    entry_market_cap REAL,
                    entry_at TEXT,
                    data TEXT,
                    status TEXT DEFAULT 'open'
                );
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE,
                    size_usd REAL,
                    quantity REAL,
                    entry_price REAL,
                    entry_at TEXT,
                    current_price REAL,
                    status TEXT DEFAULT 'open',
                    exits_json TEXT,
                    moonbag_quantity REAL DEFAULT 0,
                    data TEXT
                );
                CREATE TABLE IF NOT EXISTS debug_info (key TEXT PRIMARY KEY, value TEXT);
            ''')
            db.execute("INSERT OR IGNORE INTO debug_info VALUES ('initialized', ?)", (now(),))
            db.commit()

    def connect(self): 
        return sqlite3.connect(self.path)

    def save(self, token):
        captured, address = now(), token["address"]
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO tokens VALUES (?, ?, ?)", (address, json.dumps(token), captured))
            db.execute("INSERT INTO snapshots(address, captured_at, data) VALUES(?, ?, ?)", (address, captured, json.dumps(token)))
            
            if token.get("classification") == "CANDIDATE":
                db.execute("INSERT INTO candidates(address, captured_at, data) VALUES(?, ?, ?)", (address, captured, json.dumps(token)))
                if not db.execute("SELECT 1 FROM paper_trades WHERE address=?", (address,)).fetchone():
                    db.execute(
                        "INSERT INTO paper_trades(address, entry_price, entry_market_cap, entry_at, data, status) VALUES(?, ?, ?, ?, ?, ?)",
                        (address, token.get("price_usd", 0), token.get("market_cap", 0), captured, json.dumps({
                            "address": address,
                            "entry_price": token.get("price_usd", 0),
                            "entry_market_cap": token.get("market_cap", 0),
                            "entry_at": captured,
                            "samples": [],
                            "current_return_pct": 0,
                            "maximum_gain_pct": 0,
                            "maximum_drawdown_pct": 0,
                            "reached_2x": False,
                            "reached_5x": False,
                            "reached_10x": False,
                            "reached_20x": False,
                            "reached_50x": False,
                            "reached_100x": False,
                            "horizon_returns": {}
                        }), "open")
                    )
            
            row = db.execute("SELECT id, entry_price, entry_at, data FROM paper_trades WHERE address=?", (address,)).fetchone()
            if row and row[1] and token.get("price_usd"):
                trade = json.loads(row[3])
                gain = token["price_usd"] / row[1] - 1
                sample = {"timestamp": captured, "return_pct": round(gain * 100, 2), "market_cap": token.get("market_cap")}
                trade.setdefault("samples", []).append(sample)
                
                elapsed = (datetime.fromisoformat(captured) - datetime.fromisoformat(row[2])).total_seconds()
                for label, seconds in (("5m", 300), ("15m", 900), ("1h", 3600), ("6h", 21600), ("24h", 86400), ("48h", 172800), ("72h", 259200)):
                    if elapsed >= seconds and label not in trade.get("horizon_returns", {}):
                        trade.setdefault("horizon_returns", {})[label] = sample["return_pct"]
                
                returns = [s["return_pct"] for s in trade.get("samples", [])]
                trade.update(
                    current_return_pct=round(gain * 100, 2),
                    maximum_gain_pct=round(max(returns), 2) if returns else 0,
                    maximum_drawdown_pct=round(min(returns), 2) if returns else 0,
                    reached_2x=max(returns) >= 100 if returns else False,
                    reached_5x=max(returns) >= 400 if returns else False,
                    reached_10x=max(returns) >= 900 if returns else False,
                    reached_20x=max(returns) >= 1900 if returns else False,
                    reached_50x=max(returns) >= 4900 if returns else False,
                    reached_100x=max(returns) >= 9900 if returns else False
                )
                db.execute("UPDATE paper_trades SET data=? WHERE id=?", (json.dumps(trade), row[0]))
            
            db.commit()

    def latest(self, classification_name=None):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM tokens ORDER BY updated_at DESC").fetchall()
        items = [json.loads(row[0]) for row in rows]
        return [x for x in items if not classification_name or x.get("classification") == classification_name]

    def paper_trades(self):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM paper_trades ORDER BY entry_at DESC").fetchall()
        trades = [json.loads(row[0]) for row in rows]
        for trade in trades:
            trade.setdefault("current_return_pct", 0)
            trade.setdefault("maximum_gain_pct", 0)
            trade.setdefault("maximum_drawdown_pct", 0)
            trade.setdefault("reached_2x", False)
            trade.setdefault("reached_5x", False)
            trade.setdefault("reached_10x", False)
            trade.setdefault("reached_20x", False)
            trade.setdefault("reached_50x", False)
            trade.setdefault("reached_100x", False)
            trade.setdefault("samples", [])
            trade.setdefault("horizon_returns", {})
        return trades

    def paper_stats(self):
        trades = self.paper_trades()
        returns = [x.get("current_return_pct", 0) for x in trades if "current_return_pct" in x]
        
        if not returns:
            return {
                "candidates": len(trades),
                "measured": 0,
                "win_rate": 0,
                "average_return": 0,
                "median_return": 0,
                "best_return": 0,
                "worst_return": 0,
                "capital_initial": 10,
                "cash": 10,
                "capital_invested": 0,
                "portfolio_value": 10,
                "total_pnl": 0,
                "roi_pct": 0
            }
        
        return {
            "candidates": len(trades),
            "measured": len(returns),
            "win_rate": round(sum(value > 0 for value in returns) / len(returns) * 100, 2) if returns else 0,
            "average_return": round(sum(returns) / len(returns), 2),
            "median_return": round(median(returns), 2) if returns else 0,
            "best_return": round(max(returns), 2),
            "worst_return": round(min(returns), 2),
            "capital_initial": 10,
            "cash": 10,
            "capital_invested": 0,
            "portfolio_value": 10,
            "total_pnl": 0,
            "roi_pct": 0
        }

    def get_debug(self):
        """Return debug information for /api/debug endpoint."""
        with self.connect() as db:
            token_count = db.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
            candidate_count = db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
            paper_count = db.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
            debug_info = db.execute("SELECT key, value FROM debug_info").fetchall()
        
        debug_dict = {k: v for k, v in debug_info}
        return {
            "status": "operational",
            "database": self.path,
            "tokens_scanned": token_count,
            "candidates": candidate_count,
            "paper_positions": paper_count,
            "initialized_at": debug_dict.get("initialized", "unknown"),
            "dry_run_mode": True,
            "trading_enabled": False
        }
