# Bitt Trading — Vision

## The Thesis

Bittensor becomes one closed economic loop:

```
mine / validate / earn TAO or alpha
  → oracle observes entire subnet economy
  → portfolio policy allocates capital
  → staking generates yield
  → rewards re-enter treasury
  → policy rebalances
  → every decision becomes another labeled learning run
```

## The Currency: TAO NAV

USD can be displayed, but the agent wins if:

```
ending_TAO_after_all_exit_costs > benchmark_TAO
```

This prevents an alpha strategy from looking clever merely because TAO itself went up in dollars.

## What We're Building

A **Bittensor Capital Lab** that:
1. Holds TAO as baseline
2. Observes 128+ subnets via oracle
3. Allocates based on fundamentals (yield/price, emission, quality)
4. Takes profits in TAO
5. Every decision becomes a labeled learning run

## The Competitive Landscape

| Project | What It Does | Our Edge |
|---------|-------------|----------|
| AlphaGap | 20+ signals, top-10 index | We have autonomous learning |
| SubnetStats | Chain data analytics | We have security analysis |
| TrustedStake | Non-custodial execution | We have CG/CGE |
| SN88 | Portfolio management | We can submit strategies |
| dtao-trader | Signal generation | We have the full loop |

Our edge: **autonomous learning**. We don't just trade — we learn which strategies work, prove it with evidence, and carry validated knowledge across domains.

## The Factor Zoo (18 signals)

1. Cross-sectional momentum
2. Spot vs moving-price divergence
3. Emission momentum (gated)
4. Carry (realizable yield)
5. Actual user flow
6. Insider flow
7. Smart-wallet consensus
8. Liquidity/capacity
9. Protocol-buy state
10. Revenue/buyback fundamentals
11. Developer activity
12. Mining quality (from oracle)
13. Deregistration risk
14. Holder cost basis
15. Event momentum
16. Mean reversion
17. Root-validator basket quality
18. Ensemble

## The Benchmark Suite

Every strategy must beat:
- Free TAO (no action)
- Root TAO (low risk)
- Equal-weight (naive diversification)
- Momentum Top-10 (dumb momentum)
- Yield Top-10 (dumb carry)
- AlphaGap-style top-10 (commercial benchmark)
- SN88 strategy (Bittensor-native benchmark)

## The Learning Loop

```
TaskInstance: "Construct dTAO portfolio at block N"
Context: canonical features available BEFORE block
WorkerVersion: strategy + parameters
BudgetEnvelope: 100 TAO, max 10 positions, max 20% per position
Decision: target weights
World: historical chain replay
Outcome: TAO NAV after 7 days, drawdown, fees, turnover
Evaluator: risk-adjusted excess return vs baselines
Hydra: record factor contribution, propose next candidate
```

## What's Next (CP1)

1. Import simst from SN88
2. Import TAOStats historical data
3. Implement 5 baselines
4. Implement 7d momentum factor
5. Run walk-forward tests
6. Compare against simst
7. Start forward paper trading

## The Flywheel

```
/bitt Oracle → observes subnet economy
  → Portfolio Agent → allocates capital
  → Mining/Trading → generates TAO
  → Treasury → re-enters portfolio
  → Policy rebalances
  → Every decision → labeled learning run
  → Hydra records what worked
  → CGE proposes improvements
  → CG evaluates on held-out data
  → Validated strategies → more TAO
```

This is the same learning loop as BitSec — just with a different domain. The architecture is universal.
