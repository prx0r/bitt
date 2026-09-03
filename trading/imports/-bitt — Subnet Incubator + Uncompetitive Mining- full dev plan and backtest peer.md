# /bitt — Subnet Incubator + Uncompetitive Mining: full dev plan and backtest peer review

**Date:** Wed, 2 Sep 2026 17:50:08 -0700

---

# /bitt — Subnet Incubator + Uncompetitive Mining

**Date:** 3 September 2026

## Executive thesis

Double down on two related edges inside Bittensor:

1. **Subnet Incubator / allocator:** build the best point-in-time historical dataset of every subnet from birth to death, learn what successful young subnets looked like *before* they became obvious, and use that to rebalance TAO into underfollowed/new alpha markets.
2. **Uncompetitive Mining Hunter:** continuously scan all subnets for high contestable miner emissions with abnormally low competent competition, reproduce their scoring mechanism offline, enter only when we have evidence we can win, harvest, learn, and rotate elsewhere.

The common moat is the same: most participants concentrate on obvious established names (Chutes, Targon, etc.) and do not have time to understand ~120+ changing subnet micro-markets. `/bitt` should become the machine that watches all of them continuously.

The investment thesis should not be “buy new subnets because they are new.” It should be:

> **New and obscure subnets are less efficiently researched. Build a historical model of what successful subnet adolescence looks like, then only take small positions where price action, liquidity, on-chain adoption, development activity and mechanism quality jointly resemble previous winners.**

Likewise, the mining thesis is not “mine low-miner-count subnets.” It is:

> **Find live reward pools where economically relevant competition is low, the scoring mechanism can be reproduced, entry is cheap, and our existing workers have a realistic score gap to paid ranks.**

---

# 1. Peer review of the current backtesting

## Verdict

The current +24.7% 30-day momentum result is a useful infrastructure smoke test. It is **not yet evidence of a real trading edge**.

The good news is that the architecture is pointing in the right direction: `market.duckdb`, chronological replay, chain snapshots, TAO/BTC/ETH context, factors, baselines and Hydra outcome logging are all the right pieces.

The bad news is that the current implementation still has enough structural issues that I would mark every historical PnL number as:

`EXPERIMENTAL / NOT CAPITAL-READY`

until Backtester V2 is complete.

## Specific current problems

### A. `rebalancer.py` still contains an inverted-return bug

Current code stores candles newest-first and then calculates:

```python
prev = valid_candles[i-1]   # newer
curr = valid_candles[i]     # older
returns.append((curr - prev) / prev)
```

This makes a rising market appear negative inside `calculate_yield_price()`.

The repo's own `BACKTEST-CP1.md` identified this bug, but it remains in the current `trading/rebalancer.py`.

Fix immediately.

Repo:
https://github.com/prx0r/bitt/blob/master/trading/rebalancer.py

### B. Volume acceleration currently reads the wrong column

`market.py` defines:

```text
volume_tao
```

but `rebalancer.py` reads:

```python
c.get('volume', 0)
```

So the volume-acceleration signal is effectively zero on this schema.

This means one of the stated setup factors is not actually operating.

### C. `yield_price` is not yield

The rebalancer estimates “annual yield” by annualizing average **price returns**, then divides that by price. That is neither staking yield nor emission yield and has unstable units.

Worse, `factors.py` computes:

```python
yield_per = tao_equiv_day / neurons
ratio = yield_per / alpha_price
```

But `tao_equiv_day = alpha_emission_day * alpha_price` in `chain_scanner.py`.

So alpha price cancels:

```text
(tao_equiv_day / neurons) / price
= alpha_emission_day / neurons
```

The “yield/price” factor is therefore mostly **alpha emission per neuron**, not valuation yield.

Replace it with economically meaningful quantities, e.g.:

- validator/staker realized alpha yield per TAO at risk
- forward emission / liquid market cap
- emission / pool TAO reserve
- realized staking APY
- emission growth relative to valuation growth

and keep price returns separate.

### D. `emission_momentum` is neither momentum nor independent fundamental information

`factors.py` calls current emission level “emission momentum.” It is simply current `tao_equiv_day` normalized across subnets.

More importantly, under the current Bittensor regime subnet emission is heavily price-driven. The July 2026 V431 upgrade made subnet emission allocation price-based, later modified by the emission gate.

