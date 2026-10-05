# ASILI HAWK — Operator playbook (how we get to alpha surface)

## 1. Record outcomes (required)

### In the UI (after v2.1 deploy)
On each Focus card:
- **Log skip** — saw it, did not buy (still valuable data)
- **Log watch** — researching, no size
- **Log micro** — you took a micro position

### Record result later (API or next UI)
When you know what happened (hours later):

```powershell
# List recent journal rows to get id
Invoke-RestMethod "http://127.0.0.1:8000/api/journal?limit=20"

# Set outcome on an entry id
$body = @{ outcome = "rug"; exit_mcap = 3000; notes = "dead in 20m" } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/api/journal/ENTRY_ID/outcome" -Body $body -ContentType "application/json"
```

Outcomes: `rug` | `flat` | `loss` | `win_2x` | `win_5x` | `win_10x` | `unknown`

### Or use a Google Sheet (works even before deploy)
Columns: time, ticker, mint, action, display_score, conv, rug, entry_mcap, exit_mcap, outcome

**Target:** 50 rows with outcomes before we retune weights.

## 2. Serial deployer vs "serial rugger"

| Signal | Meaning |
|--------|---------|
| **Serial deployer** | Same creator pubkey, many mints (Hawk store) |
| **Journal high death rate** | Your logs show most of their tokens rug/loss |
| **True "rugger" proof** | Needs on-chain dump patterns + history we don't fully have yet |

Hawk will show **SERIAL DEPLOYER** and **journal death rate** when data exists.
Never treat mint-count alone as courtroom proof — treat as **risk elevation**.

## 3. Your daily job (help the system learn)

1. Open **Focus only**
2. For every name you look at: Log skip / watch / micro
3. Same day or next: tag outcome on entries
4. Never size All-noise or pure AVOID
5. After 50 outcomes: tell CTO → weight calibration pass

## 4. World-class alpha surface (definition we use)

Focus names with outcomes **beat random early entries** on your journal.
Not marketing. Not 0 PRIME days alone.
