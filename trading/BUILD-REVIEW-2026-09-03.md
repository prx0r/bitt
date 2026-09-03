# Build Review — 2026-09-03T02:45+07:00

## Honest Status

### What's Actually Wired Up
| Component | Status | Data Flow |
|-----------|--------|-----------|
| oracle.db snapshots | LIVE | chain scanner → oracle.db (129 subnets, latest block) |
| market.duckdb pool_state | PARTIAL | TAOStats API → market.duckdb (15,968 rows, Jul 23 - Sep 3) |
| market.duckdb subnet_state | PARTIAL | TAOStats API → market.duckdb (4,968 rows, Jul 23 - Sep 3) |
| market.duckdb candles | PARTIAL | chain scanner → market.duckdb (3,973 rows, Sep 1-3) |
| decision_engine.py | WORKS | reads oracle.db + market.duckdb → JSON output |
| payout_depth_scanner.py | WORKS | reads oracle.db → JSON output |
| strat_high_growth_children.py | WORKS | reads oracle.db → signals |
| strat_low_competition_miner.py | WORKS | reads oracle.db → signals |
| backtest_birth.py | WORKS | reads oracle.db + market.duckdb → results |
| TAOStats ingestion | RATE-LIMITED | ~10 subnets per burst, backfill slow |

### What's NOT Wired Up
- No daily scan daemon (manual runs only)
- No historical storage of scan results (each run overwrites)
- No backtesting against TAOStats historical data
- No real AMM execution model
- No live paper trading loop
- Benchmark adapters need Docker for local eval
- Lifecycle atlas has no meaningful data yet

### Data Gaps
- **pool_state**: only 12 days of hourly data (need months)
- **subnet_state**: only 12 days (need months)
- **epoch_history**: 2 subnets (need all 129)
- **subnet_instances**: 10 (need all 129)
- **No TAOStats OHLCV** (candles are chain-scanner only, 2 days)

### What Backtesting Actually Showed
- **27-hour backtest** (oracle.db only): Yield-focused strategy +1.3%, Hold TAO +0.0%
- **Birth backtest** (market.duckdb): 127 trades, 1-day avg -0.14%, 51.2% win rate
- **Decision engine**: SN107 top MINE (EV +1621 TAO/7d) — but this is from a SINGLE snapshot, not backtested

### Key Insight From Imports
The 7 imported emails describe a COMPLETE system. What we built today is ~20% of CP0-CP4. The real value is:
1. **Subnet Incubator** — track subnets from birth, predict appreciation
2. **Low Fruit Scan** — daily scan for low-competition high-reward opportunities
3. **Historical moat** — every scan stored, building unique dataset

## What Needs To Happen Today

### 1. Subnet Incubator Flow
- Ingest ALL subnet history from TAOStats (birth to now)
- Calculate birth-price, age, fundamental trajectory
- Build prediction model: which birth characteristics predict appreciation
- Backtest: if we bought at birth, what returns?

### 2. Low Fruit Scan (Daily)
- Scan all 129 subnets every day
- Score: competition × reward × infrastructure quality
- Store results with timestamp → building historical moat
- NOT "avoid winner-take-all" — weight everything

### 3. Historical Data Pipeline
- Backfill TAOStats pool/subnet history for all subnets
- Store scan results in append-only table
- Each scan = one row per subnet per day
- This IS the moat — nobody else has this

## Architecture For Daily Scan

```
DAILY CRON (or manual trigger)
    │
    ├─ 1. Fetch live chain state → oracle.db
    ├─ 2. Fetch TAOStats pool/subnet history → market.duckdb  
    ├─ 3. Run payout depth scan → scoring
    ├─ 4. Run decision engine → action list
    ├─ 5. Store scan results → daily_snapshots table (append-only)
    └─ 6. Compare to yesterday → delta alerts
```

## The Moat

Every daily scan adds to a growing dataset:
- `daily_subnet_scores` — (date, netuid, competition_score, reward_score, total_score, topology, ...)
- `daily_opportunities` — (date, action, netuid, ev, confidence, reasons, ...)
- `birth_predictions` — (netuid, birth_date, predicted_trajectory, actual_trajectory, ...)

After 30 days: pattern recognition on what predicts winners.
After 90 days: statistical significance on factors.
After 365 days: unique dataset nobody else has.
