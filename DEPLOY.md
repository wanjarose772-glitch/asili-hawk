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

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# other terminal
cd frontend
npm install && npm run dev
```

Open http://localhost:5173
