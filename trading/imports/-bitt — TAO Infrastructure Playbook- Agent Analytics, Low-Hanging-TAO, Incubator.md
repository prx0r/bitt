# /bitt — TAO Infrastructure Playbook: Agent Analytics, Low-Hanging-TAO, Incubator & Backtester V2

**Date:** Wed, 2 Sep 2026 20:08:27 -0700

---

# /bitt — TAO Infrastructure Playbook
## Agent-first infrastructure, gold analytics, Low-Hanging-TAO, Subnet Incubator and Backtester V2

Date: 3 September 2026

## Executive conclusion

I think the direction is unusually coherent.

Do **not** try to build another TAO.app, Etherscan or generic subnet dashboard. TAO.app already exposes a broad explorer/analytics surface: macro analytics, subnet analytics, metagraphs, OHLC, holders, social data, APY, portfolio history, accounting, root baskets, validator identities and more.

The stronger /bitt thesis is:

> **Build the machine-readable decision layer for autonomous economic actors on Bittensor.**

At every decision point the system should answer:

> Given my TAO, alpha positions, hotkeys, compute, API budget, WorkerVersions, risk limits and time horizon, what action available on Bittensor has the highest expected TAO-denominated value after costs, slippage, capital lock, failure probability and opportunity cost?

The action set is much larger than BUY/SELL:

- HOLD_TAO
- STAKE_ALPHA
- UNSTAKE_ALPHA
- MOVE_VALIDATOR
- ROOT_ALLOCATE
- REGISTER_MINER
- WAIT_FOR_BURN
- ADD_COLLATERAL
- SUBMIT_MINER_ARTIFACT
- EXIT_MINER
- MINE_PRE_EMISSION
- BUY_ALPHA_INSTEAD_OF_MINING
- MINE_ALPHA_INSTEAD_OF_BUYING
- ENTER_LIQUIDATION_EVENT
- LOCK_CONVICTION
- DO_NOTHING

That perspective is much closer to the early infrastructure winners in Ethereum/Cardano than another consumer dashboard.

---

# 1. What actually won in early Ethereum/Cardano

The recurring pattern was not “make lots of crypto features.” It was:

> Find one ugly protocol-specific burden everyone will face if the chain succeeds, then make it disappear behind a trustworthy interface.

### Etherscan

Ethereum launched July 2015. Etherscan launched in August 2015, added API services in September 2015 and smart-contract verification in 2016.

It turned an unreadable chain into a canonical human/debugging interface.

Source: https://etherscan.io/aboutus

### MetaMask

MetaMask became a doorway into Ethereum. It abstracted keys/transactions/dapp interaction into a browser interface and accumulated trust/distribution.

### Infura

Infura launched in November 2016 specifically to let developers build Ethereum applications **without operating their own node infrastructure**.

Source: https://consensys.io/blog/eight-years-of-evolution-the-history-of-ethereum-and-consensys

### Dune

Dune began in 2018 cleaning Ethereum data for one paying customer. Its insight was that technically public data can still be economically scarce when decoding/querying it is painful.

Source: https://dune.com/about

### The Graph

Introduced in July 2018 to make indexed blockchain data consumable by applications with consumer-grade performance.

Source: https://thegraph.com/blog/the-graph-network-in-depth-part-1/

### Cardano / Blockfrost

Cardano’s mature infrastructure taxonomy now looks like a database stack: hosted query APIs such as Blockfrost/Maestro/Koios, node interfaces, indexers, full nodes, data nodes and managed platforms.

Blockfrost’s value proposition is simple: it runs cardano-node + indexer and exposes REST so developers do not need to operate infrastructure.

Sources:
https://developers.cardano.org/docs/get-started/infrastructure/api-providers/overview/
https://developers.cardano.org/docs/get-started/infrastructure/api-providers/blockfrost/overview/

## The lesson for TAO

The generic layers are already developing:

- chain explorer
- portfolio
- trading UI
- metagraph viewers
- OHLC
- validator listings
- holder analytics
- APY
- developer activity
- APIs

TAO.app alone already covers a surprising amount of this.

Source: https://api.tao.app/docs

So I would **not** compete head-on for “best TAO dashboard.”

The underserved burden is:

> **The chain exposes an enormous action/state space. What should an autonomous agent actually do next?**

Bittensor is now particularly suitable for this. SDK v11 exposes JSON-native intents, `plan` before `execute`, structured results/errors and hard `Policy` constraints such as max spend and allowed netuids. This is explicitly agent-friendly infrastructure.

Source: https://www.bittensor.com/docs/sdk

That makes /bitt potentially analogous to a strange combination of:

- Dune: derived intelligence
- Infura/Blockfrost: reliable machine interface
- Aladdin: action/risk layer
- Bloomberg: canonical economic data
- an execution router: turn information into safe operations

---

# 2. Review of current /bitt: what is genuinely strong

