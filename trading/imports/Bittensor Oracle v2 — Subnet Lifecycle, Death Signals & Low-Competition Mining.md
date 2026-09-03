# Bittensor Oracle v2 — Subnet Lifecycle, Death Signals & Low-Competition Mining

**Date:** Wed, 2 Sep 2026 18:08:22 -0700

---

# Bittensor Oracle v2 — Subnet Lifecycle, Death Signals & Low-Competition Mining

## Core thesis

Double down on two related inefficiencies:

1. **Subnet Incubator** — reconstruct every subnet from birth to death and learn which early fundamental/on-chain/qualitative signals predict future price, liquidity, emissions and survival.
2. **Mining Hunter** — continuously rank every subnet by *attainable* miner profit, not headline emissions, with the explicit goal of finding stable, low-competition recurring income before spending time/TAO on high-variance moonshots like Ditto/Affine.

The information gap is real. Most participants concentrate on a handful of known names. Our edge is to systematically watch the entire network and maintain richer point-in-time histories than a human can.

---

# 1. The most interesting market inefficiencies to test

## A. Lifecycle / age-normalized mispricing

This is the highest-conviction research idea.

Every subnet should be represented as a permanent **subnet instance**, not merely a netuid:

`instance_id = netuid + registration_block`

Netuids can be reused after deregistration. Never splice two different projects into one price history.

For every instance calculate `age_blocks`, `age_hours`, `age_days` and align all subnets by age:

- launch hour
- day 1
- day 3
- day 7
- day 14
- day 30
- day 60
- day 90
- immunity expiry
- month 6
- year 1

Then ask:

- What did eventual top-quartile subnets look like on day 3?
- What did eventual failures look like before the market realized they were failing?
- Does a young subnet with current fundamentals X typically appreciate or fade over the following 7/30/90 days?
- Does the same feature mean different things at age 7d versus age 180d?

This gives us a true **Subnet Lifecycle Atlas**.

## B. Emission-gate threshold / reflexivity

Current Bittensor emissions are unusually exploitable from a research perspective because subnet TAO emission is now driven by EMA alpha price and then passed through a nonlinear emission gate.

Current official mechanics:

`demand_share_i = price_ema_i / sum(price_ema)`

then miner-burn adjustment, then a sigmoid-style emission gate. The gate midpoint is normally the 32nd-highest positive adjusted share and the default exponent is 3.

This creates a strong hypothesis:

- rising toward the gate → more effective emission → potentially more chain buying / stronger economics
- falling below the gate → emissions collapse nonlinearly → weaker miner economics / weaker narrative / possible further selling

Create:

- `distance_to_gate_abs`
- `distance_to_gate_pct`
- `gate_cross_up`
- `gate_cross_down`
- `days_above_gate`
- `days_below_gate`
- `gate_velocity`

Do event studies around every historical gate crossing.

This may be one of the most protocol-specific alpha factors available.

Source:
https://www.bittensor.com/docs/concepts/emissions

## C. Protocol chain-buy pressure vs participant sell pressure

A mature subnet can receive excess TAO emission that is used by the chain to buy alpha rather than merely injecting neutral liquidity. This means the protocol itself can become a predictable alpha buyer.

At the same time miners, validators and owners receive alpha and may sell it to pay costs.

Build a net structural-pressure estimate:

`structural_flow = protocol_chain_buy_tao - expected_miner_sell_tao - expected_owner_sell_tao - expected_validator_sell_tao + external_net_stake_flow`

This is much better than ordinary momentum because it models *why* price might move.

Features:

- chain buy TAO/day
- chain buy / market cap
- chain buy / liquidity
- chain buy / daily sell volume
- owner emission sell-through
- miner emission sell-through
- validator emission sell-through
- aggregate insider sell-through
- external wallet net inflow

TAOStats currently documents this chain-buy mechanism explicitly.

Source:
https://docs.taostats.io/docs/tao-emission

## D. Smart-money / sponsor signals

Yuma currently provides subnet acceleration including capital, registration fees, technical support, compute, introductions and go-to-market assistance. Its public accelerated portfolio gives us a clean event/sponsor label.

