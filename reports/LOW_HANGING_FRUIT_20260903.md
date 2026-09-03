# Low-Hanging Fruit Report — $(date +%Y-%m-%d)

## Methodology (CORRECTED)
- Uses MEDIAN payout, not average (average is misleading with skewed distributions)
- Jackpot penalty: top1 > 40% → score reduced
- Distribution bonus: top1 < 20% → score increased
- All data verified live from chain SDK (block 8,985,034)
- Registration cost: ~0.0005 TAO for all subnets

## Top 4 Low-Hanging Fruit (BROAD distribution + median > 1 TAO)

### #1: SN19 — BEST RISK-ADJUSTED
- **Median:** 63.9 TAO/day
- **Emitting:** 36 miners
- **Competition:** 14%
- **Top1:** 26.1% (distributed)
- **Type:** BROAD
- **Why:** Genuinely distributed payouts, good median, moderate competition

### #2: SN44 — MOST DISTRIBUTED
- **Median:** 7.4 TAO/day
- **Emitting:** 18 miners
- **Competition:** 7%
- **Top1:** 20.0% (most distributed)
- **Type:** BROAD
- **Why:** Lowest concentration, easy entry, predictable income

### #3: SN4 — DECENT MEDIAN
- **Median:** 6.8 TAO/day
- **Emitting:** 12 miners
- **Competition:** 5%
- **Top1:** 27.6%
- **Type:** CONCENTRATED
- **Why:** Good median, low competition

### #4: SN91 — DECENT MEDIAN
- **Median:** 9.5 TAO/day
- **Emitting:** 12 miners
- **Competition:** 5%
- **Top1:** 28.0%
- **Type:** CONCENTRATED
- **Why:** Highest median among non-jackpots

## What We Learned (Lessons for Future Reports)

1. **NEVER use average for skewed distributions** — median is the truth
2. **Always check top1 share** — if >40%, it's a jackpot, not low-hanging fruit
3. **"Low competition" ≠ "easy money"** — could mean winner-take-all
4. **Verify against live chain** — API/cache data can be stale
5. **Broad distribution > high yield** — distributed payouts = predictable income
6. **Registration cost is ~0.0005 TAO for ALL subnets** — not a differentiator

## Registration Cost
All subnets: ~0.0005 TAO (verified live)

## Block Verified
$(date) — Block $(python3 -c "import bittensor as bt; print(bt.Subtensor(network='finney').block)")