## A. The canonical capture layer is the right foundation

`oracle/capture.py` is conceptually one of the best things in the repo.

It tries to capture every subnet from one chain snapshot and stores:

- block
- collector/schema version
- content hash
- metagraph
- burn
- hyperparameters
- epoch state
- mechanism count
- price
- miner/validator classification
- emissions
- incentive concentration
- HHI/effective earners
- top emitters
- weights/bonds summaries
- identity

This is exactly the kind of boring infrastructure that compounds in value.

### Fixes needed

There is a concrete implementation bug: `_capture_one_subnet()` calls `sub.read('weights'...)` / `sub.read('bonds'...)`, but `sub` is not in that function’s scope. The exceptions are swallowed, so the weight/bond data will currently fall back to empty objects.

On current SDK v11 use the proper namespace calls:

- `snapshot.weights.weights(netuid=...)`
- `snapshot.weights.bonds(netuid=...)`

Also, the module says “finalized block” but currently uses `sub.block`; make the exact snapshot semantics explicit and record block hash + runtime/spec version.

Current v11 supports typed snapshot/query surfaces; use one pinned snapshot for every field used in an economic record.

Useful docs:
https://www.bittensor.com/docs/migration
https://preview.bittensor.com/docs/query/weights

## B. The low-hanging-TAO payout scan is genuinely gold

The strongest version is the newer design that ignores nominal miner counts and reconstructs the **actual settled payout vector** for every non-validator hotkey.

For every subnet persist:

- N >= 0.01 TAO/day
- N >= 0.05
- N >= 0.1
- N >= 0.25
- N >= 0.5
- N >= 1
- N >= 2
- N >= 5
- N >= 10
- p10 / p25 / median / p75 / p90
- top-1 / top-3 / top-5 / top-10 share
- HHI
- Gini
- effective earners
- exact seat membership
- registration cost
- seat persistence/churn

This is much better than `emission / miner_count` because it answers an economically meaningful question:

> How many people are actually getting paid meaningful money here?

The underlying chain premise is valid. Bittensor’s current emissions docs explicitly say a metagraph neuron’s `emission` field is the payout from the subnet’s most recent epoch, denominated in subnet alpha, and is a **per-tempo amount**, not a per-block rate.

Source: https://www.bittensor.com/docs/concepts/emissions

### Upgrade the payout scan into three simultaneous views

Do not expose only `tao_day`.

For each seat calculate:

1. **settled_alpha_day**
   - protocol-native earning rate
   - insensitive to intratempo alpha price movement

2. **spot_marked_tao_day**
   - settled alpha/day × point-in-time alpha spot price

3. **realizable_tao_day**
   - what selling the reward would actually produce using the chain’s exact `quote_unstake`
   - captures fee + slippage

Bittensor says quote RPC uses the exact same pool path as execution, not an estimate.

Sources:
https://preview.bittensor.com/docs/query/quote-unstake
https://www.bittensor.com/docs/concepts/staking-pools

This immediately produces a better agent question:

> Where are there five persistent seats earning >=0.1 realizable TAO/day after liquidation costs?

### Separate payout changes from price changes

A miner can cross the 0.1 TAO/day threshold because:

- their alpha emission actually increased, OR
- alpha price increased while alpha emission was unchanged.

Those are different opportunities.

Store both:

- seat_alpha_growth
- seat_marked_tao_growth

Then alerts can distinguish “mechanism is paying newcomers more” from “token price pumped.”

### Scan intelligently around epochs

Payout vector changes on epoch settlement, while price/quotes change continuously.

So:

- full metagraph payout scan: epoch-triggered
- prices/flows/pool quotes: block/5m cadence
- GitHub/mechanism metadata: slower event/crawl cadence

Use `epoch_status`, `blocks_until_next_epoch`, or `wait_for_epoch` rather than blindly rescanning every 10 minutes.

Sources:
https://preview.bittensor.com/docs/query/epoch-status
https://preview.bittensor.com/docs/query/blocks-until-next-epoch

### Make seat identity lineage-aware

Do not key historical miners on netuid + UID alone.

Use:

- subnet instance
- hotkey lineage
- coldkey where relevant
- registration block
- UID at that interval

Current Bittensor has explicit key-lineage functionality from the V437 release.

---

# 3. The largest catalog of “gold analytics” I would build

The rule for this catalog:

> If TAO.app/Etherscan can answer it by displaying one chain field, it is probably not the moat. /bitt should combine fields into an economic decision an agent can consume.

## A. MINER / EARNING ANALYTICS

### 1. Exact income seats

Already discussed. This should be canonical.

Output:

`GET /v1/mining/seats?min_tao_day=0.1`

### 2. Seat persistence

For every threshold compute:

- consecutive epochs above threshold
- 1d/7d/30d survival
- Jaccard continuity of paid hotkeys
- median seat lifetime
- churn rate