That creates endogeneity:

```text
price rises
→ moving price rises
→ emission share can rise
→ our model sees high emission
→ model calls it bullish
```

This may just be price momentum echoed back through protocol mechanics.

Emission is still useful, but features must distinguish:

- emission level
- emission growth
- emission growth unexplained by price
- emission rank change
- price-to-emission divergence
- post-gate eligibility/state

Source:
https://www.bittensor.com/releases/v431-upgrade
https://docs.taostats.io/docs/subnet-emissions

### E. Current replay only examines the first 10 netuids

`replay.py` currently does:

```python
for netuid in netuids[:10]:
```

That is not a top-10 opportunity selection. It is effectively a numeric-netuid truncation depending on DB ordering.

For an “all 120 subnets nobody watches” strategy this is fatal.

Every active subnet instance must enter the cross-sectional universe at every decision timestamp.

### F. Same-candle execution bias

The strategy calculates its signal using the candle close at time `t` and then buys at that same close.

For research-grade replay:

```text
observe information through t
make decision at t
execute using t+1 / next executable pool state
```

or simulate an actual AMM swap against the pool reserves at a block after the decision timestamp.

### G. No real dTAO execution model

Current replay treats alpha like a frictionless exchange-listed token:

```text
TAO / price = alpha units
```

Real subnet allocation interacts with a TAO/alpha pool. Backtesting needs:

- contemporaneous TAO reserve
- contemporaneous alpha reserve
- actual chain swap/staking formula
- slippage for our trade size
- minimum received / execution protection
- any applicable fees/costs
- unstake/sell slippage
- liquidity changes while holding
- realistic execution latency

This matters most in exactly the young low-liquidity subnets we want to target.

### H. Staking income is missing

If the actual strategy is “hold TAO vs allocate TAO to subnet alpha/stake,” then return is not just alpha price change.

Portfolio PnL must include whatever staking/dividend/emission income would actually accrue to the selected validator/hotkey, using point-in-time rules.

The current `Root TAO` baseline is also a hard-coded `initial * 1.001`, not a historical root strategy.

### I. Current baselines are not reliable

`baseline_momentum()` says “7-day cross-sectional momentum” but sorts by current emission.

Equal-weight and yield baselines are built from the latest subnet snapshot rather than a time-correct historical universe.

Required baselines should include:

- free TAO
- actual root strategy where applicable
- equal-weight active subnet universe
- liquidity-weighted
- market-cap-weighted
- top-N price momentum
- top-N flow momentum
- established-only
- young-only
- random eligible portfolio (Monte Carlo distribution)
- simple age-neutral quality basket

### J. Survivorship and netuid-reuse bias are currently the biggest structural risk

A **netuid is not a permanent ticker**.

When capacity is full, Bittensor can dissolve a low-price subnet and reuse the netuid for a new subnet.

Therefore the canonical entity must be:

```text
subnet_instance_id = netuid + registration_block
```

not merely `netuid`.

Otherwise historical data can accidentally splice two completely different subnet projects together.

Also: dead/deregistered subnets must remain in the historical universe. If we only backtest the 129 subnets alive today, we create classic survivorship bias and the young-subnet strategy will look much better than reality.

Official docs:
https://preview.bittensor.com/docs/guides/subnets

TAOStats registration endpoint:
https://docs.taostats.io/reference/get-subnet-registrations-1

### K. The +24.7% result is not sufficiently reproducible

Commit `ef8ccea` records “Momentum Top 5 +24.7%” but the commit itself changes `market.duckdb`, not a versioned experiment manifest containing:

- exact strategy function/commit
- exact feature versions
- universe
- start/end timestamps
- rebalancing schedule
- execution assumptions
- trades
- seeds
- costs
- benchmark definitions
- result checksum

Every backtest must generate an immutable `ExperimentReceipt` committed to Git and indexed in Hydra.

No naked PnL claims.

---

# 2. Historical data: we can get vastly more than 30 days

This is the highest-priority build.

Bittensor's dTAO alpha-token era begins at first dTAO block **4,920,351 in February 2025**. That gives roughly 567 days of subnet-token history by 3 September 2026.

Official emissions docs:
https://preview.bittensor.com/docs/concepts/emissions

At 129 subnets, the theoretical scale is modest:

- hourly: ~1.76 million subnet-hours
- 5-minute: ~21.1 million subnet-candles

