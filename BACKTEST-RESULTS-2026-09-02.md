# Backtest Results — 2026-09-02

## Data
- Source: oracle.db (chain scanner snapshots)
- Period: 27 hours (2026-09-01 08:37 to 2026-09-02 11:00)
- Subnets: 128
- Initial: 100 TAO

## Strategies Tested

| Strategy | Return | Max Drawdown | Positions | Description |
|----------|--------|--------------|-----------|-------------|
| Yield Focused | +1.3% | 1.3% | 37 | Top 5 by emission/price ratio |
| Hold TAO | +0.0% | 0.0% | 0 | Baseline (100% cash) |
| Momentum Top 5 | -0.5% | 5.3% | 22 | Top 5 by price momentum |
| Diversified 10 | -2.2% | 2.4% | 10 | Equal weight top 10 |
| Equal Weight Top 5 | -3.1% | 3.4% | 5 | Equal weight top 5 |

## Key Findings

1. **Yield Focused wins** — selecting subnets by emission/price ratio (+1.3%)
2. **Diversification hurts** in this short period — more positions = more drag
3. **Momentum is noisy** — 27 hours is too short for momentum signals
4. **Hold TAO is competitive** — market was slightly down overall

## Top Subnets by Return (27h)

| Subnet | Return |
|--------|--------|
| SN91 | +14.8% |
| SN38 | +14.6% |
| SN84 | +11.4% |
| SN117 | +11.0% |
| SN100 | +6.2% |

## Bottom Subnets

| Subnet | Return |
|--------|--------|
| SN60 | -9.0% |
| SN31 | -9.2% |
| SN92 | -9.4% |
| SN47 | -14.1% |
| SN103 | -20.6% |

## SN88 Strategies (from alpha.csv)

| Strategy | Description |
|----------|-------------|
| 1 | All in SN1 (100% in subnet 1) |
| 2 | Ease in (gradual entry over 8 days) |
| 3 | Rotate through top subnets |
| 4 | Diversified (5 subnets + cash buffer) |
| 5 | All cash (baseline) |

## What's Missing

1. **More historical data** — 27 hours is insufficient for robust backtesting
2. **Pool state (TAO/alpha reserves)** — needed for proper slippage modeling
3. **Emission history** — needed for yield calculations
4. **Transaction costs** — not modeled yet
5. **Rebalancing costs** — not modeled yet

## Next Steps

1. Get more historical data (need TAOStats or chain archive)
2. Implement proper pool swap simulation
3. Add transaction costs
4. Test over longer periods
5. Compare against SN88 winning strategies