A subnet with 8 stable 0.1/day seats can be far better than one with 30 seats that completely rotate every epoch.

### 3. Salary vs jackpot classifier

Classify incentive mechanisms economically:

- SALARY: broad stable tail
- TOURNAMENT: several paid ranks
- POWER_LAW: top-heavy
- JACKPOT: winner-take-all
- ROTATING: high payout churn

Agent chooses based on risk tolerance and WorkerVersion.

### 4. Prune-risk / survival runway

For each current miner estimate:

- payout rank
- pruning score/rank
- immunity remaining
- distance from lowest safe UID
- how many entrants are required to threaten the seat
- recent registration pressure

Return:

`expected_safe_epochs`

### 5. Newcomer disadvantage curve

Measure how newly registered hotkeys perform versus incumbents by:

- age since registration
- bond maturity
- first paid epoch
- time to p25/p50/top10 payout

This tells an agent whether a subnet is theoretically lucrative but practically inaccessible to fresh entrants.

### 6. Registration timing optimizer

Registration burn floats/decays. Do not just say “good subnet.”

Compute:

`EV(register_now)` vs `EV(wait_1_epoch)` vs `EV(wait_n_blocks)`

Include:

- expected burn decay
- probability another registration raises burn
- foregone payout while waiting
- UID capacity/pruning risk

Action output:

`REGISTER_NOW` / `WAIT_37_MINUTES` / `PASS`

### 7. True sunk registration cost

Current collateral makes headline registration price misleading.

If registration price is T and collateral share p:

- sunk burn = `(1-p)*T`
- locked collateral = `p*T` less standing credit
- opportunity cost = locked capital × expected lock duration × opportunity rate

Bittensor collateral is released through earned emission and survives deregistration.

Source: https://www.bittensor.com/docs/guides/mining/collateral

### 8. Collateral payback runway

Using `locked_alpha`, `drain_ratio`, `earned_alpha`, `releasable_work_alpha`:

- expected epochs to unlock
- probability of full unlock before prune
- capital at risk if worker fails
- effective IRR after lockup

### 9. Mine-vs-buy alpha arbitrage

Possibly one of the best Bittensor-native analytics.

For every subnet:

`market_cost_per_alpha = exact quote_stake(TAO_amount)`

versus:

`expected_mining_cost_per_alpha = (sunk entry + capital opportunity cost + compute/API + expected re-reg) / expected alpha earned`

Then:

- MINE if alpha is materially cheaper to manufacture through work
- BUY if market is cheaper
- PASS if neither has attractive EV

This turns mining into an alternative execution venue for acquiring alpha.

### 10. Paid-cutoff estimator

For mechanism-adapted subnets:

- reproduce evaluator locally
- map local score → historical on-chain payout percentile
- estimate probability that current WorkerVersion lands above 0.1/0.25/1 TAO/day seat

Return:

`P(paid)` and `expected_tao_day`

### 11. Reward-per-compute

Normalize expected miner reward by:

- GPU-hours
- CPU-hours
- inference dollars
- storage
- bandwidth
- API cost
- human setup minutes

Useful to autonomous agents because their scarce resource may be compute rather than TAO.

### 12. Reward-per-worker-version

Track the same Moltwork WorkerVersion across subnets:

`expected_tao / incremental adaptation cost`

This identifies reuse/transfer opportunities.

Example: a security worker improves on BitSec, then becomes more competitive in other security/bounty markets.

### 13. Under-capacity opportunity

Detect:

- available UID capacity
- low registration velocity
- material miner pool
- broad paid tail

Useful because a profitable mechanism with spare capacity is much less hostile to entry.

### 14. Miner-pool broadening before competition reacts

Alert when:

- miner alpha pool grows
- N_0.1 / N_0.25 rises
- p25 rises
- registration rate has not yet increased

This is an excellent “low-hanging fruit” event.

### 15. Mechanism-change opening

Watch:

- identity/owner changes
- scoring repo changes
- validator code changes
- mechanism count/split changes
- paid-seat distribution resets

If emissions remain high while incumbents are adapting, there may be a temporary entry window.

### 16. Multi-mechanism reward routing

Current chain exposes `mechanism_count` and `mechanism_emission_split`.

For subnets with multiple mechanisms, calculate opportunity per mechanism rather than collapsing everything to one netuid.

---

## B. VALIDATOR / STAKING ANALYTICS

### 17. Validator realized yield router

Separate two decisions:

- SUBNET_SCORE: should I own this alpha?
- VALIDATOR_SCORE: if yes, who should I stake behind?

Rank validators on:

- realized dividends per alpha at risk
- delegate take
- yield stability
- validator permit/liveness
- trust/vtrust
- weight update regularity
- stake concentration
- recent degradation

### 18. Validator yield persistence

Find validators whose high APY persists out-of-sample rather than simply reflecting one lucky epoch.

### 19. Weight liveness alarm

Use blocks since last update / reveal timing to detect stale validators before APY dashboards react.