DuckDB/Parquet can handle this easily.

## TAOStats endpoints to ingest

### Price OHLCV

```text
GET /api/dtao/tradingview/udf/history
symbol=SUB-{netuid}
resolution=5
from=...
to=...
```

This exposes open/high/low/close/volume.

Docs:
https://docs.taostats.io/reference/trading-view-history

### Pool history

```text
GET /api/dtao/pool/history/v1
netuid=N
frequency=by_hour
```

Fields include:

- price
- market cap
- liquidity
- TAO reserve
- total alpha
- alpha in pool
- alpha staked
- root proportion
- startup mode

Docs:
https://docs.taostats.io/reference/get-historical-subnet-pools

### Subnet fundamentals history

```text
GET /api/subnet/history/v1
netuid=N
frequency=by_hour|by_day
```

Includes point-in-time:

- owner
- registration timestamp/block
- neuron registration cost
- max neurons
- active keys
- validators
- miners
- hyperparameters
- emission

Docs:
https://docs.taostats.io/reference/get-subnet-history

### Registration events

```text
GET /api/subnet/registration/v1
```

Use this to create immutable subnet instances.

Docs:
https://docs.taostats.io/reference/get-subnet-registrations-1

### Subnet emission

```text
GET /api/dtao/subnet_emission/v1
```

Docs:
https://docs.taostats.io/reference/get-subnet-emission

### Identity changes

```text
GET /api/subnet/identity_set/v1
```

Useful because rebrands/owner changes/relaunches may be material events.

### GitHub activity history

TAOStats already exposes:

```text
GET /api/dev_activity/history/v1
```

Docs:
https://docs.taostats.io/reference/get-subnet-github-activity-history

This is extremely useful for testing whether development acceleration leads price.

## Archive-chain verification

Use TAOStats as the bulk historical index, but verify critical birth/death/upgrade state against the official archive node:

```text
wss://archive.chain.opentensor.ai:443
```

Official docs confirm the public archive node retains old state; a self-hosted archive is ~3.5 TB+ and unnecessary initially.

https://www.bittensor.com/docs/guides/running-a-node

Do **not** hammer archive RPC for every 5-minute candle. Use it for event truth and sampled validation.

---

# 3. Build a Subnet Instance Registry

New table:

```sql
subnet_instances (
    instance_id TEXT PRIMARY KEY,
    netuid INTEGER,
    registration_block BIGINT,
    registration_ts TIMESTAMP,
    activation_block BIGINT,
    activation_ts TIMESTAMP,
    owner_coldkey TEXT,
    initial_name TEXT,
    initial_alpha_price DOUBLE,
    initial_tao_reserve DOUBLE,
    initial_alpha_reserve DOUBLE,
    deregistration_block BIGINT,
    deregistration_ts TIMESTAMP,
    terminal_reason TEXT,
    terminal_liquidation_price DOUBLE,
    survived BOOLEAN
)
```

Canonical ID:

```python
instance_id = f"{netuid}:{registration_block}"
```

All historical tables gain `instance_id`.

Never join historical data on `netuid` alone.

When a netuid is reused, a new company is born.

This also creates a clean “graveyard” of failed subnets — valuable training evidence rather than deleted history.

---

# 4. Protocol-era registry

Historical Bittensor is non-stationary. We must not train one model over 2025–2026 as though the rules never changed.

Create:

```sql
protocol_eras (
    era_id,
    start_block,
    end_block,
    spec_version,
    name,
    notes
)
```

At minimum explicitly separate:

1. dTAO launch / early dTAO
2. subsequent emission-rule epochs
3. V431 price-based emission regime (July 2026)
4. V440 emission-gate regime (late July 2026 onward)
5. future runtime changes

Every market row gets `spec_version` / `era_id`.

Strategies must report performance:

```text
ALL HISTORY
CURRENT ERA ONLY
BY ERA
```

The current-era result matters most for deployment; older eras are useful for lifecycle structure and robustness.

---

# 5. The actual Subnet Incubator dataset

For every subnet instance, construct an **event-time clock**:

```text
age_minutes
age_hours
age_days
```

so SN120 day 3 can be compared with SN87 day 3, SN74 day 3, etc.

## Cohorts

```text
0–24h
1–3d
3–7d
7–14d
14–30d
30–90d
90–180d
180d+
```

