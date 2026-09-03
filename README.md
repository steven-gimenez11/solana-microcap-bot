# Solana Microcap Bot

Scanner selectivo de microcaps nuevas de Solana, orientado a investigación en **DRY-RUN**. Usa DexScreener, guarda snapshots en SQLite, calcula oportunidad y riesgo por separado, y simula posiciones de $1 sin wallet, claves ni transacciones.

## Seguridad y alcance
- `DRY_RUN=true` y `TRADING_ENABLED=false` son obligatorios por defecto.
- No existe módulo de ejecución real, firma, conexión a wallet ni manejo de private keys/seed phrases.
- Las métricas de seguridad que DexScreener no expone se marcan `UNKNOWN`; no se interpretan como seguras.
- Los scores son heurísticos de investigación y no garantizan beneficios ni un 10x/50x/100x.

## Ejecutar
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```
El dashboard queda en `http://localhost:5000`. Para un scan continuo, ejecutar en otro proceso: `python worker.py`.

## Render
Subir el repositorio a GitHub, elegir **New > Blueprint** en Render y conectar el repositorio. Render busca exactamente `render.yaml` en la raíz de la rama seleccionada; no `render.yami` ni otro nombre. El Blueprint crea el Web Service y el Background Worker, instala `requirements.txt` y ejecuta `gunicorn app:app`/`python worker.py`. Si ya se creó el servicio manualmente, eliminarlo o crear el Blueprint desde el Dashboard. Usar disco persistente si se desea conservar SQLite entre reinicios.

## API y tests
`GET /`, `/health`, `/api/scan`, `/api/candidates`, `/api/watchlist`, `/api/paper-trades`, `/api/stats`.
Ejecutar tests con `pytest -q`.