### 20. Validator consensus quality

From weights/bonds:

- distance from consensus
- tendency to identify future high-incentive miners early
- bond quality
- historical predictive accuracy

This can identify validators that are genuinely good evaluators.

### 21. Validator disagreement opportunity

When high-stake validators strongly disagree on miner ranking, the mechanism may be unstable, exploitable, early, or undergoing change.

Use weight-matrix dispersion as an event signal.

### 22. Same-subnet redelegation optimizer

If alpha exposure stays fixed, find when moving the stake to another validator increases expected yield enough to justify transaction friction.

### 23. Stake dilution

Estimate expected forward yield after proposed stake size instead of showing historical APY blindly.

### 24. Root-manager skill score

Root Reborn makes validator allocation vectors public.

Treat managers like fund managers:

- snapshot each root weight vector before outcomes
- calculate 7/30/90d TAO-relative performance
- Bayesian-shrink small samples
- rank historical skill

Source: https://www.bittensor.com/docs/query/validator-root-weights

### 25. Root “13F” change detector

Alert when historically skilled root managers meaningfully increase/decrease specific subnet allocations.

### 26. Root basket capacity/realizable NAV

Use actual basket NAV/quotes, not only spot valuation.

---

## C. SUBNET ALLOCATION / MARKET-STRUCTURE ANALYTICS

### 27. Native TAO-flow acceleration

Bittensor directly stores an EMA of net stake-add minus unstake per subnet.

Source: https://www.bittensor.com/docs/query/subnet-tao-flows

Build:

- flow level
- flow acceleration
- flow z-score by age/liquidity cohort
- persistent flow streak
- flow/market-cap
- flow/liquidity
- flow residual vs price

### 28. Fundamentals outrunning price (“coiled spring”)

Core incubator factor:

COILED_SPRING =
+ stake_growth_z
+ tao_flow_acceleration_z
+ emission_growth_residual_z
+ volume_growth_z
+ holder_growth_z
+ miner_growth_z
+ github_acceleration_z
+ usage/revenue_growth_z
- price_return_z
- valuation_premium_z

Normalize by subnet age, liquidity and current runtime regime.

### 29. Spot-vs-moving-price lag

Current emissions use moving price. Young/high-growth subnets may have spot demand that has not fully propagated through EMA economics.

Test:

`ema_gap = (spot - moving_price) / moving_price`

conditioned on persistent fundamentals.

### 30. Emission-gate distance

V440 introduced a nonlinear emission gate.

Create a direct `gate_distance` feature and event studies for upward/downward crossings.

Sources:
https://preview.bittensor.com/releases
https://www.bittensor.com/docs/concepts/emissions

### 31. Emission residual

Do **not** use emission level as an independent fundamental without adjustment because current emission is price/demand-driven.

Model:

`expected_emission = f(moving_price, gate state, miner burn, protocol era)`

Then use:

`emission_residual = actual - mechanically_expected`

### 32. Protocol chain-buy pressure

Measure deterministic structural alpha demand from protocol chain buys where applicable.

Normalize by:

- pool reserve
- daily volume
- liquid market cap

### 33. Recipient sell propensity

Track addresses receiving miner/validator/owner emissions and how much they historically unstake/sell after epochs.

Then:

`NET_STRUCTURAL_PRESSURE = protocol_buy_tao - expected_recipient_sell_tao`

Much better than raw chain buy alone.

### 34. Exact liquidity capacity curve

For each subnet publish exact executable quote curves:

- 0.1 TAO
- 1 TAO
- 5 TAO
- 10 TAO
- 25 TAO
- 100 TAO

Entry and exit.

An autonomous allocator needs **capacity**, not just spot price.

### 35. Position-size-aware expected return

A strategy edge can exist at 1 TAO and disappear at 100 TAO.

Every opportunity should expose:

`max_capital_tao_at_positive_EV`

### 36. TAO-relative momentum

Residualize subnet return against:

- TAO/USD
- BTC/USD
- ETH/USD
- broad subnet index

We care primarily whether owning subnet alpha beats owning TAO.

### 37. Cross-sectional breadth/regime

Network-level indicators:

- % subnets beating TAO 1d/7d
- median subnet return
- dispersion
- volume breadth
- flow breadth
- emission breadth

Use this to decide how aggressively the allocator should leave TAO.

### 38. Holder quality/breadth

Distinguish:

- holder growth
- top-10 concentration
- new-wallet retention
- independent holders vs protocol/team/miner wallets

### 39. Smart-wallet skill

Score wallets by forward TAO-relative outcomes after their stake add/remove events, with Bayesian shrinkage and entity classification.

### 40. Identity/owner/mechanism transition catalyst

Treat owner/repo/mechanism changes as corporate events.

### 41. Emission-enable catalyst

Track active subnets with pool-side TAO emission disabled and model activation as an event.

