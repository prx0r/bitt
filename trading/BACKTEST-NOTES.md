# Backtest Notes — What Works, What Doesn't, How To Proceed

**Date:** 2026-09-03
**Data:** 10 subnets, 2,531 5m timestamps (Jul 30 - Sep 3)

## What Works

### 1. Support Bounce (+2.48%, 39% win rate)
- Buy subnets near their 20-day low
- Edge: mean reversion in calm markets
- Best with 5 positions
- **Why it works:** Subnets near support have limited downside + positive drift

### 2. Child Composite (+1.72%, 35% win rate)
- Combine: low vol (40%) + momentum (30%) + support (30%)
- Best with 5 positions
- **Why it works:** Multiple uncorrelated signals reduce noise

### 3. Low Volatility (+1.11%, 30% win rate)
- Buy calmest subnets
- Best with 5 positions
- **Why it works:** Calm = stable = predictable drift

### 4. Anti-Volatility (+0.80%, 37% win rate)
- Squared low vol (penalizes extreme vol heavily)
- Best with 10 positions
- **Why it works:** Avoids the worst volatility traps

## What Doesn't Work

### 1. Pure Momentum (-5.86%)
- Buying recent winners destroys value
- **Why it fails:** Momentum reverses in this market

### 2. Pure Mean Reversion (-4.27%)
- Buying oversold subnets doesn't work alone
- **Why it fails:** Needs confirmation from other signals

### 3. Squeeze Alone (0 trades)
- Too rare to generate signals
- **Why it fails:** Compression events are infrequent

## Key Parameters

| Parameter | Optimal | Range Tested |
|-----------|---------|--------------|
| Positions | 5 | 3, 5, 10 |
| Rebalance | 24h | — |
| Hold period | 7d | — |
| Stop loss | None | -1% to -20% |
| Score threshold | 0.2 | 0.1 to 0.5 |

## Research Foundation

Based on 28 papers reviewed:

1. **Maymin (2026)**: AMM size premium — small subnets earn ~1%/day mechanically
2. **Pyo & Jang (2026)**: Low-vol anomaly confirmed in crypto (432 coins, 2018-2025)
3. **Batista & Fernandes (2026)**: Upside vol ≠ downside vol — separate them
4. **Corsi HAR-RV**: Forecast vol, don't just use historical
5. **Moreira & Muir (2017)**: Volatility-managed portfolios improve Sharpe
6. **Cederburg (2020)**: WARNING — vol management fails OOS in equities

## Recommended Backtest Procedure

### P0: Establish if low-vol is real
1. Expand to ALL subnets (129) with 5m data
2. Walk-forward cross-sectional IC (no random train/test)
3. Low-vs-high quintile with exact AMM slippage
4. Control for pool size, liquidity, price, age, TAO return
5. Leave-one-out: does result die if we exclude SN84?

### P1: Improve volatility definition
6. Upside vs downside semivolatility
7. HAR-RV forecast (1h + 6h + 24h + 7d components)
8. Two-state HMM: CALM/WILD posterior probability
9. Trade P(CALM tomorrow) not vol_7d

### P2: Bittensor mechanics
10. Reproduce Maymin SMB (size premium)
11. Pool depth / reserve / price-impact factors
12. Slippage-adjusted capacity at 0.1/1/10/50/100 TAO

### P3: Combinations
13. Low downside-vol + positive trend
14. Low forecast-vol + high active ratio
15. Support bounce × calm regime

### P4: Anti-overfit
16. Frozen monthly model versions
17. One-bar execution delay
18. Walk-forward with embargo
19. Deflated Sharpe + PBO

## What We Built (Reusable Pipeline)

```
trading/
├── engine/
│   ├── decision_engine.py      — CP4 opportunity ranking
│   ├── live_allocator.py       — Thompson sampling allocation
│   ├── backtester_v2.py        — Point-in-time testing
│   ├── incubator.py            — Birth-to-now analysis
│   ├── subnet_intelligence.py  — Classify any subnet
│   ├── signals.py              — 8 factor functions
│   └── sn88_submitter.py       — SN88 strategy generator
├── strategies/
│   ├── low_vol_alpha.json
│   ├── low_vol_active.json
│   ├── anti_yield_trap.json
│   ├── distributed_value.json
│   └── established_quality.json
├── experiments/
│   ├── full_backtest_results.json
│   ├── factor_ic_analysis.json
│   ├── child_subnet_analysis.json
│   └── calm_strategy_backtest.json
└── imports/
    └── *.md (14 strategy emails)
```

## Next Steps

1. **P0**: Expand backtest to 129 subnets with 5m data
2. **P0**: Implement HAR-RV forecast volatility
3. **P1**: Upside vs downside semivolatility
4. **P2**: Maymin SMB reproduction
5. **P3**: Build ensemble (low vol + trend + support)
6. **P4**: Walk-forward validation with embargo
