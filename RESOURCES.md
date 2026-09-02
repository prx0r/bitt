# Bitt Resources — Bittensor-Native Intelligence

## Architecture

```
Oracle → Research → Hydra
                    │
    ┌───────────────┼───────────────┐
    │               │               │
    ▼               ▼               ▼
 allocator      miners         registry
 TAO/subnets    SN60/61/62     projects
```

## Canonical Sources

| Source | Role | Priority |
|--------|------|----------|
| Bittensor SDK/btcli | Chain interface | P0 |
| Subtensor | Ultimate truth | P0 |
| TAOStats API | Historical data, 156 endpoints | P0 |
| Taoswap API | Trading data, public | P0 |
| dTAOscan | Signed subnet data | P0 |
| Binance | BTC/ETH/TAO 5m candles | P0 |

## Data Hierarchy

```
Direct chain → TAOStats → dTAOscan → derived
Never: AlphaGap says X → save X
Always: block N → chain price = X → TAOStats = X → dTAOscan = X
```

## Regime Labels

```
R0: pre-dTAO
R1: early dTAO
R2: TAO-flow emissions
R3: net-TAO-flow
R4: price-driven emissions
R5: price-driven + emission gate
R6: Root Reborn curated baskets
```

## Subnet Targets

| Subnet | Match | Lab Adapter |
|--------|-------|-------------|
| SN60 BitSec | Security agents | security-01 |
| SN61 RedTeam | Dockerized challenges | CG technique |
| SN62 Ridges | Coding agent | WorkerKit |
| SN88 Investing | Portfolio management | strategy → allocation |
| SN11 TrajectoryRL | Skill production | learned skill |
| SN74 Gittensor | Autonomous dev | later target |

## API Inventory

| API | Access | Use |
|-----|--------|-----|
| TAOStats | API key | Historical data, 156 endpoints |
| Taoswap | Public read | Trading, portfolios |
| dTAOscan | Keyless 10/min | Signed subnet data |
| Binance | Public | BTC/ETH/TAO 5m candles |
| TAO.app | Mix free/paid | OHLC, holders, social |

## Factor Zoo (start with 1, expand to 18)

1. Cross-sectional momentum (7d)
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