Current Yuma accelerated examples include Numinous, Score, RedTeam, Bitsec, Yanez MIID, Babelbit, Trishool, NIOME and Beam.

Do not simply use `yuma_accelerated=True` with today's knowledge. Build point-in-time events:

- first public accelerator announcement date
- first Yuma mention
- first institutional partnership
- first known investment/funding event
- first validator/stake flow from identifiable smart wallets

Then test forward returns versus age-matched controls.

Also track:

- Crucible backing/attention
- named validator support
- major custodian integrations
- accelerator / investor / institutional mentions
- major Bittensor ecosystem founder endorsements

Yuma accelerator:
https://www.yumaai.com/services
https://www.yumaai.com/subnets

## E. Owner conviction / skin-in-the-game

Current conviction data is extremely interesting.

Track:

- owner alpha locked %
- owner perpetual-lock %
- owner conviction trend
- unlock / switch-to-decay events
- non-owner challenger conviction
- distance of challenger to ownership threshold
- ownership-transfer events

Owner locks are observable, and current ownership rules for older subnets use a single-hotkey 18% eligible-alpha threshold.

Hypotheses:

- large owner perpetual lock predicts lower future insider selling and higher survival
- sudden unlock predicts negative forward return
- challenger conviction predicts governance catalyst/instability
- credible new owner takeover may be positive if replacing a stagnant team

Sources:
https://www.bittensor.com/docs/guides/conviction
https://www.bittensor.com/docs/query/subnet-convictions

SubnetRadar already exposes useful conviction research that we can benchmark against:
https://subnetradar.com/alpha/conviction/

## F. GitHub/developer velocity before market repricing

TAOStats already exposes subnet GitHub activity history:

`GET /api/dev_activity/history/v1`

But we should also ingest GitHub directly because raw commit count is noisy.

Features:

- commits 7/30/90d
- commit acceleration
- unique contributors
- new-contributor growth
- releases 30/90d
- days since meaningful code commit
- PR merge rate
- issue-response latency
- code additions/deletions
- % commits touching production code vs docs/config
- repository count in org
- repository creation acceleration
- dependency/update cadence
- test coverage if extractable
- validator/miner mechanism changes
- README/mechanism documentation completeness

Most interesting factor is likely **change in developer velocity**, not absolute commits.

Example:

`dev_acceleration = commits_7d / max(commits_prev_28d / 4, eps)`

SubnetRadar's Builder Index is an excellent benchmark because it explicitly compares build rank with market-cap rank:
https://subnetradar.com/github

Bittensor.ai also exposes current dev activity/holder growth in its public directory.

## G. Qualitative/event intelligence

This should be timestamped and encoded as events, not fed as unstructured hindsight.

Useful event classes:

- partnership announced
- customer announced
- revenue announced
- buyback program announced
- product launch
- public API launch
- major benchmark win
- new model/research release
- funding/accelerator backing
- team expansion
- recognized founder joins
- major validator support
- exchange/custodian integration
- hack/exploit
- scoring dispute
- validator outage
- miner revolt / fairness dispute
- mechanism rewrite
- owner transfer
- team inactivity
- repository archived
- repeated downtime
- regulatory/legal issue

SubnetRadar is now particularly valuable because it aggregates daily per-subnet team briefs and Discord activity with historical archives:
https://subnetradar.com/news

This gives us exactly the qualitative timeline needed for backtests.

Do NLP/event extraction into structured flags, but preserve raw evidence URL + timestamp.

## H. Similarity / comparable-subnet modeling

Create an embedding/profile for every subnet using:

- task/commodity
- miner mechanism
- validator mechanism
- hardware profile
- business model
- team profile
- sector
- revenue model
- API/product type
- repo architecture

Then find historical nearest neighbors.

Example question:

> A new decentralized inference subnet launched today with 6 miners, public API, active GitHub and Yuma backing. Which previous subnets looked most similar at day 10, and what happened over the next 90 days?

This is much more useful than generic crypto factors.

Also test category saturation:

- first strong subnet in a new category may receive novelty premium
- 8th clone of an existing inference subnet may not
- alternatively a new entrant in a hot category may outperform because capital already understands the thesis

