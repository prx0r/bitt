# HANDOVER — Next Agent Start Here

**Date:** 2026-09-03
**Session:** Full Bittensor trading infrastructure build
**Status:** Mining ready, trading edge small, data pipeline built

## What We Built (This Session)

### Core Infrastructure
| Component | Path | Status |
|-----------|------|--------|
| Daily mining scan | `mining/daily_scan.py` | LIVE — single command |
| Low fruit scanner | `trading/engine/low_fruit_scan_v2.py` | WORKS |
| Decision engine | `trading/engine/decision_engine.py` | WORKS |
| Backtester V2 | `trading/engine/backtester_v2.py` | WORKS |
| Signal library | `trading/engine/signals.py` | 8 signals defined |
| Strategy framework | `trading/engine/strategy_framework.py` | WORKS |
| SN88 submitter | `trading/engine/sn88_submitter.py` | WORKS |
| Live allocator | `trading/engine/live_allocator.py` | Thompson sampling |
| Hypothesis library | `trading/studio/hypothesis_library.py` | 24 hypotheses |
| Pipeline | `trading/studio/pipeline.py` | Hypothesis → Strategy → Test |
| Optimizer | `trading/studio/optimizer.py` | Fleece-style Thompson + CGE |

### Data
| Dataset | Location | Size |
|---------|----------|------|
| 5m OHLCV | `market.duckdb` subnet_candles | 18,473 candles, 128 subnets |
| Pool state | `market.duckdb` pool_state | 17,139 rows, 129 subnets |
| SN88 PnL | `trading/data/sn88_ochl.json` | 1.5M records, 65 miners |
| Live scan | `mining/scan_results/` | Latest chain snapshot |

### Mining Targets (Live Chain Verified)
| SN | Median TAO/day | Emitting | Top1% | Type |
|----|----------------|----------|-------|------|
| SN19 | 63.9 | 36 | 26% | BROAD |
| SN44 | 7.4 | 18 | 20% | BROAD |
| SN62 | 7.4 | 24 | 29% | SWE |
| SN4 | 6.8 | 12 | 28% | Multi-Mod |
| SN91 | 9.5 | 12 | 28% | Cascade |

## Key Findings

### Trading
- **Support bounce: +2.48%** (best single signal)
- **Child composite: +1.72%** (vol + momentum + support)
- **Low vol: +1.11%** (confirmed but smaller than claimed)
- **5 positions = sweet spot**
- **24h rebalance = optimal**
- **Edge is real but small** — holding TAO > trading

### Mining
- **Median, not average** — always (jackpots mislead)
- **Top1 > 40% = jackpot** — avoid
- **Broad distribution > high yield** — predictable income
- **Registration cost ~0.0005 TAO for ALL** — not a differentiator
- **Holding TAO > trading** for accumulation

## Commands

```bash
# Daily mining scan (live chain, ~4 min)
python3 mining/daily_scan.py

# View subnet registry
cat trading/data/subnet_registry.json | python3 -m json.tool

# Run backtester
python3 trading/engine/backtester_v2.py

# Run all hypothesis backtests
python3 trading/studio/hypothesis_library.py

# Check leaderboard
python3 trading/studio/runner.py

# Generate SN88 strategies
python3 trading/studio/sn88_generator.py

# View current allocation
cat trading/strategies/live_support_5pos.json
```

## Unfinished Threads (TODO)

### 1. x402 Endpoint for Paid Reports
- Create API that serves daily mining reports
- Charge 0.001 TAO per report via x402
- Reports: mining opportunities, rebalancing signals, subnet analysis
- Need: x402 integration, report generation, payment flow

### 2. X/Twitter Bot for Signals
- Post daily mining opportunities
- Post rebalancing signals
- Auto-generate charts from data
- Need: Twitter API, chart generation, scheduling

### 3. 60+ Report Ideas (from emails)
- Mining landscape daily
- Subnet type analysis
- Rebalancing signals
- SN88 performance tracking
- Security audit opportunities
- Child subnet prediction
- Regime detection alerts
- Whale movement tracking
- And 50+ more from the imported emails

### 4. Subnet Type Deep Dives
- Security (SN61 RedTeam) — reusable skills
- SWE (SN62 Ridges) — WorkerKit integration
- Research (SN67 Harnyx) — deep research
- Image Gen (SN19) — broadest payouts

### 5. Integration with Private Lab
- Security lab overlap with SN61
- WorkerKit/Hydra for miner optimization
- CGE for strategy evolution

## Directory Structure

```
bitt/
├── mining/
│   ├── daily_scan.py          # Single command daily scan
│   ├── MASTER_PLAN.md         # Mining strategy overview
│   ├── sn19/                  # Blockmachine (best broad)
│   ├── sn44/                  # TurboVision (most distributed)
│   ├── sn62/                  # Ridges (SWE agent)
│   ├── sn4/                   # Targon (multi-mod)
│   └── sn91/                  # Cascade
│
├── trading/
│   ├── AGENT-INTERFACE.md     # Agent navigation guide
│   ├── REBALANCING-GUIDE.md   # How to accumulate TAO
│   ├── BACKTEST-NOTES.md      # What works, what doesn't
│   ├── engine/                # All analytics modules
│   ├── studio/                # Hypothesis → Strategy → Test
│   ├── strategies/            # SN88 CSVs + live allocations
│   ├── experiments/           # Backtest results
│   └── imports/               # 15 strategy emails
│
├── reports/
│   └── LOW_HANGING_FRUIT_*.md # Corrected methodology
│
└── tooling/
    ├── opentao-trader/        # OpenTaoTrader (reference)
    ├── taoplicate/            # TAOplicate (reference)
    └── ...
```

## Extensibility

### Adding a new signal
```python
# In trading/engine/signals.py
def signal_new_factor(data):
    """Description of what this signal measures."""
    return score  # 0-100
```

### Adding a new hypothesis
```python
# In trading/studio/hypothesis_library.py
HYPOTHESIS_LIBRARY.append({
    "id": "H070",
    "claim": "What you believe",
    "factors": ["factor1", "factor2"],
    "status": "UNTESTED",
})
```

### Adding a new report
```python
# Create trading/reports/my_report.py
# Add to commands in HANDOVER.md
```

### Adding a new mining target
```bash
# Create folder structure
mkdir -p mining/sn{NETUID}
# Add DEV-PLAN.md with research + dev plan
# Run: python3 mining/daily_scan.py
```

## What's Next (Priority Order)

1. **Start mining SN19 or SN62** — immediate TAO income
2. **Run daily scans** — build historical data moat
3. **Backtest with more data** — validate edge on full universe
4. **x402 endpoint** — monetize reports
5. **X bot** — automated signals
6. **Subnet type deep dives** — security, SWE, research

## Files to Read First

1. `trading/REBALANCING-GUIDE.md` — how to accumulate TAO
2. `trading/BACKTEST-NOTES.md` — what works and why
3. `mining/MASTER_PLAN.md` — mining strategy
4. `trading/AGENT-INTERFACE.md` — agent navigation
