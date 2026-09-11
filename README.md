# 🦅 ASILI HAWK

**Early memecoin intelligence** — find high-potential tokens while they are still on the Pump.fun bonding curve, before they graduate and hit mainstream terminals.

## Vision

Catch the next Cashcat / Jimonthy / Pepe / Bonk **before** the bonding curve is complete.

## What it does

- Scans **Pump.fun** for tokens still on the bonding curve (`complete: false`)
- Estimates curve progress and prioritizes the early / sweet-spot zone
- Enriches with DexScreener price, volume, liquidity when available
- Scores every candidate with an Alpha engine tuned for *pre-terminal* edge
- Serves a live dark dashboard that auto-refreshes every ~28s

## Quick start (local)

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (another terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

API: http://localhost:8000/api/hawk

## Deploy to the cloud (Railway — recommended)

This project is set up so the **dashboard stays online 24/7** without your laptop.

### 1. Push to GitHub

```bash
cd asili-hawk
git init
git add .
git commit -m "ASILI HAWK v0.3"
# create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USER/asili-hawk.git
git push -u origin main
```

### 2. Deploy on Railway

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Select the `asili-hawk` repo
3. Railway will detect the config. Set the **Root Directory** to `/` (repo root)
4. Add a service with:
   - **Build command**:  
     `cd backend && pip install -r requirements.txt && cd ../frontend && npm install && npm run build`
   - **Start command**:  
     `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Generate a public domain under Settings → Networking

Your dashboard will be live at `https://your-app.up.railway.app`

### Alternative: Render / Fly.io

Same idea — build frontend into `frontend/dist`, then run the FastAPI app which serves both `/api/*` and the SPA.

## API

| Endpoint        | Description                          |
|-----------------|--------------------------------------|
| `GET /api/health` | Status                               |
| `GET /api/hawk`   | Ranked early opportunities           |
| `GET /api/stats`  | Counts (on-curve, prime, high)       |
| `GET /api/intel`  | Alias of hawk results (compat)       |

## Environment (optional)

Create `backend/.env` if you later add paid keys:

```
BIRDEYE_API_KEY=
HELIUS_API_KEY=
SOLANA_TRACKER_KEY=
```

Core discovery currently works with **public** Pump.fun + DexScreener endpoints (no key required).

## Project layout

```
asili-hawk/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI + static SPA
│   │   ├── config.py
│   │   ├── discovery/           # Pump.fun + DexScreener
│   │   ├── scoring/             # Alpha engine
│   │   └── services/            # Hawk orchestration
│   ├── requirements.txt
│   └── Procfile
├── frontend/                    # React + Vite + Tailwind
└── railway.json
```

## Disclaimer

Not financial advice. Memecoins are extremely high risk. This tool is for research and intelligence only.
