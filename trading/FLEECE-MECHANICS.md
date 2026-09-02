# Fleece Mechanics — What's Cool for Bitt Trading

## What Fleece Is

DeltaTuna 🐟 — Evolving options capital allocation using swarm intelligence + options + honest measurement. A league of allocation "schools" competes on standardized market scenarios.

## The 5 Coolest Mechanics

### 1. Thompson Pool Allocator (Bayesian Bandit)

```python
# For each fish (strategy), posterior over win probability:
# Beta(alpha = alpha0 + wins, beta = beta0 + trades - wins)
# Sample each fish's rate from its posterior
# Weight allocation by sampled_rate × tanh(pnl_factor)
```

**Why it's cool:** Fresh exploration comes free — fish with few observations have wide posteriors and get sampled high. As counts grow, sampling concentrates on true winners. Principled explore/exploit replacing hand-tuned weights.

**For bitt:** Each subnet is a "fish". Thompson sampling decides how much TAO to allocate to each subnet based on historical performance. No manual weight tuning.

### 2. School League (Swarm Evolution)

```
Fish (7 fixed strategies)
  └─ 5 Pools per school
      └─ Shark genome routes capital by regime
          └─ SCHOOL = shark + pools
              └─ LEAGUE of 12 schools
                  ├─ ranked on hash-locked scenarios
                  ├─ bottom 20% → graveyard (tombstones, never deleted)
                  └─ capital allocated by rank
```

**Why it's cool:** Multiple strategies compete. Losers go to graveyard (history is evidence). Winners get more capital. The league evolves over generations.

**For bitt:** Each subnet strategy is a "school". Schools compete. Best get more TAO allocation. Losers get less. Graveyard remembers what failed.

### 3. Orca Meta-Controller

```python
# Reads HydraDB as its brain
# Proposes experiments, schools, reallocation
# Generator, never judge
# Deterministic priors always work without LLM
```

**Why it's cool:** The system learns from its own graph memory. Orca reads what worked, what failed, and proposes next moves. No manual strategy design.

**For bitt:** Orca reads which subnets performed well, proposes rebalancing, learns from mistakes.

### 4. Regime Detection

```python
# VIX-proxy × trend contexts
# Bull/bear/quiet_range/high_vol/mixed
# Hashed into world_id
```

**Why it's cool:** The system adapts to market regimes. Different strategies work in different regimes. The system detects which regime it's in and adjusts.

**For bitt:** Detect if Bittensor is in bull/bear/sideways. Adjust allocation accordingly.

### 5. Graveyard (Evidence, Not Deletion)

```python
# Bottom 20% → graveyard
# Tombstones, never deleted
# History is evidence
```

**Why it's cool:** Failed strategies are preserved as evidence. The system learns from failures. Graveyard entries inform future admissions.

**For bitt:** When a subnet strategy fails, it goes to graveyard. The system learns not to repeat it.

## How to Port to Bitt

| Fleece Component | Bitt Equivalent |
|-----------------|-----------------|
| Fish (7 option strategies) | Subnet strategies (yield, momentum, flow, etc.) |
| Pools (5 per school) | Capability pools (security, trading, mining) |
| Shark genome | Portfolio allocation genome |
| School | Subnet strategy family |
| League | Strategy competition |
| Graveyard | Failed strategies preserved |
| Orca | CGE (proposes mutations) |
| Thompson Pool | Bayesian allocation across subnets |
| Regime detection | Market regime (bull/bear/sideways) |
| HydraDB | Same (already have it) |

## Key Algorithm: Thompson Pool

```python
# For each subnet:
# posterior = Beta(alpha0 + wins, beta0 + trades - wins)
# sample from posterior
# weight = sampled_rate × tanh(pnl_factor)
# allocate capital by weight
```

This is exactly what we need for subnet allocation. No manual weights. The system learns which subnets perform best.

## What We Should Build

1. **Subnet as Fish** — each subnet strategy is a "fish" with win/loss history
2. **Thompson Allocator** — Bayesian bandit decides capital allocation
3. **Regime Detection** — detect bull/bear/sideways in Bittensor
4. **Graveyard** — failed strategies preserved as evidence
5. **Orca** — CGE reads graph, proposes rebalancing

This is the allocation layer that sits on top of our existing oracle and baselines.