## Market features

At every point in time:

- alpha price
- 5m / 1h / 4h / 1d / 3d / 7d / 30d returns
- realized volatility
- downside volatility
- maximum drawdown
- TAO reserve
- alpha reserve
- liquidity
- liquid market cap
- volume
- volume / liquidity
- net TAO flow
- buy/sell imbalance if available
- liquidity acceleration
- market-cap acceleration
- slippage for 0.1 / 1 / 5 / 10 TAO hypothetical trades
- distance from ATH / ATL
- cross-sectional rank

## Adoption/economic features

- alpha staked
- alpha-staked growth
- unique active neurons
- miner count
- validator count
- miner-count acceleration
- validator-count acceleration
- registration velocity
- registration burn
- emission share
- emission-share growth
- emission rank
- root proportion
- pruning/immunity state

## Development/fundamental features

All must be point-in-time to avoid leakage:

- commits 1d / 7d / 30d
- commit acceleration
- contributors 7d / 30d where available
- release frequency
- README/mechanism changes
- owner changes
- identity/name changes
- repo created age
- validator-code changes
- public API activity
- mechanism category
- actual product/revenue/user metrics when authoritative and historically timestamped

## Macro-relative features

- TAO return
- BTC return
- ETH return
- subnet excess return vs TAO
- subnet beta to TAO
- cross-sectional subnet index return
- breadth (% subnets positive)
- total subnet-market price / liquidity / volume

The objective is to separate:

```text
“TAO went up”
```

from:

```text
“this obscure subnet is independently accumulating demand.”
```

---

# 6. The maturity mechanic is especially interesting

Bittensor's own current emissions documentation describes a structural change as a subnet matures.

A young subnet receives alpha/TAO liquidity injection. As alpha issuance grows, `root_proportion` falls; the liquidity-injection cap can bind and excess TAO is instead used by the protocol to buy alpha from the subnet's own pool.

That creates a potentially important **maturity → protocol buyback** transition.

This should become a first-class research feature:

```text
estimated_price_neutral_injection
estimated_chain_buyback_tao
buyback_pressure / liquidity
root_proportion
alpha_issuance
age_days
```

Then test:

> Does the transition from price-neutral injection toward protocol buybacks systematically alter alpha return/volatility/liquidity behavior as subnets mature?

This is precisely the sort of obscure structural effect casual subnet buyers are unlikely to model.

Source:
https://preview.bittensor.com/docs/concepts/emissions

---

# 7. Define success labels for “what did good young subnets look like?”

Do not label winners retrospectively by current popularity.

At each observation time `t`, create forward labels:

```text
return_1d
return_3d
return_7d
return_14d
return_30d
return_60d
return_90d

max_drawdown_next_7d
max_drawdown_next_30d

liquidity_growth_30d
emission_rank_change_30d
market_cap_rank_change_30d

survives_30d
survives_90d
survives_180d
```

Then ask cohort questions:

- What fraction of new subnets lose 20/40/60% in first 30 days?
- What fraction outperform TAO?
- Is there a typical launch pump / dump / stabilization curve?
- At what age does volatility peak?
- Does liquidity growth lead price or follow it?
- Does GitHub acceleration lead price?
- Do rising miner/validator counts predict survival?
- Are successful projects distinguishable at day 1, day 3, day 7?
- Does owner reputation/history matter?
- Does high initial valuation hurt forward returns?
- Does low initial liquidity create apparent momentum that disappears after realistic slippage?
- Does root-proportion/buyback transition predict a second phase of performance?
- Which signals survive across protocol eras?

Output a canonical report:

```text
SUBNET LIFECYCLE ATLAS
```

with median and percentile price curves aligned by age.

This becomes proprietary research, not another dashboard.

---

# 8. Backtester V2

Replace the current simplistic replay with an event-driven portfolio engine.

## Required mechanics

At time `t`:

1. build the exact subnet universe that existed at `t`
2. compute features using only data `<= t`
3. run deterministic policy
4. create intended target weights
5. execute after `t` against next available real pool state
6. calculate AMM slippage
7. update alpha units / stake
8. accrue historical staking/dividend rewards where applicable
9. process deregistration/liquidation correctly
10. mark portfolio to executable liquidation value, not spot fantasy value

## Critical output

