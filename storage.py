import json, os, sqlite3
from statistics import median
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat()
class Store:
    def __init__(self, path):
        self.path = path; directory = os.path.dirname(path)
        if directory: os.makedirs(directory, exist_ok=True)
        with self.connect() as db: db.executescript('''CREATE TABLE IF NOT EXISTS tokens (address TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, address TEXT, captured_at TEXT, data TEXT); CREATE TABLE IF NOT EXISTS candidates (id INTEGER PRIMARY KEY, address TEXT, captured_at TEXT, data TEXT); CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, address TEXT, created_at TEXT, message TEXT); CREATE TABLE IF NOT EXISTS paper_trades (id INTEGER PRIMARY KEY, address TEXT, entry_price REAL, entry_market_cap REAL, entry_at TEXT, data TEXT);''')
    def connect(self): return sqlite3.connect(self.path)
    def save(self, token):
        captured, address = now(), token["address"]
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO tokens VALUES (?, ?, ?)", (address, json.dumps(token), captured)); db.execute("INSERT INTO snapshots(address,captured_at,data) VALUES(?,?,?)", (address, captured, json.dumps(token)))
            if token.get("classification") == "CANDIDATE":
                db.execute("INSERT INTO candidates(address,captured_at,data) VALUES(?,?,?)", (address, captured, json.dumps(token)))
                if not db.execute("SELECT 1 FROM paper_trades WHERE address=?", (address,)).fetchone(): db.execute("INSERT INTO paper_trades(address,entry_price,entry_market_cap,entry_at,data) VALUES(?,?,?,?,?)", (address, token.get("price_usd", 0), token.get("market_cap", 0), captured, json.dumps({"status":"OPEN", "token":token, "amount_usd":1, "samples":[]})))
            row = db.execute("SELECT id, entry_price, entry_at, data FROM paper_trades WHERE address=?", (address,)).fetchone()
            if row and row[1] and token.get("price_usd"):
                trade = json.loads(row[3]); gain = token["price_usd"] / row[1] - 1
                sample = {"timestamp":captured, "return_pct":round(gain * 100, 2), "market_cap":token.get("market_cap")}
                trade["samples"].append(sample)
                elapsed = (datetime.fromisoformat(captured) - datetime.fromisoformat(row[2])).total_seconds()
                for label, seconds in (("5m", 300), ("15m", 900), ("1h", 3600), ("6h", 21600), ("24h", 86400), ("48h", 172800), ("72h", 259200)):
                    if elapsed >= seconds and label not in trade.get("horizon_returns", {}):
                        trade.setdefault("horizon_returns", {})[label] = sample["return_pct"]
                returns = [sample["return_pct"] for sample in trade["samples"]]
                trade.update(current_return_pct=round(gain * 100, 2), maximum_gain_pct=round(max(returns), 2), maximum_drawdown_pct=round(min(returns), 2), reached_2x=max(returns) >= 100, reached_5x=max(returns) >= 400, reached_10x=max(returns) >= 900, reached_50x=max(returns) >= 4900, reached_100x=max(returns) >= 9900)
                db.execute("UPDATE paper_trades SET data=? WHERE id=?", (json.dumps(trade), row[0]))
    def latest(self, classification_name=None):
        with self.connect() as db: rows = db.execute("SELECT data FROM tokens ORDER BY updated_at DESC").fetchall()
        items = [json.loads(row[0]) for row in rows]; return [x for x in items if not classification_name or x.get("classification") == classification_name]
    def paper_trades(self):
        with self.connect() as db: rows = db.execute("SELECT data FROM paper_trades ORDER BY entry_at DESC").fetchall()
        return [json.loads(row[0]) for row in rows]
    def paper_stats(self):
        trades = self.paper_trades(); returns = [x["current_return_pct"] for x in trades if "current_return_pct" in x]
        return {"candidates":len(trades), "measured":len(returns), "win_rate":round(sum(value > 0 for value in returns) / len(returns) * 100, 2) if returns else None, "average_return":round(sum(returns) / len(returns), 2) if returns else None, "median_return":round(median(returns), 2) if returns else None, "maximum_gain":round(max((x.get("maximum_gain_pct", 0) for x in trades), default=0), 2), "average_max_drawdown":round(sum(x.get("maximum_drawdown_pct", 0) for x in trades) / len(trades), 2) if trades else None, "reached_2x":sum(x.get("reached_2x", False) for x in trades), "reached_5x":sum(x.get("reached_5x", False) for x in trades), "reached_10x":sum(x.get("reached_10x", False) for x in trades), "lost_over_50pct":sum(x.get("maximum_drawdown_pct", 0) <= -50 for x in trades), "near_zero":sum(-10 <= x.get("current_return_pct", 0) <= 10 for x in trades), "horizons":{label:[x.get("horizon_returns", {}).get(label) for x in trades if label in x.get("horizon_returns", {})] for label in ("5m", "15m", "1h", "6h", "24h", "48h", "72h")}}