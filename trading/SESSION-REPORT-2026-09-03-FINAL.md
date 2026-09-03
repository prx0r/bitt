# Session Report — 2026-09-03 (Final)

## Architecture Built

```
data/
  ingestion/
    taostats_full.py          — TAOStats data pipeline (auth: raw key)
    taostats_backfill.py      — Rate-limited backfill with retry
  lifecycle/
    instance_registry.py      — Subnet instance tracking

trading/
  engine/
    decision_engine.py        — CP4: opportunity ranking
  features/                   — (ready for factor research)
  research/
    lifecycle_atlas.py        — Age-cohort analysis
  strategies/
    strat_high_growth_children.py
    strat_low_competition_miner.py
  backtest_birth.py           — Birth price action
  rebalancer.py               — FIXED: inverted returns, volume column
  factors.py                  — FIXED: emission momentum, yield proxy
  replay.py                   — FIXED: removed netuids[:10] limit
  BACKTEST-2026-09-03.md      — Full backtest log

mining/
  payout_depth_scanner.py     — CP0: 125 subnets scanned
  mechanism_classifier.py     — CP2: SN61=DECAY, SN62=TOP_K, SN67=BROAD
  benchmark_adapters.py       — CP3: Harnyx/Ridges/RedTeam adapters

trading/experiments/
  payout_depth_scan.json      — Full scan results
  decision_engine.json        — CP4 output
  full_scan.json              — Combined scoring
  mechanism_classifier.json   — Topology labels
  benchmarks/results.json     — Adapter test results
```

## Live Results (latest scan)

### Decision Engine (CP4) — Top Mining Opportunities

| Rank | SN | EV (7d) | P(win) | Emitters | Emit/N | Competition |
|------|-----|---------|--------|----------|--------|-------------|
| 1 | SN107 | +1621.2 | 70% | 1 | 330.9 | 1.0% |
| 2 | SN95 | +1307.6 | 70% | 1 | 266.9 | 0.4% |
| 3 | SN44 | +1105.2 | 70% | 1 | 225.6 | 0.4% |
| 4 | SN0 | +493.1 | 70% | 24 | 100.7 | 37.5% |
| 5 | SN90 | +454.4 | 70% | 2 | 92.8 | 2.1% |
| 6 | SN9 | +431.9 | 70% | 2 | 88.2 | 0.8% |
| 7 | SN110 | +391.5 | 70% | 1 | 79.9 | 0.4% |
| 8 | SN120 | +380.3 | 70% | 4 | 77.6 | 1.6% |
| 9 | SN68 | +380.3 | 70% | 1 | 77.6 | 1.6% |
| 10 | SN70 | +331.2 | 70% | 1 | 67.6 | 20.0% |

### Full Scan Summary

- **125 subnets** scanned
- **124 actionable** (score > 30)
- **102 MINE** opportunities
- **22 BUY** opportunities  
- **1 HOLD** (baseline)

### Top 5 by Combined Score

| SN | Action | Score | Emitters | Emit/N | Competition |
|----|--------|-------|----------|--------|-------------|
| SN1 | MINE | 70 | 4 | 11.0 | 1.6% |
| SN3 | MINE | 70 | 5 | 32.8 | 1.9% |
| SN4 | MINE | 70 | 6 | 55.5 | 2.3% |
| SN9 | MINE | 70 | 2 | 88.2 | 0.8% |
| SN10 | MINE | 70 | 2 | 20.2 | 0.8% |

### Mechanism Classification

| Subnet | Topology | Source |
|--------|----------|--------|
| SN67 Harnyx | BROAD_PARTICIPATION | Repo scan |
| SN62 Ridges | TOP_K | Repo scan |
| SN61 RedTeam | DECAYING_PORTFOLIO | Repo scan |

### Payout Depth (top 5)

| SN | Score | N>1 | HHI | Topology |
|----|-------|-----|-----|----------|
| SN5 | 37.5 | 24 | 0.004 | PROPORTIONAL |
| SN123 | 37.4 | 25 | 0.004 | PROPORTIONAL |
| SN33 | 37.1 | 24 | 0.004 | PROPORTIONAL |
| SN101 | 37.1 | 24 | 0.004 | PROPORTIONAL |
| SN83 | 37.0 | 23 | 0.004 | PROPORTIONAL |

## Known Issues

1. **TAOStats rate limits** — ~10 subnets per burst, backfill running slowly
2. **Pool history** — needs more backfill for lifecycle atlas
3. **Benchmark adapters** — setup OK, eval needs Docker + provider keys
4. **Decision engine** — EV model is simplified, needs real execution cost modeling

## Next Steps

- [ ] CP5: Walk-forward factor research (Spearman IC, hit rate)
- [ ] CP6: Production scanner daemon (hourly refresh)
- [ ] Wire up OpenTaoTrader execution for paper trading
- [ ] Set up Docker for Harnyx local eval
- [ ] Build real AMM execution model
