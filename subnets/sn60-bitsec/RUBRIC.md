# Bitsec SN60 — Winning Agent Rubric

## Target Performance

**Winning agent score: 83.3%**

| Metric | Value |
|--------|-------|
| Overall score | 83.3% |
| Projects passed | 15 |
| Passes | 45 |
| True positives | 254 |
| Validators | 3 |
| Runtime per project | ~13 minutes |

## What This Means

- 15 projects tested
- 3 validators per project (45 total passes)
- 254 true vulnerabilities found
- ~17 TP per project average
- ~13 minutes per project runtime

## How to Beat This

1. **Find more true positives** — aim for >254 TPs
2. **Fewer false positives** — precision matters
3. **Faster runtime** — under 13 minutes
4. **Consistent across validators** — all 3 should score similarly

## Scoring Formula

From the docs:
- True positives score points
- False positives deduct points
- Detection rate = TP / expected
- Precision = TP / (TP + FP)
- F1 = 2 * precision * recall / (precision + recall)

## Project Types

Based on the leaderboard, the test set includes:
- Code4rena audit contests (fenix-finance, superposition, etc.)
- Sherlock audit contests
- Cantina audit contests
- Custom benchmark projects

## Key Insight

The winning agent found 254 TPs across 15 projects. That's ~17 vulnerabilities per project on average. To beat it, we need to find MORE vulnerabilities with HIGHER precision.
