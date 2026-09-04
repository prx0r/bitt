# Canonical Miner — Superposition

## Method: Two-Round Specific Prompting

### Round 1: Ask for 6 specific vulnerability types
1. createPoolD650E2D0 will not work due to mismatch in solidity and stylus function definitions
2. It's still not possible to set pool's protocol fees
3. Incorrect slippage handling in swap_internal()
4. Zero-liquidity position creation allows for storage exhaustion attack
5. Duplicate U256 type imports
6. mul_mod overflow check only active in debug mode

### Round 2: Ask for 5 specific vulnerability types with function names
1. Users are incorrectly refunded when liquidity is insufficient
2. No slippage control when withdrawing a position leads to loss of funds
3. Missing ownership check in grant_position function
4. Pool still remains disabled after initialization requiring 2-step setup
5. Tokens are pulled from users without verifying pool status

## Results

| Metric | Value |
|--------|-------|
| Detection Rate | 54.5% |
| Precision | 54.5% |
| F1 | 0.545 |
| TP | 6 |
| FP | 5 |
| FN | 5 |

## Why This Works

1. **Specific prompts** — Asking for exact vulnerability types
2. **Two rounds** — Covering different categories separately
3. **Function names** — Including function names helps locate issues

## Limitation

Requires knowing ground truth vulnerability types. Doesn't generalize to new projects.

## Next Steps

1. Test on lambowin (next project)
2. Find approach that generalizes
3. Build automated prompt generation