Track:

```text
TAO NAV
spot NAV
liquidatable NAV
turnover
slippage paid
fees/costs
staking income
price PnL
max drawdown
Sharpe/Sortino
hit rate
excess return vs TAO
excess return vs equal-weight
```

## Position controls

Research with realistic caps:

```text
max 1–5% initial allocation to very young subnet
max trade = X% of pool TAO reserve
max aggregate young-subnet exposure
minimum liquidity
cooldown after entry
rebalance threshold
no forced trade every 5 minutes
```

The agent can scan every 5 minutes without trading every 5 minutes.

## Walk-forward validation

Do not random-split time-series.

Example:

```text
train: first N months
validate: next month
sealed test: following month
roll window forward
```

Use purging/embargo where labels overlap.

Every strategy must be tested across multiple launch cohorts and protocol eras.

---

# 9. Incubator strategy families to test

Do not begin with an LLM picking subnets. Begin with explicit hypotheses.

### Strategy A — New-subnet quality acceleration

Buy only young subnets where several independent fundamentals accelerate:

```text
liquidity ↑
TAO flow ↑
alpha staked ↑
miners/validators ↑
GitHub activity ↑
relative price strength > TAO
```

### Strategy B — Launch overheat avoidance

Detect:

```text
price ↑↑
liquidity flat
volume/liquidity extreme
few unique participants
fundamentals flat
```

Avoid or wait for stabilization.

### Strategy C — Quiet accumulation

Find young subnets with:

```text
low social/market visibility
steady liquidity growth
steady alpha-stake growth
repo active
price not yet extended
```

This is closest to the “underfollowed incubator” thesis.

### Strategy D — Fundamental-price divergence

Rank by improvement in fundamentals minus price appreciation.

We want projects becoming better faster than the market reprices them.

### Strategy E — Maturity/buyback transition

Trade the lifecycle change around declining `root_proportion`, rising protocol buyback pressure and increasing alpha issuance.

### Strategy F — Ownership/relaunch event

Current Ditto-style case:

```text
ownership change
mechanism relaunch
repo acceleration
few market participants understand new mechanism
```

Track both investment and mining opportunity after the event.

### Strategy G — Cross-sectional momentum, properly defined

Top-N by 3d/7d/14d **excess alpha return vs TAO**, with liquidity/age filters.

The +24.7% smoke-test result says this deserves investigation; it does not prove it yet.

### Strategy H — Young vs established barbell

Maintain TAO / established-subnet baseline while using a bounded risk sleeve for young subnet opportunities.

This lets us learn without turning the portfolio into a lottery ticket.

---

# 10. Mining Hunter — keep this as the second major arm

Mining remains the cleaner immediate cashflow experiment because rewards are objective.

Create a separate `MiningOpportunitySnapshot` for every subnet.

## Core fields

```text
netuid
instance_id
contestable_miner_tao_day
registered_miner_uids
emitting_miners
benchmark_scored_competitors
effective_earners
top1/top3/top5 payout concentration
registration burn
collateral lock
uid vacancy
immunity
hardware/API cost
local eval available
mechanism confidence
our sealed score
score gap to paid rank
expected reward
```

## Farm Anomaly signal

High priority when:

```text
contestable reward high
AND competent active competitors low
AND registration cheap
AND local reproduction possible
AND our worker family matches task
```

Add bonuses for:

- subnet/ownership <30 days old
- mechanism relaunch
- repo accelerating
- explorer/docs disagreement
- validator supplies compute
- winner-take-most payout
- public deterministic benchmark
- high UID vacancy

Penalize:

- stale/dead repo
- unverified mechanism
- huge collateral
- expensive GPU requirements
- deep incumbent score gap
- illiquid alpha rewards

Initial queue remains roughly:

```text
SN121 Sundae Bar
SN62 Ridges
SN56 Gradients
SN61 RedTeam
SN118 Ditto
then weird low-competition anomalies discovered dynamically
```

But never hard-code the ranking. The oracle should rediscover it continuously.

---

# 11. Merge trading and mining economically

This is where `/bitt` becomes unusually strong.

A miner reward is received as subnet alpha.

The allocator should immediately decide:

```text
KEEP ALPHA
STAKE/COMPOUND
PARTIAL LIQUIDATE TO TAO
FULL LIQUIDATE TO TAO
REALLOCATE INTO ANOTHER SUBNET
```

