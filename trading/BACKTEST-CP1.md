# Backtest CP1 — What Needs Fixing

## Bugs to Fix

### 1. market.py — schema corruption
```text
Currently:
  open  = alpha_price (OK)
  close = tao_equiv_day (WRONG — this is emission, not price)

Fix:
  open  = alpha_price
  high  = alpha_price
  low   = alpha_price
  close = alpha_price
```

### 2. replay.py — accounting errors
```text
Currently:
  Mutates holding by PnL AND adds PnL to cash (double-counts)
  final_tao ignores remaining position value

Fix:
  Portfolio tracks alpha UNITS, not TAO value
  PnL = (current_price - entry_price) * units
  final_tao = cash + sum(units * current_price)
```

### 3. replay.py — SQL ordering
```text
Currently:
  GROUP BY netuid ORDER BY timestamp DESC
  Does not reliably select newest row

Fix:
  Use window function or subquery to get truly latest
```

### 4. calculate_yield_price() — backwards returns
```text
Currently:
  Candle array is newest-first
  Return loop computes older - newer (negative)

Fix:
  Reverse array before computing returns
  Or compute returns as (newer - older) / older
```

## Data to Backfill

### Priority 1: TAOStats 5m OHLCV
```text
GET /api/dtao/tradingview/udf/history
symbol=SUB-{netuid}
resolution=5
from={timestamp}
to={timestamp}
```

### Priority 2: TAOStats pool history
```text
GET /api/dtao/pool/history/v1
netuid={netuid}
frequency=by_hour
limit=500
```

### Priority 3: BTC/ETH/TAO from Binance
Already have 500 candles. Need to extend.

## Acceptance Criteria

1. replay.py produces non-zero returns on historical data
2. Portfolio tracks alpha UNITS (not fake TAO values)
3. SQL queries reliably select newest row per subnet
4. Returns are computed correctly (newer - older) / older
5. No double-counting of gains/losses
6. Walk-forward test passes on held-out data
