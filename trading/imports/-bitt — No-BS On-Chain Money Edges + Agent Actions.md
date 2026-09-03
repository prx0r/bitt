# /bitt — No-BS On-Chain Money Edges + Agent Actions

**Date:** Wed, 2 Sep 2026 18:33:00 -0700

---

# /bitt — No-BS On-Chain Money Edges + Agent Actions

Date: 3 Sep 2026

## Thesis

The strongest version of `/bitt` is not a trading bot and not a miner scanner. It is an **action allocator** for the Bittensor economy.

At every decision point it asks:

> Given our TAO, existing alpha positions, compute, API budget, WorkerVersions and hotkeys, what permitted action has the best expected TAO-denominated return after sunk costs, capital lock, slippage, fees and failure probability?

Actions include:

- HOLD_TAO
- BUY_ALPHA
- SELL_ALPHA
- MOVE_VALIDATOR
- REGISTER_MINER
- SUBMIT_MINER_ARTIFACT
- EXIT_MINER
- WAIT_FOR_BURN
- MINE_PRE_EMISSION
- ENTER_DISSOLUTION_TRADE
- LOCK_CONVICTION
- ROOT_ALLOCATE

The key advantage is that Bittensor exposes an unusually large amount of economic state on-chain: spot and moving alpha prices, pool reserves/weights, exact swap quotes, TAO flows, emissions, chain buys, miner/validator payouts, registrations, UID churn, validator weights, ownership conviction, identities, collateral and root-fund allocations.

---

# Tier 1 — I would build these now

## 1. Mine-vs-buy alpha arbitrage — strongest synthesis

This is the most interesting opportunity I found because almost nobody should naturally compare these two acquisition paths.

For every subnet compute the executable market cost of acquiring alpha:

```
market_cost_per_alpha =
    quote_stake(TAO_amount).tao_spent / alpha_received
```

Then compute the expected cost of producing the same alpha by mining:

```
true_entry_cost =
    sunk_registration_burn
  + opportunity_cost(locked_collateral)
  + setup_compute

expected_mining_cost_per_alpha =
   (true_entry_cost
    + inference/API/GPU costs
    + expected re-registration cost)
   / expected alpha earned
```

Expected alpha earned must come from the *actual payout curve*, not `emission / miner_count`:

```
expected_alpha_day =
    alpha_out_day
    * miner_pool_share
    * expected_incentive_share
```

Normally miners receive ~41% of alpha_out. If `owner_cut_enabled=false`, there is no 18% owner cut and participants receive the full alpha_out, effectively making the miner half ~50% instead of ~41% — about a 22% uplift in miner-side pool size before individual incentive weighting.

Then:

```
if mining_cost_per_alpha << market_cost_per_alpha
and survival_probability high:
    MINE
elif market_cost_per_alpha < mining_cost_per_alpha
and investment thesis positive:
    BUY
else:
    PASS
```

This turns mining into another execution venue for alpha.

This is especially attractive for artifact/algorithm subnets where expensive evaluation is done by validators and our cost is mostly offline development/API inference.

Official sources:
https://www.bittensor.com/docs/concepts/staking-pools
https://www.bittensor.com/docs/guides/mining/collateral
https://www.bittensor.com/docs/hyperparameters/owner-cut-enabled

---

## 2. Low-competition recurring miner hunter

This should remain the first mining objective: recurring, understandable alpha rather than giant winner-take-all jackpots.

The scanner should stop using active miner count as competition. Use **effective competition**.

Features:

- miner alpha pool/day
- full incentive distribution
- top1/top3/top5/top10 shares
- HHI / effective earners
- pruning cutoff incentive
- number of actually emitting miners
- registration churn
- deregistration/UID churn
- under-capacity slots
- immunity remaining
- scoring mechanism reproducibility
- local benchmark percentile
- compute/API requirements
- collateral policy
- owner-cut policy
- registration burn
- emission enabled status
- expected alpha liquidity on exit

The target profile for boring income:

```
valuable miner pool
+ wide payout distribution
+ few effective competitors
+ cheap true sunk registration cost
+ under-capacity or large safety margin above prune cutoff
+ reproducible/local benchmark
+ low ongoing compute
+ liquid enough alpha
```

The important new point is **registration cost accounting**.

Current Bittensor allows a subnet to split registration price T into:

```
burned = (1-p) * T
locked_collateral = p * T
```

The locked part is not sunk; it is alpha stake that releases as the hotkey earns emission. So a subnet showing a 1 TAO registration price with 90% collateral is economically very different from a subnet burning the whole 1 TAO.

