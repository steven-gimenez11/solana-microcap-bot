from flask import Flask, jsonify, render_template_string
from scanner import Scanner
scanner, app = Scanner(), Flask(__name__)
PAGE = '''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Solana Microcap Scanner</title><style>body{margin:0;background:#101418;color:#e8edf2;font:15px system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:24px}header{display:flex;justify-content:space-between;border-bottom:1px solid #35404a;padding-bottom:18px}h1{font-size:clamp(22px,5vw,40px)}.status{color:#57d39b}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:22px 0}.metric{background:#192128;border:1px solid #303d47;padding:16px}.metric b{display:block;font-size:25px;margin-top:8px}.token{border-top:1px solid #35404a;padding:16px 0}.danger{color:#ff9d8d}@media(max-width:600px){main{padding:16px}header{display:block}}</style><main><header><div><h1>SOLANA MICROCAP SCANNER</h1><span class="status">● ACTIVE</span> MODE: DRY RUN</div><a href="/api/scan" style="color:#75c9ff">API</a></header><div class="grid">{% for k,v in metrics.items() %}<div class="metric">{{k}}<b>{{v}}</b></div>{% endfor %}</div><h2>Watchlist y candidatos</h2>{% for t in tokens %}<section class="token"><b>{{t.symbol}}</b> · {{t.classification}} · Opportunity {{t.opportunity_score|default(0)}} · Risk {{t.risk_score|default(0)}}<br>MC ${{"%.0f"|format(t.market_cap)}} · Liquidity ${{"%.0f"|format(t.liquidity_usd)}} · Volume ${{"%.0f"|format(t.volume_24h)}} · Age {{t.age_hours}}h<br><span class="danger">{{t.risk_flags|join(', ') or 'No flags'}}</span> · <a href="{{t.dexscreener_url}}" target="_blank">DexScreener</a><br><small>{{t.address}}</small></section>{% else %}<p>No hay snapshots todavía. Ejecuta el worker para iniciar.</p>{% endfor %}</main>'''
@app.get("/")
def index():
    all_tokens = scanner.store.latest(); tokens = [x for x in all_tokens if x.get("classification") in {"WATCH","STRONG_WATCH","CANDIDATE"}]
    metrics = {"tokens scanned":len(all_tokens),"watchlist":sum(x.get("classification")=="WATCH" for x in tokens),"strong watch":sum(x.get("classification")=="STRONG_WATCH" for x in tokens),"candidates":sum(x.get("classification")=="CANDIDATE" for x in tokens),"paper positions":len(scanner.store.paper_trades())}
    return render_template_string(PAGE, tokens=tokens[:100], metrics=metrics)
@app.get("/health")
def health(): return jsonify({"status":"ok","mode":"DRY_RUN","trading_enabled":False})
@app.get("/api/scan")
def api_scan(): return jsonify(scanner.scan())
@app.get("/api/candidates")
def candidates(): return jsonify(scanner.store.latest("CANDIDATE"))
@app.get("/api/watchlist")
def watchlist(): return jsonify([x for x in scanner.store.latest() if x.get("classification") in {"WATCH","STRONG_WATCH"}])
@app.get("/api/paper-trades")
def paper_trades(): return jsonify(scanner.store.paper_trades())
@app.get("/api/stats")
def stats(): return jsonify(scanner.store.paper_stats())
if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)