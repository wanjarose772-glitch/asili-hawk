# Helius / Solana step-change

## What it unlocks

With `HELIUS_API_KEY` set on Render:

| Capability | Method | Effect on Hawk |
|------------|--------|----------------|
| Top holder concentration | `getTokenLargestAccounts` | top1% / top10% → rug_risk + holder_quality |
| Confidence ceiling | — | Confidence can rise above 78 when holders OK |
| PRIME gating | — | Extreme concentration can block PRIME |

Without the key, Hawk continues to work and labels holder fields `INSUFFICIENT_DATA`.

## Setup

1. Create a free key at https://dashboard.helius.dev
2. Render → your service → **Environment**
   - `HELIUS_API_KEY` = your key
3. Redeploy (or restart)

Optional later:
- `SOLANA_TRACKER_KEY` — pre-indexed pump curve/holder APIs
- `BIRDEYE_API_KEY` — broader market metrics

## Limits / honesty

- Top accounts often include **bonding-curve / pool** ATAs — ratios are directional, not pure “retail holders”
- Does **not** yet include full creator track-record indexing or smart-money PnL graphs
- Rate limits: free Helius tiers are limited; Hawk only enriches top ~12 candidates per scan

## Still needs more data for full vision

| Gap | Practical source |
|-----|------------------|
| Creator serial-rug history | Indexer of prior mints by creator + outcomes |
| Smart-money wallets | Curated wallet set + Helius tx history / third-party PnL |
| Wash trading | Full tx stream / Bitquery / custom clustering |
| Persistent velocity | Redis / DB across Render restarts |
