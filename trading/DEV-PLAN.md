# Bitt Trading — Dev Plan

## CP1: Deterministic Paper Portfolio Replay

### Definition of Done:
1. Import SN88 simst
2. Import TAOStats historical pool data
3. Extend /bitt observations with economic-state fields
4. Reconstruct executable TAO return for timestamped allocations
5. Implement 5 boring baselines
6. Implement 1 factor: 7-day cross-sectional momentum
7. Run walk-forward tests
8. Compare against simst
9. Store as canonical WorkerKit/Hydra artifacts
10. Start forward paper trading

### Baselines to beat:
- Free TAO (no action)
- Root TAO (low-risk)
- Equal-weight eligible subnets
- Equal-weight liquid-20
- Emission-weighted
- 7d momentum top-N
- Yield top-N
- AlphaGap-style top-10 weekly

### Factor zoo (18 signals):
1. Cross-sectional momentum (1d/3d/7d/30d)
2. Spot vs moving-price divergence
3. Emission momentum (gated, not naive)
4. Carry (realizable yield after take)
5. Actual user flow (pool-state derived)
6. Insider flow (miner/validator/owner)
7. Smart-wallet consensus
8. Liquidity/capacity (executable quotes)
9. Protocol-buy state
10. Revenue/buyback fundamentals
11. Developer activity
12. Mining quality (from /bitt oracle)
13. Deregistration risk
14. Holder cost basis / seller exhaustion
15. Event momentum
16. Mean reversion (filtered)
17. Root-validator basket quality
18. Ensemble

### Currency: TAO NAV
- Agent wins if ending_TAO > benchmark_TAO
- USD can be displayed but not the objective
