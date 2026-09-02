# SN88 Integration — How It All Connects

## The RL Loop for Bitt WorkerKit

```
State:     market data at time t (from chain)
Action:    portfolio allocation (HOLD_TAO or ALLOCATE X% to SN Y)
Reward:    TAO NAV after N periods
Agent:     Thompson Pool Allocator (from Fleece)
Environment: historical chain replay (simst)
Learning:  which allocations work → promote/reject
```

This is exactly what the directive described:
> "the backtesting environment becomes the RL loop for our workerkit"

## SN88's Granular Data

From simst's `ochl.col`:
```
uid, hotkey, date, netuid,
block_open, block_high, block_low, block_close,
price_open, price_high, price_low, price_close,
alpha_open, alpha_high, alpha_low, alpha_close,
value_open, value_high, value_low, value_close,
swap_open, swap_high, swap_low, swap_close
```

**Block-level OHLCV for every subnet.** That's the granular data we need.

## Can We Simultaneously Submit to SN88 and Trade Live?

**Yes.** The strategy format is identical:

```
# SN88 strategy file (alpha.csv)
uid,date,time,block,init,fund,strat,notes
1,2025-03-20,00:00:01,5165832,1,1000,{1:0.27, 2:0.15, 4:0.21, 19:0.16, 41:0.16},diversified

# Our SHADOW mode decision
{
  "action": "ALLOCATE",
  "netuid": 64,
  "target_weight": 0.20,
  "strategy_version": "momentum-v3"
}
```

Same allocation dict. Same rebalancing. The difference:
- SN88: their validators score our strategy
- Live: we execute the same allocation on our own wallet

## How Fleece Maps to Bitt

| Fleece Component | Bitt Equivalent |
|-----------------|-----------------|
| Fish (7 strategies) | Subnet strategies (yield, momentum, flow) |
| Pools (5 per school) | Capability pools |
| Shark genome | Portfolio allocation genome |
| School | Subnet strategy family |
| League | Strategy competition |
| Graveyard | Failed strategies preserved |
| Orca | CGE (proposes mutations) |
| Thompson Pool | Bayesian allocation across subnets |
| Regime detection | Market regime (bull/bear/sideways) |

## The Key Insight

The backtesting environment IS the RL loop. Every decision is a labeled learning run:

```
MarketFrame(t)
  → features
  → setup detection
  → rebalance decision (HOLD or ALLOCATE)
  → outcome at t+1h, t+4h, t+24h, t+72h
  → label: was this decision good?
  → CGE proposes improvement
  → CG evaluates on held-out data
  → promote/reject
```

And we can simultaneously:
1. Backtest using simst (historical)
2. Paper trade using SHADOW mode (current)
3. Submit to SN88 (external evaluation)
4. Eventually trade live

All using the same strategy, same allocation logic, same learning loop.