Both are testable.

## I. Holder breadth vs whale concentration

Track:

- unique holders
- holder growth 1/7/30d
- HHI / Gini concentration
- top 1/5/10 holder share
- owner share
- miners' share
- validators' share
- whales' cost basis
- holders in profit
- new buyer count
- repeat buyer count
- buyer/seller breadth

A particularly interesting divergence:

`price up + holder breadth up` likely healthier than `price up + one whale buying`.

SubnetStats is already reconstructing classified insider flow, wallet cost basis, cohort flows and holder concentration from chain records. Treat it as both a research source and a benchmark for features we can reproduce ourselves:
https://subnetstats.app/

Metagraphed also has account-level stake-flow endpoints.

## J. Native TAO-flow EMA

This is low-hanging fruit and should be in `/bitt` immediately.

The current SDK exposes:

`sub.subnets.subnet_tao_flows()`

which returns per-subnet EMA of stake additions minus removals.

Features:

- `tao_flow_ema`
- `flow / liquidity`
- `flow / market_cap`
- flow acceleration
- positive-flow streak
- negative-flow streak
- flow divergence from price

Potentially high signal:

- price flat/down while TAO flow turns strongly positive → accumulation
- price rising while TAO flow turns negative → distribution

Official docs:
https://www.bittensor.com/docs/query/subnet-tao-flows

## K. Mechanical index/rebalance effects

Yuma now operates market-cap-weighted subnet funds / YCX-style benchmarks and states monthly rebalancing for its Composite Fund.

If fund AUM or identifiable execution wallets become observable, test:

- month-end rebalance flows
- market-cap rank crossings
- inclusion/exclusion effects
- concentration changes

This may be small today but becomes more valuable as institutional capital grows.

---

# 2. Death prediction

Build a separate **Subnet Death Model**, not just a sell signal.

Suggested target labels:

### Hard death

- subnet deregistered within 7/30/90 days

### Soft death

- falls into bottom 10% by EMA price
- emission share collapses >80%
- liquidity falls >50%
- alpha drawdown >60%
- loses >50% holder count
- repo inactive for >N days plus negative flow

Current official runtime docs indicate subnet deregistration is price-based and the lowest EMA-price non-immune subnet is recycled when capacity is full. Do not hardcode immunity length: query chain state/runtime because documentation around historical immunity periods has changed.

Likely leading death indicators:

1. persistent negative TAO-flow EMA
2. distance below emission gate increasing
3. falling EMA-price rank
4. declining holder breadth
5. sell volume dominated by insiders/miners/owner
6. rising `miner emission sold / miner emission earned`
7. owner unlock / owner selling
8. liquidity falling
9. volume becoming one-sided sells
10. zero/declining GitHub activity
11. long unresolved validator/scoring failures
12. repeated Discord complaints / team silence
13. loss of active miners
14. registration demand disappearing
15. external product/revenue inactivity
16. owner/identity churn
17. challenger conviction / governance instability
18. emission-disabled flag
19. no public API/product surface after age-adjusted grace period
20. failure to improve relative to same-age cohort

Important: I found no canonical *native* Bittensor mechanism in current official docs for borrowing/shorting arbitrary subnet alpha. Native pools are spot stake/unstake AMMs. Therefore:

- backtest real long/short portfolios as a **research diagnostic**
- live implementation should initially express death views by exiting to TAO / avoiding / rotating capital into winners
- implement `paper_short` abstraction now
- plug in a live short execution adapter only when a verified venue with actual alpha borrow/perps exists

Do not fake a short via an ordinary unstake.

---

# 3. Pair and barbell strategies

The oracle should ultimately produce relative-value books rather than isolated picks.

### Lifecycle pair
Long high-growth child / paper-short age-matched weak child.

Controls macro TAO direction and tests whether lifecycle scoring actually separates winners from losers.

### Sector pair
Long strongest inference subnet / short weakest inference subnet.

Controls category narrative.

### Sponsor pair
Long newly accelerator-backed subnet / short age-and-sector matched unsupported subnet.

