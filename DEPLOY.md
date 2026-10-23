# Deploy ASILI HAWK to the cloud (24/7 access)

You do **not** need to keep your laptop on. Once deployed, open the URL from any phone or computer.

## Option A — Railway (easiest, free tier available)

1. Create a free account at https://railway.app
2. Push this project to a GitHub repo (or use Railway’s “Deploy from local”)
3. **New Project → Deploy from GitHub** → select the repo
4. Railway should pick up `Dockerfile` or `nixpacks.toml` automatically.
   - If it asks for commands:
     - **Build**: `cd backend && pip install -r requirements.txt && cd ../frontend && npm ci && npm run build`
     - **Start**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Open **Settings → Networking → Generate Domain**
6. Done. Bookmark `https://your-app.up.railway.app`

Before exposing the service publicly, configure these variables in the host:

```text
ENVIRONMENT=production
OPERATOR_API_TOKEN=<a long random secret stored only in the host>
CORS_ORIGINS=https://your-app.up.railway.app
```

Manual journal writes require the `X-Operator-Token` header outside development.
The dashboard hides its manual journal buttons when the server reports writes
disabled; never put the operator token in frontend/Vite configuration. For
same-origin hosting, dashboard requests need no CORS exception, but keep CORS
restricted to the deployed origin for any other browser clients.

The same container serves:
- Dashboard UI at `/`
- Live API at `/api/hawk`, `/api/stats`, `/api/health`

## Option B — Render

1. https://render.com → New → Web Service
2. Connect the GitHub repo
3. Runtime: Docker (uses the included `Dockerfile`)
4. Create Web Service → free tier is fine for this load

## Option C — Fly.io

```bash
fly launch
fly deploy
```

Uses the same Dockerfile.

## After deploy

- Dashboard auto-refreshes every ~28 seconds
- No API keys required for core Pump.fun + DexScreener discovery
- Optional later: add `BIRDEYE_API_KEY` / `HELIUS_API_KEY` in the host’s environment variables for deeper intel

## Local test before deploy

Use Node.js 20.19+ (or 22.12+) for the current Vite toolchain. Install exactly
from the lockfile with `npm ci` so local and deployed builds match.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# other terminal
cd frontend
npm ci && npm run dev
```

Open http://localhost:5173

Local development defaults to `ENVIRONMENT=development`, where journal controls
are enabled. A green `/api/health` only means the app process is running; it does
not certify upstream data freshness or signal quality. Do not treat this build
as market-ready until upstream outage/freshness telemetry, durable production
storage, and a labeled historical backtest have been validated using collected
real-market data.
