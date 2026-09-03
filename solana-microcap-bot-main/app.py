from flask import Flask, jsonify, render_template_string
from scanner import Scanner
from config import settings

scanner, app = Scanner(), Flask(__name__)

PAGE = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solana Microcap Scanner V2</title><style>
body{margin:0;background:#101418;color:#e8edf2;font:15px/1.4 system-ui}.wrap{padding:20px}h1,h2{margin:0 0 10px}.sub{opacity:.72;margin-bottom:16px}
.metrics{display:flex;gap:12px;flex-wrap:wrap}.card{background:#0f1720;padding:12px;border-radius:8px;min-width:150px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:7px;border-bottom:1px solid #25313b;text-align:left}.tokens{margin-top:20px;overflow-x:auto}.ok{color:#6ee7b7}.warn{color:#fbbf24}</style></head><body><div class="wrap">
<h1>Solana Microcap Scanner V2</h1><div class="sub"><span class="ok">● ACTIVE</span> · DRY RUN · búsqueda asimétrica, no garantía de 100x</div>
<div class="metrics"><div class="card">Tokens: {{m.scanned}}</div><div class="card">Watch: {{m.watch}}</div><div class="card">Strong: {{m.strong}}</div><div class="card">Candidates: {{m.candidates}}</div></div>
<h2 style="margin-top:20px">Paper Portfolio</h2><div class="metrics">
<div class="card">Capital: ${{p.capital_initial}}</div><div class="card">Cash: ${{p.cash}}</div><div class="card">Invertido: ${{p.capital_invested}}</div><div class="card">Valor: ${{p.portfolio_value}}</div><div class="card">PnL: ${{p.total_pnl}}</div><div class="card">ROI: {{p.roi_pct}}%</div><div class="card">Posiciones: {{p.open_positions}}/{{maxpos}}</div></div>
<div class="tokens"><h2>Top Tokens</h2><table><thead><tr><th>Symbol</th><th>MC</th><th>Liq</th><th>Vol24h</th><th>Opp</th><th>Risk</th><th>Security</th><th>Momentum</th><th>Asym</th><th>Class</th><th>Flags</th></tr></thead><tbody>
{% for t in tokens %}<tr><td>{{t.symbol}}</td><td>${{ '%.0f'|format(t.market_cap or 0) }}</td><td>${{ '%.0f'|format(t.liquidity_usd or 0) }}</td><td>${{ '%.0f'|format(t.volume_24h or 0) }}</td><td>{{t.opportunity_score}}</td><td>{{t.risk_score}}</td><td>{{t.security_score}}</td><td>{{(t.momentum or {}).get('momentum_score')}}</td><td>{{t.upside_asymmetry_score}}</td><td>{{t.classification}}</td><td>{{(t.risk_flags or [])|join(', ')}}</td></tr>{% endfor %}</tbody></table></div>
<div class="tokens"><h2>Paper Trades</h2><table><thead><tr><th>Symbol</th><th>Status</th><th>Entry</th><th>Current</th><th>Multiple</th><th>PnL%</th><th>Peak%</th><th>Exit</th></tr></thead><tbody>
{% for t in trades %}<tr><td>{{t.symbol}}</td><td>{{t.status}}</td><td>{{t.entry_price}}</td><td>{{t.current_price}}</td><td>{{t.multiple}}x</td><td>{{t.current_return_pct}}</td><td>{{t.maximum_gain_pct}}</td><td>{{t.why_exited or '-'}}</td></tr>{% endfor %}</tbody></table></div>
</div></body></html>'''


@app.get("/")
def index():
    all_tokens = scanner.store.latest()
    tokens = [x for x in all_tokens if x.get("classification") in {"WATCH", "STRONG_WATCH", "CANDIDATE"}]
    tokens.sort(key=lambda x: (x.get("classification") == "CANDIDATE", x.get("opportunity_score") or 0), reverse=True)
    metrics = type("M", (), {
        "scanned": len(all_tokens), "watch": sum(x.get("classification") == "WATCH" for x in tokens),
        "strong": sum(x.get("classification") == "STRONG_WATCH" for x in tokens),
        "candidates": sum(x.get("classification") == "CANDIDATE" for x in tokens),
    })()
    portfolio = type("P", (), scanner.store.paper_stats())()
    return render_template_string(PAGE, tokens=tokens[:100], m=metrics, p=portfolio, trades=scanner.store.paper_trades()[:50], maxpos=settings.max_open_positions)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "mode": "DRY_RUN", "trading_enabled": settings.trading_enabled})


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