Tests whether sponsorship is signal or merely story.

### Builder-value pair
Long high GitHub velocity + low market-cap rank / short low GitHub velocity + high market-cap rank.

### Flow divergence pair
Long positive smart-money flow + weak recent price / short negative insider flow + strong recent price.

### Barbell for actual capital
Until native alpha shorting is verified:

- majority TAO / established liquid names
- small portfolio of top-ranked young-subnet opportunities

This lets us harvest asymmetric new-subnet upside without exposing the whole stack to thin pools.

---

# 4. Mining Hunter — recurring income first

The mining oracle should explicitly distinguish **stable yield targets** from **moonshots**.

Do not rank by miner-pool TAO/day alone.

Use:

`ExpectedNetMinerTAO/day = miner_pool_tao_equiv_day × expected_incentive_share - compute - API - registration_amortization - expected_reregistration_cost - exit_slippage`

Estimate `expected_incentive_share` from actual competition.

## High-priority mining features

### Competition

- active miners
- unique miner coldkeys
- unique miner IP clusters
- max UIDs
- free slots
- registrations 1d/7d/30d
- deregistrations 1d/7d/30d
- miner churn
- burn price and burn velocity
- immunity period
- lowest active incentive
- next prune incentive
- incentive HHI
- effective number of earners
- top1/top3/top10 share
- reward persistence of incumbent top miners

TAOStats explicitly states that miner incentive-distribution shape is a direct indication of competitiveness. It also exposes miner coldkey distribution and IP distribution.

Sources:
https://docs.taostats.io/docs/distribution
https://docs.taostats.io/reference/get-subnet-miner-incentive-distribution

### Attainability

For each subnet create:

- local benchmark available?
- deterministic replay?
- validator supplies compute?
- miner requires GPU?
- estimated hardware $/day
- API $/day
- artifact submission vs continuously running service
- score observable?
- public leaderboard?
- evaluator reproducible?
- hidden dataset risk
- incumbent secret advantage
- mechanism change frequency

Then run our own baseline and calculate predicted percentile against the observed incentive distribution.

### Stability

For recurring income prefer:

- under-capacity or low churn
- broad reward distribution
- stable scoring rules
- cheap registration
- low compute/API OPEX
- deterministic/public benchmark
- no dominant secret incumbent
- slow mechanism change
- repeatable worker process

This is different from Ditto/Affine/SN121-style winner-take-most opportunities. Those remain high-EV experiments but belong in a separate **moonshot queue**.

The goal is:

1. obtain one or two boring subnet miner cashflows
2. automatically accrue alpha/TAO
3. reinvest part of rewards
4. use surplus to attempt high-variance competitions
5. continuously re-evaluate whether another subnet is now easier

This turns mining into a portfolio of jobs, not a single subnet identity.

## Mining opportunity score

Start with something interpretable:

`stable_mining_score = attainable_reward_tao_day × reward_stability × benchmark_confidence / (opex_day + burn_amortized + prune_risk_cost)`

Then a separate:

`moonshot_score = P(top_k) × jackpot_reward - submission_cost - training_cost - registration_cost`

Never combine them into one opaque number.

---

# 5. Data sources — priority order

## TAOStats — historical backbone

This is currently the richest obvious historical source.

Useful endpoints:

Subnet history:
https://api.taostats.io/api/subnet/history/v1

Historical pool state:
https://api.taostats.io/api/dtao/pool/history/v1

5m/1m/15m/60m OHLCV:
https://api.taostats.io/api/dtao/tradingview/udf/history

Metagraph history:
https://api.taostats.io/api/metagraph/history/v1

Subnet emission history:
https://api.taostats.io/api/dtao/subnet_emission/v1

Subnet registration history:
https://api.taostats.io/api/subnet/registration/v1

GitHub history:
https://api.taostats.io/api/dev_activity/history/v1

Miner incentive distribution:
https://api.taostats.io/api/subnet/distribution/incentive/v1

Identity history:
https://api.taostats.io/api/subnet/identity_set/v1

This is enough to build most of the historical panel immediately.

## Direct Bittensor chain/archive — truth + verification

