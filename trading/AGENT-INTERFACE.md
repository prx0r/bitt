# /bitt Trading Studio — Agent Interface

## What This Is

A Bittensor trading research studio where agents can:
- Create hypotheses about market behavior
- Turn them into machine-readable strategies
- Backtest against historical 5m data
- Optimize via Fleece-style evolution
- Log everything immutably

## Quick Start for Agents

```python
from trading.studio.pipeline import Pipeline, Hypothesis, Strategy
from trading.studio.hypothesis_library import HYPOTHESIS_LIBRARY, FACTORS

# 1. Create a hypothesis
h = Hypothesis(
    claim="Low volatility subnets outperform",
    factors=[FACTORS["vol_7d"]],
    horizon="1d",
)

# 2. Compile to strategy
pipeline = Pipeline(Path("/root/bitt/trading/studio"))
strategy = pipeline.compile_strategy(h, [FACTORS["vol_7d"]])

# 3. Test (calls backtester)
result = pipeline.run_test(strategy, "2026-07-30", "2026-09-03")

# 4. Decide
decision = pipeline.evaluate_and_decide(result)
# Returns: "PROMOTE", "ARCHIVE", or "REJECT"
```

## Directory Structure

```
trading/
├── studio/
│   ├── pipeline.py           # Hypothesis → Strategy → Test
│   ├── hypothesis_library.py # 24 hypotheses from emails
│   ├── optimizer.py          # Fleece-style Thompson + CGE
│   ├── runner.py             # Immutable experiment logging
│   ├── hypotheses/           # 24 hypothesis JSONs
│   ├── compiled/             # Compiled strategy JSONs
│   ├── results/              # Test results (immutable)
│   ├── graveyard/            # Failed experiments
│   ├── leaderboard.json      # Strategy rankings
│   └── optimizer_state.json  # Thompson state
├── engine/
│   ├── backtester_v2.py      # Core backtester
│   ├── signals.py            # Factor functions
│   └── sn88_submitter.py     # SN88 format
├── strategies/
│   ├── sn88_*.csv            # SN88 submissions
│   └── live_*.json           # Live allocations
└── BACKTEST-NOTES.md         # What works, what doesn't
```

## Available Signals (from research)

| Signal | IC | Source | Status |
|--------|-----|--------|--------|
| vol_7d | -0.170 | Factor analysis | TESTED |
| support_20d | +3.89% edge | Factor analysis | TESTED |
| child_composite | +1.72% | Combined | TESTED |
| emit_per (anti-yield) | -0.129 | Factor analysis | TESTED |
| hhi_emit (distributed) | -0.101 | Factor analysis | TESTED |
| active_ratio | +0.053 | Factor analysis | TESTED |
| price_level | +0.080 | Factor analysis | TESTED |
| upside_vol | — | Batista 2026 | UNTESTED |
| har_forecast | — | Corsi HAR-RV | UNTESTED |
| hmm_prob_calm | — | Huang regime | UNTESTED |
| whale_inflow | — | WSI 97th pctile | UNTESTED |
| stake_velocity | — | OpenTaoTrader | UNTESTED |
| pair_spread | — | PMR pairs | UNTESTED |
| momentum_7d | — | Fieberg CTREND | UNTESTED |
| inverse_vol_sizing | — | Moreira/Muir | UNTESTED |

## Commands

```bash
# Run backtest (all hypotheses)
python3 trading/studio/run_all_hypotheses.py

# Run single hypothesis
python3 trading/studio/pipeline.py

# Check leaderboard
python3 trading/studio/runner.py

# Generate SN88 strategies
python3 trading/studio/sn88_generator.py

# View results
cat trading/studio/leaderboard.json | python3 -m json.tool
```

## Data Available

- **5m OHLCV**: 18,473 candles, 128 subnets, Jul 30 - Sep 3
- **Pool state**: 17,139 rows, 129 subnets
- **SN88 PnL**: 1.5M records, 65 miners
- **Factor ICs**: 7 factors tested
- **Hypotheses**: 24 cataloged, 7 tested, 17 untested

## Key Findings

1. **5 positions = sweet spot** (not 3, not 10)
2. **Support bounce** is the strongest single signal (+2.48%)
3. **Child composite** combines signals effectively (+1.72%)
4. **Low vol** is real but smaller than claimed (+1.11%)
5. **Momentum kills** (-5.86%) — don't chase winners
6. **All strategies beat baseline** (-0.18%)