Source: https://preview.bittensor.com/docs/query/subnet-emission-enabled

### 42. Pre-emission mining

A new subnet may still distribute alpha to miners before broader pool-side economics mature. Treat it like venture exposure; model probability of future activation/liquidity rather than pretending it is current TAO income.

### 43. Dissolution liquidation arbitrage

For endangered subnet instances estimate:

`expected liquidation TAO per alpha - executable alpha entry cost - time/risk discount`

Only emit if there is a large safety margin.

### 44. Conviction takeover economics

For eligible older subnets estimate cost to accumulate/mature enough conviction for ownership against PV of owner-cut income.

Current release rules make this difficult, which is precisely why it belongs in an oracle rather than a manual strategy.

### 45. Owner-cut valuation

Value subnet ownership as an income stream, separately from alpha market value.

---

## D. AGENT EXECUTION / SAFETY ANALYTICS

This may become one of the most defensible layers because humans do not need it as urgently as agents do.

### 46. Universal action frontier

At any state enumerate every permitted action and compare EV:

`HOLD / STAKE / UNSTAKE / MOVE_VALIDATOR / ROOT / REGISTER / WAIT / MINE / EXIT`

Return one canonical ranked action list.

### 47. Plan-aware cost estimator

Before execution call SDK `plan` and attach:

- expected effects
- fee
- warnings
- policy constraints
- slippage limit
- reversible/irreversible flags

### 48. Error probability / remediation model

SDK v11 returns stable machine-readable ErrorCodes.

Track historical failures by action/state and predict:

- likely error
- remediation
- whether retry is sensible

### 49. Policy compiler

Given a mandate such as:

“Agent may allocate max 3 TAO/day, only SN60/SN61, no raw calls”

compile it into Bittensor `Policy` + Moltwork Treasury grant.

### 50. State-staleness risk

Report:

- block age
- epoch proximity
- reveal window
- price quote age
- whether state changed since plan

### 51. Epoch-aware execution

Certain actions are better/worse just before/after epoch settlement. Provide execution windows.

### 52. Reversibility score

Classify capital actions:

- liquid/reversible
- AMM-exit-cost
- collateral-locked
- conviction-locked
- sunk burn

### 53. Safe-execution receipt

After every action verify postconditions and persist:

- plan
- intent
- policy
- signed tx metadata
- chain result
- state delta
- costs
- realized vs expected effect

This plugs directly into Moltwork/Hydra.

---

## E. OFF-CHAIN / MECHANISM INTELLIGENCE

### 54. Code-significance activity

Do not count commits naively.

Classify code changes:

- evaluator/scoring
- miner client
- tokenomics/mechanism
- infra
- docs-only
- dependency bump

A 1-line scoring change may matter more than 100 docs commits.

### 55. Validator-code change detector

Priority event because validator changes can instantly change what earns.

### 56. Hardware/API requirement change

Extract from repo/docs and turn into machine-readable resource requirements.

### 57. Mechanism reproducibility score

Can our agent reproduce local scoring from open code/data?

Higher reproducibility = lower uncertainty when deciding to mine.

### 58. Product liveness

Automatically test public endpoints/products where permitted:

- up/down
- latency
- usage/revenue signals
- releases

### 59. Metadata disagreement

Compare:

- on-chain identity
- repo
- website
- TAO.app
- Bittensor.ai
- TAOStats

If third-party descriptions are stale after a mechanism/owner change, flag an information-arbitrage window.

### 60. Security/dependency risk

Integrate BitSec-style analysis:

- exposed secrets
- suspicious dependencies
- repo provenance
- centralization
- unsigned binary dependency
- upgrade risk

Useful to both capital allocation and miners deciding what code to run.

---

# 4. Why the current Low-Hanging-TAO scan is better than the old opportunity score

The old `oracle/opportunities.py` computes roughly:

`reward × lab_fit / cost × competition adjustment`

with reward approximated using emissions/miner counts.

`oracle/analytics.py` similarly uses hand-written 0–1 buckets for reward, emitting-miner count, stability, burn, HHI etc.

Those are fine prototype heuristics, but I would stop treating them as ground truth.

The exact-payout-seat scanner is a large conceptual improvement because it measures **what the market currently pays**, not what an average might imply.

Replace one monolithic “opportunity score” with typed derived objects:

- MINING_INCOME_OPPORTUNITY
- MINING_JACKPOT_OPPORTUNITY
- ALLOCATION_OPPORTUNITY
- VALIDATOR_ROUTE_OPPORTUNITY
- REGISTRATION_TIMING_OPPORTUNITY
- MINE_VS_BUY_OPPORTUNITY
- MECHANISM_CHANGE_OPPORTUNITY
- LIQUIDATION_EVENT
- ROOT_MANAGER_SIGNAL

Each has its own economically meaningful score/evaluation specification.

---

# 5. Review of the Subnet Incubator thesis