Continue the existing block-pinned scanner.

Add explicit reads for:

- subnet TAO-flow EMA
- subnet moving price / EMA
- emission-gate state/theta if exposed
- conviction
- owner-cut locks
- registration/deregistration events
- stake adds/removes/moves
- pool reserves
- protocol alpha / burned alpha
- chain buy state
- emission-enabled state

Archive RPC should verify historical boundary cases and reconstruct anything TAOStats lacks.

## Metagraphed — free account/event intelligence

Excellent for:

- account stake flow
- account stake moves
- account/subnet position history
- neuron history
- current metagraph
- chain events
- API-surface discovery

Docs:
https://metagraph.sh/docs

## GitHub API — developer truth

Use TAOStats history for bootstrap, then native GitHub for richer factors.

## SubnetRadar — qualitative/event layer

Excellent current sources:

Builder Index:
https://subnetradar.com/github

News + daily subnet/Discord briefs:
https://subnetradar.com/news

Conviction:
https://subnetradar.com/alpha/conviction/

This gives us a structured way to timestamp partnerships, outages, disputes, launches and technical changes.

## SubnetStats — benchmark / optional paid derived layer

Their current service is already reconstructing:

- miner/validator/owner/outsider trade classification
- whale/cohort flows
- holder concentration
- wallet cost basis
- emission sell-through
- smart-money leaderboard
- exchange flow

We should reproduce the highest-value factors ourselves from chain data, but their $49.99 web plan can be useful for validating our classifications before paying for a larger API plan.

https://subnetstats.app/

## Bittensor.ai

Good current directory for:

- developer activity
- holders
- mechanism summaries
- hardware requirements
- repo metadata

Use as discovery/cross-check, not canonical historical source.

## Yuma / Crucible / official subnet sites

Use as timestamped qualitative evidence for:

- accelerator status
- funding
- partnerships
- product/revenue claims
- ecosystem backing

---

# 6. Historical storage design

Do not keep stuffing everything into one generic candle table.

Suggested DuckDB/Parquet model:

### subnet_instances

- instance_id
- netuid
- registration_block
- registration_ts
- deregistration_block
- deregistration_ts
- owner_initial
- owner_current
- identity history pointer

### market_5m

- instance_id
- ts
- OHLC
- volume
- tao_reserve
- alpha_reserve
- liquidity

### fundamentals_1h

- instance_id
- ts
- price_ema
- emission_share
- chain_buy_tao
- root_prop
- alpha_issuance
- alpha_staked
- holders
- miners
- validators
- registrations
- burn
- tao_flow_ema
- gate_distance

### metagraph_daily

- instance_id
- uid/hotkey/coldkey
- role
- incentive
- emission
- trust
- consensus
- stake

### developer_daily

- instance_id
- commits
- contributors
- releases
- PRs
- issues
- acceleration metrics

### qualitative_events

- instance_id
- event_ts
- event_type
- source
- evidence
- confidence

### mining_snapshots

- instance_id
- ts
- miner_pool_tao_day
- miner_count
- unique_operators
- incentive distribution
- cutoff
- burn
- churn
- estimated OPEX
- local benchmark result

---

# 7. Backtesting methodology

Do **not** jump straight to XGBoost/LLMs.

First establish whether the factors exist.

### Phase A — descriptive lifecycle atlas

For every feature show median/p25/p75 trajectory by age for:

- future winner cohort
- middle cohort
- failure/deregistered cohort

### Phase B — univariate signal tests

For each feature calculate:

- Spearman rank IC vs forward 7/30/90d TAO returns
- monotonic quintile returns
- hit rate
- drawdown
- survival probability
- effect conditioned on subnet age

### Phase C — event studies

Events:

- Yuma backing
- partnership
- chain-buy transition
- gate crossing
- owner lock/unlock
- repo acceleration
- product release
- revenue announcement
- ownership change

Measure -30d to +90d where data allows.

### Phase D — simple multivariate models

Use:

- regularized logistic regression for death probability
- Cox / survival model for deregistration hazard
- linear/rank model for forward returns
- gradient-boosted trees only after simple factors are understood

