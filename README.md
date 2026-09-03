# Solana Microcap Bot V3

Scanner + paper portfolio + optional live executor for Solana microcaps. The strategy is deliberately selective and keeps a small moonbag after partial exits so a rare extreme winner can remain exposed to 20x/50x/100x. Those outcomes are not predictable or guaranteed; microcaps can go to zero.

## Default mode

The repository ships **safe by default**:

- `DRY_RUN=true`
- `TRADING_ENABLED=false`
- no wallet secret is included
- paper capital: $10
- max paper/live position: $1
- max simultaneous positions: 3

The scanner discovers tokens through DexScreener profiles/boosts and explicitly refreshes any open paper/live positions so exit logic can continue even if the token falls out of discovery feeds.

## V3 live architecture

`scanner -> risk/security/momentum/asymmetry -> CANDIDATE -> second live gate -> Jupiter Swap API V2 -> dedicated bot wallet`

The live executor uses Jupiter's `/swap/v2/order` + `/swap/v2/execute` flow. It refuses routes above `MAX_PRICE_IMPACT_PCT`, preserves `MIN_SOL_RESERVE`, applies a 24h per-token cooldown, and never opens more than `MAX_OPEN_POSITIONS`.

Live entry additionally requires the CANDIDATE to meet `LIVE_MIN_ASYMMETRY_SCORE` and `LIVE_MIN_MOMENTUM_SCORE`.

Exit behavior: 50% of original token amount at 2x, 20% at 5x, 15% at 10x, leaving ~15% as moonbag unless risk/exit rules force a complete exit. Critical risk, extreme sell pressure, a severe drawdown from a profitable peak, or failed momentum can close the remainder.

## Live activation (do not commit secrets)

Create a **separate Solana wallet only for this bot**. Never use a main wallet. Put only the amount you are prepared to lose in it.

Add these as secret environment variables in Render:

- `JUPITER_API_KEY`
- `SOLANA_PRIVATE_KEY_B58`

Then live mode requires all three deliberate switches:

- `DRY_RUN=false`
- `TRADING_ENABLED=true`
- `LIVE_TRADING_ACK=I_ACCEPT_REAL_LOSS_RISK`

If one is missing, the app fails closed instead of trading.

Never paste the private key into GitHub, README, logs, issues, or chat.

## Endpoints

- `/` dashboard
- `/health`
- `/api/debug`
- `/api/candidates`
- `/api/watchlist`
- `/api/paper-trades`
- `/api/stats`
- `/api/live-status`
- `/api/live-trades`

## Render Free limitation

`render.yaml` intentionally remains on `plan: free`. The worker and web server run in the same web service so they share SQLite. A free Render web service can sleep/restart and its local filesystem is ephemeral. Therefore V3 can execute live swaps when awake, but **free Render cannot guarantee uninterrupted overnight monitoring or persistent SQLite history**. Do not rely on it for guaranteed 24/7 execution.

## Tests

```bash
pip install -r requirements.txt
pytest -q
```