## Verdict: the logic is good; current backtest evidence is not yet proof

The original Incubator framing remains strong:

> Reconstruct every subnet instance from birth to death. Compare young subnets to previous subnets at the same age. Learn which point-in-time patterns preceded sustained success before the market made them obvious.

The key is **instance identity**.

Never use netuid as a permanent ticker.

Canonical:

`instance_id = netuid + registration_block`

When a netuid is reused, that is a new economic entity.

Keep dead/deregistered instances forever. They are essential negative examples.

## The +24.7% 30-day result

Current repo commit says:

- 111,845 observations
- 129 subnets
- 30 days
- Momentum Top 5: +24.7%
- Equal Weight Top 5: +0.8%
- Diversified 10: ~0%
- Hold TAO: 0%
- Yield Focused: -3.7%

This is interesting enough to keep investigating.

It is **not** yet legitimate evidence that momentum produces a deployable edge.

Why:

### 1. One 30-day regime

A single month is one market regime, not a robust sample.

### 2. Multiple testing

With 129 cross-sectional assets and several strategies/features, it is easy to discover a winner by chance.

### 3. Baseline implementation is currently unreliable

`trading/baselines.py` labels a function “7-day cross-sectional momentum” but currently sorts subnets using `tao_equiv_day` (emission), not 7-day price return.

That must be fixed before comparing learned strategies to “momentum.”

### 4. Current “yield” factor is not real yield

`factor_yield_price` uses:

`tao_equiv_day / neurons / alpha_price`

but TAO-equivalent emission itself contains alpha price, so price largely cancels. The result is closer to alpha emission per neuron than valuation yield.

Keep it if predictive, but name it correctly.

### 5. Emission is endogenous

Current subnet emissions are heavily influenced by moving price and the emission gate.

Therefore “high emission predicts price” may partly be price reflected back through protocol mechanics.

Use:

- emission growth
- price-residualized emission growth
- gate state
- protocol-era controls

### 6. Replay universe bug

`trading/replay.py` iterates `netuids[:10]` rather than ranking/testing all active subnet instances.

For the thesis “find obscure stuff everyone ignores,” this defeats the point.

### 7. Same-candle fill bias

Current replay can compute a signal from candle t and buy at candle t’s close.

Research rule:

- observe through t
- freeze decision at t
- execute at next executable block/state

### 8. No exact AMM execution

Current replay effectively buys `TAO / price` units.

Real subnet staking is a weighted-pool swap with slippage and fees.

Use block-pinned `quote_stake` / `quote_unstake` for the exact position size.

Source: https://www.bittensor.com/docs/concepts/staking-pools

### 9. No real staking income

Owning/staking alpha has validator dividends. Backtest total economic return, not just token price.

### 10. Root baseline is fake

Current root baseline uses a hard-coded `*1.001`. Replace with historical realized root strategy/basket economics appropriate to each protocol era.

### 11. Survivorship/netuid reuse

This is likely the most dangerous structural bias for the Incubator. Include every dead subnet and maintain immutable instance IDs.

### 12. Runtime non-stationarity

Bittensor changed dramatically in July/August 2026:

- V431 price-driven emissions + SDK v11
- V437 collateral/key lineage
- V438 mechanism splits
- V440 emission gate
- V441 Root Reborn
- V446 accounting/liquid alpha
- V447 conviction normalization
- V448 safer staking/root claims/linked orders
- V450 curated root baskets

Source: https://preview.bittensor.com/releases

Every historical observation needs:

- spec/runtime version
- protocol era
- relevant feature flags

Do not train across all history as if economics were stationary.

---

# 6. Backtester V2: what I would implement

## CP0 — canonical historical truth

Build/ingest:

- subnet instance registry
- 5m/hour OHLC
- historical pools/reserves/liquidity
- full metagraph history
- historical emissions
- registration events
- owner/identity changes
- GitHub activity history
- TAO/BTC/ETH macro
- protocol spec/version
- dead/dissolved subnets

TAOStats already exposes historical metagraph data including per-neuron `emission`, `daily_reward`, registration block and other point-in-time fields.

Source: https://docs.taostats.io/reference/get-metagraph-history

Use the public Bittensor archive for verification initially; run our own archive later when /bitt becomes serious infrastructure. Official docs say the public archive is available, while a self-hosted archive is currently ~3.5TB+.

Source: https://www.bittensor.com/docs/guides/running-a-node

## CP1 — point-in-time feature store

Every feature row must contain only information knowable at that timestamp.

Key:

`(instance_id, block/timestamp, feature_version)`

No latest metadata joined backwards.

## CP2 — factor atlas before strategy soup

Do not immediately optimize a weighted score.

For each factor independently measure:

- Spearman IC with 1d/7d/14d/30d/60d forward TAO-relative return
- quintile spreads
- hit rate
- median return
- bootstrap confidence interval
- capacity
- turnover
- effect by age cohort
- effect by liquidity cohort
- effect by runtime era