### Phase E — strict walk-forward portfolio simulation

At each timestamp use only information observable then.

Universe must include dead/deregistered subnet instances.

Model:

- actual Balancer AMM entry/exit quotes
- fees
- price impact
- liquidity constraints
- alpha staking emissions if strategy holds alpha
- missing-data handling
- no filling at impossible candle midpoints

Benchmarks:

- TAO
- root stake
- equal-weight all eligible
- market-cap weighted / YCX-like
- established-subnet basket
- simple momentum
- age-only strategy
- flow-only strategy
- lifecycle composite

---

# 8. Initial hypotheses I would test first

These are ranked roughly by expected information value, not guaranteed profitability.

1. **Net TAO flow acceleration** predicts 7/30d forward returns.
2. **Emission-gate distance/crossing** predicts nonlinear future returns and survival.
3. **Chain-buy TAO / liquidity** predicts positive forward alpha performance.
4. **Insider/miner sell-through** predicts negative forward performance.
5. **Owner perpetual-lock %** predicts survival and lower drawdown.
6. **Developer acceleration** predicts forward return for young subnets more strongly than mature ones.
7. **Holder breadth growth** is stronger than raw volume.
8. **Yuma/accelerator backing** improves survival odds after matching on age/category.
9. **Mechanism stability + public benchmark + low unique-operator competition** predicts durable mining profitability.
10. **Discord/scoring disputes + repo inactivity + owner unlock + negative flow** jointly predict death far earlier than price rank alone.
11. **Young subnets with strong fundamentals but low EMA price** outperform because age-dependent EMA smoothing delays economic recognition.
12. **Category-adjusted relative strength** beats raw momentum because many subnets move together on narrative.

---

# 9. Build order

## CP0 — make history trustworthy

- subnet-instance registry
- netuid reuse handling
- TAOStats historical downloader with pagination/retry/resume
- 5m OHLCV from each instance birth
- hourly pool/subnet fundamentals
- daily metagraph/developer history
- direct-chain verification samples

Acceptance: every active + historical subnet instance has a birth timestamp and no reused netuid is silently merged.

## CP1 — Lifecycle Atlas

- age-aligned feature matrices
- age cohort charts
- outcome labels
- winner/death cohort comparison
- simple rank IC tables

Acceptance: answer “what did successful subnets look like at day 7 versus failed ones?” with real historical numbers.

## CP2 — structural flow model

- TAO-flow EMA
- protocol chain buys
- classified participant emissions
- miner/owner sell-through
- holder breadth

## CP3 — qualitative intelligence

- Yuma accelerator events
- GitHub acceleration
- SubnetRadar news/Discord event extraction
- partnership/revenue/product events

## CP4 — Death Model

- survival/hazard model
- probability of deregistration 30/90d
- paper-short research portfolio

## CP5 — Mining Hunter v2

- full miner incentive distributions
- unique operator count
- registration/prune churn
- deterministic local benchmark adapters
- stable-income vs moonshot leaderboards

## CP6 — Unified capital allocator

Every 5m/hour ask:

> Is the best use of the next unit of TAO to remain TAO, buy a high-growth subnet, fund an easy miner, or reserve capital for a higher-EV mining experiment?

Record every decision and outcome into Hydra.

---

# Final strategic framing

The gap is not “build a better generic crypto trader.”

The gap is:

**Nobody has time to deeply understand every subnet. The oracle does.**

It keeps the complete corporate/economic history of every subnet, understands each project's mechanism and team, watches developer/product/community events, knows who is buying and selling, knows which child subnets resemble historical winners, knows which mature subnets are deteriorating, and simultaneously knows where mining competition is weak enough for our worker to earn.

That gives us two compounding feedback loops:

`better subnet intelligence → better alpha allocation → more TAO`

and

`better miner selection → recurring rewards → more TAO → more experiments`

The most exciting long-term artifact is the **Subnet Lifecycle Atlas**. It becomes Bittensor's equivalent of a private startup/market dataset: every subnet from birth, every fundamental change, every team/repo/event signal, every market movement, and the outcome. That is the dataset from which both the incubator strategy and the death model emerge.