Score:

```
true_sunk_entry = (1-p)*T
capital_lock_cost = locked_collateral * opportunity_rate * expected_lock_duration
```

Official:
https://www.bittensor.com/docs/guides/mining/collateral
https://www.bittensor.com/docs/guides/mining/burn

### Registration-timing agent

Registration burn decays continuously and jumps after successful registrations. The miner agent should never blindly register when it decides a subnet is profitable.

It should maintain:

```
EV(register now)
vs
EV(wait 1 tempo)
```

and submit with a price limit when the expected lost reward from waiting is smaller than expected burn savings.

This is cost optimization rather than alpha generation, but repeated across many miner deployments it compounds.

---

## 3. Validator yield router — low friction recurring optimization

Once we own alpha in a subnet, choosing the validator is a separate decision from owning the subnet.

Current Bittensor mechanics are unusually favorable here: **moving stake between hotkeys on the same subnet is not an AMM swap**. It does not create pool price impact or swap fee (ordinary transaction fee still applies).

So an agent can continuously compare validators using:

- realized dividends per alpha
- validator take
- historical yield stability
- validator permit/liveness
- trust
- weight-setting regularity
- stake concentration
- churn
- slashing/operational events if relevant

Then redelegate alpha from a deteriorating validator to a better one without changing subnet exposure.

This is much more attractive than cross-subnet high-frequency rotation because you aren't repeatedly paying AMM costs.

Official:
https://www.bittensor.com/docs/concepts/staking-pools
https://www.bittensor.com/docs/guides/staking

For `/bitt`, maintain two independent scores:

```
SUBNET_SCORE = should I own this alpha?
VALIDATOR_SCORE = if I own it, who should I delegate to?
```

---

## 4. High-growth-child allocator

This is the incubator thesis from the previous research.

Don't ask “which subnet is best?” Ask:

> Which subnet is becoming successful much faster than its price is repricing?

Core factor:

```
COILED_SPRING =
  stake_growth_z
+ tao_flow_acceleration_z
+ emission_growth_z
+ volume_growth_z
+ holder_growth_z
+ miner_growth_z
+ github_acceleration_z
+ usage/revenue_growth_z
- price_return_z
- valuation_premium_z
```

Normalize against subnets of similar **age, liquidity and runtime regime**.

Bittensor exposes a native EMA of net user TAO stake flow (`SubnetEmaTaoFlow`), so this is not inferred social sentiment — it is chain-recorded capital movement.

Official:
https://www.bittensor.com/docs/query/subnet-tao-flows

The main research question is not whether flows correlate with price contemporaneously. It is whether **acceleration in fundamentals while price lags** predicts excess return 7/14/30/60 days later.

---

## 5. Structural protocol-bid factor

Mature subnets can receive protocol chain buys: excess TAO emission that cannot be paired with alpha injection is swapped into subnet alpha.

This is deterministic structural demand.

Read actual chain state rather than approximate it.

Candidate factor:

```
chain_buy_pressure = daily_excess_tao / tao_pool
```

But the better factor is:

```
NET_STRUCTURAL_PRESSURE =
   protocol_chain_buy_tao_day
 - expected miner/validator/owner sell_tao_day
```

We can estimate recipient sell propensity by identifying hotkeys/coldkeys receiving emissions and measuring their post-epoch stake removals / alpha sales historically.

This distinguishes:

- subnet with 100 TAO/day of protocol buying but recipients dump 150 TAO/day
- subnet with 60 TAO/day of protocol buying and recipients mostly hold

The second may have the stronger structural floor.

Official emission mechanics:
https://www.bittensor.com/docs/concepts/emissions

Useful existing repo already cloned in `/bitt`:
`buckZz7/dtao-trader`
It already queries `SubnetExcessTao` and logs chain-buy pressure. Reuse the extraction code, but revalidate every strategy assumption against current runtime because parts of its July 2026 research predate current pool/runtime mechanics.

---

# Tier 2 — more novel / event-driven

## 6. EMA catch-up trade in young subnets

Current cross-subnet emissions use **moving alpha price**, not raw spot, and the EMA reacts slowly when a subnet is young.

That creates a potentially exploitable lag.

A newborn subnet may have:

```
spot price >> moving price
```

while flows, holders, miner demand and usage remain strong.

If demand persists, moving price mechanically catches up over time. Because moving price contributes to its emission share, the subnet can receive improving emission economics *after* the initial demand shock.

Factor:

```
ema_gap = (spot_price - moving_price) / moving_price
```

Condition it on:

- age
- persistent positive TAO flow
- holder breadth
- price not already vertical
- emission enabled
- distance to emission gate

This should be tested as an event study. It may be one of the cleanest Bittensor-native signals because generic traders tend to look at spot charts, not runtime EMA mechanics.

Official:
https://www.bittensor.com/docs/concepts/emissions

---

## 7. Emission-gate crossing

After moving-price share is adjusted for miner burn, Bittensor passes the subnet through a nonlinear emission gate.

This means a subnet near the gate midpoint can experience a disproportionate change in final emission from a relatively small change in demand/fundamentals.

Define:

```
gate_distance = log(adjusted_pre_gate_share / theta)
```

Run event studies for:

- crossing upward through theta
- crossing downward
- approaching from below with accelerating flows
- holding above despite price correction

Potential trade:

```
positive fundamentals
+ spot/moving EMA gap
+ gate_distance just below zero
→ buy before upward crossing
```

Do not assume it works. This is exactly the kind of structural hypothesis the historical engine should prove or kill.

---

## 8. Pre-emission mining / activation catalyst

New subnets register with `subnet_emission_enabled=false`.

Crucial detail: while pool-side TAO emission is disabled, `alpha_out` **still pays miners and validators**. What is disabled is TAO/alpha pool injection and excess-TAO chain buys.

So a high-quality new subnet can have a period where:

- miner competition is low
- miners still accumulate alpha
- broad capital avoids it because pool-side emissions are not enabled
- root activation is a future catalyst

Agent action:

1. Detect active subnet + emission disabled.
2. Reproduce scoring locally.
3. Estimate alpha/day available to miners.
4. Assess team/mechanism probability of root enable.
5. Mine early only when mining cost per alpha is extremely low.
6. Treat accumulated alpha as venture exposure, not recurring TAO cash flow until liquidity/catalyst proves out.

Official:
https://www.bittensor.com/docs/hyperparameters/subnet-emission-enabled

This is higher risk than our recurring miner bucket, so keep it separate.

---

## 9. Smart-wallet / smart-root-manager factor

Bittensor is unusually transparent about who stakes where.

Metagraphed exposes account-level stake flow, stake moves, registration history and subnet position history, while chain-wide endpoints rank stake flow, registrations, turnover, alpha volume and concentration.

Instead of copying whales blindly, build a **wallet skill model**.

For every economically meaningful address:

```
after each stake-add event:
    calculate 7d / 14d / 30d subnet excess return

after each stake-remove event:
    calculate avoided 7d / 14d / 30d loss
```

Then Bayesian-shrink the results so a wallet with two lucky trades doesn't rank above one with 100 good decisions.

Separate entities:

- subnet owners
- miners
- validators
- root managers
- obvious mechanical treasury wallets
- independent allocators

Only the last categories should become trading signals.

Root Reborn makes this even more interesting. Root validator allocation vectors are public (`validator-root-weights`) and the chain exposes basket holdings/NAV. We can build a Bittensor equivalent of institutional 13F tracking and test whether allocations of historically skilled root managers predict future subnet returns.

Official:
https://metagraph.sh/docs/chain-analytics
https://www.bittensor.com/docs/query/validator-root-weights

### Repo to clone: TAOplicate

`TidalWavesNode/TAOplicate`

```
git clone https://github.com/TidalWavesNode/TAOplicate.git tooling/taoplicate
```

It already has event-driven stake/unstake following over WebSocket, proportional sizing, dry-run mode, SQLite analytics and safety controls.

Do **not** use its naive copy-trading strategy. Reuse the event/execution plumbing after `/bitt` has learned which wallets actually possess predictive skill.

---

## 10. Mechanism-transition / stale-metadata edge

We already saw this with Ditto SN118: owner/repo/mechanism changed while third-party explorer metadata was stale.

Detect:

- owner changed recently
- subnet identity URL/GitHub changed
- repo changed sharply
- validator code changed scoring mechanism
- active miners suddenly reset/fall
- emissions remain high
- public aggregators still describe old mechanism

For mining, this may create a short window before competitors understand the new game.

For trading, it is effectively a corporate turnaround/reverse-merger event.

Use on-chain `identity-history` + GitHub diffing + mechanism parser.

---

# Tier 3 — rare, weird, potentially large

## 11. Dissolution liquidation arbitrage — death model is not dead

You cannot natively short arbitrary subnet alpha today, but official subnet docs reveal a stranger trade.

When a subnet dissolves, its TAO reserve is distributed pro-rata across alpha holders. The docs explicitly state that the resulting liquidation payout **can exceed the market value of the alpha at dissolution**.

