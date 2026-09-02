# Bitsec SN60 API — Agent Reference

All endpoints return JSON. Base URL: `http://localhost:8402`

## Endpoints

### GET /api/bitsec
Overview: chain + economics + competition + tools + submissions in one call.
```json
{
  "subnet": "Bitsec (SN60)",
  "block": 8971620,
  "chain": { "burn_tao": 0.0005, "tempo": 360, "alpha_price": 0.005397, "neuron_count": 256, "miner_count": 246, "emitting_count": 2 },
  "economics": { "total_tao_day": 31.87, "contestable_miner_tao_day": 7.97, "miner_tao_day": 7.97, "validator_tao_day": 23.90 },
  "competition": { "hhi": 0.5, "effective_earners": 2.0, "top_emitters": [...] },
  "our_submissions": [],
  "tools": { "slither": {"installed": true}, "mythril": {"installed": true}, ... }
}
```

### GET /api/bitsec/subnet
Full chain data including weights, bonds, hyperparameters, identity.

### GET /api/bitsec/competition
What it takes to earn:
```json
{
  "contestable_miner_tao_day": 7.97,
  "champion": { "uid": 46, "incentive": 0.5, "tao_day": 7.97 },
  "fifth_place": { "uid": null, "incentive": 0, "tao_day": 0 },
  "analysis": {
    "enter_above_incentive": 0,
    "daily_income_if_paid_usd": 0,
    "cost_to_enter_tao": 0.0005,
    "cost_to_enter_usd": 0.12
  }
}
```

### GET /api/bitsec/submissions
Our submission history (SQLite-backed, grows as we submit).

### GET /api/bitsec/tools
Available analysis tools and their status.

### GET /api/bitsec/leaderboard
Current leaderboard with UID, incentive, TAO/day, hotkey, weight detail.

### GET /api/bitsec/experiments
CGE experiment results (grows as we run experiments).

## Agent Usage

```python
import http.client, json

def query_bitsec(endpoint):
    conn = http.client.HTTPSConnection("localhost", 8402)
    conn.request("GET", f"/api/bitsec{endpoint}")
    return json.loads(conn.getresponse().read())

# Get everything
data = query_bitsec("")

# Just competition
comp = query_bitsec("/competition")

# Just leaderboard
lb = query_bitsec("/leaderboard")
```

## Dashboard

Open `dashboard/bitsec.html` in browser for visual monitoring.
