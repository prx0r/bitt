# Mining Master Plan — Low-Hanging Fruit

**Date:** 2026-09-03
**Methodology:** Live chain SDK data, median payouts, jackpot penalty

## The Honest Picture

### What Works
- **Mining beats trading** for TAO accumulation
- **Broad distribution** > high yield (predictable income)
- **Registration cost** is ~0.0005 TAO for ALL subnets (not a differentiator)
- **Holding TAO** is probably the smartest base strategy

### What Doesn't Work
- Trading strategies are weak (~2-3% on small samples)
- High yield subnets are jackpots (top1 > 40%)
- "Low competition" can mean winner-take-all
- Average payout is misleading — always use median

## Top 5 Targets (Ranked by Risk-Adjusted Return)

### #1: SN19 — Blockmachine (Image Generation)
- **Median:** 63.9 TAO/day
- **Emitting:** 36 miners
- **Competition:** 14%
- **Top1:** 26.1% (BROAD)
- **Reg cost:** ~0.0005 TAO
- **Dev plan:** mining/sn19/DEV-PLAN.md

### #2: SN44 — TurboVision
- **Median:** 7.4 TAO/day
- **Emitting:** 18 miners
- **Competition:** 7%
- **Top1:** 20.0% (MOST DISTRIBUTED)
- **Dev plan:** mining/sn44/DEV-PLAN.md

### #3: SN62 — Ridges (SWE Agent)
- **Median:** 7.4 TAO/day
- **Emitting:** 24 miners
- **Competition:** 9%
- **Top1:** 29.0%
- **Dev plan:** mining/sn62/DEV-PLAN.md
- **Why strategic:** Skills reusable across bounties

### #4: SN4 — Targon (Multi-Modality)
- **Median:** 6.8 TAO/day
- **Emitting:** 12 miners
- **Competition:** 5%
- **Dev plan:** mining/sn4/DEV-PLAN.md

### #5: SN91 — Cascade
- **Median:** 9.5 TAO/day
- **Emitting:** 12 miners
- **Competition:** 5%
- **Dev plan:** mining/sn91/DEV-PLAN.md

## Commands

```bash
# Daily mining scan (live chain)
python3 mining/daily_scan.py

# View all opportunities
cat trading/data/subnet_registry.json | python3 -m json.tool

# Check specific subnet
python3 -c "import bittensor as bt; mg=bt.Subtensor(network='finney').at(bt.Subtensor(network='finney').block).subnets.metagraph(19); print(f'SN19: {sum(1 for n in mg.neurons if n.active)} active')"
```

## Key Learnings for Future Reports

1. **Median, not average** — always
2. **Check top1 share** — >40% = jackpot
3. **Live chain verification** — never trust cached data
4. **Broad distribution > high yield** — predictable income
5. **Registration cost is same for all** — not a differentiator