So the death model can become a liquidation-arbitrage scanner rather than a short model.

For the lowest-price non-immune subnet(s):

```
expected_liquidation_tao_per_alpha
vs
exact executable alpha entry cost
```

Need to incorporate:

- protocol-owned alpha in denominator (dilutes users)
- current pool weights/accounting
- probability and timing of actual dissolution
- next subnet registration timing
- slippage entering
- risk that price/TAO reserve changes first

Only act if:

```
expected liquidation value
- entry cost
- slippage
- time/risk discount
> large safety margin
```

This is event-driven and probably rare, but it is a real protocol-specific arb hypothesis worth backtesting.

Official:
https://preview.bittensor.com/docs/guides/subnets

---

## 12. Conviction takeover / owner-cut acquisition

This is high-capital, not near-term, but economically real.

For subnets at least one year old, ownership can transfer when one hotkey's own matured conviction exceeds 18% of eligible alpha.

Ownership itself earns the subnet owner cut — normally 18% of alpha emission.

So neglected old subnets can theoretically be valued like acquisitions:

```
takeover_cost = executable cost of obtaining/locking enough alpha
owner_income = 18% of future alpha_out
```

Then compare:

```
PV(owner_income) / takeover_cost
```

The current rules deliberately made this harder: single hotkey must exceed 18%, conviction takes time to mature for challengers, and on many subnets enough alpha cannot even be bought from the pool.

But the oracle can still identify anomalously cheap ownership situations.

Official:
https://www.bittensor.com/releases/conviction-normalization
https://preview.bittensor.com/docs/guides/conviction

Treat this as an acquisition strategy, not a trading strategy.

---

## 13. Root-manager business after we prove the allocator

Root Reborn turns root validators into managed subnet baskets. Their allocation weights and basket state are public.

If `/bitt` eventually demonstrates robust out-of-sample allocation performance, the endpoint isn't merely trading our own TAO. It can become a root validator strategy and attract delegation.

Do not do this now. First build a verifiable track record.

---

# Things I would NOT spend time on yet

1. Generic high-frequency subnet trading — AMM swap fees + price impact + noise make this unattractive without a very strong edge.
2. Generic APY/yield chasing — your own 30-day test already showed yield-focused allocation underperformed.
3. Blind smart-wallet copying — many flows are operational, owner/miner related or simply late.
4. Raw active-miner-count ranking — payout concentration matters much more.
5. Raw GitHub commit count — easy to game, and quantity does not equal product progress.
6. Alpha halving front-running — deterministic and interesting, but not worth prioritizing until an event study shows an effect.
7. Copying public famous-subnet portfolios — that's exactly where our information advantage is lowest.

---

# The unified action score

Every opportunity, mining or capital allocation, should normalize to one schema:

```
OpportunityAction {
    action_type,
    netuid,
    subnet_instance_id,

    expected_tao_day,
    expected_alpha_day,
    probability_profitable,
    expected_payback_days,

    capital_at_risk_tao,
    sunk_cost_tao,
    locked_capital_tao,
    compute_cost_day,
    api_cost_day,

    entry_slippage,
    exit_slippage,
    liquidity_risk,
    pruning_risk,

    confidence,
    evidence_age,
    evidence_sources,

    baseline_return,
    excess_ev
}
```

Then the agent can compare radically different actions on the same basis:

```
register Ridges miner
vs
buy 5 TAO of a high-growth child
vs
move existing alpha to a better validator
vs
wait 40 minutes for a lower registration burn
vs
hold free/root TAO
```

This is the economic brain.

---

# Data feeds `/bitt` should ingest continuously

## Direct chain — canonical

- spot alpha price
- moving alpha price
- pool weights
- TAO reserve
- alpha reserve
- exact quote-stake / quote-unstake
- per-subnet swap fee
- TAO EMA flow
- alpha/TAO emission accounting
- chain buy / excess TAO
- emission enabled
- owner cut enabled
- miner burn
- emission gate config / distance
- current registration burn
- collateral lock share + drain ratio
- immunity
- neuron capacity
- incentive/dividend distribution
- miner collateral earned/locked
- weights and bonds
- conviction locks
- subnet identity
- root validator allocations / basket state

## Metagraphed — free indexed event layer

Use:

- `/api/v1/chain/stake-flow`
- `/stake-moves`
- `/alpha-volume`
- `/registrations`
- `/deregistrations`
- `/axon-removals`
- `/serving`
- `/weights`
- `/weights/setters`
- `/concentration`
- `/performance`
- `/identity-history`
- `/turnover`