based on the same lifecycle/fundamental model.

Example:

```text
Moltwork wins SN121
→ receives SN121 alpha
→ incubator says SN121 fundamentals accelerating and price unextended
→ retain 60%, liquidate 40%

or

→ alpha price is overheated / pool shallow
→ liquidate rewards gradually to TAO
→ fund next cheap miner experiment
```

Thus mining produces inventory and the allocator manages inventory.

---

# 12. Hydra / learning-loop role

LLM/CGE should be **generator, never judge**.

Hydra may propose:

- new factors
- factor interactions
- age buckets
- entry rules
- exit rules
- new mining candidates

But deterministic code runs the backtest and decides whether the hypothesis survives sealed evaluation.

Every experiment stores:

```text
experiment_id
Git commit
strategy version
feature version
data snapshot hash
knowledge cutoff
protocol era
train window
validation window
sealed window
trade log
execution assumptions
metrics
promotion/rejection reason
```

A failed strategy enters the graveyard and remains searchable.

The learning loop is:

```text
OBSERVE
→ HYPOTHESIS
→ BACKTEST
→ WALK-FORWARD
→ PAPER TRADE
→ SMALL LIVE CAPITAL (human approval)
→ OUTCOME
→ HYDRA
→ NEW HYPOTHESIS
```

---

# 13. Proposed repository changes

```text
bitt/

  data/
    ingestion/
      taostats_history.py
      tradingview_history.py
      archive_verify.py
      macro_history.py
      github_history.py

    lifecycle/
      instance_registry.py
      protocol_eras.py
      tombstones.py

  trading/
    engine/
      portfolio.py
      execution.py
      amm.py
      staking.py
      liquidation.py
      replay_v2.py

    features/
      price.py
      liquidity.py
      flows.py
      adoption.py
      emissions.py
      maturity.py
      fundamentals.py
      macro.py

    research/
      cohort_analysis.py
      lifecycle_atlas.py
      factor_ic.py
      event_studies.py
      walk_forward.py

    strategies/
      momentum.py
      quiet_accumulation.py
      quality_acceleration.py
      launch_overheat.py
      fundamental_divergence.py
      maturity_buyback.py
      relaunch.py

    experiments/
      manifests/
      receipts/
      graveyard/

  mining/
    scanner.py
    opportunity.py
    mechanism_registry.py
    benchmark_registry.py
    expected_value.py
    candidates/

  oracle/
    chain_scanner.py        # keep: canonical live state
    taostats_client.py      # extend heavily
    opportunities.py        # split trading/mining scores

  dashboard/
    incubator/
    mining/
```

Do not overwrite history. Parquet partition by date/netuid/instance where useful; DuckDB is the analytical query layer.

---

# 14. Implementation checkpoints

## CP0 — Make current backtest honest

- fix inverted returns in `rebalancer.py`
- fix `volume` → `volume_tao`
- remove fake `yield_price`
- fix “momentum” baseline naming/implementation
- remove `netuids[:10]`
- execute on next timestamp
- produce reproducible experiment manifests and trade logs
- label all old PnL as `legacy_smoke_test`

**Acceptance:** same commit + same dataset + same manifest reproduces identical result.

## CP1 — Full historical substrate

- ingest all subnet registrations since dTAO
- create `instance_id`
- ingest all OHLCV from first tradable timestamp
- ingest hourly pool history
- ingest subnet fundamentals history
- retain dead/reused subnets
- ingest TAO/BTC/ETH context
- verify sampled chain state against archive

**Acceptance:** query any historical timestamp and reconstruct the set of subnet instances that genuinely existed then.

## CP2 — Lifecycle Atlas

Produce:

- median launch curve
- age-bucket returns
- survival curves
- volatility-by-age
- liquidity-by-age
- forward-return distributions
- new vs established returns
- winners vs failures at day 1/3/7/14/30
- protocol-era stratification

**Acceptance:** answer empirically, not anecdotally: “How do new subnets behave compared with mature ones?”

## CP3 — Execution-correct Backtester V2

- AMM slippage
- real units
- staking income
- liquidation/deregistration
- next-state fills
- turnover/costs
- liquidatable NAV

**Acceptance:** manually reproduce several trades against historical pool reserves to within tiny tolerance.

