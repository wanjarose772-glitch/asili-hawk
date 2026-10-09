# ASILI HAWK v2.4.0-aie-merge — CTO delivery

## What shipped
1. **VOLUME_WATCH** — silent graduated + real volume → Focus (micro only)
2. **GeckoTerminal** new pools discovery (ported from AIE-core)
3. **Dex h1 volume/txns** enrichment for runner scoring
4. **Smart-money / distribution** signal from Helius holders (AIE-inspired)
5. Dual Pump discovery + Focus/journal operator loop (prior)

## Deploy
Push this tree to asili-hawk main (Render). Confirm version `2.4.0-aie-merge`.

## Operator rules
- VOLUME_WATCH / attention_watch → research or micro only
- RUNNER_CANDIDATE with chat → higher priority
- Log journal on production; add Render disk for DB_PATH persistence

## Not yet (next)
- Full AIE wallet graph / curated smart wallets
- Birdeye paid pipelines
- Redis cross-restart memory