plus account stake-flow/position-history endpoints.

Docs:
https://metagraph.sh/docs/chain-analytics

## TAOStats — historical research

Use historical:

- pools
- OHLCV
- metagraph
- miner incentive distribution
- registrations
- GitHub development activity

Store ourselves and stop depending on current-only features.

---

# Repos: what to clone vs what we already have

## CLONE NOW — RyanMercier/OpenTaoTrader

```
git clone https://github.com/RyanMercier/OpenTaoTrader.git tooling/opentao-trader
```

Why: `/bitt` should not rebuild another execution loop. OpenTaoTrader already has:

- same causal signal pipeline for paper/live
- AMM-aware execution/slippage
- zero-lookahead feature computation
- live pre-flight pool refresh
- dry run
- plugin strategies
- position/trade/equity SQLite
- loss kill-switch
- backtester with attribution/slippage analysis

Pair it with the `RyanMercier/OpenTaoAPI` clone already in `/bitt`.

## CLONE NOW — TidalWavesNode/TAOplicate

```
git clone https://github.com/TidalWavesNode/TAOplicate.git tooling/taoplicate
```

Why: event-driven smart-wallet stake tracking/copy execution. Reuse infrastructure, replace strategy.

## ALREADY IN `/bitt` — keep/use

- `buckZz7/dtao-trader` — chain-buy extraction, emission status, pool/price logger. Great source code; economic research needs updating against current runtime.
- `RyanMercier/OpenTaoAPI` — excellent direct-chain self-hosted historical/API layer.
- `EZTrades-dev/miner-spy` — HHI, coldkey/IP/operator concentration. Useful because 20 hotkeys may actually be one mining operator.
- `epappas/tao-trading` — simple hysteresis rebalancing. Keep as baseline, not alpha strategy.
- `metagraphed` — event/indexing/API reference.
- `subtensor-labs` — infra/research reference.
- existing miner automation toolkit — execution ideas only.

## DON'T PRIORITIZE

I inspected public generic “Bittensor investing agents” and miner automation repos. Most are famous-subnet portfolio monitors, DCA/profit-taking scripts or stale miner installers. They do not have a meaningful research edge. One miner toolkit I checked even contains obviously stale registration-cost examples. Clone primitives, never clone their economic assumptions.

---

# Build order I recommend

## CP0 — unify actions
Create `OpportunityAction` and require every mining/trading/yield recommendation to report comparable EV/cost/confidence.

## CP1 — mine-vs-buy
Add exact `quote_stake`, registration collateral, miner payout distribution, pruning cutoff, local benchmark percentile. Produce `alpha_cost_mine` vs `alpha_cost_buy` for every mineable subnet.

## CP2 — recurring-miner board
Output:

- BORING/RECURRING
- ARTIFACT/JACKPOT
- CAPITAL HEAVY
- UNVERIFIED

Do not blend them into one ranking.

## CP3 — validator router
Track validator realized yield/take/liveness and paper-redelegate same-subnet stake.

## CP4 — lifecycle allocator
Full historical subnet instances from birth. Implement coiled-spring, flow acceleration, age-relative fundamentals.

## CP5 — structural protocol factors
Chain-buy minus recipient-selling model, EMA-gap, gate-distance event studies, emission activation.

## CP6 — entity skill
Backtest every meaningful wallet/root manager before following any flow. Import TAOplicate event executor only after the skill model exists.

## CP7 — weird-event lab
Dissolution arb and conviction acquisition as research-only strategies until historical/runtime simulations prove them.

---

# Final prioritization

If the objective is to start accumulating TAO rather than make a cool dashboard, my current order is:

1. **Low-competition recurring mining**, but scored correctly.
2. **Mine-vs-buy alpha arbitrage** to decide whether mining is actually the cheapest acquisition venue.
3. **Validator yield routing** for alpha we already hold.
4. **High-growth-child allocation** once the lifecycle history is reconstructed properly.
5. **Structural chain-buy / recipient-sell pressure** as a trading factor.
6. **EMA catch-up / emission-gate crossing** after event-study validation.
7. **Mechanism-transition and pre-emission mining** for opportunistic high-alpha plays.
8. **Smart-wallet/root-manager signals** only after historical skill scoring.
9. **Dissolution liquidation arb** as rare event-driven research.
10. **Conviction takeover / root fund** later when capital and evidence justify it.

The key is that none of this should authorize live capital automatically yet. Every new action should first run in replay/paper mode and create a decision → outcome record in Hydra. Human approval remains the final gate for registration or capital movement until we have enough evidence.
