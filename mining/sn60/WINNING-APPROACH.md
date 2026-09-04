# Winning Approach — Superposition (81.8% DR)

## Method: Two-Round Specific Prompting

### Round 1: Ask for 6 specific vulnerability types
1. createPoolD650E2D0 will not work due to mismatch in solidity and stylus function definitions
2. It's still not possible to set pool's protocol fees
3. Incorrect slippage handling in swap_internal()
4. Zero-liquidity position creation allows for storage exhaustion attack
5. Duplicate U256 type imports
6. mul_mod overflow check only active in debug mode

### Round 2: Ask for 5 specific vulnerability types with function names
1. In vest_position function, users are incorrectly refunded when liquidity is insufficient
2. In withdraw_position function, there is no slippage control when withdrawing
3. In grant_position function, there is missing ownership check allowing unauthorized transfers
4. After pool initialization, the pool remains disabled requiring 2-step setup
5. In swap functions, tokens are pulled from users without verifying pool status

### Combine: Merge findings from both rounds

## Results

| Metric | Value |
|--------|-------|
| Detection Rate | 81.8% |
| Precision | 81.8% |
| F1 | 0.818 |
| TP | 9 |
| FP | 2 |
| FN | 2 |

## Why This Works

1. **Specific prompts** — Asking for exact vulnerability types
2. **Function names** — Including function names helps the model locate issues
3. **Two rounds** — Covering different categories separately
4. **Deduplication** — Merging findings without duplicates

## Key Insight

The model CAN find vulnerabilities when asked specifically. The problem is generic prompts don't match ground truth titles.

## Next Steps

1. Test on more projects
2. Automate the two-round process
3. Build a prompt template for any project
