# SN19 — Blockmachine (RPC Marketplace)

## Live Chain Data (Block 8,985,034)
- **Median payout:** 63.9 TAO/day
- **Emitting:** 36 miners
- **Competition:** 14%
- **Top1:** 26.1% (BROAD)
- **Reg cost:** ~0.0005 TAO
- **Type:** RPC MARKETPLACE (not image generation)

## Why This is Low-Hanging Fruit
- Highest median payout among broad subnets
- 36 miners earning regularly — not winner-take-all
- Top1 only 26% — genuinely distributed
- Infrastructure provider = consistent demand

## Dev Plan
1. ✅ Research: Read subnet docs, understand mechanism
2. ✅ Clone: Cloned miner repo from taostat/blockmachine-miner
3. ✅ Build: Created pricing optimizer using bitsec pattern
4. ⬜ Test: Run local evaluation
5. ⬜ Register: 0.0005 TAO
6. ⬜ Deploy: Submit RPC node
7. ⬜ Iterate: Improve based on validator feedback

## Current Status
- Miner built: `mining/sn19/miner.py`
- Pattern: Pricing optimization using free inference APIs
- Next: Test against real subnet challenges

## Resources
- [Imported email](../../imports/SN19 Blockmachine — Autonomous Winning Miner Agent Guide.md)
- Repo: https://github.com/taostat/blockmachine-miner
- Docs: https://blockmachine.io/whitepaper
