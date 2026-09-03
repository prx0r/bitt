# /bitt — Bittensor Trading Infrastructure

## Quick Start

```bash
# Run low fruit scan (30 seconds)
python3 trading/engine/low_fruit_scan_v2.py

# Run backtester
python3 trading/engine/backtester_v2.py

# Start steady data collection
python3 data/ingestion/steady_collector.py

# Run decision engine
python3 trading/engine/decision_engine.py
```

## Architecture

```
bitt/
├── data/
│   ├── ingestion/           # Data collectors
│   │   ├── chain_collector.py      # SDK-based (fast, rate-limited)
│   │   ├── steady_collector.py     # Slow but reliable (daemon mode)
│   │   ├── taostats_full.py        # TAOStats API pipeline
│   │   └── taostats_backfill.py    # Historical backfill
│   └── lifecycle/
│       └── instance_registry.py    # Subnet instance tracking
│
├── trading/
│   ├── engine/              # Core analytics
│   │   ├── low_fruit_scan_v2.py    # Daily opportunity scan
│   │   ├── decision_engine.py      # MINE/BUY/HOLD ranking
│   │   ├── backtester_v2.py        # Point-in-time backtesting
│   │   ├── incubator.py            # Birth-to-now analysis
│   │   └── snapshot_persistence.py # Historical storage (the moat)
│   ├── strategies/
│   │   ├── strat_high_growth_children.py
│   │   └── strat_low_competition_miner.py
│   ├── research/
│   │   └── lifecycle_atlas.py      # Age-cohort analysis
│   ├── experiments/                # Results, manifests
│   └── imports/                    # Strategy emails
│
├── mining/
│   ├── payout_depth_scanner.py     # Seat analysis
│   ├── three_view_payout.py        # Settled/spot/realizable
│   ├── mechanism_classifier.py     # Auto-label payout topology
│   ├── benchmark_adapters.py       # Harnyx/Ridges/RedTeam
│   └── mine_vs_buy.py              # Cost comparison
│
└── market.duckdb                   # All data lives here
```

## Data Tables

| Table | What | Update Freq |
|-------|------|-------------|
| `metagraph_snapshot` | Per-neuron per-block | Every 3s (SDK) |
| `subnet_metrics_live` | Per-subnet metrics | Every 3s |
| `pool_state` | Price, reserves, liquidity | TAOStats hourly |
| `subnet_state` | Emission, miners, validators | TAOStats hourly |
| `daily_subnet_scan` | Low fruit scores (append-only) | Daily |
| `daily_scan_log` | Scan metadata | Daily |

## Key Metrics

### Low Fruit Score (0-100)
- **Easiness** (35%): participation breadth, competition density
- **Yield** (25%): emission per neuron
- **Stability** (20%): volatility, validator count, active ratio
- **Access** (10%): registration cost, open slots
- **Stickiness** (10%): will this still pay in 30 days?

### Subnet Classification
- **BLUECHIP**: high price, established, stable
- **GROWTH**: high momentum, expanding
- **VALUE**: high yield, low price, overlooked (the low fruit)
- **DYING**: declining, low activity
- **MOONSHOT**: high risk, high reward

### Three-View Payout
1. **settled_alpha_day**: protocol-native, price-insensitive
2. **spot_marked_tao_day**: alpha * spot_price
3. **realizable_tao_day**: after slippage

## Top Findings

| Finding | Value |
|---------|-------|
| SN90 | 0.0005 TAO reg, 92 TAO/day, 159 open slots |
| SN47 | 0.05 TAO reg, 17 TAO/day, 127 open slots |
| SN62 | Best mining target (SWE agent, low competition) |
| SN107 | Highest EV mining (330 TAO/neuron) |
| Momentum strategy | -85% (doesn't work) |
| Equal weight | -7% (barely works) |

## The Moat

Every daily scan adds to `daily_subnet_scan` (append-only). After:
- **30 days**: pattern recognition on what predicts winners
- **90 days**: statistical significance on factors
- **365 days**: unique dataset nobody else has

## External References

- [TAOStats API](https://docs.taostats.io)
- [Bittensor SDK](https://www.bittensor.com/docs/sdk)
- [Subnet Pools](https://www.bittensor.com/docs/concepts/staking-pools)
- [Emissions](https://www.bittensor.com/docs/concepts/emissions)
