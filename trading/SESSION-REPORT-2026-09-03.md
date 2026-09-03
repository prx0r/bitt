# Session Report — 2026-09-03

## Summary

Built out the full Bittensor trading infrastructure from email specs:
- Imported 7 Bittensor strategy emails from Gmail
- Cloned 5 new repos (OpenTaoTrader, TAOplicate, RedTeam miner, Trail of Bits skills)
- Fixed 4 critical bugs in existing trading code
- Built TAOStats data ingestion pipeline
- Built payout depth scanner (CP0)
- Ran full backtesting on 3 strategies

## What Was Built

### 1. Data Pipeline
- `data/ingestion/taostats_full.py` — Full TAOStats ingestion (pool, subnet, metagraph)
- Auth: `Authorization: <raw_key>` (no Bearer prefix)
- Market DB: 5,968 pool rows, 4,968 subnet rows, 3,973 candles

### 2. Bug Fixes
- `trading/rebalancer.py` — Fixed inverted return calculation (candles newest-first)
- `trading/rebalancer.py` — Fixed volume column mismatch (volume -> volume_tao)
- `trading/factors.py` — Fixed fake yield_price (now documented as emission/price proxy)
- `trading/factors.py` — Fixed emission_momentum (now uses emission share, not raw level)
- `trading/replay.py` — Removed netuids[:10] limit (now scans ALL subnets)

### 3. Strategies Built
- `trading/strat_high_growth_children.py` — Allocates to new/undervalued subnets
- `trading/strat_low_competition_miner.py` — Identifies easy mining opportunities
- `trading/backtest_birth.py` — Simulates buying at subnet launch

### 4. Payout Depth Scanner (CP0)
- `mining/payout_depth_scanner.py` — Full payout depth analysis
- Scans 125 subnets, calculates HHI, Gini, topology classification

## Payout Depth Scan Results

### Top 15 Mining Opportunities (by income score)

| Rank | SN | Score | Emitters | Emit/N | Price | N>1 | HHI | Topology |
|------|-----|-------|----------|--------|-------|-----|-----|----------|
| 1 | SN5 | 37.5 | 241 | 0.2938 | 0.0128 | 24 | 0.004 | PROPORTIONAL |
| 2 | SN123 | 37.4 | 250 | 0.0615 | 0.0027 | 25 | 0.004 | PROPORTIONAL |
| 3 | SN33 | 37.1 | 242 | 0.1134 | 0.0050 | 24 | 0.004 | PROPORTIONAL |
| 4 | SN101 | 37.1 | 244 | 0.1036 | 0.0045 | 24 | 0.004 | PROPORTIONAL |
| 5 | SN83 | 37.0 | 231 | 0.2253 | 0.0098 | 23 | 0.004 | PROPORTIONAL |
| 6 | SN13 | 36.9 | 239 | 0.1357 | 0.0059 | 23 | 0.004 | PROPORTIONAL |
| 7 | SN50 | 36.9 | 238 | 0.1274 | 0.0055 | 23 | 0.004 | PROPORTIONAL |
| 8 | SN32 | 36.6 | 232 | 0.0739 | 0.0032 | 23 | 0.004 | PROPORTIONAL |
| 9 | SN45 | 36.3 | 229 | 0.0612 | 0.0027 | 22 | 0.004 | PROPORTIONAL |
| 10 | SN79 | 35.9 | 210 | 0.1512 | 0.0066 | 21 | 0.005 | PROPORTIONAL |
| 11 | SN105 | 35.5 | 203 | 0.1638 | 0.0071 | 20 | 0.005 | PROPORTIONAL |
| 12 | SN53 | 33.7 | 152 | 0.6734 | 0.0292 | 15 | 0.007 | PROPORTIONAL |
| 13 | SN34 | 31.6 | 133 | 0.2800 | 0.0121 | 13 | 0.007 | PROPORTIONAL |
| 14 | SN88 | 31.2 | 132 | 0.0890 | 0.0039 | 13 | 0.008 | PROPORTIONAL |
| 15 | SN67 | 30.7 | 128 | 0.1284 | 0.0056 | 12 | 0.008 | PROPORTIONAL |

### Topology Distribution
- WINNER_TAKE_ALL: 63 subnets (avoid)
- PROPORTIONAL: 29 subnets (good for mining)
- TOP_K: 2 subnets (selective)
- UNKNOWN: 31 subnets (research needed)

## Repos Cloned

| Repo | Location | Purpose |
|------|----------|---------|
| RyanMercier/OpenTaoTrader | tooling/opentao-trader | AMM execution, backtester |
| TidalWavesNode/TAOplicate | tooling/taoplicate | Smart-wallet tracking |
| RedTeamSubnet/miner | subnets/sn61-redteam-miner | SN61 mining |
| trailofbits/skills | reference/trailofbits-skills | Security audit primitives |
| EnvCommons/BountyBench | reference/bountybench | Bug bounty benchmarks |

## Key Findings

1. **SN5, SN123, SN33** are top mining opportunities with proportional payouts
2. **63 subnets are winner-take-all** — avoid for recurring mining income
3. **SN67 (Harnyx) at #15** — confirmed good opportunity (241 emitters, score 30.7)
4. **TAOStats API** — auth is raw key in Authorization header, no prefix
5. **129 subnets** currently active on chain

## Next Steps (from email specs)

- [ ] CP1: Epoch history persistence + seat half-life calculation
- [ ] CP2: Mechanism classifier (auto-clone repos, label payout topology)
- [ ] CP3: Local benchmark adapters (Harnyx, Ridges, RedTeam)
- [ ] CP4: Opportunity decision engine
- [ ] CP5: Build subnet instance registry
- [ ] CP6: Lifecycle Atlas (age-bucket returns, survival curves)
