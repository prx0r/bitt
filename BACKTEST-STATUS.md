# Backtest Status — Why We Can't Backtest Yet

## What We Have

| Data Source | Records | Coverage |
|-------------|---------|----------|
| oracle.db | 31 scans, 3999 records | ~1 day (Sep 1-2) |
| market.duckdb | 4138 subnet records, 500 macro candles | ~1 day |
| TAOStats API | 129 subnets with alpha prices | Live snapshot |
| Binance | 500 BTC/ETH/TAO 5m candles | ~41 hours |

## What We Need for Backtesting

| Requirement | Current | Needed |
|-------------|---------|--------|
| Historical subnet data | 31 scans (~1 day) | Weeks/months of 5m data |
| Alpha price history | 1 snapshot | Continuous 5m OHLCV |
| Emission history | 1 snapshot | Daily/hourly emissions |
| BTC/ETH context | 41 hours | Months of 5m data |
| Regime labels | 1 data point | Time-series of regimes |

## Why We Can't Backtest Yet

**The core problem:** We have ~1 day of data. Backtesting requires historical data over weeks/months.

**Specific blockers:**
1. **No alpha price history** — TAOStats gives us current price, not historical
2. **No emission history** — Only current emission snapshot
3. **No momentum data** — Need 288+ records (24h of 5m data) for momentum calculations
4. **No regime history** — Need time-series of BTC/ETH/TAO to detect regime changes
5. **Walk-forward impossible** — Can't split 1 day into train/test

**What would fix this:**
- TAOStats historical API (if available)
- Archive node access (wss://archive.chain.opentensor.ai)
- Wait for our oracle to accumulate more scans (30 min intervals)
- Use simst from SN88 (has historical dTAO data from March 2025)

**The honest answer:** We have 1 day of data. We can test the infrastructure, but we can't do a meaningful backtest yet. The system works — it just needs more data to learn from.
