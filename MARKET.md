# ASILI HAWK — Market-ready (v2.6)

## Product
Private Solana early-token intelligence + paper learning journal.

## Core loop
1. Discover (Pump + Dex fallback)
2. Score (risk, runner, volume_watch, ladder)
3. Focus board for operator attention
4. Auto paper-journal eligible names
5. Resolve 2x / 5x / -50% / 6h
6. Export `/api/journal/export` for GitHub backup

## Deploy
- Render: set `DB_PATH=/var/data/hawk_snapshots.db` if disk attached
- Free tier: export journal daily to GitHub/local JSON

## APIs
- GET /api/health — version + journal summary
- GET /api/focus — operator board
- POST /api/journal/auto-tick — force paper cycle
- GET /api/journal/learning — hit rates
- GET /api/journal/export — full backup JSON

## Not included
- Live trading / wallet execution
- Guaranteed alpha