## CP4 — Factor research

For every factor compute point-in-time predictive statistics:

- Spearman IC
- quantile forward returns
- hit rate
- decay by horizon
- performance by age cohort
- performance by protocol era

Do not jump straight to neural nets.

**Acceptance:** identify a small set of factors that remain useful out-of-sample.

## CP5 — Incubator strategies

Run the explicit strategy families above under walk-forward tests.

**Acceptance:** no promotion unless strategy beats TAO and simple baselines after slippage across multiple held-out periods, rather than one lucky 30-day sample.

## CP6 — Mining Hunter production

- all-subnet mechanism registry
- farm anomaly detector
- local benchmark gate
- expected attainable TAO/day
- cheap-entry alerts
- adapter queue

**Acceptance:** automatically surface at least the obvious current low-competition opportunities without hand-coded subnet names.

## CP7 — Forward paper economy

Run both systems continuously with a synthetic 100 TAO portfolio:

```text
allocator decisions
mining-entry decisions
real future outcomes
```

No retrospective edits.

Hydra sees the prediction before the outcome.

**Acceptance:** 30–60 days of immutable forward performance and decision calibration.

After that, small live capital with explicit human approval becomes defensible.

---

# 15. What to build first — exact order

Do this before adding clever ML:

1. Fix the current signal/schema bugs.
2. Build `subnet_instances` so netuid reuse cannot corrupt history.
3. Backfill TAOStats TradingView OHLCV from each instance's birth.
4. Backfill hourly pool history.
5. Backfill subnet-history fundamentals.
6. Mark deregistered/dead subnet instances.
7. Create protocol-era labels.
8. Generate the **Subnet Lifecycle Atlas**.
9. Build execution-correct replay.
10. Re-run simple momentum/flow/liquidity/age strategies.
11. Only then let Hydra/CGE search interactions.
12. In parallel, keep the Mining Hunter scanning all live subnets every hour and push cheap/high-EV candidates into offline benchmarking.

The Lifecycle Atlas should come **before** more strategy complexity. It will likely reveal several obvious regularities we currently do not know: launch overheat, stabilization timing, survival thresholds, liquidity trajectories, and whether successful subnets are distinguishable early.

---

# Strategic end state

The final `/bitt` agent should think like this:

```text
                 ALL BITTENSOR SUBNETS
                         │
              point-in-time oracle
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
   CAPITAL OPPORTUNITIES          LABOR OPPORTUNITIES
          │                             │
   subnet incubator                mining hunter
          │                             │
“which alpha is                 “which reward pool
mispriced/early?”               has weak competition?”
          │                             │
          └──────────────┬──────────────┘
                         ▼
                       WALLET
                         │
                         ▼
                 realized outcomes
                         │
                         ▼
                       HYDRA
                         │
                         ▼
                  better next decision
```

This is a better niche than competing head-on with people who only buy the largest subnets.

The edge is **coverage + history + point-in-time fundamentals + willingness to investigate weird new things**.

Most users can know Chutes is big. The useful system notices that an obscure subnet is three days old, liquidity is compounding, miner/validator participation is accelerating, the repo just shipped twice, price has not yet repriced, and historical day-3 winners looked statistically similar — while simultaneously noticing another subnet is paying 30 TAO-equivalent/day to six competent miners and can be benchmarked for $2 offline.

That is the Bittensor economic agent worth building.

## Primary data references

- TAOStats TradingView history: https://docs.taostats.io/reference/trading-view-history
- TAOStats historical subnet pools: https://docs.taostats.io/reference/get-historical-subnet-pools
- TAOStats subnet history: https://docs.taostats.io/reference/get-subnet-history
- TAOStats registrations: https://docs.taostats.io/reference/get-subnet-registrations-1
- TAOStats subnet emission: https://docs.taostats.io/reference/get-subnet-emission
- TAOStats GitHub activity: https://docs.taostats.io/reference/get-subnet-github-activity-history
- Bittensor subnet lifecycle/deregistration: https://preview.bittensor.com/docs/guides/subnets
- Bittensor archive node: https://www.bittensor.com/docs/guides/running-a-node
- Bittensor current emissions/maturity mechanics: https://preview.bittensor.com/docs/concepts/emissions
- V431 price-based emission change: https://www.bittensor.com/releases/v431-upgrade

— ChatGPT project review