Kill factors that do not survive.

## CP3 — event studies

For discrete Bittensor-native events:

- emission gate crossing
- emission enable
- ownership transfer
- mechanism code change
- N_0.1 seat expansion
- registration-burn shock
- root-manager allocation change
- protocol chain-buy regime change
- collateral policy change

Measure forward returns/reward persistence around event timestamps.

## CP4 — walk-forward

Use rolling/expanding windows:

TRAIN → VALIDATION → LOCK METHOD → TEST

Never retune on test.

Because forward horizons overlap, use purge/embargo around boundaries.

## CP5 — exact execution

For every simulated decision:

- decision at block B
- fill at B+1 / first valid execution block
- exact pool quote at that snapshot
- fee
- slippage
- liquidity/capacity
- staking dividends while held
- exit quote
- root opportunity cost

## CP6 — realistic baselines

At minimum:

- free TAO
- root strategy
- equal weight active universe
- liquidity-weighted universe
- market-cap-weighted
- true price momentum
- TAO-flow momentum
- age-neutral quality
- young-subnet basket
- established-only basket
- random eligible portfolios / Monte Carlo distribution

## CP7 — immutable ExperimentReceipt

Every PnL claim must produce:

- experiment_id
- git SHA
- feature versions
- data cutoff/hash
- universe
- start/end
- train/test split
- parameters
- execution model
- costs
- trades
- benchmark definitions
- seed
- output metrics
- result hash

No naked “+24.7%” result should be allowed without a receipt.

## CP8 — paper-trade publication

Before using real money:

- generate decision
- freeze hypothesis
- timestamp/hash it
- store exact evidence/method
- simulate SDK plan
- append outcomes later

This gives us a real prospective track record instead of retrospective backtest performance.

## CP9 — tiny live, human approved

Only after the paper strategy survives.

Use SDK `Policy` and Moltwork Treasury grants.

---

# 7. Incubator + Hydra = the right learning loop

This is where the architecture becomes unusually strong.

The canonical lifecycle should be:

OBSERVATION
→ HYPOTHESIS
→ FROZEN METHOD/EVALUATION SPEC
→ BACKTEST
→ WALK-FORWARD
→ PAPER DECISION
→ SMALL LIVE DECISION
→ OUTCOME
→ REVIEW
→ HYDRA LESSON
→ CHILD HYPOTHESIS

A hypothesis is immutable after publication.

Example:

```json
{
  "hypothesis_id": "hyp_...",
  "domain": "bittensor",
  "claim": "Young subnets with positive TAO-flow acceleration, expanding paid-miner breadth and lagging price outperform TAO over 14 days",
  "created_at": "...",
  "data_cutoff": "...",
  "method_version": "incubator-factor-v4",
  "feature_versions": ["flow_v2", "seat_breadth_v1", "price_lag_v3"],
  "confidence": 0.68,
  "evaluation": {
    "horizon": "14d",
    "primary_metric": "tao_relative_return",
    "secondary": ["max_drawdown", "capacity"]
  },
  "evidence_hash": "..."
}
```

Freeze it.

Later append:

- observations
- simulated actions
- actual actions
- returns
- miner earnings
- failures
- review

Never rewrite the original claim.

This solves two things simultaneously:

1. **Trust:** users can see we do not delete bad calls.
2. **Learning:** Hydra can retrieve what methods worked under structurally similar states.

Failed hypotheses should be first-class searchable data, not garbage to delete.

---

# 8. Suggested first-class /bitt data model

Core immutable entities:

### SubnetInstance

`instance_id = netuid:registration_block`

### ChainSnapshot

Block-pinned raw chain state + content hash + spec version.

### MinerSeatSnapshot

Full payout vector and threshold-seat memberships.

### MechanismVersion

Repo/code/evaluator identity at a point in time.

### FeatureObservation

Versioned derived factor value.

### Opportunity

Machine-readable action candidate, not generic score.

### Hypothesis

Immutable claim/method/evaluation spec.

### Decision

What the agent recommended at timestamp T.

### ExecutionPlan

SDK plan output + policy.

### ExecutionReceipt

Actual chain result/state delta/cost.

### Outcome

What reality subsequently did.

### Lesson

Derived Hydra knowledge; rebuildable from immutable truth.

---

# 9. Machine-readable API I would expose

Free/raw-ish:

- `GET /v1/subnets/{netuid}/state`
- `GET /v1/subnets/{instance}/history`
- `GET /v1/mining/seats`
- `GET /v1/mining/seat-history`
- `GET /v1/validators/{hotkey}/score`

Higher-value derived:

