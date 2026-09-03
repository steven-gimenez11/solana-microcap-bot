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
      <div class="card">Tokens scanned: {{ metrics['tokens scanned'] }}</div>
      <div class="card">Watchlist: {{ metrics['watchlist'] }}</div>
      <div class="card">Strong watch: {{ metrics['strong watch'] }}</div>
      <div class="card">Candidates: {{ metrics['candidates'] }}</div>
    </div>

    <h2 style="margin-top:20px">Paper Portfolio</h2>
    <div class="metrics">
      <div class="card">Capital initial virtual: ${{ portfolio.capital_initial }}</div>
      <div class="card">Cash virtual: ${{ portfolio.cash }}</div>
      <div class="card">Capital invested: ${{ portfolio.capital_invested }}</div>
      <div class="card">Portfolio value: ${{ portfolio.portfolio_value }}</div>
      <div class="card">Total PnL: ${{ portfolio.total_pnl }}</div>
      <div class="card">ROI %: {{ portfolio.roi_pct }}</div>
    </div>

    <div class="tokens">
      <h2>Top Tokens</h2>
      <table>
        <thead><tr><th>Symbol</th><th>Name</th><th>Score</th><th>Risk</th><th>Classification</th></tr></thead>
        <tbody>
        {% for t in tokens %}
          <tr>
            <td>{{ t['symbol'] }}</td>
            <td>{{ t['name'] }}</td>
            <td>{{ t.get('opportunity_score') }}</td>
            <td>{{ t.get('risk_score') }}</td>
            <td>{{ t.get('classification') }}</td>
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
    metrics = {"tokens scanned": len(all_tokens), "watchlist": sum(x.get("classification") == "WATCH" for x in tokens), "strong watch": sum(x.get("classification") == "STRONG_WATCH" for x in tokens), "candidates": sum(x.get("classification") == "CANDIDATE" for x in tokens)}
    portfolio = scanner.store.paper_stats()
    # expose portfolio fields conveniently to template
    class P: pass
    p = P()
    p.capital_initial = portfolio.get('capital_initial')
    p.cash = portfolio.get('cash')
    p.capital_invested = portfolio.get('capital_invested')
    p.portfolio_value = portfolio.get('portfolio_value')
    p.total_pnl = portfolio.get('total_pnl')
    p.roi_pct = portfolio.get('roi_pct')
    return render_template_string(PAGE, tokens=tokens[:100], metrics=metrics, portfolio=p)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "mode": "DRY_RUN" if scanner.store else "unknown", "trading_enabled": settings.trading_enabled})

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
    # return scanner debug info; never include secrets
    return jsonify(scanner.store.get_debug())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
