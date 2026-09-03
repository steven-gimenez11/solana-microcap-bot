from flask import Flask, jsonify, render_template_string
from scanner import Scanner
from config import settings

scanner, app = Scanner(), Flask(__name__)

PAGE = '''<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Solana Microcap Scanner</title>
  <style>
    body{margin:0;background:#101418;color:#e8edf2;font:15px/1.4 system-ui,Segoe UI,Roboto,Helvetica,Arial}
    .wrap{padding:20px}
    h1,h2{margin:0 0 10px}
    .metrics{display:flex;gap:12px;flex-wrap:wrap}
    .card{background:#0f1720;padding:12px;border-radius:8px;min-width:160px}
    table{width:100%;border-collapse:collapse}
    th,td{padding:6px;border-bottom:1px solid #132029;text-align:left}
    .tokens{margin-top:20px}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Solana Microcap Scanner</h1>
    <div class="metrics">
      <div class="card">Tokens scanned: {{ metrics['tokens_scanned'] }}</div>
      <div class="card">Watchlist: {{ metrics['watchlist'] }}</div>
      <div class="card">Strong watch: {{ metrics['strong_watch'] }}</div>
      <div class="card">Candidates: {{ metrics['candidates'] }}</div>
    </div>

    <h2 style="margin-top:20px">Paper Portfolio</h2>
    <div class="metrics">
      <div class="card">Capital inicial: ${{ portfolio.capital_initial }}</div>
      <div class="card">Cash: ${{ portfolio.cash }}</div>
      <div class="card">Invertido: ${{ portfolio.capital_invested }}</div>
      <div class="card">Valor: ${{ portfolio.portfolio_value }}</div>
      <div class="card">PnL: ${{ portfolio.total_pnl }}</div>
      <div class="card">ROI: {{ portfolio.roi_pct }}%</div>
    </div>

    <div class="tokens">
      <h2>Top Tokens</h2>
      <table>
        <thead><tr><th>Symbol</th><th>Name</th><th>Score</th><th>Risk</th><th>Classification</th></tr></thead>
        <tbody>
        {% for t in tokens %}
          <tr>
            <td>{{ t['symbol'] or 'N/A' }}</td>
            <td>{{ t['name'] or 'N/A' }}</td>
            <td>{{ t.get('opportunity_score', 0) }}</td>
            <td>{{ t.get('risk_score', 0) }}</td>
            <td>{{ t.get('classification', 'REJECTED') }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
'''

@app.get("/")
def index():
    all_tokens = scanner.store.latest()
    tokens = [x for x in all_tokens if x.get("classification") in {"WATCH", "STRONG_WATCH", "CANDIDATE"}]
    metrics = {
        "tokens_scanned": len(all_tokens),
        "watchlist": sum(1 for x in tokens if x.get("classification") == "WATCH"),
        "strong_watch": sum(1 for x in tokens if x.get("classification") == "STRONG_WATCH"),
        "candidates": sum(1 for x in tokens if x.get("classification") == "CANDIDATE")
    }
    portfolio = scanner.store.paper_stats()
    
    class P: pass
    p = P()
    p.capital_initial = portfolio.get('capital_initial', 0)
    p.cash = portfolio.get('cash', 0)
    p.capital_invested = portfolio.get('capital_invested', 0)
    p.portfolio_value = portfolio.get('portfolio_value', 0)
    p.total_pnl = portfolio.get('total_pnl', 0)
    p.roi_pct = portfolio.get('roi_pct', 0)
    
    return render_template_string(PAGE, tokens=tokens[:100], metrics=metrics, portfolio=p)

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "mode": "DRY_RUN",
        "trading_enabled": settings.trading_enabled,
        "database": settings.database_path
    })

@app.get("/api/scan")
def api_scan():
    return jsonify(scanner.scan())

@app.get("/api/candidates")
def candidates():
    return jsonify(scanner.store.latest("CANDIDATE"))

@app.get("/api/watchlist")
def watchlist():
    return jsonify([x for x in scanner.store.latest() if x.get("classification") in {"WATCH", "STRONG_WATCH"}])

@app.get("/api/paper-trades")
def paper_trades():
    return jsonify(scanner.store.paper_trades())

@app.get("/api/stats")
def stats():
    return jsonify(scanner.store.paper_stats())

@app.get("/api/debug")
def api_debug():
    return jsonify(scanner.store.get_debug())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