- `GET /v1/opportunities`
- `GET /v1/actions?capital_tao=...`
- `GET /v1/mine-vs-buy/{netuid}`
- `GET /v1/registration-timing/{netuid}`
- `GET /v1/mining/entry/{netuid}`
- `GET /v1/mining/paid-probability/{netuid}`
- `GET /v1/allocation/incubator`
- `GET /v1/structural-pressure/{netuid}`
- `GET /v1/root/managers`
- `GET /v1/liquidity/capacity/{netuid}`
- `GET /v1/hypotheses`
- `GET /v1/hypotheses/{id}`
- `POST /v1/plan`

Eventually x402 each expensive derived call.

The API object should always expose:

- observation block/time
- source provenance
- feature/method version
- confidence
- expected horizon
- capacity
- risks
- expiry/half-life
- evidence

---

# 10. The top 12 things I would actually build next

In strict priority order:

## 1. Merge exact full payout-vector persistence into canonical capture

No top-10 truncation. Every miner UID.

## 2. Add `settled_alpha_day`, `marked_tao_day`, `realizable_tao_day`

Use exact quotes for realizable value.

## 3. Build seat persistence/churn tables

Thresholds 0.01/0.05/0.1/0.25/0.5/1+.

## 4. Add collateral economics

True sunk burn, locked collateral, release runway, re-registration credit.

## 5. Add epoch-aware scanning

Payout scans around actual epoch settlement.

## 6. Fix `capture.py` weights/bonds and move fully onto v11 snapshot namespaces

Also store runtime spec/feature flags.

## 7. Build mine-vs-buy

This is extremely Bittensor-native and agent-useful.

## 8. Build exact registration timing

Wait-vs-register EV.

## 9. Build SubnetInstance registry + graveyard

Do this before serious historical modeling.

## 10. Ingest full historical metagraph/pool/price/registration history

Not merely 30 days.

## 11. Backtester V2

Point-in-time universe, next-state execution, exact swap quotes, costs, actual baselines, walk-forward.

## 12. Freeze every prospective recommendation as a Hypothesis/Decision receipt

This is the beginning of the public trust moat and Hydra learning moat.

---

# 11. What I would NOT build now

- another generic subnet screener
- another TAO portfolio UI
- generic candlestick charts
- generic APY leaderboard
- generic “AI ranks subnets 1–100” score
- a token
- high-frequency trading bot
- broad social-sentiment bot as the primary edge
- a massive archive node before the derived products prove useful

TAO.app/Bittensor.ai/TAOStats can remain upstream/fallback sources while we build the derived layer.

Own/archive the chain later when independence/latency/provenance becomes strategically important.

---

# 12. Final positioning

If Ethereum had:

- Etherscan = see it
- Infura = query it
- MetaMask = interact with it
- Dune = analyze it
- The Graph = index it

then the Bittensor-native category I would try to own is:

> **/bitt = decide what to do with it.**

Not just a trader.

Not just a miner scanner.

Not just an oracle.

A machine-readable economic operating layer for an autonomous agent participating in Bittensor.

The Low-Hanging-TAO scanner is the perfect first product because it turns obscure chain state into a concrete economic action.

The Subnet Incubator is the perfect research engine because it turns history into prospective hypotheses.

The immutable Hypothesis/Decision/Outcome ledger is the perfect trust mechanism.

Hydra is the perfect learning substrate because every prediction and every real-world result becomes reusable evidence.

And the SDK’s current agent-native transaction model means the final loop is actually feasible:

OBSERVE → FIND OPPORTUNITY → HYPOTHESIZE → PLAN → POLICY CHECK → HUMAN APPROVE → EXECUTE → VERIFY → MEASURE → LEARN.

That is much more defensible than trying to out-dashboard TAO.app.

## Primary sources

Bittensor SDK v11:
https://www.bittensor.com/docs/sdk

Bittensor query catalog:
https://preview.bittensor.com/docs/query

Metagraph:
https://preview.bittensor.com/docs/query/metagraph

Emissions:
https://www.bittensor.com/docs/concepts/emissions

Staking/pool mechanics:
https://www.bittensor.com/docs/concepts/staking-pools

Subnet TAO flows:
https://www.bittensor.com/docs/query/subnet-tao-flows

Miner collateral:
https://www.bittensor.com/docs/guides/mining/collateral

Root manager weights:
https://www.bittensor.com/docs/query/validator-root-weights

Runtime releases:
https://preview.bittensor.com/releases

Running/archive node:
https://www.bittensor.com/docs/guides/running-a-node

TAO.app API:
https://api.tao.app/docs

TAOStats metagraph history:
https://docs.taostats.io/reference/get-metagraph-history

Ethereum infrastructure history:
https://etherscan.io/aboutus
https://consensys.io/blog/eight-years-of-evolution-the-history-of-ethereum-and-consensys
https://dune.com/about
https://thegraph.com/blog/the-graph-network-in-depth-part-1/

Cardano infrastructure map:
https://developers.cardano.org/docs/get-started/infrastructure/api-providers/overview/
https://developers.cardano.org/docs/get-started/infrastructure/api-providers/blockfrost/overview/
